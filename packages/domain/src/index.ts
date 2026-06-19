export const ACTOR_KINDS = ["customer", "staff"] as const;
export type ActorKind = (typeof ACTOR_KINDS)[number];

export const SESSION_STATUSES = [
  "CREATED",
  "SHOOTING",
  "WAITING_SELECTION",
  "EDITING",
  "COMPLETED",
  "EXPIRED",
] as const;
export type SessionStatus = (typeof SESSION_STATUSES)[number];

export const EDIT_MODES = ["beauty", "retouch", "filter", "enhance"] as const;
export type EditMode = (typeof EDIT_MODES)[number];

export const UPLOAD_SOURCES = ["iphone", "ftp"] as const;
export type UploadSource = (typeof UPLOAD_SOURCES)[number];

export const PHOTO_ASSET_VARIANTS = ["original", "thumbnail", "album"] as const;
export type PhotoAssetVariant = (typeof PHOTO_ASSET_VARIANTS)[number];

export const RESULT_ASSET_VARIANTS = ["result"] as const;
export type ResultAssetVariant = (typeof RESULT_ASSET_VARIANTS)[number];

export const EDIT_JOB_STATUSES = ["queued", "running", "completed", "failed"] as const;
export type EditJobStatus = (typeof EDIT_JOB_STATUSES)[number];

export const DEFAULT_STORE_ID = "default-store";
export const DEFAULT_SESSION_DURATION_MINUTES = 12;
export const DEFAULT_SIGNED_ASSET_TTL_SECONDS = 900;
export const DEFAULT_STYLE_NAME = "清新日系";

export interface CustomerUser {
  id: string;
  phone: string;
  nickname: string;
  wechatOpenId?: string;
  createdAt?: string;
}

export interface StaffUser {
  id: string;
  storeId: string;
  username: string;
  role: string;
  createdAt?: string;
}

export interface ShootSession {
  id: string;
  storeId: string;
  phone: string;
  sessionName: string;
  status: SessionStatus;
  startTime: string;
  endTime: string;
  durationMinutes: number;
  photoCount: number;
  selectedCount: number;
  completedJobCount: number;
  printCount: number;
  completedAt?: string;
  preShootReminder?: SessionReminder;
}

export interface SessionReminder {
  id: string;
  sessionId: string;
  kind: "pre_shoot_aesthetic_profile";
  title: string;
  message: string;
  dueAt: string;
  status: "SCHEDULED" | "DUE" | "SENT" | "CANCELLED";
  subscriptionAccepted: boolean;
  subscriptionStatus: string;
  templateId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface EditJob {
  id: string;
  photoId?: string;
  sessionId?: string;
  mode: EditMode;
  styleName: string | null;
  status: EditJobStatus;
  statusMessage: string;
  resultImageUrl: string | null;
  resultAssetUrl?: string | null;
  createdAt?: string;
  finishedAt?: string | null;
}

export interface PhotoAsset {
  id: string;
  sessionId?: string;
  filename: string;
  source: UploadSource;
  selected: boolean;
  capturedAt: string;
  previewUrl: string;
  originalImageUrl?: string;
  thumbnailUrl?: string;
  albumImageUrl?: string;
  latestJob: EditJob | null;
}

export interface PrintRecord {
  id: string;
  sessionId: string;
  photoId: string;
  staffUserId: string;
  printedAt: string;
}

export interface StaffSessionDetail {
  session: ShootSession;
  photos: PhotoAsset[];
  printRecords: PrintRecord[];
}

export interface CustomerAuthResult {
  token: string;
  user: CustomerUser;
}

export interface StaffAuthResult {
  token: string;
  staff: StaffUser;
}

export interface CompletedResult {
  photoId: string;
  filename: string;
  previewUrl: string;
  resultImageUrl: string;
  mode: EditMode;
}

export * from "./editorial-content";
export * from "./jesr-content";
