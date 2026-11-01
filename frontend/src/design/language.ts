// Keep persisted scientific identifiers in English; translate presentation only.
export const uiLanguage = import.meta.env.VITE_RUFLEX_UI_LANG === "ru"
  ? "ru"
  : import.meta.env.VITE_RUFLEX_UI_LANG === "en" || import.meta.env.MODE === "test" ? "en" : "ru";

export function ui(english: string, russian: string): string {
  return uiLanguage === "en" ? english : russian;
}

const statusLabels: Record<string, string> = {
  OK: "Рассчитано",
  EMPTY: "Нет примеров",
  ALLOW: "В области применения",
  BLOCK: "Вне области применения",
  UNDECLARED: "Область не задана",
  PASSED_AVAILABLE_CHECKS: "Доступные проверки пройдены",
  NOT_APPLICABLE: "Не применяется",
  NOT_AVAILABLE: "Недоступно",
  SUCCEEDED: "Завершено",
  RUNNING: "Выполняется",
  QUEUED: "Ожидает запуска",
  CANCELLED: "Отменено",
  FROZEN: "Зафиксировано",
  LOCKED_NOT_EVALUATED: "Итоговый тест закрыт",
  completed: "Завершено",
  succeeded: "Завершено",
  train_only: "Только обучение",
  PASS: "Пройдено",
  FAIL: "Не пройдено",
  WARN: "Предупреждение",
  WARNING: "Предупреждение",
  FAILED: "Сбой",
  ERROR: "Ошибка",
  SUPPORTED: "Подтверждено",
  UNSUPPORTED: "Не подтверждено",
  "N/A": "Н/Д",
  ACCEPT: "Принять",
  REVIEW: "Проверить",
  LOW_CONFIDENCE: "Низкая уверенность",
  RUN_DISAGREEMENT: "Модели расходятся в решении",
  HIGH_DISPERSION: "Большой разброс вероятностей",
  INSUFFICIENT_RUN_SUPPORT: "Недостаточно сопоставимых обучений",
  OUT_OF_SCOPE: "Вне области применения",
};

export function uiStatus(status: string): string {
  return uiLanguage === "ru" ? statusLabels[status] ?? status : status;
}
