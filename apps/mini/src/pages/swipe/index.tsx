import Taro, { useDidShow } from "@tarojs/taro";
import { Button, Image, Input, Picker, Slider, Text, View } from "@tarojs/components";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  DEFAULT_SESSION_DURATION_MINUTES,
  DEFAULT_STORE_ID,
  type CompletedResult,
  type EditMode,
} from "@hellobeauty/domain";

import { getLocalImageSrc, useLocalImageMap } from "../../utils/use-local-image";
import SeedGallery from "../../components/seed-gallery";
import {
  type CustomerSession,
  type CustomerProfile,
  type EntryPreference,
  type EntrySeedChoice,
  type SessionPhoto,
  assetUrl,
  clearCurrentSession,
  clearSessionScopedState,
  completeSession,
  createSession,
  createMockPhoneNumber,
  initializeJesrRecipe,
  listSessionPhotos,
  listCustomerSessions,
  loginCustomer,
  pollEditJob,
  processTargetedRetouchV2,
  readCustomerProfile,
  readCurrentSession,
  readCustomerToken,
  readEntryPreference,
  readSessionCode,
  renderWithRecipe,
  schedulePreShootStyleReminder,
  selectCreativeStyle,
  selectPhoto,
  setReferencePhotoPreference,
  setSeedGalleryPreference,
  smartOptimize,
  uploadIngressPhoto,
  writeCompletedResults,
  writeCurrentSession,
  writeCustomerAuth,
  writeEntryPreference,
  writeSessionCode,
} from "../../utils/api";
import "./swipe.css";

type FlowStep =
  | "entry"
  | "appointments"
  | "stylePreference"
  | "styleProfileGallery"
  | "upload"
  | "capture"
  | "selection"
  | "edit"
  | "complete"
  | "profile";
type CaptureState = "idle" | "countdown" | "shooting" | "ended";
type EntryMode = "upload" | "none";
type EditChannel = "smart" | "retouch" | "creative";
type EditView = "channels" | EditChannel;
type AfterLoginAction = "entry" | "start" | "profile" | "appointment";
type ChromeVars = Record<string, string>;
type RetouchPreviewMode = "original" | "retouched" | "compare";

const HERO_IMAGE = "/beauty/fresh_japanese/fresh_japanese_02.jpeg";
const POSE_IMAGE = "/beauty/clear_korean/clear_korean_03.jpeg";
const PRE_SHOOT_TEMPLATE_ID =
  typeof process !== "undefined" ? process.env?.TARO_APP_PRE_SHOOT_TEMPLATE_ID?.trim() : undefined;
const APPOINTMENT_LEAD_MINUTES = 3;
const SHOOTING_SIMULATION_SECONDS = 60;
const LOOK_IMAGES = [
  "/beauty/fresh_japanese/fresh_japanese_11.jpeg",
  "/beauty/retro_hongkong/retro_hongkong_16.jpeg",
  "/beauty/clear_korean/clear_korean_14.jpeg",
  "/beauty/lazy_french/lazy_french_17.jpeg",
  "/beauty/american_hotgirl/american_hotgirl_18.jpeg",
];

const CREATIVE_STYLES = [
  {
    id: "fresh_japanese",
    label: "日系清纯",
    description: "柔光、低饱和、白皙、淡蓝粉调",
    image: "/beauty/fresh_japanese/fresh_japanese_02.jpeg",
  },
  {
    id: "clear_korean",
    label: "韩系清透",
    description: "水光肌、高透感、冷色调",
    image: "/beauty/clear_korean/clear_korean_03.jpeg",
  },
  {
    id: "retro_hongkong",
    label: "港式复古",
    description: "暖黄调、柔焦、90年代胶片",
    image: "/beauty/retro_hongkong/retro_hongkong_04.jpeg",
  },
  {
    id: "lazy_french",
    label: "法式慵懒",
    description: "奶油调、午后自然光",
    image: "/beauty/lazy_french/lazy_french_05.jpeg",
  },
  {
    id: "american_hotgirl",
    label: "美式辣妹",
    description: "高对比、小麦肤、暖棕调",
    image: "/beauty/american_hotgirl/american_hotgirl_06.jpeg",
  },
] as const;

type CreativeStyleId = (typeof CREATIVE_STYLES)[number]["id"];

const PROFILE_VECTOR_BY_STYLE: Record<CreativeStyleId, Record<string, number>> = {
  fresh_japanese: {
    light_tendency: 0.55,
    warmth: -0.12,
    contrast: -0.08,
    texture_tendency: 0.22,
    makeup_intensity: -0.18,
    facial_detail_preference: 0.18,
    style_strength: 0.42,
    identity_tolerance: -0.35,
  },
  clear_korean: {
    light_tendency: 0.48,
    warmth: -0.08,
    contrast: 0.04,
    texture_tendency: 0.28,
    makeup_intensity: 0.08,
    facial_detail_preference: 0.22,
    style_strength: 0.48,
    identity_tolerance: -0.32,
  },
  retro_hongkong: {
    light_tendency: -0.08,
    warmth: 0.38,
    contrast: 0.42,
    texture_tendency: -0.06,
    makeup_intensity: 0.26,
    facial_detail_preference: 0.18,
    style_strength: 0.58,
    identity_tolerance: -0.28,
  },
  lazy_french: {
    light_tendency: 0.16,
    warmth: 0.22,
    contrast: -0.16,
    texture_tendency: 0.1,
    makeup_intensity: 0.04,
    facial_detail_preference: 0.2,
    style_strength: 0.45,
    identity_tolerance: -0.3,
  },
  american_hotgirl: {
    light_tendency: 0.02,
    warmth: 0.32,
    contrast: 0.46,
    texture_tendency: -0.04,
    makeup_intensity: 0.48,
    facial_detail_preference: 0.24,
    style_strength: 0.68,
    identity_tolerance: -0.24,
  },
};

const SEED_CHOICES: EntrySeedChoice[] = CREATIVE_STYLES.flatMap((style, styleIndex) =>
  [0, 1].map((itemIndex) => ({
    seed_id: `${style.id}_${itemIndex + 1}`,
    style_id: style.id,
    liked: itemIndex === 0,
    profile: {
      ...PROFILE_VECTOR_BY_STYLE[style.id],
      style_strength: PROFILE_VECTOR_BY_STYLE[style.id].style_strength + itemIndex * 0.03,
      light_tendency: PROFILE_VECTOR_BY_STYLE[style.id].light_tendency + itemIndex * 0.03,
    },
  })),
);

function getChromeVars(): ChromeVars {
  const fallbackClearance = 88;
  const navRowHeight = 44;
  try {
    const windowInfo = Taro.getWindowInfo?.();
    const menuRect = Taro.getMenuButtonBoundingClientRect?.();
    const statusBarHeight = Number(windowInfo?.statusBarHeight ?? 0);
    const menuBottom = Number(menuRect?.bottom ?? 0);
    const clearance = Math.ceil(Math.max(menuBottom + 10, statusBarHeight + 52, fallbackClearance));
    return {
      "--hb-status-clearance": `${clearance}px`,
      "--hb-nav-row-height": `${navRowHeight}px`,
      "--hb-topbar-height": `${clearance + navRowHeight}px`,
    };
  } catch {
    return {
      "--hb-status-clearance": `${fallbackClearance}px`,
      "--hb-nav-row-height": `${navRowHeight}px`,
      "--hb-topbar-height": `${fallbackClearance + navRowHeight}px`,
    };
  }
}

const RETOUCH_PRESETS = [
  { key: "skin_smooth", label: "磨皮", group: "面部", defaultValue: 0 },
  { key: "face_slim", label: "瘦脸", group: "面部", defaultValue: 0 },
  { key: "face_contour", label: "轮廓", group: "面部", defaultValue: 0 },
  { key: "eye_size", label: "亮眼", group: "眼睛", defaultValue: 0 },
  { key: "eye_shape", label: "眼型", group: "眼睛", defaultValue: 0 },
  { key: "nose_lift", label: "鼻梁", group: "鼻子", defaultValue: 0 },
  { key: "nose_tip", label: "鼻尖", group: "鼻子", defaultValue: 0 },
  { key: "lip_saturation", label: "唇色", group: "嘴巴", defaultValue: 0 },
  { key: "lip_shape", label: "唇形", group: "嘴巴", defaultValue: 0 },
  { key: "neck_smooth", label: "颈纹", group: "颈部", defaultValue: 0 },
  { key: "neck_line", label: "颈线", group: "颈部", defaultValue: 0 },
  { key: "body_ratio", label: "比例", group: "身体", defaultValue: 0 },
  { key: "shoulder_line", label: "肩颈线", group: "身体", defaultValue: 0 },
] as const;

const RETOUCH_TABS = ["面部", "眼睛", "鼻子", "嘴巴", "颈部", "身体"] as const;
const RETOUCH_VIEW_TABS: Array<{ key: RetouchPreviewMode; label: string }> = [
  { key: "original", label: "原图" },
  { key: "retouched", label: "精修" },
  { key: "compare", label: "对比" },
];
const DEFAULT_RETOUCH_PARAMS: Record<string, number> = Object.fromEntries(
  RETOUCH_PRESETS.map((preset) => [preset.key, preset.defaultValue]),
);
const SMART_RETOUCH_PARAMS: Record<string, number> = {
  skin_smooth: 18,
  face_slim: 8,
  face_contour: 6,
  eye_size: 8,
  eye_shape: 5,
  nose_lift: 5,
  nose_tip: 3,
  lip_saturation: 10,
  lip_shape: 4,
  neck_smooth: 8,
  neck_line: 5,
  body_ratio: 3,
  shoulder_line: 4,
};

function normalizeSessionCode(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 3);
  return digits ? digits.padStart(3, "0") : "001";
}

function sessionCodeFromSession(session: CustomerSession | null | undefined): string {
  const phoneDigits = session?.phone?.replace(/\D/g, "");
  const match = session?.sessionName?.match(/^(\d{1,3})_/);
  if (match?.[1] && match[1] !== phoneDigits?.slice(0, match[1].length)) {
    return normalizeSessionCode(match[1]);
  }
  if (session?.sessionName?.includes("__") && match?.[1]) {
    return normalizeSessionCode(match[1]);
  }
  return "";
}

function displaySessionCode(session: CustomerSession | null | undefined, fallback = "001"): string {
  const code = sessionCodeFromSession(session);
  return code || normalizeSessionCode(fallback);
}

function numericSessionCode(session: CustomerSession | null | undefined): number {
  const code = sessionCodeFromSession(session);
  if (!code) {
    return 0;
  }
  const value = Number(code);
  return Number.isFinite(value) ? value : 0;
}

function canStartSession(session: CustomerSession | null | undefined, now = Date.now()): boolean {
  if (!session || isSessionCompleted(session)) {
    return false;
  }
  const start = new Date(session.startTime).getTime();
  return !Number.isFinite(start) || start <= now;
}

function selectPreferredSession(sessions: CustomerSession[]): CustomerSession | null {
  const activeSessions = sessions.filter((item) => !isSessionCompleted(item));
  const now = Date.now();
  return (
    activeSessions.find((item) => canStartSession(item, now)) ??
    activeSessions[0] ??
    null
  );
}

