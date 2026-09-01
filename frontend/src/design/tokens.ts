export const studioLayout = {
  topBar: 44,
  rail: 48,
  explorer: 240,
  inspector: 320,
  bottom: 220,
  status: 24,
  minWidth: 1180,
  minHeight: 720,
} as const;

export type StudioTheme = "light" | "dark";

export const navigation = ["PROJECT", "DATA", "BUILD", "EXPERIMENT", "EVALUATE", "TRACE", "EXPLAIN", "VERIFY", "TEST", "REPORT"] as const;
