// Turns the raw files into exactly what each part of the page shows. No network, no React.
import { STALE_AFTER_HOURS } from "../config";
import type { Conditions, Meta, Recommendations } from "./generated/types";
import { addDays, ageOf, nzDateKey, type AgeUnit } from "./time";

export interface Spot { id: string; name: string; lat: number; lon: number; notes: string }
export type Window = Recommendations["spots"][number]["windows"][number];
export type Hour = Conditions["hourly"][number];

export interface TodayCard {
  spot: Spot;
  /** Best window that touches today and has not ended; null when there is none. */
  window: Window | null;
  /** True when today had windows but they are all over. */
  passed: boolean;
  /** Tide height for each hour of today, for the small curve on the card. */
  tide: { time: string; height: number | null }[];
}

const overlapsDay = (w: Window, dayKey: string) =>
  nzDateKey(new Date(w.start_utc)) <= dayKey && nzDateKey(new Date(new Date(w.end_utc).getTime() - 1)) >= dayKey;

export function todayCards(spots: Spot[], recs: Recommendations | null,
                           conditions: Record<string, Conditions | undefined>, now: Date): TodayCard[] {
  const today = nzDateKey(now);
  return spots.map((spot) => {
    const all = recs?.spots.find((s) => s.spot_id === spot.id)?.windows ?? [];
    const todays = all.filter((w) => overlapsDay(w, today));
    const open = todays.filter((w) => new Date(w.end_utc) > now).sort((a, b) => b.score - a.score);
    const tide = (conditions[spot.id]?.hourly ?? [])
      .filter((h) => nzDateKey(new Date(h.time_utc)) === today)
      .map((h) => ({ time: h.time_utc, height: h.tide_height_m }));
    return { spot, window: open[0] ?? null, passed: todays.length > 0 && open.length === 0, tide };
  });
}

export interface WeekDay { dateKey: string; relative: "today" | "tomorrow" | null; windows: { spot: Spot; window: Window }[] }

/** Windows that have not ended, grouped by NZ calendar day, earliest first. */
export function weekDays(spots: Spot[], recs: Recommendations | null, now: Date): WeekDay[] {
  if (!recs) return [];
  const today = nzDateKey(now);
  const days = new Map<string, WeekDay["windows"]>();
  for (const entry of recs.spots) {
    const spot = spots.find((s) => s.id === entry.spot_id);
    if (!spot) continue;
    for (const window of entry.windows) {
      if (new Date(window.end_utc) <= now) continue;
      const key = nzDateKey(new Date(window.start_utc));
      days.set(key, [...(days.get(key) ?? []), { spot, window }]);
    }
  }
  return [...days.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([dateKey, windows]) => ({
    dateKey,
    relative: dateKey === today ? "today" : dateKey === addDays(today, 1) ? "tomorrow" : null,
    windows: windows.sort((a, b) => a.window.start_utc.localeCompare(b.window.start_utc) || b.window.score - a.window.score),
  }));
}

export type Block = "tide" | "forecast" | "flow";
export interface Freshness { state: "fresh" | "stale" | "failed" | "never"; age: AgeUnit | null; since: string | null }

const BLOCK_SOURCES: Record<Block, (keyof Meta["sources"])[]> = {
  tide: ["linz_tides"],
  forecast: ["open_meteo_forecast", "open_meteo_marine"],
  flow: ["ecan_flow"],
};

/** How old each block of data is, judged by its least recently updated source. */
export function freshness(meta: Meta | null, block: Block, now: Date): Freshness {
  if (!meta) return { state: "never", age: null, since: null };
  const sources = BLOCK_SOURCES[block].map((name) => meta.sources[name]);
  const times = sources.map((s) => s.last_success_utc);
  if (times.some((t) => t === null)) return { state: "never", age: null, since: null };
  const oldest = (times as string[]).sort()[0];
  const age = ageOf(oldest, now);
  // tides come from a yearly file, so only "the update failed" matters for them
  const limit = block === "flow" ? STALE_AFTER_HOURS.flow : block === "forecast" ? STALE_AFTER_HOURS.forecast : Infinity;
  const failed = sources.some((s) => s.status === "failed");
  const state = failed ? "failed" : age.hours > limit ? "stale" : "fresh";
  return { state, age: { unit: age.unit, value: age.value }, since: oldest };
}

/** The hours that are not over yet: the current hour first. The files also hold the hours since the last collection. */
export function upcomingHours(hours: Hour[], now: Date): Hour[] {
  return hours.filter((h) => new Date(h.time_utc).getTime() + 3_600_000 > now.getTime());
}

export interface DayBand { index: number; dateKey: string }

/** Index of the first hour of each NZ calendar day inside the hourly list. */
export function dayStarts(hours: Hour[]): DayBand[] {
  const out: DayBand[] = [];
  let last = "";
  hours.forEach((h, index) => {
    const key = nzDateKey(new Date(h.time_utc));
    if (key !== last) out.push({ index, dateKey: key });
    last = key;
  });
  return out;
}

/** Position of an instant on the hourly axis (fractional), or null when outside it. */
export function axisPosition(hours: Hour[], iso: string): number | null {
  if (!hours.length) return null;
  const pos = (new Date(iso).getTime() - new Date(hours[0].time_utc).getTime()) / 3_600_000;
  return pos < 0 || pos > hours.length ? null : pos;
}

/** 0..7 index into the eight moon phase names, from the 0..1 lunar fraction. */
export const moonPhaseIndex = (fraction: number): number => Math.round(fraction * 8) % 8;

/** WMO weather code -> one of a handful of pictures. */
export type Sky = "clear" | "partly" | "cloud" | "fog" | "drizzle" | "rain" | "snow" | "storm";
export function skyOf(code: number | null): Sky | null {
  if (code === null) return null;
  if (code === 0) return "clear";
  if (code <= 2) return "partly";
  if (code === 3) return "cloud";
  if (code === 45 || code === 48) return "fog";
  if (code >= 51 && code <= 57) return "drizzle";
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return "rain";
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "snow";
  if (code >= 95) return "storm";
  return "cloud";
}
