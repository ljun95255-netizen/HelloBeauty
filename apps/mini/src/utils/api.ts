import Taro from "@tarojs/taro";

import {
  buildAbsoluteUrl,
  createApiClient,
  type ApiTransport,
  type ApiTransportRequestOptions,
  type ApiTransportUploadOptions,
} from "@hellobeauty/api-client";
import type {
  CompletedResult,
  CustomerUser as CustomerProfile,
  EditJob,
  PhotoAsset as SessionPhoto,
  SessionReminder,
  ShootSession as CustomerSession,
} from "@hellobeauty/domain";

export type { CompletedResult, CustomerProfile, CustomerSession, EditJob, SessionPhoto, SessionReminder };

const apiBaseFromEnv =
  typeof process !== "undefined" ? process.env?.TARO_APP_API_BASE_URL : undefined;

const API_BASE = (apiBaseFromEnv ?? "http://127.0.0.1:7860").replace(/\/$/, "");

export const CUSTOMER_TOKEN_KEY = "hellobeauty.customer.token";
export const CUSTOMER_PROFILE_KEY = "hellobeauty.customer.profile";
export const CURRENT_SESSION_KEY = "hellobeauty.current.session";
export const COMPLETED_RESULTS_KEY = "hellobeauty.completed.results";
export const ENTRY_PREFERENCE_KEY = "hellobeauty.entry.preference";
export const SESSION_CODE_KEY = "hellobeauty.session.code";

export type EntryPreferenceMode = "upload" | "curated" | "none";

export interface EntrySeedChoice {
  seed_id: string;
  style_id?: string | null;
  profile: Record<string, number>;
  liked: boolean;
}

const LOCAL_IMAGE_CACHE = new Map<string, string>();

export interface EntryPreference {
  mode: EntryPreferenceMode;
  uploadedFiles: string[];
  likedSampleIds: string[];
  seedChoices?: EntrySeedChoice[];
  referencePhotoIds?: string[];
}

const taroTransport: ApiTransport = {
  async request<T>(url: string, options: ApiTransportRequestOptions = {}): Promise<T> {
    const response = await Taro.request({
      url,
      method: options.method ?? "GET",
      timeout: 20000,
      data: options.data,
      header: {
        ...(options.data !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
        ...(options.headers ?? {}),
      },
    });

    const payload = response.data as { detail?: string };
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw new Error(payload?.detail ?? `Request failed with status ${response.statusCode}`);
    }

    return response.data as T;
  },

  async upload<T>(url: string, options: ApiTransportUploadOptions): Promise<T> {
    if (typeof options.file !== "string") {
      throw new Error("Taro upload transport expects a local file path");
    }

    const response = await Taro.uploadFile({
      url,
      name: options.fieldName ?? "image",
      filePath: options.file,
      timeout: 20000,
      formData: options.formData,
      header: {
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
        ...(options.headers ?? {}),
      },
    });

    const payload =
      typeof response.data === "string"
        ? (() => {
            try {
              return JSON.parse(response.data) as { detail?: string };
            } catch {
              return null;
            }
          })()
        : (response.data as { detail?: string });

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw new Error(payload?.detail ?? `图片上传失败（状态 ${response.statusCode}）`);
    }

    if (!payload) {
      throw new Error("上传响应格式无效，请检查服务端返回内容");
    }

    return payload as T;
  },
};

const client = createApiClient({
  apiBaseUrl: API_BASE,
  transport: taroTransport,
});

export function buildUrl(path: string): string {
  return buildAbsoluteUrl(API_BASE, path);
}

export function assetUrl(path: string | null | undefined): string {
  return client.buildAssetUrl(path);
}

const BACKEND_BEAUTY_ASSET_PREFIX = "/assets/beauty/";
const MINI_BEAUTY_ASSET_PREFIX = "/beauty/";
const MOCK_PHONE_PREFIXES = ["130", "131", "132", "155", "166", "177", "188", "199"];

