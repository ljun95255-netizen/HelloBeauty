export const colors = {
  editorialPrimary: "#1C1C1C",
  editorialSecondary: "#F9F8F6",
  editorialAccentMuted: "#6b7280",
  editorialAccentWarm: "#816d70",
  line: "rgba(28, 28, 28, 0.14)",
  lineStrong: "rgba(28, 28, 28, 0.24)",
  wash: "rgba(28, 28, 28, 0.04)",
  washStrong: "rgba(28, 28, 28, 0.08)",

  // Web editorial theme
  webBackground: "#121417",
  webBackgroundSoft: "#181b20",
  webPanel: "#1d2229",
  webSurface: "rgba(255, 255, 255, 0.04)",
  webSurfaceStrong: "rgba(255, 255, 255, 0.08)",
  webLine: "rgba(255, 255, 255, 0.14)",
  webText: "#f5f7fa",
  webMuted: "#9aa4b2",
  webAccent: "#9fb3c8",
  webAccentStrong: "#d8e4f0",
  webAccentWarm: "#d7c0a0",
  webPrimary: "#9fb3c8",
  webPrimaryHover: "#b8c9d8",

  // Mini editorial theme
  miniPage: "#F9F8F6",
  miniSurface: "#FFFDFA",
  miniSurfaceMuted: "rgba(28, 28, 28, 0.04)",
  miniText: "#1C1C1C",
  miniMuted: "#6b7280",
  miniPrimary: "#1C1C1C",
  miniAccent: "#816d70",

  danger: "#8A5A5F",
  success: "#4F5E52",
} as const;

export const radii = {
  pill: "9999px",
  xl: "0px",
  lg: "0px",
  md: "0px",
  sm: "0px",
} as const;

export const spacing = {
  xs: "8px",
  sm: "16px",
  md: "24px",
  lg: "32px",
  xl: "48px",
  xxl: "72px",
} as const;

export const durations = {
  fast: "160ms",
  normal: "260ms",
  slow: "420ms",
} as const;

export const shadows = {
  sm: "none",
  md: "none",
  lg: "none",
  xl: "none",
  card: "none",
} as const;

export const editorialTypography = {
  display:
    '"Iowan Old Style", "Palatino Linotype", "Book Antiqua", "Songti SC", "Noto Serif SC", serif',
  body:
    '"PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Helvetica Neue", Arial, sans-serif',
  lineHeight: {
    display: 1.04,
    body: 1.75,
    compact: 1.45,
  },
} as const;

export const editorialMotion = {
  revealDistance: "22px",
  sectionOffset: "80px",
  mediaLift: "-4%",
} as const;

export const webThemeVariables = {
  "--bg": colors.webBackground,
  "--bg-soft": colors.webBackgroundSoft,
  "--surface": colors.webSurface,
  "--surface-strong": colors.webSurfaceStrong,
  "--line": colors.webLine,
  "--line-strong": colors.lineStrong,
  "--text": colors.webText,
  "--muted": colors.webMuted,
  "--accent": colors.webAccent,
  "--accent-strong": colors.webAccentStrong,
  "--accent-warm": colors.webAccentWarm,
  "--primary": colors.webPrimary,
  "--primary-hover": colors.webPrimaryHover,
  "--panel": colors.webPanel,
  "--shadow-sm": shadows.sm,
  "--shadow-md": shadows.md,
  "--shadow-lg": shadows.lg,
  "--shadow-card": shadows.card,
  "--editorial-display": editorialTypography.display,
  "--editorial-body": editorialTypography.body,
  "--editorial-reveal-distance": editorialMotion.revealDistance,
  "--editorial-section-offset": editorialMotion.sectionOffset,
} as const;
