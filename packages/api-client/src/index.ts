import {
  DEFAULT_SIGNED_ASSET_TTL_SECONDS,
  type CustomerAuthResult,
  type EditJob,
  type EditMode,
  type JESRAestheticProfile,
  type JESRProfileRecipe,
  type JESRSeedChoice,
  type PhotoAsset,
  type PrintRecord,
  type SessionReminder,
  type ShootSession,
  type StaffAuthResult,
  type StaffSessionDetail,
} from "@hellobeauty/domain";

type HeadersMap = Record<string, string>;

export interface ApiTransportRequestOptions {
  data?: unknown;
  headers?: HeadersMap;
  method?: "GET" | "POST";
  token?: string;
}

export interface ApiTransportUploadOptions {
  fieldName?: string;
  file: unknown;
  fileName?: string;
  formData?: Record<string, string>;
  headers?: HeadersMap;
  token?: string;
}

export interface ApiTransport {
  request<T>(url: string, options?: ApiTransportRequestOptions): Promise<T>;
  upload<T>(url: string, options: ApiTransportUploadOptions): Promise<T>;
}

type FetchLike = (
  input: string,
  init?: {
    method?: string;
    body?: unknown;
    headers?: HeadersMap;
    cache?: string;
  },
) => Promise<{
  ok: boolean;
  status: number;
  json(): Promise<unknown>;
}>;

export interface SignedAssetRefreshOptions<TPayload> {
  currentPath: string | null | undefined;
  refresh: () => Promise<TPayload>;
  selectPath: (payload: TPayload) => string | null | undefined;
  now?: number;
}

export interface PollEditJobOptions {
  intervalMs?: number;
  maxAttempts?: number;
}

export interface ApiClientConfig {
  apiBaseUrl: string;
  signedAssetTtlSeconds?: number;
  transport: ApiTransport;
}

export interface CustomerLoginPayload {
  nickname?: string;
  phone: string;
}

export interface StaffLoginPayload {
  password: string;
  username: string;
}

export interface CreateSessionPayload {
  durationMinutes: number;
  sessionCode?: string | null;
  startTime?: string | null;
  storeId: string;
}

export interface PreShootReminderSubscriptionPayload {
  subscriptionAccepted?: boolean;
  subscriptionStatus?: string | null;
  templateId?: string | null;
}

export interface CreateEditJobPayload {
  mode: EditMode;
  photoId: string;
  styleName?: string | null;
}

export interface SearchSessionOptions {
  phone?: string;
}

export interface UploadCameraIngressPayload {
  file: unknown;
  fileName?: string;
  sessionId: string;
  storeId: string;
  temporary?: boolean;
  token: string;
}

function normalizeBaseUrl(value: string): string {
  return value.replace(/\/$/, "");
}

function buildJsonHeaders(options: ApiTransportRequestOptions = {}): HeadersMap {
  const headers: HeadersMap = {
    ...(options.data !== undefined ? { "Content-Type": "application/json" } : {}),
    ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    ...(options.headers ?? {}),
  };
  return headers;
}

function extractErrorDetail(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  return `Request failed with status ${status}`;
}

