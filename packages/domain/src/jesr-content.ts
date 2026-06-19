export const CREATIVE_STYLE_PRESET_IDS = [
  "fresh_japanese",
  "retro_hongkong",
  "clear_korean",
  "lazy_french",
  "american_hotgirl",
] as const;
export type CreativeStylePresetId = (typeof CREATIVE_STYLE_PRESET_IDS)[number];

export const BASE_STYLE_SOURCES = ["reference_photo", "seed_gallery"] as const;
export type BaseStyleSource = (typeof BASE_STYLE_SOURCES)[number];

export const JESR_AESTHETIC_PROFILE_SOURCES = [
  "seed_gallery",
  "reference_photos",
  "questionnaire",
  "hybrid",
  "seed_selection",
  "reference_photo",
  "preference",
  "preference_profile",
] as const;
export type JESRAestheticProfileSource = (typeof JESR_AESTHETIC_PROFILE_SOURCES)[number];

export const JESR_AESTHETIC_PROFILE_STATUSES = [
  "not_initialized",
  "ready",
  "defaulted",
  "invalid",
] as const;
export type JESRAestheticProfileStatus = (typeof JESR_AESTHETIC_PROFILE_STATUSES)[number];

export const PAIN_TAGS = [
  "identity_not_preserved",
  "texture_too_fake",
  "style_or_lighting_mismatch",
] as const;
export type PainTag = (typeof PAIN_TAGS)[number];

export interface BaseStyleProfile {
  light_tendency: number;
  warmth: number;
  contrast: number;
  texture_tendency: number;
  makeup_intensity: number;
  facial_detail_preference: number;
}

export interface JESRAestheticProfileVector extends BaseStyleProfile {
  style_strength: number;
  identity_tolerance: number;
}

export interface BaseStyleSeed {
  id: string;
  label: string;
  anchor_profile: BaseStyleProfile;
  anchor_recipe?: Record<string, unknown>;
}

export interface SeedChoice {
  seed_id: string;
  liked: boolean;
}

export interface JESRSeedChoice extends SeedChoice {
  style_id?: CreativeStylePresetId | null;
  profile?: JESRAestheticProfileVector;
}

export interface JESRAestheticConstraints {
  negative_rules: string[];
  identity_preservation_priority: "low" | "medium" | "high";
  allow_face_shape_change: boolean;
  allow_eye_enlarge: boolean;
  allow_heavy_smoothing: boolean;
}

export interface JESRAestheticProfile {
  version: "jesr_aesthetic_profile.v1";
  profile_id: string;
  profile_status: JESRAestheticProfileStatus;
  source: Exclude<JESRAestheticProfileSource, "seed_selection" | "reference_photo" | "preference" | "preference_profile">;
  profile_revision: number;
  profile_vector: JESRAestheticProfileVector;
  style_preferences: {
    preferred_style_ids: CreativeStylePresetId[];
    rejected_style_ids: CreativeStylePresetId[];
    atmosphere_tags: string[];
    color_tags: string[];
    angle_tags: string[];
  };
  constraints: JESRAestheticConstraints;
  evidence: {
    seed_choices: JESRSeedChoice[];
    reference_photo_ids: string[];
    questionnaire_answers: Record<string, unknown>;
    unresolved_seed_ids: string[];
  };
  metadata?: {
    clamped_fields?: string[];
    [key: string]: unknown;
  };
  created_at: string;
  updated_at: string;
}

export interface JESRProfileRecipeMetadata {
  profile_recipe_version: "jesr_profile_recipe.v1";
  aesthetic_profile_id: string | null;
  aesthetic_profile_revision: number | null;
  source: "JESR-Aesthetic-Profile";
  display_label: "JESR-Profile-Recipe";
  compat_version: "jesr_core.v1";
}

export interface JESRProfileRecipe extends Record<string, unknown> {
  version: "jesr_core.v1";
  style_id: CreativeStylePresetId | null;
  style_preset_id?: CreativeStylePresetId | null;
  tone: Record<string, number>;
  face: Record<string, number>;
  creative: Record<string, unknown>;
  feedback: Record<string, unknown>;
  jesr: JESRProfileRecipeMetadata;
}

export interface JESRFeedbackState {
  pain_tags: PainTag[];
  free_text?: string | null;
  recipe_delta?: Record<string, unknown>;
}

