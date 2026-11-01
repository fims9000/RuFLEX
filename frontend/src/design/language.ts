// Keep persisted scientific identifiers in English; translate presentation only.
export const uiLanguage = import.meta.env.VITE_RUFLEX_UI_LANG === "ru"
  ? "ru"
  : import.meta.env.VITE_RUFLEX_UI_LANG === "en" || import.meta.env.MODE === "test" ? "en" : "ru";

export function ui(english: string, russian: string): string {
  return uiLanguage === "en" ? english : russian;
}

const statusLabels: Record<string, string> = {
  PASS: "Пройдено",
  FAIL: "Ошибка",
  WARN: "Предупреждение",
  WARNING: "Предупреждение",
  FAILED: "Не пройдено",
  SUPPORTED: "Подтверждено",
  UNSUPPORTED: "Не подтверждено",
  "N/A": "Н/Д",
  ACCEPT: "Принять",
  REVIEW: "Проверить",
  OUT_OF_SCOPE: "Вне области применения",
};

export function uiStatus(status: string): string {
  return uiLanguage === "ru" ? statusLabels[status] ?? status : status;
}
