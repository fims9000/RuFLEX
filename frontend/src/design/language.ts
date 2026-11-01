// Keep persisted scientific identifiers in English; translate presentation only.
export const uiLanguage = import.meta.env.VITE_RUFLEX_UI_LANG === "ru"
  ? "ru"
  : import.meta.env.VITE_RUFLEX_UI_LANG === "en" || import.meta.env.MODE === "test" ? "en" : "ru";

export function ui(english: string, russian: string): string {
  return uiLanguage === "en" ? english : russian;
}