export const JESR_PROXY_EVALUATION_STATUSES = [
  "evaluated",
  "partial",
  "pending_jesr_proxy_eval",
  "not_evaluable",
  "invalid_input",
] as const;
export type JESRProxyEvaluationStatus = (typeof JESR_PROXY_EVALUATION_STATUSES)[number];

export interface JESRProxyEvaluationRecord {
  proxy_evaluator_id: string;
  profile_alignment_score: number | null;
  identity_acceptability: number | null;
  style_cue_score: number | null;
  naturalness_proxy_score: number | null;
  negative_rule_violation_rate: number | null;
  proxy_eval_status: JESRProxyEvaluationStatus;
}

export interface JESRGuardState {
  selected_variant?: string;
  fallback_to_fidelity?: boolean;
  guard_reason?: string;
  identity_similarity?: number | null;
}

export interface BaseStyle {
  base_style_source: BaseStyleSource;
  base_style_profile: BaseStyleProfile;
  reference_photo_ids: string[];
  seed_choices: SeedChoice[];
}

export interface ProbeCandidate {
  id: string;
  photo_id: string;
  session_id: string;
  variant_index: number;
  recipe_snapshot: Record<string, unknown>;
  parent_style_preset: string | null;
  parent_base_style_source: string | null;
  perturbations: {
    denoising_strength_delta: number;
    structure_weight_delta: number;
    style_strength_delta: number;
  };
  preview_asset_key: string | null;
  result_asset_key: string | null;
  render_metadata: Record<string, unknown>;
  resultUrl?: string | null;
}

export interface ProbeFeedback {
  probe_id: string;
  liked: boolean;
}

export interface JesrRecipe {
  session_id: string;
  base_style_source: BaseStyleSource | null;
  base_style_profile: BaseStyleProfile | null;
  reference_photo_ids: string[];
  seed_choices: SeedChoice[];
  base_recipe: Record<string, unknown> | null;
  creative_style_preset: CreativeStylePresetId | null;
  creative_base_recipe: Record<string, unknown> | null;
  current_recipe: Record<string, unknown> | null;
  recipe: Record<string, unknown> | null;
  version: number;
  base_recipe_version?: number;
  source: string | null;
  created_at: string;
  updated_at: string;
}

export interface JesrIteration {
  id: string;
  session_id: string;
  photo_id: string;
  iteration_number: number;
  input_recipe: Record<string, unknown>;
  pain_tags: PainTag[];
  render_job_id: string;
  output_recipe: Record<string, unknown>;
  output_image_id: string | null;
  style_preset: CreativeStylePresetId | null;
  recipe_version: number;
  metrics: JesrMetrics | null;
  created_at: string;
}

export interface JesrMetrics {
  IPS: number;
  SAS: number;
  SID: number;
  FHS: number;
  ODI: number;
  CEN: number;
  PG: number;
}

export interface CreativeStylePreset {
  id: CreativeStylePresetId;
  label: string;
  version: string;
  recipe_overrides: Record<string, unknown>;
}

export interface ExperimentSummary {
  session_id: string;
  total_experiments: number;
  phases: string[];
  metrics_summary: Record<string, unknown>;
  grouped_by_base_style_source: Record<string, { count: number; experiment_ids: string[] }>;
  grouped_by_creative_style_preset: Record<string, { count: number; experiment_ids: string[] }>;
  experiments: ExperimentRecord[];
}

export interface ExperimentRecord {
  experiment_id: string;
  session_id: string;
  photo_id: string;
  timestamp: string;
  phase: "probe" | "iteration";
  base_style_source: BaseStyleSource | null;
  reference_photo_ids: string[];
  seed_choices: SeedChoice[];
  probe_choices: ProbeFeedback[];
  pain_tags: PainTag[];
  base_recipe_version: number;
  recipe_version: number;
  creative_style_preset: CreativeStylePresetId | null;
  selected_style_preset: CreativeStylePresetId | null;
  render_settings: Record<string, unknown>;
  output_image_id: string;
  metrics: JesrMetrics;
}

export const CREATIVE_STYLE_PRESET_LABELS: Record<CreativeStylePresetId, string> = {
  fresh_japanese: "清新日系",
  retro_hongkong: "复古港风",
  clear_korean: "清透韩系",
  lazy_french: "法式慵懒",
  american_hotgirl: "美式辣妹",
} as const;