function selectStartCandidate(
  sessions: CustomerSession[],
  storedSession: CustomerSession | null | undefined,
): CustomerSession | null {
  const activeSessions = sessions.filter((item) => !isSessionCompleted(item));
  const startableSession = activeSessions.find((item) => canStartSession(item));
  if (startableSession) {
    return startableSession;
  }
  const storedMatch = storedSession
    ? activeSessions.find((item) => item.id === storedSession.id)
    : null;
  return storedMatch ?? activeSessions[0] ?? null;
}

function selectServiceRetouchSession(
  current: CustomerSession | null,
  sessions: CustomerSession[],
): CustomerSession | null {
  if (current) {
    return current;
  }
  return selectPreferredSession(sessions) ?? sessions[0] ?? null;
}

function nextSessionCodeFromHistory(sessions: CustomerSession[], fallback: string): string {
  const maxCode = sessions.reduce((max, item) => {
    const code = numericSessionCode(item);
    return Number.isFinite(code) ? Math.max(max, code) : max;
  }, 0);
  return normalizeSessionCode(String(maxCode > 0 ? maxCode + 1 : Number(normalizeSessionCode(fallback))));
}

function getSelectedPhotos(photos: SessionPhoto[]): SessionPhoto[] {
  return photos.filter((photo) => photo.selected);
}

function maskPhone(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 7) {
    return digits || "未登录";
  }
  return `${digits.slice(0, 3)}****${digits.slice(-4)}`;
}

