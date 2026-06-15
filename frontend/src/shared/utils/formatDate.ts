/** Парсит даты из API: dd.mm.yyyy, dd.mm.yyyy HH:MM:SS, ISO. */
export function parseApiDate(value?: string): Date | null {
  if (!value?.trim()) return null;

  const trimmed = value.trim();
  const ruMatch = trimmed.match(/^(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2}):(\d{2}))?$/);
  if (ruMatch) {
    const [, day, month, year, hours = "0", minutes = "0", seconds = "0"] = ruMatch;
    return new Date(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hours),
      Number(minutes),
      Number(seconds)
    );
  }

  const parsed = new Date(trimmed);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatDisplayDate(value?: string): string {
  const date = parseApiDate(value);
  if (!date) return value?.trim() || "—";

  return date.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}
