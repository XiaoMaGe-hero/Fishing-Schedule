// All times in the data are UTC. Everything on screen is New Zealand time,
// whatever time zone the visitor's device is set to.
export const NZ_ZONE = "Pacific/Auckland";

const partsFormat = new Intl.DateTimeFormat("en-NZ", {
  timeZone: NZ_ZONE, hourCycle: "h23", weekday: "short", year: "numeric", month: "2-digit",
  day: "2-digit", hour: "2-digit", minute: "2-digit",
});
const monthFormat = new Intl.DateTimeFormat("en-NZ", { timeZone: NZ_ZONE, month: "short" });

export interface NzParts { dateKey: string; weekday: string; day: number; month: string; hour: number; minute: number }

export function nzParts(date: Date): NzParts {
  const p = Object.fromEntries(partsFormat.formatToParts(date).map((x) => [x.type, x.value]));
  return {
    dateKey: `${p.year}-${p.month}-${p.day}`,
    weekday: p.weekday,
    day: Number(p.day),
    month: monthFormat.format(date),
    hour: Number(p.hour),
    minute: Number(p.minute),
  };
}

export const nzDateKey = (date: Date): string => nzParts(date).dateKey;

/** "06:05" */
export function formatTime(date: Date): string {
  const p = nzParts(date);
  return `${String(p.hour).padStart(2, "0")}:${String(p.minute).padStart(2, "0")}`;
}

/** "Tue 13 Oct" */
export function formatDay(date: Date): string {
  const p = nzParts(date);
  return `${p.weekday} ${p.day} ${p.month}`;
}

/** Add whole days to a "YYYY-MM-DD" key (calendar arithmetic, no time zone involved). */
export function addDays(dateKey: string, days: number): string {
  const [y, m, d] = dateKey.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** "Tue 13 Oct" for a "YYYY-MM-DD" key. */
export function formatDateKey(dateKey: string): string {
  const [y, m, d] = dateKey.split("-").map(Number);
  const noon = new Date(Date.UTC(y, m - 1, d, 0, 0)); // 00:00 UTC is midday-ish in NZ on the same calendar day
  return formatDay(noon);
}

export type AgeUnit = { unit: "minutes" | "hours" | "days"; value: number };

/** How long ago, rounded the way people say it. */
export function ageOf(iso: string, now: Date): AgeUnit & { hours: number } {
  const hours = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 3_600_000);
  if (hours < 1) return { unit: "minutes", value: Math.max(1, Math.round(hours * 60)), hours };
  if (hours < 48) return { unit: "hours", value: Math.round(hours), hours };
  return { unit: "days", value: Math.round(hours / 24), hours };
}