function normalizePhoneInput(value: unknown): string {
  return String(value ?? "").replace(/\D/g, "").slice(0, 11);
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function minimumAppointmentStart(now = Date.now()): Date {
  const next = new Date(now);
  next.setSeconds(0, 0);
  next.setMinutes(next.getMinutes() + APPOINTMENT_LEAD_MINUTES);
  return next;
}

function defaultAppointmentStart(): Date {
  return minimumAppointmentStart();
}

function dateInputValue(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

function timeInputValue(date: Date): string {
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

function buildAppointmentStart(dateValue: string, timeValue: string): Date | null {
  const [year, month, day] = dateValue.split("-").map(Number);
  const [hour, minute] = timeValue.split(":").map(Number);
  if (![year, month, day, hour, minute].every(Number.isFinite)) {
    return null;
  }
  return new Date(year, month - 1, day, hour, minute, 0, 0);
}

function resetAppointmentStartInput(): { date: string; time: string } {
  const nextStart = defaultAppointmentStart();
  return {
    date: dateInputValue(nextStart),
    time: timeInputValue(nextStart),
  };
}

function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) {
    return "待定";
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "待定";
  }
  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

function formatDuration(seconds: number): string {
  const safeSeconds = Math.max(0, Math.ceil(seconds));
  return `${pad2(Math.floor(safeSeconds / 60))}:${pad2(safeSeconds % 60)}`;
}

function isSessionCompleted(session: CustomerSession | null | undefined): boolean {
  return session?.status === "COMPLETED" || !!session?.completedAt;
}

function formatSessionStartHint(session: CustomerSession | null | undefined, now = Date.now()): string {
  if (!session) {
    return "暂无预约";
  }
  if (isSessionCompleted(session)) {
    return "已完成";
  }
  const start = new Date(session.startTime).getTime();
  if (!Number.isFinite(start)) {
    return "未完成";
  }
  const diffMinutes = Math.ceil((start - now) / 60000);
  if (diffMinutes > 60) {
    return `还有 ${Math.ceil(diffMinutes / 60)} 小时开始`;
  }
  if (diffMinutes > 0) {
    return `还有 ${diffMinutes} 分钟开始`;
  }
  return "可开始拍摄";
}

function sessionStatusLabel(session: CustomerSession): string {
  if (isSessionCompleted(session)) {
    return "完成";
  }
  return "未完成";
}

function reminderDateTime(start: Date | null): Date | null {
  return start ? new Date(start.getTime() - APPOINTMENT_LEAD_MINUTES * 60 * 1000) : null;
}

async function requestPreShootSubscription(): Promise<{
  subscriptionAccepted: boolean;
  subscriptionStatus: string;
  templateId: string | null;
}> {
  const templateId = PRE_SHOOT_TEMPLATE_ID || null;
  const requestSubscribeMessage = (Taro as any).requestSubscribeMessage;
  if (!templateId || typeof requestSubscribeMessage !== "function") {
    return {
      subscriptionAccepted: false,
      subscriptionStatus: templateId ? "UNAVAILABLE" : "NOT_CONFIGURED",
      templateId,
    };
  }
  try {
    const result = await requestSubscribeMessage({ tmplIds: [templateId] });
    const status = String(result?.[templateId] ?? "UNKNOWN").toUpperCase();
    return {
      subscriptionAccepted: status === "ACCEPT",
      subscriptionStatus: status,
      templateId,
    };
  } catch {
    return {
      subscriptionAccepted: false,
      subscriptionStatus: "REQUEST_FAILED",
      templateId,
    };
  }
}

function isSessionMissingError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  return /Session not found|status 404|404 Not Found/i.test(error.message);
}

function getSeedChoicesFromPreference(preference: EntryPreference | null): EntrySeedChoice[] {
  if (preference?.seedChoices?.length) {
    return preference.seedChoices;
  }
  if (preference?.likedSampleIds?.length) {
    const likedIds = new Set(preference.likedSampleIds);
    return SEED_CHOICES.map((choice) => ({ ...choice, liked: likedIds.has(choice.seed_id) }));
  }
  return [];
}

function hasLocalAestheticProfile(preference: EntryPreference | null): boolean {
  return getSeedChoicesFromPreference(preference).length > 0;
}

function buildRetouchPreviewFilter(params: Record<string, number>): string {
  const skin = Math.max(-30, Math.min(30, params.skin_smooth ?? 0));
  const lips = Math.max(-30, Math.min(30, params.lip_saturation ?? 0));
  const contour = Math.max(-30, Math.min(30, params.face_contour ?? 0));
  const brightness = 1 + skin / 300;
  const saturation = 1 + lips / 260;
  const contrast = 1 + contour / 420;
  return `brightness(${brightness.toFixed(3)}) saturate(${saturation.toFixed(3)}) contrast(${contrast.toFixed(3)})`;
}

async function materializeImageForAlbum(path: string): Promise<string> {
  if (path.startsWith("data:image/")) {
    const match = path.match(/^data:image\/\w+;base64,(.+)$/);
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
    return filePath;
  }

  const preparedPath = assetUrl(path);
  if (preparedPath.startsWith("http://") || preparedPath.startsWith("https://")) {
    const activeToken = readCustomerToken();
    const downloadResult = await Taro.downloadFile({
      url: preparedPath,
      timeout: 20000,
      header: activeToken ? { Authorization: `Bearer ${activeToken}` } : undefined,
    });
    if (
      downloadResult.statusCode < 200 ||
      downloadResult.statusCode >= 300 ||
      !downloadResult.tempFilePath
    ) {
      throw new Error("图片下载失败");
    }
    return downloadResult.tempFilePath;
  }

  return preparedPath;
}

export default function SwipePage() {
  const [flowStep, setFlowStep] = useState<FlowStep>("entry");
  const [captureState, setCaptureState] = useState<CaptureState>("idle");
  const [phone, setPhone] = useState(() => readCustomerProfile()?.phone ?? "");
  const [sessionCode, setSessionCode] = useState(readSessionCode());
  const [token, setToken] = useState(readCustomerToken());
  const [session, setSession] = useState<CustomerSession | null>(readCurrentSession());
  const [sessions, setSessions] = useState<CustomerSession[]>([]);
  const [referenceFiles, setReferenceFiles] = useState<string[]>([]);
  const [photos, setPhotos] = useState<SessionPhoto[]>([]);
  const [serviceRetouchPhotos, setServiceRetouchPhotos] = useState<SessionPhoto[]>([]);
  const [serviceRetouchMode, setServiceRetouchMode] = useState(false);
  const [profileReturnMode, setProfileReturnMode] = useState(false);
  const [countdown, setCountdown] = useState(3);
  const [shootingRemainingSeconds, setShootingRemainingSeconds] = useState(SHOOTING_SIMULATION_SECONDS);
  const [editChannel, setEditChannel] = useState<EditChannel>("smart");
  const [editView, setEditView] = useState<EditView>("channels");
  const [retouchTab, setRetouchTab] = useState<(typeof RETOUCH_TABS)[number]>("面部");
  const [retouchPreviewMode, setRetouchPreviewMode] = useState<RetouchPreviewMode>("retouched");
  const [creativeStyle, setCreativeStyle] = useState<CreativeStyleId>("fresh_japanese");
  const [retouchParams, setRetouchParams] = useState<Record<string, number>>(
    () => ({ ...DEFAULT_RETOUCH_PARAMS }),
  );
  const [preferenceSet, setPreferenceSet] = useState(false);
  const [results, setResults] = useState<CompletedResult[]>([]);
  const [selectedResultIds, setSelectedResultIds] = useState<Set<string>>(() => new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loginSheetOpen, setLoginSheetOpen] = useState(false);
  const [entrySheetOpen, setEntrySheetOpen] = useState(false);
  const [appointmentDraftOpen, setAppointmentDraftOpen] = useState(false);
  const [afterLoginAction, setAfterLoginAction] = useState<AfterLoginAction>("start");
  const [nowTick, setNowTick] = useState(() => Date.now());
  const [chromeVars, setChromeVars] = useState<ChromeVars>(() => getChromeVars());
  const [appointmentStartInput, setAppointmentStartInput] = useState(resetAppointmentStartInput);
  const refreshInFlightRef = useRef(false);
  const completedSessionIdRef = useRef("");
  const editRunIdRef = useRef(0);

  const galleryPhotos = serviceRetouchMode ? serviceRetouchPhotos : photos;
  const shootRecentPhotos = useMemo(() => [...photos].reverse(), [photos]);
  const recentPhotos = useMemo(() => [...galleryPhotos].reverse(), [galleryPhotos]);
  const selectedPhotos = useMemo(() => getSelectedPhotos(galleryPhotos), [galleryPhotos]);
  const selectedPhotoIds = useMemo(() => new Set(selectedPhotos.map((photo) => photo.id)), [selectedPhotos]);
  const selectedSmartResults = useMemo(
    () => results.filter((result) => result.mode === "beauty" && selectedPhotoIds.has(result.photoId)),
    [results, selectedPhotoIds],
  );
  const hasCompleteSmartResults = useMemo(() => {
    if (selectedPhotos.length === 0 || selectedSmartResults.length !== selectedPhotos.length) {
      return false;
    }
    const resultIds = new Set(selectedSmartResults.map((result) => result.photoId));
    return selectedPhotos.every((photo) => resultIds.has(photo.id));
  }, [selectedPhotos, selectedSmartResults]);
  const selectedRetouchResults = useMemo(
    () => results.filter((result) => result.mode === "retouch" && selectedPhotoIds.has(result.photoId)),
    [results, selectedPhotoIds],
  );
  const selectedExportResults = useMemo(
    () => results.filter((result) => selectedResultIds.has(result.photoId)),
    [results, selectedResultIds],
  );
  const latestPhoto = shootRecentPhotos[0] ?? null;
  const imageMap = useLocalImageMap([...photos, ...serviceRetouchPhotos].map((photo) => photo.previewUrl));
  const resultMap = useLocalImageMap(results.map((result) => result.resultImageUrl));
  const activePhoto = selectedPhotos[0] ?? latestPhoto;
  const activeStyle = CREATIVE_STYLES.find((style) => style.id === creativeStyle) ?? CREATIVE_STYLES[0];
  const normalizedCode = session ? displaySessionCode(session, sessionCode) : normalizeSessionCode(sessionCode);
  const displaySessionName = session?.sessionName ?? "暂无场次";
  const activeSessionHint = formatSessionStartHint(session, nowTick);
  const activeSessionCanStart = canStartSession(session, nowTick);
  const selectedAppointmentStart = buildAppointmentStart(appointmentStartInput.date, appointmentStartInput.time);
  const selectedReminderStart = reminderDateTime(selectedAppointmentStart);
  const storedReferencePhotoIds = readEntryPreference()?.referencePhotoIds ?? [];
  const hasSyncedReferencePhotos = storedReferencePhotoIds.length > 0;
  const showDock =
    flowStep === "entry" ||
    flowStep === "appointments" ||
    flowStep === "stylePreference" ||
    flowStep === "styleProfileGallery" ||
    flowStep === "upload" ||
    flowStep === "profile";
  const showAppointmentForm = !session || appointmentDraftOpen;
  const profileToolMode = profileReturnMode || serviceRetouchMode;
  const activeSessionCompleted = isSessionCompleted(session);
  const shootingProgressPercent = Math.max(
    0,
    Math.min(100, (shootingRemainingSeconds / SHOOTING_SIMULATION_SECONDS) * 100),
  );

  const getPhotoSrc = (photo: SessionPhoto | null | undefined): string =>
    photo ? getLocalImageSrc(photo.previewUrl, imageMap) : HERO_IMAGE;
  const smartPreviewItems =
    hasCompleteSmartResults
      ? selectedSmartResults.map((result, index) => ({
          id: result.photoId,
          src: getLocalImageSrc(result.resultImageUrl, resultMap),
          label: `优化结果 ${index + 1}`,
        }))
      : (selectedPhotos.length > 0 ? selectedPhotos : activePhoto ? [activePhoto] : []).map((photo, index) => ({
          id: photo.id,
          src: getPhotoSrc(photo),
          label: `待优化 ${index + 1}`,
        }));
  const activeRetouchResult = activePhoto
    ? selectedRetouchResults.find((result) => result.photoId === activePhoto.id) ?? null
    : null;
  const originalPreviewSrc = activePhoto ? getPhotoSrc(activePhoto) : HERO_IMAGE;
  const retouchedPreviewSrc = activeRetouchResult
    ? getLocalImageSrc(activeRetouchResult.resultImageUrl, resultMap)
    : originalPreviewSrc;
  const retouchPreviewFilter = activeRetouchResult ? "none" : buildRetouchPreviewFilter(retouchParams);

  const commitCompletedResults = (nextResults: CompletedResult[]) => {
    setResults(nextResults);
    setSelectedResultIds(new Set(nextResults.map((result) => result.photoId)));
    writeCompletedResults(nextResults);
  };

  const toggleResultSelection = (photoId: string) => {
    setSelectedResultIds((current) => {
      const next = new Set(current);
      if (next.has(photoId)) {
        next.delete(photoId);
      } else {
        next.add(photoId);
      }
      return next;
    });
  };

  useEffect(() => {
    setChromeVars(getChromeVars());
  }, []);

  useEffect(() => {
    if (flowStep !== "appointments") {
      return undefined;
    }
    setNowTick(Date.now());
    const timer = setInterval(() => setNowTick(Date.now()), 30000);
    return () => clearInterval(timer);
  }, [flowStep]);

  useEffect(() => () => {
    editRunIdRef.current += 1;
  }, []);

  const clearStaleSession = () => {
    clearSessionScopedState();
    setSession(null);
    setPhotos([]);
    setServiceRetouchMode(false);
    setServiceRetouchPhotos([]);
    setProfileReturnMode(false);
    commitCompletedResults([]);
    setReferenceFiles([]);
    setPreferenceSet(hasLocalAestheticProfile(readEntryPreference()));
    setCaptureState("idle");
    setEntrySheetOpen(false);
  };

  const refreshCustomerSessions = async (
    activeToken = readCustomerToken(),
    preferredSessionId?: string,
  ): Promise<CustomerSession[]> => {
    if (!activeToken) {
      setSessions([]);
      setSession(null);
      return [];
    }
    const nextSessions = await listCustomerSessions(activeToken);
    setSessions(nextSessions);
    const preferredMatch = preferredSessionId
      ? nextSessions.find((item) => item.id === preferredSessionId)
      : null;
    const storedSession = readCurrentSession();
    const storedMatch = storedSession
      ? nextSessions.find((item) => item.id === storedSession.id)
      : null;
    const nextActiveSession =
      preferredMatch ??
      (storedMatch && !isSessionCompleted(storedMatch) ? storedMatch : null) ??
      selectPreferredSession(nextSessions);
    if (nextActiveSession) {
      writeCurrentSession(nextActiveSession);
      setSession(nextActiveSession);
    } else {
      clearCurrentSession();
      setSession(null);
    }
    setSessionCode(nextSessionCodeFromHistory(nextSessions, sessionCode));
    return nextSessions;
  };

  const refreshPhotos = async (sessionId?: string): Promise<boolean> => {
    const activeSession = sessionId ?? session?.id;
    const activeToken = readCustomerToken();
    if (!activeSession || !activeToken) {
      return true;
    }
    if (refreshInFlightRef.current) {
      return true;
    }

    refreshInFlightRef.current = true;
    try {
      const nextPhotos = await listSessionPhotos(activeToken, activeSession);
      setPhotos(nextPhotos);
      return true;
    } catch (nextError) {
      if (isSessionMissingError(nextError)) {
        clearStaleSession();
        if (!["entry", "appointments", "profile", "stylePreference", "styleProfileGallery"].includes(flowStep)) {
          setFlowStep("appointments");
          setError("当前场次已失效，请重新预约后再拍摄。");
        }
        return false;
      }
      throw nextError;
    } finally {
      refreshInFlightRef.current = false;
    }
  };

  const handleLogin = async (phoneOverride?: string) => {
    if (loading) return null;
    const nextPhone = normalizePhoneInput(phoneOverride ?? phone);
    if (!nextPhone) {
      setError("请输入手机号");
      return null;
    }

    setPhone(nextPhone);
    setLoading(true);
    setError("");
    try {
      const payload: { token: string; user: CustomerProfile } = await loginCustomer(
        nextPhone,
        "店内体验用户",
      );
      writeCustomerAuth(payload.token, payload.user);
      setToken(payload.token);
      return payload.token;
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "登录失败");
      return null;
    } finally {
      setLoading(false);
    }
  };

  const ensureToken = async () => {
    const activeToken = readCustomerToken();
    if (activeToken) {
      setToken(activeToken);
      return activeToken;
    }
    setAfterLoginAction("entry");
    setLoginSheetOpen(true);
    return null;
  };

  const ensureSession = async () => {
    const activeToken = await ensureToken();
    if (!activeToken) {
      return null;
    }

    if (session) {
      return session;
    }

    const storedSession = readCurrentSession();
    if (storedSession) {
      setSession(storedSession);
      return storedSession;
    }

    setError("请先预约场次");
    setFlowStep("appointments");
    void Taro.showModal({
      title: "请先预约",
      content: "预约成功后即可开始拍摄、选片和美颜精修。",
      confirmText: "去预约",
      showCancel: false,
    });
    return null;
  };

  const ensureStartableSession = async (loginAction: AfterLoginAction = "start") => {
    const activeToken = readCustomerToken();
    if (!activeToken) {
      setAfterLoginAction(loginAction);
      setLoginSheetOpen(true);
      return null;
    }

    setToken(activeToken);
    const nextSessions = await refreshCustomerSessions(activeToken);
    const activeSession = selectStartCandidate(nextSessions, readCurrentSession() ?? session);
    if (!activeSession) {
      setFlowStep("appointments");
      void Taro.showModal({
        title: "请先预约",
        content: "你还没有预约场次。预约成功后即可开始拍摄。",
        confirmText: "去预约",
        showCancel: false,
      });
      return null;
    }

    setSession(activeSession);
    writeCurrentSession(activeSession);
    if (!canStartSession(activeSession)) {
      setFlowStep("appointments");
      void Taro.showModal({
        title: "还未到拍摄时间",
        content: `${formatSessionStartHint(activeSession)}。到店后再点击开始拍摄。`,
        confirmText: "知道了",
        showCancel: false,
      });
      return null;
    }

    return activeSession;
  };

  const createAppointment = async () => {
    if (loading) {
      return null;
    }
    const activeToken = readCustomerToken();
    if (!activeToken) {
      setAfterLoginAction("appointment");
      setLoginSheetOpen(true);
      return null;
    }

    const appointmentStart = buildAppointmentStart(appointmentStartInput.date, appointmentStartInput.time);
    if (!appointmentStart || appointmentStart.getTime() < minimumAppointmentStart().getTime()) {
      setAppointmentStartInput(resetAppointmentStartInput());
      setError(`请选择至少${APPOINTMENT_LEAD_MINUTES}分钟后的预约开始时间`);
      return null;
    }

    setLoading(true);
    setError("");
    try {
      const nextCode = nextSessionCodeFromHistory(sessions, sessionCode);
      const subscription = await requestPreShootSubscription();
      const nextSession = await createSession(
        activeToken,
        DEFAULT_STORE_ID,
        DEFAULT_SESSION_DURATION_MINUTES,
        nextCode,
        appointmentStart.toISOString(),
      );
      let sessionWithReminder = nextSession;
      let reminderDueAt = nextSession.preShootReminder?.dueAt ?? reminderDateTime(appointmentStart)?.toISOString();
      try {
        const reminder = await schedulePreShootStyleReminder(activeToken, nextSession.id, subscription);
        sessionWithReminder = {
          ...nextSession,
          preShootReminder: reminder,
        };
        reminderDueAt = reminder.dueAt;
      } catch {
        setError("预约已成功，提醒授权同步失败，可稍后重新进入预约页同步。");
        void Taro.showToast({ title: "提醒同步失败", icon: "none" });
      }
      setSessionCode(nextCode);
      writeSessionCode(nextCode);
      writeCurrentSession(sessionWithReminder);
      setSession(sessionWithReminder);
      setAppointmentDraftOpen(false);
      setPhotos([]);
      await refreshCustomerSessions(activeToken, sessionWithReminder.id);
      writeCurrentSession(sessionWithReminder);
      setSession(sessionWithReminder);
      await refreshPhotos(nextSession.id);
      void Taro.showToast({ title: "预约成功", icon: "success" });
      const reminderCopy = subscription.subscriptionAccepted
        ? `${formatDateTime(reminderDueAt)} 会提醒你完成风格爱好。若有想打卡照片，开始拍摄前会和风格爱好一起使用。`
        : `已为你记录 ${formatDateTime(appointmentStart)} 的预约。拍摄前可从“我的预约”进入风格爱好，想打卡照片也会在开始拍摄前合并使用。`;
      void Taro.showModal({
        title: "拍摄前准备",
        content: reminderCopy,
        confirmText: "去填写",
        cancelText: "稍后",
      }).then((result) => {
        if (result.confirm) {
          setFlowStep("stylePreference");
        }
      });
      return sessionWithReminder;
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "预约失败");
      return null;
    } finally {
      setLoading(false);
    }
  };

  const chooseReferencePhotos = async (sourceType: Array<"album" | "camera"> = ["album", "camera"]) => {
    try {
      const result = await Taro.chooseImage({ count: 6, sourceType });
      const nextFiles = result.tempFilePaths ?? [];
      setReferenceFiles(nextFiles);
      setError("");
      const currentPreference = readEntryPreference();
      writeEntryPreference({
        mode: "upload",
        uploadedFiles: nextFiles,
        likedSampleIds: currentPreference?.likedSampleIds ?? [],
        seedChoices: currentPreference?.seedChoices,
        referencePhotoIds: currentPreference?.referencePhotoIds,
      });
    } catch {
      void Taro.showToast({ title: "暂未选择照片", icon: "none" });
    }
  };

  const requestAestheticProfile = async () => {
    const result = await Taro.showModal({
      title: "请先填写风格爱好",
      content: "拍摄前需要先完成风格爱好。没有心仪照片时，也需要先从风格照片里选择喜欢或不喜欢。",
      confirmText: "去填写",
      showCancel: false,
    });
    if (result.confirm) {
      setEntrySheetOpen(false);
      setFlowStep("styleProfileGallery");
    }
  };

  const ensureLocalAestheticProfile = async () => {
    const preference = readEntryPreference();
    if (hasLocalAestheticProfile(preference)) {
      return preference;
    }
    await requestAestheticProfile();
    return null;
  };

  const syncAestheticProfileToSession = async (activeToken: string, sessionId: string, preference: EntryPreference) => {
    const seedChoices = getSeedChoicesFromPreference(preference);
    if (seedChoices.length === 0) {
      return;
    }
    await setSeedGalleryPreference(activeToken, sessionId, seedChoices);
  };

  const startFlow = async (mode: EntryMode) => {
    const profilePreference = await ensureLocalAestheticProfile();
    if (!profilePreference) {
      return;
    }

    const preferenceReferenceIds = profilePreference.referencePhotoIds ?? [];
    if (mode === "upload" && referenceFiles.length === 0 && preferenceReferenceIds.length === 0) {
      setFlowStep("upload");
      setError("请先上传心仪照片");
      return;
    }

    const activeToken = readCustomerToken();
    if (!activeToken) {
      setAfterLoginAction("start");
      setLoginSheetOpen(true);
      return;
    }
    const activeSession = await ensureStartableSession("start");
    if (!activeSession) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      await syncAestheticProfileToSession(activeToken, activeSession.id, profilePreference);
      if (mode === "upload" && referenceFiles.length > 0) {
        const uploadedPhotos = [];
        for (const filePath of referenceFiles) {
          uploadedPhotos.push(await uploadIngressPhoto(activeToken, DEFAULT_STORE_ID, activeSession.id, filePath));
        }
        await setReferencePhotoPreference(
          activeToken,
          activeSession.id,
          uploadedPhotos.map((photo) => photo.id),
        );
        setPreferenceSet(true);
        writeEntryPreference({
          mode: "upload",
          uploadedFiles: [],
          likedSampleIds: profilePreference.likedSampleIds,
          seedChoices: getSeedChoicesFromPreference(profilePreference),
          referencePhotoIds: uploadedPhotos.map((photo) => photo.id),
        });
      } else if (mode === "upload" && preferenceReferenceIds.length > 0) {
        await setReferencePhotoPreference(activeToken, activeSession.id, preferenceReferenceIds);
        setPreferenceSet(true);
      }
      const photosReady = await refreshPhotos(activeSession.id);
      if (!photosReady) {
        return;
      }
      setServiceRetouchMode(false);
      setServiceRetouchPhotos([]);
      setFlowStep("capture");
      setCountdown(3);
      setShootingRemainingSeconds(SHOOTING_SIMULATION_SECONDS);
      setCaptureState("countdown");
    } catch (nextError) {
      if (isSessionMissingError(nextError)) {
        clearStaleSession();
        setFlowStep("appointments");
        setError("当前场次已失效，请重新预约后再拍摄。");
        return;
      }
      setError(nextError instanceof Error ? nextError.message : "拍摄准备失败");
    } finally {
      setLoading(false);
    }
  };

  const uploadShootPhotos = async () => {
    const activeSession = await ensureSession();
    if (!activeSession) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const activeToken = readCustomerToken();
      if (!activeToken) {
        setAfterLoginAction("start");
        setLoginSheetOpen(true);
        return;
      }
      const result = await Taro.chooseImage({ count: 9, sourceType: ["album", "camera"] });
      for (const filePath of result.tempFilePaths ?? []) {
        await uploadIngressPhoto(activeToken, DEFAULT_STORE_ID, activeSession.id, filePath);
      }
      await refreshPhotos(activeSession.id);
      await refreshCustomerSessions(activeToken);
      void Taro.showToast({ title: "已收到照片", icon: "success" });
    } catch (nextError) {
      if (isSessionMissingError(nextError)) {
        clearStaleSession();
        setFlowStep("appointments");
        setError("当前场次已失效，请重新预约后再上传照片。");
        return;
      }
      setError(nextError instanceof Error ? nextError.message : "照片上传失败");
    } finally {
      setLoading(false);
    }
  };

  const togglePhoto = async (photo: SessionPhoto) => {
    if (!token) {
      return;
    }
    const updated = await selectPhoto(token, photo.id, !photo.selected);
    if (serviceRetouchMode) {
      setServiceRetouchPhotos((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } else {
      setPhotos((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    }
  };

  const toggleAllPhotos = async () => {
    if (!token || galleryPhotos.length === 0) {
      return;
    }
    const shouldSelectAll = selectedPhotos.length !== galleryPhotos.length;
    const updatedPhotos = await Promise.all(
      galleryPhotos
        .filter((photo) => photo.selected !== shouldSelectAll)
        .map((photo) => selectPhoto(token, photo.id, shouldSelectAll)),
    );
    const updatedMap = new Map(updatedPhotos.map((photo) => [photo.id, photo]));
    if (serviceRetouchMode) {
      setServiceRetouchPhotos((current) => current.map((photo) => updatedMap.get(photo.id) ?? photo));
    } else {
      setPhotos((current) => current.map((photo) => updatedMap.get(photo.id) ?? photo));
    }
  };

  const ensurePhotoAlbumPermission = async () => {
    try {
      await Taro.authorize({ scope: "scope.writePhotosAlbum" });
      return true;
    } catch {
      const modal = await Taro.showModal({
        title: "需要相册权限",
        content: "保存照片前需要授权访问相册。",
        confirmText: "去授权",
        cancelText: "取消",
      });
      if (!modal.confirm) {
        return false;
      }
      const settings = await Taro.openSetting();
      return !!settings.authSetting?.["scope.writePhotosAlbum"];
    }
  };

  const savePathsToAlbum = async (paths: string[]): Promise<boolean> => {
    if (paths.length === 0) {
      void Taro.showToast({ title: "请先选片", icon: "none" });
      return false;
    }
    const allowed = await ensurePhotoAlbumPermission();
    if (!allowed) {
      setError("未获得相册权限");
      return false;
    }
    setLoading(true);
    setError("");
    try {
      for (const path of paths) {
        const filePath = await materializeImageForAlbum(path);
        await Taro.saveImageToPhotosAlbum({ filePath });
      }
      void Taro.showToast({ title: `已保存 ${paths.length} 张`, icon: "success" });
      return true;
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "保存失败");
      return false;
    } finally {
      setLoading(false);
    }
  };

  const submitCurrentSession = async (): Promise<boolean> => {
    const activeToken = readCustomerToken();
    const activeSession = session ?? readCurrentSession();
    if (!activeToken || !activeSession) {
      return false;
    }
    if (isSessionCompleted(activeSession)) {
      return true;
    }
    if (completedSessionIdRef.current === activeSession.id) {
      return true;
    }
    try {
      completedSessionIdRef.current = activeSession.id;
      const nextSession = await completeSession(activeToken, activeSession.id);
      const storedSession = readCurrentSession();
      if (storedSession?.id === activeSession.id) {
        clearCurrentSession();
      }
      setSession(nextSession);
      const nextSessions = await listCustomerSessions(activeToken);
      setSessions(nextSessions);
      return true;
    } catch (nextError) {
      completedSessionIdRef.current = "";
      setError(nextError instanceof Error ? nextError.message : "场次状态提交失败");
      return false;
    }
  };

  const runSmartOptimize = async (): Promise<CompletedResult[]> => {
    if (loading) {
      return [];
    }
    const activeToken = await ensureToken();
    const activeSession = serviceRetouchMode ? session : await ensureSession();
    if (!activeToken || !activeSession || selectedPhotos.length === 0) {
      setError("请先选片");
      return [];
    }

    setLoading(true);
    setError("");
    try {
      const settledResults = await Promise.all(
        selectedPhotos.map(async (photo) => {
          try {
            const response = await smartOptimize(activeToken, photo.id);
            return {
              ok: true as const,
              result: {
                photoId: photo.id,
                filename: photo.filename,
                previewUrl: photo.previewUrl,
                resultImageUrl: response.image,
                mode: "beauty" as EditMode,
              },
            };
          } catch (error) {
            return { ok: false as const, error };
          }
        }),
      );
      const nextResults = settledResults.flatMap((item) => (item.ok ? [item.result] : []));
      if (nextResults.length === 0) {
        const firstError = settledResults.find((item) => !item.ok)?.error;
        throw firstError instanceof Error ? firstError : new Error("精修失败");
      }
      commitCompletedResults(nextResults);
      const failedCount = selectedPhotos.length - nextResults.length;
      if (failedCount > 0) {
        setError(`${failedCount} 张处理失败，已保留 ${nextResults.length} 张成功结果。`);
      }
      return nextResults;
    } catch (nextError) {
      if (isSessionMissingError(nextError)) {
        clearStaleSession();
        setFlowStep("appointments");
        setError("当前场次已失效，请重新预约后再精修。");
        return [];
      }
      setError(nextError instanceof Error ? nextError.message : "精修失败");
      if (serviceRetouchMode) {
        setServiceRetouchPhotos([]);
      }
      return [];
    } finally {
      setLoading(false);
    }
  };

  const exportSmartResults = async () => {
    if (loading) {
      return;
    }
    const exportResults = hasCompleteSmartResults ? selectedSmartResults : await runSmartOptimize();
    if (exportResults.length === 0) {
      return;
    }
    commitCompletedResults(exportResults);
    if (profileToolMode) {
      setServiceRetouchPhotos([]);
    }
    if (!profileToolMode) {
      const submitted = await submitCurrentSession();
      if (!submitted) {
        return;
      }
    }
    setFlowStep("complete");
    void Taro.showToast({ title: `已生成 ${exportResults.length} 张`, icon: "success" });
  };

  const runEdit = async () => {
    if (loading) {
      return;
    }
    if (editChannel === "smart") {
      await runSmartOptimize();
      return;
    }

    const activeToken = await ensureToken();
    const activeSession = serviceRetouchMode ? session : await ensureSession();
    if (!activeToken || !activeSession || selectedPhotos.length === 0) {
      setError("请先选片");
      return;
    }

    const runId = editRunIdRef.current + 1;
    editRunIdRef.current = runId;
    setLoading(true);
    setError("");
    try {
      let nextResults: CompletedResult[] = [];
      if (editChannel === "retouch") {
        const settledResults = await Promise.all(
          selectedPhotos.map(async (photo) => {
            try {
              const response = await processTargetedRetouchV2(activeToken, photo.id, retouchParams);
              return {
                ok: true as const,
                result: {
                  photoId: photo.id,
                  filename: photo.filename,
                  previewUrl: photo.previewUrl,
                  resultImageUrl: response.image,
                  mode: "retouch" as EditMode,
                },
              };
            } catch (error) {
              return { ok: false as const, error };
            }
          }),
        );
        nextResults = settledResults.flatMap((item) => (item.ok ? [item.result] : []));
        if (nextResults.length === 0) {
          const firstError = settledResults.find((item) => !item.ok)?.error;
          throw firstError instanceof Error ? firstError : new Error("精修失败");
        }
      } else {
        try {
          await initializeJesrRecipe(activeToken, activeSession.id, selectedPhotos[0].id);
        } catch (nextError) {
          const message = nextError instanceof Error ? nextError.message : "";
          if (!message.includes("JESR recipe already initialized")) {
            throw nextError;
          }
        }
        await selectCreativeStyle(activeToken, activeSession.id, creativeStyle);
        const settledResults = await Promise.all(
          selectedPhotos.map(async (photo) => {
            try {
              const job = await renderWithRecipe(activeToken, activeSession.id, photo.id, "auto");
              const completed = await pollEditJob(activeToken, job.id);
              if (editRunIdRef.current !== runId) {
                throw new Error("任务已取消");
              }
              if (!completed.resultImageUrl) {
                throw new Error("创意化结果缺失，请稍后重试");
              }
              return {
                ok: true as const,
                result: {
                  photoId: photo.id,
                  filename: photo.filename,
                  previewUrl: photo.previewUrl,
                  resultImageUrl: completed.resultImageUrl,
                  mode: "filter" as EditMode,
                },
              };
            } catch (error) {
              return { ok: false as const, error };
            }
          }),
        );
        if (settledResults.some((item) => !item.ok && item.error instanceof Error && item.error.message === "任务已取消")) {
          throw new Error("任务已取消");
        }
        nextResults = settledResults.flatMap((item) => (item.ok ? [item.result] : []));
        if (nextResults.length === 0) {
          const firstError = settledResults.find((item) => !item.ok)?.error;
          throw firstError instanceof Error ? firstError : new Error("精修失败");
        }
      }
      commitCompletedResults(nextResults);
      if (profileToolMode) {
        setServiceRetouchPhotos([]);
      }
      const failedCount = selectedPhotos.length - nextResults.length;
      if (failedCount > 0) {
        setError(`${failedCount} 张处理失败，已保留 ${nextResults.length} 张成功结果。`);
      }
      if (!profileToolMode) {
        const submitted = await submitCurrentSession();
        if (!submitted) {
          return;
        }
      }
      setFlowStep("complete");
    } catch (nextError) {
      if (nextError instanceof Error && nextError.message === "任务已取消") {
        return;
      }
      if (isSessionMissingError(nextError)) {
        clearStaleSession();
        setFlowStep("appointments");
        setError("当前场次已失效，请重新预约后再精修。");
        return;
      }
      if (serviceRetouchMode) {
        setServiceRetouchPhotos([]);
      }
      setError(nextError instanceof Error ? nextError.message : "精修失败");
    } finally {
      if (editRunIdRef.current === runId) {
        setLoading(false);
      }
    }
  };

  const openStartSheet = async () => {
    setError("");
    setProfileReturnMode(false);
    const activeSession = await ensureStartableSession("start");
    if (!activeSession) {
      return;
    }
    setServiceRetouchMode(false);
    setServiceRetouchPhotos([]);
    const photosReady = await refreshPhotos(activeSession.id);
    if (!photosReady) {
      setFlowStep("appointments");
      void Taro.showModal({
        title: "场次已失效",
        content: "当前缓存的场次已不存在，请重新预约后再开始拍摄。",
        confirmText: "去预约",
        showCancel: false,
      });
      return;
    }
    setEntrySheetOpen(true);
  };

  const openAppointments = async () => {
    setError("");
    setProfileReturnMode(false);
    const activeToken = readCustomerToken();
    if (!activeToken) {
      setAfterLoginAction("appointment");
      setLoginSheetOpen(true);
      return;
    }
    setToken(activeToken);
    await refreshCustomerSessions(activeToken);
    setFlowStep("appointments");
  };

  const openProfile = async () => {
    const activeToken = readCustomerToken();
    const storedProfile = readCustomerProfile();
    if (storedProfile?.phone) {
      setPhone(storedProfile.phone);
    }
    if (!activeToken) {
      setAfterLoginAction("profile");
      setLoginSheetOpen(true);
      return;
    }
    setToken(activeToken);
    const nextSessions = await refreshCustomerSessions(activeToken);
    const targetSession = readCurrentSession() ?? selectPreferredSession(nextSessions);
    if (targetSession) {
      await refreshPhotos(targetSession.id);
    }
    setFlowStep("profile");
  };

  const confirmLogin = async (phoneOverride?: string) => {
    const activeToken = await handleLogin(phoneOverride);
    if (!activeToken) {
      return;
    }
    setLoginSheetOpen(false);
    if (afterLoginAction === "profile") {
      await refreshCustomerSessions(activeToken);
      setFlowStep("profile");
      return;
    }
    if (afterLoginAction === "appointment") {
      await refreshCustomerSessions(activeToken);
      setFlowStep("appointments");
      return;
    }
    if (afterLoginAction === "entry") {
      await refreshCustomerSessions(activeToken);
      setFlowStep("entry");
      return;
    }
    const activeSession = readCurrentSession();
    if (!activeSession) {
      setFlowStep("appointments");
      void Taro.showModal({
        title: "请先预约",
        content: "你还没有预约场次。预约成功后即可开始拍摄。",
        confirmText: "去预约",
        showCancel: false,
      });
      return;
    }
    setSession(activeSession);
    const photosReady = await refreshPhotos(activeSession.id);
    if (!photosReady) {
      setFlowStep("appointments");
      void Taro.showModal({
        title: "场次已失效",
        content: "当前缓存的场次已不存在，请重新预约后再开始拍摄。",
        confirmText: "去预约",
        showCancel: false,
      });
      return;
    }
    setEntrySheetOpen(true);
  };

  const requestWechatPhoneLogin = async () => {
    const mockPhone = createMockPhoneNumber();
    setPhone(mockPhone);
    await confirmLogin(mockPhone);
  };

  const openEditChannel = (channel: EditChannel) => {
    if (selectedPhotos.length === 0) {
      setFlowStep("selection");
      void Taro.showToast({ title: "请先选择照片", icon: "none" });
      return;
    }
    setEditChannel(channel);
    setEditView(channel);
    if (channel === "smart" && !hasCompleteSmartResults && !serviceRetouchMode) {
      void runSmartOptimize();
    }
    if (channel === "retouch") {
      setRetouchPreviewMode("retouched");
    }
  };

  const resetRetouchParams = () => {
    setRetouchParams({ ...DEFAULT_RETOUCH_PARAMS });
    setRetouchPreviewMode("original");
  };

  const applySmartRetouchParams = () => {
    setRetouchParams({ ...DEFAULT_RETOUCH_PARAMS, ...SMART_RETOUCH_PARAMS });
    setRetouchPreviewMode("retouched");
  };

  const openStylePreference = () => {
    setError("");
    if (!readCustomerToken()) {
      setAfterLoginAction("profile");
      setLoginSheetOpen(true);
      return;
    }
    setFlowStep("stylePreference");
  };

  const handleStyleProfileConfirm = async (choices: EntrySeedChoice[]) => {
    const likedSampleIds = choices.filter((choice) => choice.liked).map((choice) => choice.seed_id);
    if (choices.length === 0) {
      void Taro.showToast({ title: "请至少判断一张", icon: "none" });
      return;
    }
    const nextPreference: EntryPreference = {
      mode: "curated",
      uploadedFiles: referenceFiles,
      likedSampleIds,
      seedChoices: choices,
      referencePhotoIds: readEntryPreference()?.referencePhotoIds,
    };
    writeEntryPreference({
      ...nextPreference,
      uploadedFiles: referenceFiles,
    });
    const activeToken = readCustomerToken();
    const activeSession = readCurrentSession();
    if (activeToken && activeSession) {
      setLoading(true);
      setError("");
      try {
        await setSeedGalleryPreference(activeToken, activeSession.id, choices);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "风格爱好同步失败");
        setLoading(false);
        return;
      } finally {
        setLoading(false);
      }
    }
    setPreferenceSet(true);
    void Taro.showToast({ title: "已保存风格爱好", icon: "success" });
    setFlowStep("appointments");
    const reminderSession = readCurrentSession() ?? session;
    if (!reminderSession) {
      void Taro.showModal({
        title: "风格爱好已保存",
        content: "预约成功后，可以在我的预约里开始拍摄。",
        confirmText: "去预约",
        showCancel: false,
      });
      return;
    }
    const reminderCanStart = canStartSession(reminderSession);
    void Taro.showModal({
      title: "到店拍摄提醒",
      content: `${formatSessionStartHint(reminderSession)}。到店后可以在“我的预约”点击开始拍摄。`,
      confirmText: reminderCanStart ? "开始拍摄" : "知道了",
      cancelText: "稍后",
      showCancel: reminderCanStart,
    }).then((result) => {
      if (result.confirm && reminderCanStart) {
        void openStartSheet();
      }
    });
  };

  const openOriginalPhotos = async () => {
    setError("");
    setProfileReturnMode(true);
    setServiceRetouchMode(false);
    setServiceRetouchPhotos([]);
    const activeToken = await ensureToken();
    if (!activeToken) {
      return;
    }

    const nextSessions = sessions.length > 0 ? sessions : await refreshCustomerSessions(activeToken);
    const targetSession = session ?? readCurrentSession() ?? selectPreferredSession(nextSessions);
    if (!targetSession) {
      setFlowStep("appointments");
      void Taro.showToast({ title: "请先预约场次", icon: "none" });
      return;
    }

    setSession(targetSession);
    writeCurrentSession(targetSession);
    const photosReady = await refreshPhotos(targetSession.id);
    if (!photosReady) {
      return;
    }
    const nextPhotos = await listSessionPhotos(activeToken, targetSession.id);
    setPhotos(nextPhotos);
    if (nextPhotos.length === 0) {
      setFlowStep("selection");
      void Taro.showToast({ title: "当前原图相册为空，可先上传", icon: "none" });
      return;
    }
    setFlowStep("selection");
  };

  const openServiceRetouchUpload = async () => {
    setProfileReturnMode(true);
    const activeToken = await ensureToken();
    if (!activeToken) {
      return;
    }
    const nextSessions = sessions.length > 0 ? sessions : await refreshCustomerSessions(activeToken);
    const targetSession = selectServiceRetouchSession(session ?? readCurrentSession(), nextSessions);
    if (!targetSession) {
      setFlowStep("appointments");
      void Taro.showToast({ title: "请先预约一次场次", icon: "none" });
      return;
    }

    setLoading(true);
    setError("");
    try {
      const result = await Taro.chooseImage({ count: 1, sourceType: ["album", "camera"] });
      const filePath = result.tempFilePaths?.[0];
      if (!filePath) {
        return;
      }
      const uploaded = await uploadIngressPhoto(activeToken, DEFAULT_STORE_ID, targetSession.id, filePath, true);
      const selected = await selectPhoto(activeToken, uploaded.id, true);
      setSession(targetSession);
      setServiceRetouchPhotos([{ ...selected, selected: true }]);
      setServiceRetouchMode(true);
      setEditView("channels");
      setFlowStep("edit");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "上传精修照片失败");
    } finally {
      setLoading(false);
    }
  };

  const openBeautyRetouch = () => {
    setError("");
    setProfileReturnMode(true);
    if (sessions.length > 1) {
      void openServiceRetouchUpload();
      return;
    }
    const realSelectedPhotos = getSelectedPhotos(photos);
    if (photos.length === 0) {
      void openServiceRetouchUpload();
      return;
    }
    setServiceRetouchMode(false);
    setServiceRetouchPhotos([]);
    if (realSelectedPhotos.length === 0) {
      void openServiceRetouchUpload();
      return;
    }
    setEditView("channels");
    setFlowStep("edit");
  };

  const exportOriginalPhotos = async () => {
    if (loading) {
      return;
    }
    if (selectedPhotos.length === 0) {
      void Taro.showToast({ title: "请先选片", icon: "none" });
      return;
    }
    const saved = await savePathsToAlbum(selectedPhotos.map((photo) => photo.originalImageUrl ?? photo.previewUrl));
    if (!saved) {
      return;
    }
    if (!profileToolMode) {
      await submitCurrentSession();
    }
    returnHomeAfterComplete();
  };

  const returnHomeAfterComplete = () => {
    const shouldReturnToProfile = profileReturnMode || serviceRetouchMode;
    if (!shouldReturnToProfile) {
      clearSessionScopedState();
    } else {
      writeCompletedResults([]);
    }
    completedSessionIdRef.current = "";
    if (!shouldReturnToProfile) {
      setSession(null);
      setPhotos([]);
    }
    setServiceRetouchMode(false);
    setServiceRetouchPhotos([]);
    setProfileReturnMode(false);
    commitCompletedResults([]);
    setReferenceFiles([]);
    setCaptureState("idle");
    setEditView("channels");
    setFlowStep(shouldReturnToProfile ? "profile" : "entry");
  };

  useDidShow(() => {
    const storedToken = readCustomerToken();
    const storedProfile = readCustomerProfile();
    const storedSession = readCurrentSession();
    const storedPreference = readEntryPreference();
    setToken(storedToken);
    if (storedProfile?.phone) {
      setPhone(storedProfile.phone);
    }
    setSession(storedSession);
    setReferenceFiles(storedPreference?.uploadedFiles ?? []);
    setPreferenceSet(hasLocalAestheticProfile(storedPreference));
    if (!storedToken && flowStep === "entry" && !loginSheetOpen) {
      setAfterLoginAction("entry");
      setLoginSheetOpen(true);
      return;
    }
    if (storedToken) {
      void refreshCustomerSessions(storedToken);
    }
    if (storedSession) {
      void refreshPhotos(storedSession.id);
    }
  });

  useEffect(() => {
    if (captureState !== "countdown") {
      return;
    }
    const timer = setInterval(() => {
      setCountdown((current) => {
          if (current <= 1) {
            clearInterval(timer);
            setShootingRemainingSeconds(SHOOTING_SIMULATION_SECONDS);
            setCaptureState("shooting");
            return 0;
          }
        return current - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
    }, [captureState]);

  useEffect(() => {
    if (flowStep !== "capture" || captureState !== "shooting") {
      return;
    }
    const timer = setInterval(() => {
      setShootingRemainingSeconds((current) => {
        if (current <= 1) {
          clearInterval(timer);
          setCaptureState("ended");
          return 0;
        }
        return current - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [captureState, flowStep]);

  useEffect(() => {
    if (flowStep !== "capture" || captureState !== "shooting" || !session?.id) {
      return;
    }
    const timer = setInterval(() => {
      void refreshPhotos(session.id);
    }, 3500);
    return () => clearInterval(timer);
  }, [captureState, flowStep, session?.id]);

  return (
    <View className="swipe-page" style={chromeVars as any}>
      {flowStep === "entry" ? (
        <View className="home-screen dot-pattern">
          <View className="home-hero">
            <Text className="brand-title">HelloBeauty</Text>
            <View className="brand-rule" />
            <Text className="brand-subtitle">你的AI摄影师</Text>
          </View>

            <Button className="start-button breathe" loading={loading} onClick={() => void openStartSheet()}>
            开始拍摄
          </Button>
        </View>
      ) : null}

      {flowStep === "appointments" ? (
        <View className="page-shell">
          <View className="topbar">
            <Button className="nav-icon" onClick={() => setFlowStep("entry")}>←</Button>
            <Text className="topbar-title">我的预约</Text>
            <View className="nav-space" />
          </View>

          {session ? (
            <View className="appointment-card appointment-card-active">
              <Text className="appointment-number">#{normalizedCode}</Text>
              <Text className="meta-line">▦ {session.sessionName}</Text>
              <Text className="meta-line">◷ {formatDateTime(session.startTime)} · {session.durationMinutes}分钟 · 1号拍摄间</Text>
              <Text className="meta-line">提醒 {formatDateTime(session.preShootReminder?.dueAt)} · 风格爱好</Text>
              <View className="appointment-status-row">
                <Text className={activeSessionCompleted ? "status-chip status-chip-done" : "status-chip"}>
                  {sessionStatusLabel(session)}
                </Text>
                <Text className="countdown-label">{activeSessionHint}</Text>
              </View>
            </View>
          ) : (
            <View className="appointment-card">
              <Text className="appointment-number">暂无预约</Text>
              <Text className="meta-line">预约成功后才会创建拍摄场次。</Text>
              <Text className="meta-line">登录用户也可以先浏览“我的”等其他页面，不会强制预约。</Text>
            </View>
          )}

          {session && !appointmentDraftOpen ? (
            <Button
              className="sharp-secondary appointment-secondary"
              onClick={() => {
                setAppointmentStartInput(resetAppointmentStartInput());
                setAppointmentDraftOpen(true);
              }}
            >
              新增预约
            </Button>
          ) : null}

          {showAppointmentForm ? (
            <View className="appointment-time-panel">
              <Text className="prep-title">预约开始时间</Text>
              <View className="appointment-time-row">
                <Picker
                  mode="date"
                  value={appointmentStartInput.date}
                  start={dateInputValue(new Date())}
                  onChange={(event) =>
                    setAppointmentStartInput((current) => ({
                      ...current,
                      date: String(event.detail.value),
                    }))
                  }
                >
                  <View className="appointment-picker-button">{appointmentStartInput.date}</View>
                </Picker>
                <Picker
                  mode="time"
                  value={appointmentStartInput.time}
                  onChange={(event) =>
                    setAppointmentStartInput((current) => ({
                      ...current,
                      time: String(event.detail.value),
                    }))
                  }
                >
                  <View className="appointment-picker-button">{appointmentStartInput.time}</View>
                </Picker>
              </View>
              <Text className="body-copy">系统会在 {formatDateTime(selectedReminderStart)} 调度风格爱好提醒。</Text>
            </View>
          ) : null}

          <Button
            className="block-primary appointment-main-action"
            loading={loading}
            disabled={loading || (!!session && !activeSessionCanStart && !appointmentDraftOpen)}
            onClick={() => (showAppointmentForm ? void createAppointment() : void openStartSheet())}
          >
            {showAppointmentForm ? "预约场次" : activeSessionCompleted ? "已完成" : activeSessionCanStart ? "开始拍摄" : "未到时间"}
          </Button>

          <View className="prep-card" onClick={openStylePreference}>
            <View>
              <Text className="prep-title">拍摄前准备</Text>
              <Text className="body-copy">建议开拍前{APPOINTMENT_LEAD_MINUTES}分钟完成风格爱好。</Text>
            </View>
            <Text className={preferenceSet ? "prep-status prep-status-ready" : "prep-status"}>
              {preferenceSet ? "已完成" : "去填写"}
            </Text>
          </View>

          <Text className="section-label">历史记录</Text>
          {sessions.length > 0 ? sessions.map((item) => (
            <View
              className="history-row"
              key={item.id}
              onClick={() => {
                setSession(item);
                if (!isSessionCompleted(item)) {
                  writeCurrentSession(item);
                }
                void refreshPhotos(item.id);
              }}
            >
              <View>
                <Text className="history-title">#{displaySessionCode(item, sessionCode)} · {formatDateTime(item.startTime)}</Text>
                <Text className="history-meta">{item.durationMinutes}分钟 · {formatSessionStartHint(item)}</Text>
              </View>
              <Text className={isSessionCompleted(item) ? "history-status history-status-done" : "history-status"}>
                {sessionStatusLabel(item)}
              </Text>
            </View>
          )) : (
            <Text className="body-copy">还没有历史场次。</Text>
          )}
        </View>
      ) : null}

      {flowStep === "stylePreference" ? (
        <View className="page-shell dot-pattern">
          <View className="topbar">
            <Button className="nav-icon" onClick={() => setFlowStep("profile")}>←</Button>
            <Text className="topbar-title">风格爱好</Text>
            <View className="nav-space" />
          </View>

          <View className="section-heading style-pref-heading">
            <Text className="heading-title">风格爱好</Text>
            <Text className="body-copy">风格爱好会记录你喜欢的人像方向，拍摄和精修时会优先参考。</Text>
          </View>

          <View className="mode-card" onClick={() => setFlowStep("upload")}>
            <View>
              <Text className="mode-title">有心仪照片</Text>
              <Text className="body-copy">上传想打卡照片；开始拍摄前会与风格爱好合并使用。</Text>
            </View>
            <Text className="mode-index">01</Text>
          </View>
          <View
            className="mode-card mode-card-dark"
            onClick={() => {
              if (hasLocalAestheticProfile(readEntryPreference())) {
                void Taro.showToast({ title: "风格爱好已完成", icon: "success" });
                return;
              }
              void requestAestheticProfile();
            }}
          >
            <View>
              <Text className="mode-title">暂时没有</Text>
              <Text className="mode-copy-inverse">从25张风格照片中左右滑动，记录你的风格爱好。</Text>
            </View>
            <Text className="mode-index">02</Text>
          </View>
        </View>
      ) : null}

      {flowStep === "styleProfileGallery" ? (
        <View className="page-shell dot-pattern">
          <View className="topbar">
            <Button className="nav-icon" onClick={() => setFlowStep("stylePreference")}>←</Button>
            <Text className="topbar-title">风格爱好</Text>
            <View className="nav-space" />
          </View>

          <View className="section-heading style-pref-heading">
            <Text className="heading-title">选择你的风格爱好</Text>
          </View>

          <View className="seed-gallery-panel">
            <SeedGallery onConfirm={(choices) => void handleStyleProfileConfirm(choices)} loading={loading} />
          </View>
        </View>
      ) : null}

      {flowStep === "upload" ? (
        <View className="page-shell dot-pattern">
          <View className="topbar">
            <Button className="nav-icon" onClick={() => setFlowStep("stylePreference")}>←</Button>
            <Text className="topbar-title">上传心仪照片</Text>
            <View className="nav-space" />
          </View>

          <View className="upload-center">
            <View className="upload-box" onClick={() => void chooseReferencePhotos()}>
              {referenceFiles[0] ? (
                <Image className="upload-preview" src={referenceFiles[0]} mode="aspectFill" />
              ) : hasSyncedReferencePhotos ? (
                <View className="upload-empty">
                  <Text className="upload-icon">✓</Text>
                  <Text className="upload-title">心仪照片已同步</Text>
                  <Text className="upload-caption">可直接开始拍摄</Text>
                </View>
              ) : (
                <View className="upload-empty">
                  <Text className="upload-icon">▧</Text>
                  <Text className="upload-title">点击上传心仪照片</Text>
                  <Text className="upload-caption">让AI学习你喜欢的风格</Text>
                </View>
              )}
            </View>

            <View className="upload-actions">
              <Button className="pill-secondary" onClick={() => void chooseReferencePhotos(["camera"])}>拍照</Button>
              <Button className="sharp-secondary" onClick={() => void chooseReferencePhotos(["album"])}>相册</Button>
            </View>
          </View>

          {referenceFiles.length > 0 || hasSyncedReferencePhotos ? (
            <View className="recipe-card">
              <View className="recipe-accent" />
              <View>
                <Text className="recipe-title">风格爱好已准备</Text>
                <Text className="body-copy">
                  {referenceFiles.length > 0
                    ? `已选择 ${referenceFiles.length} 张心仪照片，开始拍摄前会同步到本场次。`
                    : `已同步 ${storedReferencePhotoIds.length} 张心仪照片，可直接进入拍摄。`}
                </Text>
              </View>
            </View>
          ) : null}

          <Button
            className="block-primary"
            loading={loading}
            disabled={referenceFiles.length === 0 && !hasSyncedReferencePhotos}
            onClick={() => void startFlow("upload")}
          >
            开始拍摄
          </Button>
        </View>
      ) : null}

      {flowStep === "capture" && captureState === "countdown" ? (
        <View className="pose-screen">
          <View className="pose-card">
            <Image className="pose-image" src={POSE_IMAGE} mode="aspectFill" />
            <Text className="pose-page">1/4</Text>
            <View className="pose-caption">
              <Text>侧身45° 手自然下垂</Text>
            </View>
            <Button className="pose-arrow pose-arrow-left">‹</Button>
            <Button className="pose-arrow pose-arrow-right">›</Button>
          </View>
          <Text className="pose-count">{countdown}</Text>
        </View>
      ) : null}

      {flowStep === "capture" && (captureState === "shooting" || captureState === "ended") ? (
        <View className="shoot-screen dot-pattern">
            <View className="shoot-status">
              <Text className="session-pill">#{normalizedCode}</Text>
              <Text className="shooting-text">{captureState === "ended" ? "拍摄已结束" : "正在拍摄中..."}</Text>
              <Text className="timer-text">{formatDuration(shootingRemainingSeconds)}</Text>
            </View>

          <View className="photo-stack-wrap">
            <View className="stack-card stack-card-back" />
            <View className="stack-card stack-card-mid" />
            <View className="live-photo-card">
              <Image className="live-photo" src={getPhotoSrc(latestPhoto)} mode="aspectFill" />
              <View className="photo-gradient">
                  <Text className="photo-meta">{latestPhoto ? "最新照片" : "等待照片接入"}</Text>
              </View>
            </View>
          </View>

          <View className="dot-row">
            {[0, 1, 2, 3, 4].map((index) => (
              <View
                key={index}
                className={
                    index === 2
                      ? "shot-dot shot-dot-active"
                      : index < Math.min(shootRecentPhotos.length, 2)
                        ? "shot-dot shot-dot-seen"
                        : "shot-dot"
                }
              />
            ))}
          </View>

          <View className="shoot-actions">
            <Button className="sharp-secondary" loading={loading} onClick={() => void uploadShootPhotos()}>
              手机补拍/上传
            </Button>
              <Button
                className="block-primary block-primary-inline"
                onClick={() => {
                  setCaptureState("ended");
                  setFlowStep("selection");
                }}
              >
                {captureState === "ended" ? "查看原图" : "结束拍摄"}
              </Button>
          </View>

          <View className="bottom-progress">
              <Text>剩余 {formatDuration(shootingRemainingSeconds)}</Text>
              <View className="progress-track">
                <View className="progress-fill" style={{ width: `${shootingProgressPercent}%` }} />
              </View>
          </View>
        </View>
      ) : null}

      {flowStep === "selection" ? (
          <View className="album-screen">
            <View className="topbar topbar-fixed">
            <Button className="nav-text" onClick={() => setFlowStep(profileToolMode ? "profile" : "capture")}>← 返回</Button>
              <Text className="topbar-title">{serviceRetouchMode ? "上传精修" : "选片"}</Text>
              <Button className="nav-text" onClick={() => void toggleAllPhotos()}>
                {selectedPhotos.length === galleryPhotos.length && galleryPhotos.length > 0 ? "取消全选" : "全选"}
              </Button>
          </View>

          {recentPhotos.length > 0 ? (
            <View className="album-grid">
              {recentPhotos.map((photo) => (
                <View className="album-item" key={photo.id} onClick={() => void togglePhoto(photo)}>
                  <Image className="album-image" src={getPhotoSrc(photo)} mode="aspectFill" />
                  <View className={photo.selected ? "checkmark checkmark-active" : "checkmark"}>
                    <Text>{photo.selected ? "✓" : ""}</Text>
                  </View>
                </View>
              ))}
            </View>
          ) : (
              <View className="empty-state">
                <Text className="empty-title">{serviceRetouchMode ? "还没有上传精修照片" : "当前场次还没有照片"}</Text>
                <Text className="body-copy">
                  {serviceRetouchMode ? "可临时上传照片做美颜精修，原图不会进入拍摄原图相册。" : "可以先用手机补拍上传，正式接入相机后会自动出现在这里。"}
                </Text>
                <Button className="sharp-secondary" loading={loading} onClick={() => void (serviceRetouchMode ? openServiceRetouchUpload() : uploadShootPhotos())}>
                  上传照片
                </Button>
            </View>
          )}

          <View className="album-action-bar">
            <Text className="selected-count">已选 {selectedPhotos.length} 张</Text>
            <View className="album-buttons">
                <Button
                  className="bar-button bar-button-dark"
                  loading={loading}
                  onClick={() => void exportOriginalPhotos()}
                  disabled={serviceRetouchMode}
                >
                  {serviceRetouchMode ? "不保存原图" : "原图导出"}
                </Button>
              <Button
                className="bar-button bar-button-light"
                onClick={() => {
                  if (selectedPhotos.length === 0) {
                    void Taro.showToast({ title: "请先选择照片", icon: "none" });
                    return;
                  }
                  setEditView("channels");
                  setFlowStep("edit");
                }}
              >
                美颜精修
              </Button>
            </View>
          </View>
        </View>
      ) : null}

      {flowStep === "edit" ? (
        <View className={editView === "retouch" ? "editor-screen" : "page-shell"}>
            {editView !== "retouch" ? (
              <View className="topbar">
                <Button
                  className="nav-icon"
                  onClick={() => {
                    if (editView !== "channels") {
                      setEditView("channels");
                      return;
                    }
                    setFlowStep(profileToolMode ? "profile" : "selection");
                  }}
                >
                  ←
                </Button>
              <Text className="topbar-title">{editView === "creative" ? "创意化风格" : "美颜精修"}</Text>
              <View className="nav-space" />
            </View>
          ) : null}

          {editView === "channels" ? (
            <View className="channel-page">
              <View className="section-heading">
                <Text className="heading-title">Select Channel</Text>
                <Text className="body-copy">选择一种精修方式开始处理。</Text>
              </View>

              <View className="channel-list">
                <View className="channel-card" onClick={() => openEditChannel("smart")}>
                  <Text className="channel-icon">✦</Text>
                  <View className="channel-copy">
                    <Text className="channel-title">一键智能优化</Text>
                    <Text className="body-copy">AI自适应，懒人福音</Text>
                  </View>
                  <Text className="arrow-text">→</Text>
                </View>
                <View className="channel-card" onClick={() => openEditChannel("retouch")}>
                  <Text className="channel-icon">⌘</Text>
                  <View className="channel-copy">
                    <Text className="channel-title">针对性精修</Text>
                    <Text className="body-copy">手动微调，指哪修哪</Text>
                  </View>
                  <Text className="arrow-text">→</Text>
                </View>
                <View className="channel-card" onClick={() => openEditChannel("creative")}>
                  <Text className="channel-icon">◐</Text>
                  <View className="channel-copy">
                    <Text className="channel-title">创意化风格</Text>
                    <Text className="body-copy">5大风格，原图直入</Text>
                  </View>
                  <Text className="arrow-text">→</Text>
                </View>
              </View>

              <Text className="footer-note">三个通道互相独立，均可直接导出</Text>
            </View>
          ) : null}

          {editView === "smart" ? (
            <View className="smart-screen">
              <View className="smart-preview-list">
                {smartPreviewItems.map((item) => (
                  <View className="export-photo-frame smart-result-card" key={item.id}>
                    <View className="export-photo-frame-spacer" />
                    <View className="export-photo-frame-inner">
                      <Image className="export-photo-frame-image" src={item.src} mode="aspectFill" />
                    </View>
                    <Text className="smart-result-label">{item.label}</Text>
                  </View>
                ))}
              </View>

              <View className="smart-actions">
                <Button className="sharp-secondary smart-secondary" onClick={() => setFlowStep("stylePreference")}>
                  调整爱好风格
                </Button>
                <Button
                  className="block-primary smart-primary"
                  loading={loading}
                  disabled={loading}
                  onClick={() => void exportSmartResults()}
                >
                  导出图片
                </Button>
              </View>
            </View>
          ) : null}

          {editView === "retouch" ? (
            <View className="retouch-editor">
              <View className="editor-topbar">
                <Button className="nav-icon" onClick={() => setEditView("channels")}>×</Button>
                <View className="editor-tabs">
                  {RETOUCH_VIEW_TABS.map((tab) => (
                    <Button
                      key={tab.key}
                      className={retouchPreviewMode === tab.key ? "editor-tab editor-tab-active" : "editor-tab"}
                      onClick={() => setRetouchPreviewMode(tab.key)}
                    >
                      {tab.label}
                    </Button>
                  ))}
                </View>
                <Button className="nav-icon" loading={loading} disabled={loading} onClick={() => void runEdit()}>□</Button>
              </View>

              <View className="editor-preview">
                {retouchPreviewMode === "compare" ? (
                  <View className="compare-preview">
                    <View className="compare-pane">
                      <Image className="editor-image" src={originalPreviewSrc} mode="aspectFit" />
                      <Text className="compare-label">原图</Text>
                    </View>
                    <View className="compare-pane">
                      <Image
                        className="editor-image"
                        src={retouchedPreviewSrc}
                        mode="aspectFit"
                        style={{ filter: retouchPreviewFilter }}
                      />
                      <Text className="compare-label">精修</Text>
                    </View>
                  </View>
                ) : (
                  <Image
                    className="editor-image"
                    src={retouchPreviewMode === "original" ? originalPreviewSrc : retouchedPreviewSrc}
                    mode="aspectFit"
                    style={retouchPreviewMode === "original" ? undefined : { filter: retouchPreviewFilter }}
                  />
                )}
              </View>

              <View className="retouch-tabs">
                {RETOUCH_TABS.map((tab) => (
                  <Button
                    key={tab}
                    className={retouchTab === tab ? "retouch-tab retouch-tab-active" : "retouch-tab"}
                    onClick={() => setRetouchTab(tab)}
                  >
                    {tab}
                  </Button>
                ))}
              </View>

              <View className="slider-panel">
                {RETOUCH_PRESETS.filter((preset) => preset.group === retouchTab).map((preset) => (
                  <View className="slider-row" key={preset.key}>
                    <Text className="slider-label">{preset.label}</Text>
                    <Slider
                      className="retouch-slider"
                      min={-50}
                      max={50}
                      step={1}
                      value={retouchParams[preset.key] ?? 0}
                      activeColor="#1C1C1C"
                      backgroundColor="rgba(28,28,28,0.14)"
                      blockColor="#FFFDFA"
                      blockSize={16}
                      onChange={(event) =>
                        setRetouchParams((current) => ({
                          ...current,
                          [preset.key]: event.detail.value,
                        }))
                      }
                    />
                    <Text className="slider-value">{retouchParams[preset.key] ?? 0}</Text>
                  </View>
                ))}
              </View>

              <View className="editor-footer">
                <Button className="footer-button" onClick={applySmartRetouchParams}>智能优化</Button>
                <Button className="footer-button footer-muted" onClick={resetRetouchParams}>还原</Button>
                <Button className="footer-button footer-dark" loading={loading} onClick={() => void runEdit()}>
                  导出
                </Button>
              </View>
            </View>
          ) : null}

          {editView === "creative" ? (
            <View className="creative-screen">
              <View className="warning-banner">
                <Text>!</Text>
                <Text>创意化风格仅支持使用原始照片，精修后的照片请先保存到相册后再上传。</Text>
              </View>

              <View className="style-list">
                {CREATIVE_STYLES.map((style) => (
                  <View
                    key={style.id}
                    className={creativeStyle === style.id ? "style-card style-card-active" : "style-card"}
                    onClick={() => setCreativeStyle(style.id)}
                  >
                    <Image className="style-image" src={style.image} mode="aspectFill" />
                    <View className="style-copy">
                      <Text className="style-name">{style.label}</Text>
                      <Text className="body-copy">{style.description}</Text>
                    </View>
                    <View className={creativeStyle === style.id ? "style-radio style-radio-active" : "style-radio"}>
                      <Text>{creativeStyle === style.id ? "✓" : ""}</Text>
                    </View>
                  </View>
                ))}
              </View>

              <View className="sticky-submit">
                <Button className="block-primary" loading={loading} onClick={() => void runEdit()}>
                  选择照片并生成
                </Button>
              </View>
            </View>
          ) : null}
        </View>
      ) : null}

      {flowStep === "complete" ? (
        <View className="page-shell result-screen">
          <View className="topbar">
            <Button className="nav-icon" onClick={() => (profileToolMode ? returnHomeAfterComplete() : setFlowStep("selection"))}>←</Button>
            <Text className="topbar-title">导出结果</Text>
            <View className="nav-space" />
          </View>

          <View className="result-summary">
            <Text className="heading-title">已生成 {results.length} 张</Text>
            <Text className="body-copy">当前通道：{editChannel === "creative" ? activeStyle.label : editChannel === "smart" ? "一键智能优化" : "针对性精修"}</Text>
            {results.length > 0 ? (
              <Text className="body-copy result-selected-copy">已选 {selectedExportResults.length} 张</Text>
            ) : null}
          </View>

          {results.length > 0 ? (
            <View className="result-list">
              {results.map((result, index) => {
                const selected = selectedResultIds.has(result.photoId);
                return (
                  <Button
                    className={
                      selected
                        ? "export-photo-frame result-card result-photo-card result-card-selected"
                        : "export-photo-frame result-card result-photo-card"
                    }
                    key={result.photoId}
                    ariaLabel={`第 ${index + 1} 张导出结果，${selected ? "已选中，点击取消选择" : "未选中，点击选择"}`}
                    onClick={() => toggleResultSelection(result.photoId)}
                  >
                    <View className={selected ? "export-check export-check-active" : "export-check"}>
                      <Text>{selected ? "✓" : ""}</Text>
                    </View>
                    <View className="export-photo-frame-spacer" />
                    <View className="export-photo-frame-inner">
                      <Image
                        className="export-photo-frame-image"
                        src={getLocalImageSrc(result.resultImageUrl, resultMap)}
                        mode="aspectFill"
                      />
                    </View>
                  </Button>
                );
              })}
            </View>
          ) : (
            <View className="empty-state">
              <Text className="empty-title">暂无导出结果</Text>
              <Text className="body-copy">完成选片后选择任意精修通道，即可在这里保存结果。</Text>
            </View>
          )}

          <Button
            className="block-primary"
            disabled={selectedExportResults.length === 0 || loading}
            loading={loading}
            onClick={() => void savePathsToAlbum(selectedExportResults.map((result) => result.resultImageUrl))}
          >
            {selectedExportResults.length === 0 ? "请选择图片" : `保存选中（${selectedExportResults.length}）`}
          </Button>
          <Button className="sharp-secondary" onClick={returnHomeAfterComplete}>
            {profileToolMode ? "回到我的" : "回到首页"}
          </Button>
        </View>
      ) : null}

      {flowStep === "profile" ? (
        <View className="page-shell">
          <View className="topbar">
            <Button className="nav-icon" onClick={() => setFlowStep("entry")}>←</Button>
            <Text className="topbar-title">我的</Text>
            <View className="nav-space" />
          </View>

            <View className="profile-card">
              <View className="profile-avatar">
                <Text>{token ? "我" : "人"}</Text>
              </View>
              <Text className="profile-name">{token ? maskPhone(phone) : "未登录"}</Text>
              <Text className="body-copy">当前场次 {displaySessionName} · 共 {sessions.length} 次</Text>
            </View>

          <View className="profile-list">
            <View className="profile-action-button" onClick={openStylePreference}>
              <Text>风格爱好</Text>
              <Text>{preferenceSet ? "已生成" : "未生成"}</Text>
            </View>
              <View className="profile-action-button" onClick={() => void openAppointments()}>
                <Text>我的场次</Text>
                <Text>{sessions.length > 0 ? `${sessions.length} 次` : "暂无"}</Text>
            </View>
            <View className="profile-action-button" onClick={() => void openOriginalPhotos()}>
              <Text>拍摄原图</Text>
              <Text>{photos.length} 张</Text>
            </View>
              <View className="profile-action-button" onClick={openBeautyRetouch}>
                <Text>美颜精修</Text>
                <Text>{selectedPhotos.length > 0 ? `${selectedPhotos.length} 张` : sessions.length > 1 ? "可上传" : "待选片"}</Text>
              </View>
          </View>
        </View>
      ) : null}

      {error ? (
        <View className="error-toast">
          <Text>{error}</Text>
        </View>
      ) : null}

        {showDock ? (
          <View className="bottom-dock">
            <View
              className={flowStep === "appointments" ? "dock-side dock-side-active" : "dock-side"}
              onClick={() => void openAppointments()}
            >
              <Text className="dock-icon">◷</Text>
              <Text className="dock-label">预约</Text>
            </View>
            <View className="dock-main" onClick={() => void openStartSheet()}>
              <Text>＋</Text>
            </View>
            <View
              className={flowStep === "profile" ? "dock-side dock-side-active" : "dock-side"}
              onClick={() => void openProfile()}
            >
            <View className="dock-profile-icon" />
            <Text className="dock-label">我的</Text>
          </View>
        </View>
      ) : null}

      {entrySheetOpen ? (
        <View className="sheet-overlay">
          <View className="bottom-sheet mode-sheet">
            <View className="sheet-handle" />
            <Text className="sheet-title">选择拍摄入口</Text>
            <View className="mode-card" onClick={() => {
              setEntrySheetOpen(false);
              setFlowStep("upload");
            }}>
              <View>
                <Text className="mode-title">有心仪照片</Text>
                <Text className="body-copy">上传打卡照片，并与风格爱好一起使用。</Text>
              </View>
              <Text className="mode-index">01</Text>
            </View>
            <View className="mode-card mode-card-dark" onClick={() => {
              setEntrySheetOpen(false);
              void startFlow("none");
            }}>
              <View>
                <Text className="mode-title">暂时没有</Text>
                <Text className="mode-copy-inverse">使用已预约场次，拍完后选片和精修。</Text>
              </View>
              <Text className="mode-index">02</Text>
            </View>
            <Button className="sheet-close" onClick={() => setEntrySheetOpen(false)}>取消</Button>
          </View>
        </View>
      ) : null}

      {loginSheetOpen ? (
        <View className="sheet-overlay">
          <View className="bottom-sheet login-sheet">
            <View className="sheet-handle" />
            <View className="login-heading">
              <Text className="sheet-title">欢迎</Text>
              <Text className="sheet-subtitle">使用手机号或微信授权登录</Text>
            </View>

            <View className="login-form">
              <View className="line-input">
                <Text className="line-input-icon">▯</Text>
                <Input
                  type="number"
                  value={phone}
                  onInput={(event) => setPhone(normalizePhoneInput(event.detail.value))}
                  placeholder="请输入手机号"
                />
              </View>
            </View>

            <View className="login-actions">
              <Button className="wechat-auth" loading={loading} onClick={() => void requestWechatPhoneLogin()}>
                微信手机号一键授权
              </Button>

              <Button className="block-primary sheet-primary" loading={loading} onClick={() => void confirmLogin()}>
                确认登录
              </Button>
            </View>
            <Text className="terms-text">登录即表示同意《用户协议》和《隐私政策》</Text>
            <Button className="sheet-close" onClick={() => setLoginSheetOpen(false)}>取消</Button>
          </View>
        </View>
      ) : null}
    </View>
  );
}