export function createFetchTransport(fetchImpl?: FetchLike): ApiTransport {
  const runtimeFetch = fetchImpl ?? ((globalThis.fetch as unknown) as FetchLike);
  if (!runtimeFetch) {
    throw new Error("Fetch transport is unavailable in this runtime");
  }

  return {
    async request<T>(url: string, options: ApiTransportRequestOptions = {}): Promise<T> {
      const response = await runtimeFetch(url, {
        method: options.method ?? "GET",
        body: options.data === undefined ? undefined : JSON.stringify(options.data),
        headers: buildJsonHeaders(options),
        cache: "no-store",
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(extractErrorDetail(payload, response.status));
      }
      return payload as T;
    },

    async upload<T>(url: string, options: ApiTransportUploadOptions): Promise<T> {
      if (typeof options.file === "string") {
        throw new Error("Fetch transport expects a File or Blob-like object, not a file path");
      }

      const FormDataCtor = (globalThis as { FormData?: new () => { append(name: string, value: unknown, fileName?: string): void } }).FormData;
      if (!FormDataCtor) {
        throw new Error("FormData is unavailable in this runtime");
      }

      const form = new FormDataCtor();
      for (const [key, value] of Object.entries(options.formData ?? {})) {
        form.append(key, value);
      }
      form.append(options.fieldName ?? "image", options.file, options.fileName);

      const response = await runtimeFetch(url, {
        method: "POST",
        body: form,
        headers: {
          ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
          ...(options.headers ?? {}),
        },
        cache: "no-store",
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(extractErrorDetail(payload, response.status));
      }
      return payload as T;
    },
  };
}

export function buildAbsoluteUrl(apiBaseUrl: string, path: string | null | undefined): string {
  if (!path) {
    return "";
  }
  if (
    path.startsWith("http://") ||
    path.startsWith("https://") ||
    path.startsWith("data:") ||
    path.startsWith("wxfile://") ||
    path.startsWith("file://")
  ) {
    return path;
  }
  return `${normalizeBaseUrl(apiBaseUrl)}${path}`;
}

export function getSignedAssetExpiry(path: string | null | undefined): number | null {
  if (!path) {
    return null;
  }
  const match = path.match(/[?&]expires=(\d+)/);
  if (!match) {
    return null;
  }
  return Number(match[1]) * 1000;
}

export function isSignedAssetUrlExpired(
  path: string | null | undefined,
  now: number = Date.now(),
): boolean {
  const expiresAt = getSignedAssetExpiry(path);
  if (!expiresAt) {
    return false;
  }
  return expiresAt <= now + 15_000;
}

export async function ensureFreshSignedAssetUrl<TPayload>(
  options: SignedAssetRefreshOptions<TPayload>,
): Promise<string> {
  if (options.currentPath && !isSignedAssetUrlExpired(options.currentPath, options.now)) {
    return options.currentPath;
  }

  const payload = await options.refresh();
  const nextPath = options.selectPath(payload);
  if (!nextPath) {
    throw new Error("Signed asset URL is missing after refresh");
  }
  return nextPath;
}

export async function pollEditJobUntilComplete(
  loadJob: () => Promise<EditJob>,
  options: PollEditJobOptions = {},
): Promise<EditJob> {
  const maxAttempts = options.maxAttempts ?? 24;
  const intervalMs = options.intervalMs ?? 1_200;

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const job = await loadJob();
    if (job.status === "completed" && job.resultImageUrl) {
      return job;
    }
    if (job.status === "failed") {
      throw new Error(job.statusMessage || "AI 任务失败");
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error("poll 超时，AI 任务仍未完成");
}

export function createApiClient(config: ApiClientConfig) {
  const apiBaseUrl = normalizeBaseUrl(config.apiBaseUrl);
  const signedAssetTtlSeconds = config.signedAssetTtlSeconds ?? DEFAULT_SIGNED_ASSET_TTL_SECONDS;
  const { transport } = config;

  const request = <T>(path: string, options?: ApiTransportRequestOptions) =>
    transport.request<T>(buildAbsoluteUrl(apiBaseUrl, path), options);

  const upload = <T>(path: string, options: ApiTransportUploadOptions) =>
    transport.upload<T>(buildAbsoluteUrl(apiBaseUrl, path), options);

  const loadEditJob = (token: string, jobId: string) =>
    request<{ job: EditJob }>(`/api/edit-jobs/${jobId}`, {
      token,
    }).then((response) => response.job);

  return {
    apiBaseUrl,
    signedAssetTtlSeconds,

    buildAssetUrl(path: string | null | undefined): string {
      return buildAbsoluteUrl(apiBaseUrl, path);
    },

    loginCustomer(payload: CustomerLoginPayload): Promise<CustomerAuthResult> {
      return request<CustomerAuthResult>("/api/customer/auth/wechat-phone", {
        method: "POST",
        data: {
          phone: payload.phone,
          nickname: payload.nickname,
        },
      });
    },

    loginStaff(payload: StaffLoginPayload): Promise<StaffAuthResult> {
      return request<StaffAuthResult>("/api/staff/auth/login", {
        method: "POST",
        data: payload,
      });
    },

    createSession(token: string, payload: CreateSessionPayload): Promise<ShootSession> {
      return request<{ session: ShootSession }>("/api/sessions", {
        method: "POST",
        token,
        data: {
          store_id: payload.storeId,
          duration_minutes: payload.durationMinutes,
          session_code: payload.sessionCode ?? null,
          start_time: payload.startTime ?? null,
        },
      }).then((response) => response.session);
    },

    getSession(token: string, sessionId: string): Promise<ShootSession> {
      return request<{ session: ShootSession }>(`/api/sessions/${sessionId}`, {
        token,
      }).then((response) => response.session);
    },

    listCustomerSessions(token: string): Promise<ShootSession[]> {
      return request<{ sessions: ShootSession[] }>("/api/customer/sessions", {
        token,
      }).then((response) => response.sessions);
    },

    listSessionPhotos(token: string, sessionId: string): Promise<PhotoAsset[]> {
      return request<{ photos: PhotoAsset[] }>(`/api/sessions/${sessionId}/photos`, {
        token,
      }).then((response) => response.photos);
    },

    completeSession(token: string, sessionId: string): Promise<ShootSession> {
      return request<{ session: ShootSession }>(`/api/sessions/${sessionId}/complete`, {
        method: "POST",
        token,
      }).then((response) => response.session);
    },

    listSessionReminders(token: string, sessionId: string): Promise<SessionReminder[]> {
      return request<{ ok: boolean; reminders: SessionReminder[] }>(`/api/sessions/${sessionId}/reminders`, {
        token,
      }).then((response) => response.reminders);
    },

    schedulePreShootStyleReminder(
      token: string,
      sessionId: string,
      payload: PreShootReminderSubscriptionPayload = {},
    ): Promise<SessionReminder> {
      return request<{ ok: boolean; reminder: SessionReminder }>(
        `/api/sessions/${sessionId}/reminders/pre-shoot-style`,
        {
          method: "POST",
          token,
          data: {
            subscription_accepted: payload.subscriptionAccepted ?? false,
            subscription_status: payload.subscriptionStatus ?? null,
            template_id: payload.templateId ?? null,
          },
        },
      ).then((response) => response.reminder);
    },

    updateStaffReminderStatus(
      token: string,
      reminderId: string,
      status: SessionReminder["status"],
    ): Promise<SessionReminder> {
      return request<{ ok: boolean; reminder: SessionReminder }>(
        `/api/staff/reminders/${reminderId}/status`,
        {
          method: "POST",
          token,
          data: { status },
        },
      ).then((response) => response.reminder);
    },

    selectPhoto(token: string, photoId: string, selected: boolean): Promise<PhotoAsset> {
      return request<{ photo: PhotoAsset }>(`/api/photos/${photoId}/select`, {
        method: "POST",
        token,
        data: { selected },
      }).then((response) => response.photo);
    },

    createEditJob(token: string, payload: CreateEditJobPayload): Promise<EditJob> {
      return request<{ job: EditJob }>("/api/edit-jobs", {
        method: "POST",
        token,
        data: {
          photo_id: payload.photoId,
          mode: payload.mode,
          style_name: payload.styleName ?? null,
        },
      }).then((response) => response.job);
    },

    getEditJob(token: string, jobId: string): Promise<EditJob> {
      return loadEditJob(token, jobId);
    },

    pollEditJob(token: string, jobId: string, options?: PollEditJobOptions): Promise<EditJob> {
      return pollEditJobUntilComplete(() => loadEditJob(token, jobId), options);
    },

    searchStaffSessions(token: string, options: SearchSessionOptions = {}): Promise<ShootSession[]> {
      const query = options.phone?.trim()
        ? `?phone=${encodeURIComponent(options.phone.trim())}`
        : "";
      return request<{ sessions: ShootSession[] }>(`/api/staff/sessions/search${query}`, {
        token,
      }).then((response) => response.sessions);
    },

    getStaffSessionDetail(token: string, sessionId: string): Promise<StaffSessionDetail> {
      return request<StaffSessionDetail>(`/api/staff/sessions/${sessionId}`, {
        token,
      });
    },

    createPrintRecord(token: string, sessionId: string, photoId: string): Promise<PrintRecord> {
      return request<{ record: PrintRecord }>("/api/staff/prints", {
        method: "POST",
        token,
        data: {
          session_id: sessionId,
          photo_id: photoId,
        },
      }).then((response) => response.record);
    },

    uploadCameraIngressPhoto(payload: UploadCameraIngressPayload): Promise<PhotoAsset> {
      return upload<{ photo: PhotoAsset }>(
        `/api/ingress/camera/${payload.storeId}/upload`,
        {
          file: payload.file,
          fileName: payload.fileName,
          token: payload.token,
          formData: {
            session_id: payload.sessionId,
            ...(payload.temporary ? { temporary: "true" } : {}),
          },
        },
      ).then((response) => response.photo);
    },

    setBaseStyleFromReferencePhotos(token: string, sessionId: string, photoIds: string[]): Promise<{ ok: boolean; base_style: unknown }> {
      return request<{ ok: boolean; base_style: unknown }>(
        `/api/sessions/${sessionId}/base-style/reference-photos`,
        {
          method: "POST",
          token,
          data: { photo_ids: photoIds },
        },
      );
    },

    setBaseStyleFromSeedGallery(token: string, sessionId: string, choices: Array<{ seed_id: string; liked: boolean }>): Promise<{ ok: boolean; base_style: unknown }> {
      return request<{ ok: boolean; base_style: unknown }>(
        `/api/sessions/${sessionId}/base-style/seed-selection`,
        {
          method: "POST",
          token,
          data: { choices },
        },
      );
    },

    getBaseStyle(token: string, sessionId: string): Promise<{ ok: boolean; base_style: unknown }> {
      return request<{ ok: boolean; base_style: unknown }>(
        `/api/sessions/${sessionId}/base-style`,
        { token },
      );
    },

    getJesrAestheticProfile(token: string, sessionId: string): Promise<{ ok: boolean; jesr_aesthetic_profile: JESRAestheticProfile | null; profile_status: string }> {
      return request<{ ok: boolean; jesr_aesthetic_profile: JESRAestheticProfile | null; profile_status: string }>(
        `/api/sessions/${sessionId}/jesr/aesthetic-profile`,
        { token },
      );
    },

    setJesrAestheticProfileFromReferencePhotos(token: string, sessionId: string, photoIds: string[]): Promise<{ ok: boolean; jesr_aesthetic_profile: JESRAestheticProfile; profile_status: string }> {
      return request<{ ok: boolean; jesr_aesthetic_profile: JESRAestheticProfile; profile_status: string }>(
        `/api/sessions/${sessionId}/jesr/aesthetic-profile/reference-photos`,
        {
          method: "POST",
          token,
          data: { reference_photo_ids: photoIds },
        },
      );
    },

    setJesrAestheticProfileFromSeedGallery(token: string, sessionId: string, choices: JESRSeedChoice[]): Promise<{ ok: boolean; jesr_aesthetic_profile: JESRAestheticProfile; profile_status: string; jesr_profile_recipe: JESRProfileRecipe }> {
      return request<{ ok: boolean; jesr_aesthetic_profile: JESRAestheticProfile; profile_status: string; jesr_profile_recipe: JESRProfileRecipe }>(
        `/api/sessions/${sessionId}/jesr/aesthetic-profile/seed-gallery`,
        {
          method: "POST",
          token,
          data: { choices },
        },
      );
    },

    getJesrProfileRecipe(token: string, sessionId: string): Promise<{ ok: boolean; recipe: JESRProfileRecipe; jesr_profile_recipe: JESRProfileRecipe; recipe_status: string }> {
      return request<{ ok: boolean; recipe: JESRProfileRecipe; jesr_profile_recipe: JESRProfileRecipe; recipe_status: string }>(
        `/api/sessions/${sessionId}/jesr/profile-recipe`,
        { token },
      );
    },

    initializeJesrProfileRecipe(token: string, sessionId: string, styleId?: string | null): Promise<{ ok: boolean; recipe: JESRProfileRecipe; jesr_profile_recipe: JESRProfileRecipe }> {
      return request<{ ok: boolean; recipe: JESRProfileRecipe; jesr_profile_recipe: JESRProfileRecipe }>(
        `/api/sessions/${sessionId}/jesr/profile-recipe/initialize`,
        {
          method: "POST",
          token,
          data: { style_id: styleId ?? null },
        },
      );
    },

    generateProbeGallery(token: string, photoId: string): Promise<{ ok: boolean; probes: unknown[] }> {
      return request<{ ok: boolean; probes: unknown[] }>(
        `/api/photos/${photoId}/probe/generate`,
        { method: "POST", token },
      );
    },

    submitProbeFeedback(token: string, photoId: string, feedback: Array<{ probe_id: string; liked: boolean }>): Promise<{ ok: boolean; recorded: unknown[] }> {
      return request<{ ok: boolean; recorded: unknown[] }>(
        "/api/probe-feedback",
        {
          method: "POST",
          token,
          data: { photo_id: photoId, feedback },
        },
      );
    },

    getProbeResults(token: string, sessionId: string): Promise<{ ok: boolean; probes: unknown[] }> {
      return request<{ ok: boolean; probes: unknown[] }>(
        `/api/sessions/${sessionId}/probe-results`,
        { token },
      );
    },

    initializeJesrRecipe(token: string, sessionId: string, photoId: string): Promise<{ ok: boolean; recipe: unknown }> {
      return request<{ ok: boolean; recipe: unknown }>(
        `/api/sessions/${sessionId}/jesr-recipe/initialize`,
        {
          method: "POST",
          token,
          data: { photo_id: photoId },
        },
      );
    },

    selectCreativeStyle(token: string, sessionId: string, presetId: string | null): Promise<{ ok: boolean; recipe: unknown }> {
      return request<{ ok: boolean; recipe: unknown }>(
        `/api/sessions/${sessionId}/style-select`,
        {
          method: "POST",
          token,
          data: { preset_id: presetId },
        },
      );
    },

    iterateJesrRecipe(
      token: string,
      sessionId: string,
      photoId: string,
      painTags: string[],
      freeTextFeedback?: string,
    ): Promise<{ ok: boolean; iteration: unknown; updated_recipe: unknown; render_job: unknown }> {
      return request<{ ok: boolean; iteration: unknown; updated_recipe: unknown; render_job: unknown }>(
        `/api/sessions/${sessionId}/iterate`,
        {
          method: "POST",
          token,
          data: { photo_id: photoId, pain_tags: painTags, free_text_feedback: freeTextFeedback ?? null },
        },
      );
    },

    getJesrRecipe(token: string, sessionId: string): Promise<{ ok: boolean; recipe: unknown }> {
      return request<{ ok: boolean; recipe: unknown }>(
        `/api/sessions/${sessionId}/jesr-recipe`,
        { token },
      );
    },

    getIterations(token: string, sessionId: string): Promise<{ ok: boolean; iterations: unknown[] }> {
      return request<{ ok: boolean; iterations: unknown[] }>(
        `/api/sessions/${sessionId}/iterations`,
        { token },
      );
    },

    rollbackIteration(token: string, sessionId: string, iterationId: string): Promise<{ ok: boolean; rollback_iteration: unknown }> {
      return request<{ ok: boolean; rollback_iteration: unknown }>(
        `/api/sessions/${sessionId}/iterations/${iterationId}/rollback`,
        { method: "POST", token },
      );
    },

    getStylePresets(token?: string): Promise<{ ok: boolean; presets: unknown[] }> {
      return request<{ ok: boolean; presets: unknown[] }>(
        "/api/style-presets",
        { token },
      );
    },

    sampleSeedPhotos(count?: number): Promise<{ ok: boolean; seeds: unknown[] }> {
      return request<{ ok: boolean; seeds: unknown[] }>(
        `/api/seeds/sample?count=${count ?? 10}`,
      );
    },

    setSeedGalleryPreference(token: string, sessionId: string, choices: Array<{ seed_id: string; style_id?: string | null; profile: Record<string, number>; liked: boolean }>): Promise<{ ok: boolean; base_style: unknown; preference: unknown }> {
      return request<{ ok: boolean; base_style: unknown; preference: unknown }>(
        `/api/sessions/${sessionId}/base-style/seed-gallery`,
        {
          method: "POST",
          token,
          data: { choices },
        },
      );
    },

    getPreferenceProfile(token: string, sessionId: string): Promise<{ ok: boolean; preference: unknown }> {
      return request<{ ok: boolean; preference: unknown }>(
        `/api/sessions/${sessionId}/preference-profile`,
        { token },
      );
    },

    smartOptimize(token: string, photoId: string, mode?: string): Promise<{ ok: boolean; status: string; image: string; preference_used: boolean; render_mode: string }> {
      return request<{ ok: boolean; status: string; image: string; preference_used: boolean; render_mode: string }>(
        `/api/photos/${photoId}/smart-optimize`,
        { method: "POST", token, data: { mode: mode ?? "style_only" } },
      );
    },

    targetedRetouchV2(token: string, photoId: string, params: Record<string, number>): Promise<{ ok: boolean; status: string; image: string }> {
      return request<{ ok: boolean; status: string; image: string }>(
        `/api/photos/${photoId}/targeted-retouch-v2`,
        { method: "POST", token, data: { params } },
      );
    },

    renderWithRecipe(token: string, sessionId: string, photoId: string, mode?: string): Promise<{ ok: boolean; job: EditJob }> {
      return request<{ ok: boolean; job: EditJob }>(
        `/api/sessions/${sessionId}/render`,
        {
          method: "POST",
          token,
          data: { photo_id: photoId, mode: mode ?? "auto" },
        },
      );
    },

    exportSessionExperiments(token: string, sessionId: string, format?: string): Promise<{ ok: boolean; export_path: string }> {
      return request<{ ok: boolean; export_path: string }>(
        `/api/sessions/${sessionId}/export-experiments`,
        {
          token,
        },
      );
    },
  };
}
