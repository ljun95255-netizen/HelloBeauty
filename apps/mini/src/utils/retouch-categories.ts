/**
 * retouch-categories.ts — 针对性精修美容类别定义
 *
 * 参考: 醒图/美图秀秀的精修面板结构
 * 设计: Editorial + Parallax Sections design tokens
 */

export interface RetouchParam {
  key: string;
  label: string;
  icon: string;
  min: number;
  max: number;
  step: number;
  defaultValue: number;
  description: string;
}

export interface RetouchCategory {
  id: string;
  label: string;
  icon: string;
  params: RetouchParam[];
}

export type SmudgeMode = "none" | "arms" | "chest" | "waist" | "legs";

export const SMUDGE_MODES: { id: SmudgeMode; label: string }[] = [
  { id: "arms", label: "手臂" },
  { id: "chest", label: "胸部" },
  { id: "waist", label: "腰部" },
  { id: "legs", label: "腿部" },
];

export const RETOUCH_CATEGORIES: RetouchCategory[] = [
  {
    id: "face",
    label: "脸型",
    icon: "😊",
    params: [
      { key: "jawline", label: "下颌线", icon: "◻", min: -50, max: 50, step: 1, defaultValue: 0, description: "收紧或放宽下颌" },
      { key: "chin", label: "下巴", icon: "▽", min: -50, max: 50, step: 1, defaultValue: 0, description: "拉长或缩短下巴" },
      { key: "forehead", label: "额头", icon: "⬆", min: -30, max: 30, step: 1, defaultValue: 0, description: "调整额头高度" },
      { key: "face_width", label: "脸宽", icon: "⬅➡", min: -50, max: 50, step: 1, defaultValue: 0, description: "收窄或加宽面部" },
    ],
  },
  {
    id: "eyes",
    label: "眼睛",
    icon: "👁",
    params: [
      { key: "eye_size", label: "大眼", icon: "🔍", min: 0, max: 100, step: 1, defaultValue: 0, description: "放大双眼" },
      { key: "eye_distance", label: "眼距", icon: "↔", min: -50, max: 50, step: 1, defaultValue: 0, description: "调整两眼间距" },
      { key: "eye_tilt", label: "眼尾", icon: "↗", min: -30, max: 30, step: 1, defaultValue: 0, description: "上扬或下垂眼尾" },
      { key: "eye_brightness", label: "亮眼", icon: "✨", min: 0, max: 100, step: 1, defaultValue: 0, description: "提亮眼白和虹膜" },
    ],
  },
  {
    id: "eyebrows",
    label: "眉毛",
    icon: "🖊",
    params: [
      { key: "eyebrow_thickness", label: "浓淡", icon: "▬", min: -30, max: 30, step: 1, defaultValue: 0, description: "加重或减淡眉毛" },
      { key: "eyebrow_arch", label: "眉峰", icon: "⌃", min: -30, max: 30, step: 1, defaultValue: 0, description: "调整眉峰弧度" },
      { key: "eyebrow_distance", label: "眉距", icon: "↔", min: -30, max: 30, step: 1, defaultValue: 0, description: "拉近或拉远眉间距" },
    ],
  },
  {
    id: "nose",
    label: "鼻子",
    icon: "👃",
    params: [
      { key: "nose_bridge", label: "鼻梁", icon: "|", min: -50, max: 50, step: 1, defaultValue: 0, description: "收窄或加宽鼻梁" },
      { key: "nose_tip", label: "鼻头", icon: "●", min: -50, max: 50, step: 1, defaultValue: 0, description: "缩小或放大鼻头" },
      { key: "nose_length", label: "鼻长", icon: "↓", min: -30, max: 30, step: 1, defaultValue: 0, description: "缩短或拉长鼻子" },
    ],
  },
  {
    id: "mouth",
    label: "嘴巴",
    icon: "👄",
    params: [
      { key: "mouth_width", label: "嘴宽", icon: "↔", min: -30, max: 30, step: 1, defaultValue: 0, description: "收窄或加宽嘴唇" },
      { key: "lip_thickness", label: "唇厚", icon: "⬆", min: -30, max: 30, step: 1, defaultValue: 0, description: "薄唇或厚唇效果" },
      { key: "smile", label: "微笑", icon: "🙂", min: 0, max: 100, step: 1, defaultValue: 0, description: "调节嘴角上扬弧度" },
      { key: "lip_saturation", label: "唇色", icon: "💄", min: -30, max: 30, step: 1, defaultValue: 0, description: "增强或减弱唇色饱和度" },
    ],
  },
  {
    id: "teeth",
    label: "牙齿",
    icon: "😁",
    params: [
      { key: "teeth_whiten", label: "美白", icon: "🦷", min: 0, max: 100, step: 1, defaultValue: 0, description: "牙齿美白程度" },
    ],
  },
  {
    id: "skin",
    label: "皮肤",
    icon: "💆",
    params: [
      { key: "skin_smoothing", label: "磨皮", icon: "🧴", min: 0, max: 100, step: 1, defaultValue: 0, description: "皮肤平滑细腻度" },
      { key: "skin_brightness", label: "肤色", icon: "☀", min: -30, max: 30, step: 1, defaultValue: 0, description: "提亮或加深肤色" },
      { key: "pore_hiding", label: "毛孔", icon: "🔬", min: 0, max: 100, step: 1, defaultValue: 0, description: "隐藏毛孔程度" },
      { key: "dark_circle", label: "黑眼圈", icon: "🕶", min: 0, max: 100, step: 1, defaultValue: 0, description: "去除黑眼圈" },
    ],
  },
  {
    id: "body",
    label: "身体",
    icon: "🧍",
    params: [
      { key: "shoulder", label: "肩膀", icon: "▬", min: -30, max: 30, step: 1, defaultValue: 0, description: "收窄或加宽肩膀" },
      { key: "arms", label: "手臂", icon: "💪", min: -30, max: 30, step: 1, defaultValue: 0, description: "纤细或丰满手臂" },
      { key: "chest", label: "胸部", icon: "❤", min: -20, max: 20, step: 1, defaultValue: 0, description: "调整胸部饱满度" },
      { key: "waist", label: "腰部", icon: "⏳", min: -50, max: 50, step: 1, defaultValue: 0, description: "收腰或放宽腰部" },
      { key: "legs", label: "腿部", icon: "🦵", min: -30, max: 30, step: 1, defaultValue: 0, description: "拉长或缩短腿部" },
    ],
  },
  {
    id: "hair",
    label: "头发",
    icon: "💇",
    params: [
      { key: "hair_volume", label: "发量", icon: "🦰", min: -30, max: 30, step: 1, defaultValue: 0, description: "增加或减少发量" },
      { key: "hair_shine", label: "光泽", icon: "🌟", min: 0, max: 100, step: 1, defaultValue: 0, description: "发丝光泽度" },
    ],
  },
];