export function createMockPhoneNumber(): string {
  const prefix = MOCK_PHONE_PREFIXES[Math.floor(Math.random() * MOCK_PHONE_PREFIXES.length)];
  const suffix = String(Date.now() + Math.floor(Math.random() * 100000000)).slice(-8).padStart(8, "0");
  return `${prefix}${suffix}`;
}

function miniBeautyAssetPath(path: string): string | null {
  const normalizedPath = path.trim().replace(/^https?:\/\/[^/]+/i, "").split(/[?#]/)[0];
  if (normalizedPath.startsWith(BACKEND_BEAUTY_ASSET_PREFIX)) {
    return `${MINI_BEAUTY_ASSET_PREFIX}${normalizedPath.slice(BACKEND_BEAUTY_ASSET_PREFIX.length)}`;
  }
  if (normalizedPath.startsWith(BACKEND_BEAUTY_ASSET_PREFIX.slice(1))) {
    return `${MINI_BEAUTY_ASSET_PREFIX}${normalizedPath.slice(BACKEND_BEAUTY_ASSET_PREFIX.length - 1)}`;
  }
  if (normalizedPath.startsWith(MINI_BEAUTY_ASSET_PREFIX)) {
    return normalizedPath;
  }
  if (normalizedPath.startsWith(MINI_BEAUTY_ASSET_PREFIX.slice(1))) {
    return `/${normalizedPath}`;
  }
  return null;
}

function createLocalImageCacheKey(url: string): string {
  if (url.startsWith("data:image/")) {
    return `data-image:${url.length}:${stableTextHash(url)}`;
  }
  return url.replace(/[?#].*$/, "");
}

function stableTextHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

export async function resolveMiniImageSrc(path: string | null | undefined): Promise<string> {
  const url = assetUrl(path);
  if (!url) {
    return "";
  }

  if (url.startsWith("data:image/")) {
    const cacheKey = createLocalImageCacheKey(url);
    const cachedFilePath = LOCAL_IMAGE_CACHE.get(cacheKey);
    if (cachedFilePath) {
      return cachedFilePath;
    }

    const match = url.match(/^data:image\/\w+;base64,(.+)$/);
    if (!match) {
      throw new Error("图片格式无效");
    }
    const filePath = `${Taro.env.USER_DATA_PATH}/hellobeauty-${Date.now()}-${Math.round(
      Math.random() * 1000,
    )}.png`;
    await new Promise<void>((resolve, reject) => {
      Taro.getFileSystemManager().writeFile({
        filePath,
        data: match[1],
        encoding: "base64",
        success: () => resolve(),
        fail: (error) => reject(new Error(error.errMsg || "图片写入失败")),
      });
    });
    LOCAL_IMAGE_CACHE.set(cacheKey, filePath);
    return filePath;
  }

  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    return url;
  }

  const cacheKey = createLocalImageCacheKey(url);
  const cachedFilePath = LOCAL_IMAGE_CACHE.get(cacheKey);
  if (cachedFilePath) {
    return cachedFilePath;
  }

  const downloadResult = await Taro.downloadFile({
    url,
    timeout: 20000,
    header: readCustomerToken() ? { Authorization: `Bearer ${readCustomerToken()}` } : undefined,
  });

  if (
    downloadResult.statusCode < 200 ||
    downloadResult.statusCode >= 300 ||
    !downloadResult.tempFilePath
  ) {
    throw new Error("图片下载失败");
  }

  LOCAL_IMAGE_CACHE.set(cacheKey, downloadResult.tempFilePath);
  return downloadResult.tempFilePath;
}

export async function loginCustomer(phone: string, nickname?: string): Promise<{
  token: string;
  user: CustomerProfile;
}> {
  return client.loginCustomer({ phone, nickname });
}

export async function createSession(
  token: string,
  storeId: string,
  durationMinutes: number,
  sessionCode?: string | null,
  startTime?: string | null,
): Promise<CustomerSession> {
  return client.createSession(token, { storeId, durationMinutes, sessionCode, startTime });
}

export async function listCustomerSessions(token: string): Promise<CustomerSession[]> {
  return client.listCustomerSessions(token);
}

export async function schedulePreShootStyleReminder(
  token: string,
  sessionId: string,
  payload: { subscriptionAccepted?: boolean; subscriptionStatus?: string | null; templateId?: string | null },
): Promise<SessionReminder> {
  return client.schedulePreShootStyleReminder(token, sessionId, payload);
}

export async function listSessionPhotos(token: string, sessionId: string): Promise<SessionPhoto[]> {
  return client.listSessionPhotos(token, sessionId);
}

export async function selectPhoto(
  token: string,
  photoId: string,
  selected: boolean,
): Promise<SessionPhoto> {
  return client.selectPhoto(token, photoId, selected);
}

export async function createEditJob(
  token: string,
  photoId: string,
  mode: EditJob["mode"],
): Promise<EditJob> {
  return client.createEditJob(token, { photoId, mode });
}

export async function initializeJesrRecipe(
  token: string,
  sessionId: string,
  photoId: string,
): Promise<unknown> {
  return client.initializeJesrRecipe(token, sessionId, photoId);
}

export async function selectCreativeStyle(
  token: string,
  sessionId: string,
  presetId: string | null,
): Promise<unknown> {
  return client.selectCreativeStyle(token, sessionId, presetId);
}

export async function renderWithRecipe(
  token: string,
  sessionId: string,
  photoId: string,
  mode = "auto",
): Promise<EditJob> {
  const response = await client.renderWithRecipe(token, sessionId, photoId, mode);
  return response.job;
}

export async function pollEditJob(token: string, jobId: string): Promise<EditJob> {
  return client.pollEditJob(token, jobId);
}

export async function completeSession(token: string, sessionId: string): Promise<CustomerSession> {
  return client.completeSession(token, sessionId);
}

export async function uploadIngressPhoto(
  token: string,
  storeId: string,
  sessionId: string,
  filePath: string,
  temporary = false,
): Promise<SessionPhoto> {
  return client.uploadCameraIngressPhoto({
    token,
    storeId,
    sessionId,
    file: filePath,
    temporary,
  });
}

export function readCustomerToken(): string {
  return Taro.getStorageSync(CUSTOMER_TOKEN_KEY) ?? "";
}

export function readCustomerProfile(): CustomerProfile | null {
  return Taro.getStorageSync(CUSTOMER_PROFILE_KEY) ?? null;
}

export function writeCustomerAuth(token: string, profile: CustomerProfile): void {
  const existingToken = readCustomerToken();
  const existingProfile = readCustomerProfile();
  const isSwitchingAccount =
    (existingToken && existingToken !== token) ||
    (existingProfile?.phone && existingProfile.phone !== profile.phone);
  if (isSwitchingAccount || (!existingToken && readCurrentSession())) {
    clearFlowState();
  }
  Taro.setStorageSync(CUSTOMER_TOKEN_KEY, token);
  Taro.setStorageSync(CUSTOMER_PROFILE_KEY, profile);
}

export function clearCustomerAuth(): void {
  Taro.removeStorageSync(CUSTOMER_TOKEN_KEY);
  Taro.removeStorageSync(CUSTOMER_PROFILE_KEY);
}

export function readCurrentSession(): CustomerSession | null {
  return Taro.getStorageSync(CURRENT_SESSION_KEY) ?? null;
}

export function writeCurrentSession(session: CustomerSession): void {
  Taro.setStorageSync(CURRENT_SESSION_KEY, session);
}

export function clearCurrentSession(): void {
  Taro.removeStorageSync(CURRENT_SESSION_KEY);
}

export function readSessionCode(): string {
  return Taro.getStorageSync(SESSION_CODE_KEY) || "001";
}

export function writeSessionCode(sessionCode: string): void {
  const normalized = sessionCode.trim() || "001";
  Taro.setStorageSync(SESSION_CODE_KEY, normalized);
}

export function readCompletedResults(): CompletedResult[] {
  return Taro.getStorageSync(COMPLETED_RESULTS_KEY) ?? [];
}

export function writeCompletedResults(results: CompletedResult[]): void {
  Taro.setStorageSync(COMPLETED_RESULTS_KEY, results);
}

export function readEntryPreference(): EntryPreference | null {
  return Taro.getStorageSync(ENTRY_PREFERENCE_KEY) ?? null;
}

export function writeEntryPreference(preference: EntryPreference): void {
  Taro.setStorageSync(ENTRY_PREFERENCE_KEY, preference);
}

export function clearEntryPreference(): void {
  Taro.removeStorageSync(ENTRY_PREFERENCE_KEY);
}

export function clearSessionScopedState(): void {
  Taro.removeStorageSync(CURRENT_SESSION_KEY);
  Taro.removeStorageSync(COMPLETED_RESULTS_KEY);

  const preference = readEntryPreference();
  if (!preference) {
    return;
  }

  const hasSeedProfile = (preference.seedChoices ?? []).length > 0 || preference.likedSampleIds.length > 0;
  if (!hasSeedProfile) {
    Taro.removeStorageSync(ENTRY_PREFERENCE_KEY);
    return;
  }

  Taro.setStorageSync(ENTRY_PREFERENCE_KEY, {
    ...preference,
    mode: preference.mode === "upload" ? "curated" : preference.mode,
    uploadedFiles: [],
    referencePhotoIds: undefined,
  });
}

export async function sampleSeedPhotos(count?: number): Promise<Array<{ id: string; style_id: string; photo_url: string; profile: Record<string, number> }>> {
  const resp = await client.sampleSeedPhotos(count);
  return (resp.seeds as Array<Record<string, unknown>>).map((seed) => {
    const rawImagePath = seed.photo_url ?? seed.imageUrl ?? seed.image_url;
    const rawImageUrl = typeof rawImagePath === "string" ? rawImagePath : "";
    return {
      id: String(seed.id ?? ""),
      style_id: String(seed.style_id ?? ""),
      photo_url: miniBeautyAssetPath(rawImageUrl) ?? assetUrl(rawImageUrl),
      profile: seed.profile && typeof seed.profile === "object" ? seed.profile as Record<string, number> : {},
    };
  });
}

export async function setSeedGalleryPreference(
  token: string,
  sessionId: string,
  choices: EntrySeedChoice[],
): Promise<unknown> {
  return client.setJesrAestheticProfileFromSeedGallery(token, sessionId, choices as any);
}

export async function setReferencePhotoPreference(
  token: string,
  sessionId: string,
  photoIds: string[],
): Promise<unknown> {
  return client.setJesrAestheticProfileFromReferencePhotos(token, sessionId, photoIds);
}

export async function getPreferenceProfile(token: string, sessionId: string): Promise<{ source: string; profile: Record<string, number> | null; is_set: boolean }> {
  const resp = await client.getJesrAestheticProfile(token, sessionId);
  const profile = resp.jesr_aesthetic_profile;
  return {
    source: profile?.source ?? "none",
    profile: (profile?.profile_vector as Record<string, number> | undefined) ?? null,
    is_set: profile?.profile_status === "ready",
  };
}

export async function smartOptimize(token: string, photoId: string, mode?: string): Promise<{ image: string; status: string }> {
  return client.smartOptimize(token, photoId, mode);
}

export async function processTargetedRetouchV2(token: string, photoId: string, params: Record<string, number>): Promise<{ image: string; status: string }> {
  return client.targetedRetouchV2(token, photoId, params);
}

export async function iterateJesrRecipe(
  token: string,
  sessionId: string,
  photoId: string,
  painTags: string[],
  freeTextFeedback?: string,
): Promise<unknown> {
  return client.iterateJesrRecipe(token, sessionId, photoId, painTags, freeTextFeedback);
}

export function clearFlowState(): void {
  Taro.removeStorageSync(CURRENT_SESSION_KEY);
  Taro.removeStorageSync(COMPLETED_RESULTS_KEY);
  Taro.removeStorageSync(ENTRY_PREFERENCE_KEY);
}
