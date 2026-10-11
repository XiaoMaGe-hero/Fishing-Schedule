// Turns rows of the history table into the two snapshots a record keeps. No network here.
import type { ConditionsHour, HistoryRow, ScoreSnapshot } from "./types";

const HOUR = 3_600_000;
const iso = (ms: number) => new Date(ms).toISOString().replace(".000Z", "Z");

/** Start (UTC) of every clock hour the trip touches. 06:30-09:10 gives the hours starting 06, 07, 08 and 09. */
export function tripHours(startedAt: string, endedAt: string): string[] {
  const start = Math.floor(new Date(startedAt).getTime() / HOUR) * HOUR;
  const end = new Date(endedAt).getTime();
  const hours: string[] = [];
  for (let t = start; t < end; t += HOUR) hours.push(iso(t));
  return hours;
}

export interface Snapshots { conditions_snapshot: ConditionsHour[] | null; score_snapshot: ScoreSnapshot | null }

/**
 * Keep the rows that belong to the trip, in time order.
 * No rows -> both snapshots are null (the trip is older than the history, or collection was down).
 * Rows without a score (hours collected before scoring existed) -> conditions only.
 */
export function buildSnapshots(rows: HistoryRow[], hours: string[]): Snapshots {
  const wanted = new Set(hours.map((h) => new Date(h).getTime()));
  const mine = rows
    .filter((r) => wanted.has(new Date(r.time_utc).getTime()))
    .sort((a, b) => new Date(a.time_utc).getTime() - new Date(b.time_utc).getTime());
  if (!mine.length) return { conditions_snapshot: null, score_snapshot: null };

  const conditions = mine.map(({ score: _s, ruleset_version: _v, ...rest }) => ({ ...rest, time_utc: iso(new Date(rest.time_utc).getTime()) }));
  const scored = mine.filter((r) => r.score !== null);
  if (!scored.length) return { conditions_snapshot: conditions, score_snapshot: null };

  const mean = scored.reduce((sum, r) => sum + (r.score as number), 0) / scored.length;
  const versions = scored.map((r) => r.ruleset_version).filter((v): v is number => v !== null);
  return {
    conditions_snapshot: conditions,
    score_snapshot: {
      hours: scored.map((r) => ({ time_utc: iso(new Date(r.time_utc).getTime()), score: r.score as number, ruleset_version: r.ruleset_version })),
      mean_score: Math.round(mean * 10) / 10,
      ruleset_version: versions.length ? Math.max(...versions) : null,
    },
  };
}

export interface ConditionsSummary {
  hours: number;
  tide: { from: number; to: number; phase: "rising" | "falling" | "turning" } | null;
  windKmh: number | null;
  gustKmh: number | null;
  windRelative: "onshore" | "offshore" | "cross" | null;
  waveM: number | null;
  seaTempC: number | null;
  rainPct: number | null;
  flowM3s: number | null;
}

const present = (values: (number | null)[]) => values.filter((v): v is number => v !== null);
const mean = (values: number[]) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : null);
const max = (values: number[]) => (values.length ? Math.max(...values) : null);

/** The few numbers shown on a record card: averages for steady things, the worst hour for gusts, waves and rain. */
export function summarise(snapshot: ConditionsHour[]): ConditionsSummary {
  const tides = snapshot.filter((h) => h.tide_height_m !== null);
  const phases = new Set(snapshot.map((h) => h.tide_phase).filter(Boolean));
  const relatives = new Set(snapshot.map((h) => h.wind_relative).filter(Boolean));
  return {
    hours: snapshot.length,
    tide: tides.length ? {
      from: tides[0].tide_height_m as number,
      to: tides[tides.length - 1].tide_height_m as number,
      phase: phases.size === 1 ? ([...phases][0] as "rising" | "falling") : "turning",
    } : null,
    windKmh: mean(present(snapshot.map((h) => h.wind_speed_kmh))),
    gustKmh: max(present(snapshot.map((h) => h.wind_gust_kmh))),
    windRelative: relatives.size === 1 ? ([...relatives][0] as ConditionsSummary["windRelative"]) : null,
    waveM: max(present(snapshot.map((h) => h.wave_height_m))),
    seaTempC: mean(present(snapshot.map((h) => h.sea_temp_c))),
    rainPct: max(present(snapshot.map((h) => h.precip_prob_pct))),
    flowM3s: mean(present(snapshot.map((h) => h.river_flow_m3s))),
  };
}
