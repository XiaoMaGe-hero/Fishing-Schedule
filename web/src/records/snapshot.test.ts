import { describe, expect, it } from "vitest";
import { buildSnapshots, summarise, tripHours } from "./snapshot";
import type { HistoryRow } from "./types";

const row = (time: string, over: Partial<HistoryRow> = {}): HistoryRow => ({
  time_utc: time, tide_height_m: 1, tide_phase: "rising", air_temp_c: 12, precip_prob_pct: 10, weather_code: 1,
  wind_speed_kmh: 10, wind_gust_kmh: 20, wind_dir_deg: 270, wind_relative: "offshore", wave_height_m: 0.8,
  swell_height_m: 0.5, sea_temp_c: 13.5, is_daylight: true, river_flow_m3s: 80, score: 70, ruleset_version: 3, ...over,
});

describe("tripHours", () => {
  it("covers every clock hour the trip touches", () => {
    expect(tripHours("2026-10-10T17:30:00Z", "2026-10-10T20:10:00Z")).toEqual([
      "2026-10-10T17:00:00Z", "2026-10-10T18:00:00Z", "2026-10-10T19:00:00Z", "2026-10-10T20:00:00Z"]);
  });
  it("does not include the hour that starts exactly when the trip ends", () => {
    expect(tripHours("2026-10-10T17:00:00Z", "2026-10-10T19:00:00Z")).toEqual(["2026-10-10T17:00:00Z", "2026-10-10T18:00:00Z"]);
  });
});

describe("buildSnapshots", () => {
  const hours = ["2026-10-10T17:00:00Z", "2026-10-10T18:00:00Z"];
  it("keeps one entry per hour, with the score and ruleset version apart from the conditions", () => {
    // the database returns times as "+00:00", and may return more than was asked for
    const s = buildSnapshots([row("2026-10-10T18:00:00+00:00", { score: 80 }), row("2026-10-10T17:00:00+00:00", { score: 61 }),
                              row("2026-10-10T19:00:00+00:00")], hours);
    expect(s.conditions_snapshot!.map((h) => h.time_utc)).toEqual(hours);
    expect(s.conditions_snapshot![0]).not.toHaveProperty("score");
    expect(s.conditions_snapshot![0].sea_temp_c).toBe(13.5);
    expect(s.score_snapshot).toEqual({
      hours: [{ time_utc: hours[0], score: 61, ruleset_version: 3 }, { time_utc: hours[1], score: 80, ruleset_version: 3 }],
      mean_score: 70.5, ruleset_version: 3,
    });
  });
  it("gives empty snapshots when the history has nothing for the trip", () => {
    expect(buildSnapshots([], hours)).toEqual({ conditions_snapshot: null, score_snapshot: null });
    expect(buildSnapshots([row("2026-10-11T03:00:00Z")], hours)).toEqual({ conditions_snapshot: null, score_snapshot: null });
  });
  it("keeps the conditions when the hours were never scored", () => {
    const s = buildSnapshots([row(hours[0], { score: null, ruleset_version: null })], hours);
    expect(s.conditions_snapshot).toHaveLength(1);
    expect(s.score_snapshot).toBeNull();
  });
  it("keeps a score of 0 (a vetoed hour) as a score", () => {
    const s = buildSnapshots([row(hours[0], { score: 0 }), row(hours[1], { score: 50 })], hours);
    expect(s.score_snapshot!.mean_score).toBe(25);
  });
});

describe("summarise", () => {
  it("averages steady values and takes the worst hour for gusts, waves and rain", () => {
    const { conditions_snapshot } = buildSnapshots([
      row("2026-10-10T17:00:00Z", { tide_height_m: 0.5, wind_speed_kmh: 10, wind_gust_kmh: 20, wave_height_m: 0.6, precip_prob_pct: 5 }),
      row("2026-10-10T18:00:00Z", { tide_height_m: 1.5, tide_phase: "falling", wind_speed_kmh: 20, wind_gust_kmh: 41, wave_height_m: 1.1, precip_prob_pct: 40, river_flow_m3s: null }),
    ], ["2026-10-10T17:00:00Z", "2026-10-10T18:00:00Z"]);
    expect(summarise(conditions_snapshot!)).toEqual({
      hours: 2, tide: { from: 0.5, to: 1.5, phase: "turning" }, windKmh: 15, gustKmh: 41, windRelative: "offshore",
      waveM: 1.1, seaTempC: 13.5, rainPct: 40, flowM3s: 80,
    });
  });
  it("copes with hours that have no forecast", () => {
    const { conditions_snapshot } = buildSnapshots([row("2026-10-10T17:00:00Z", {
      tide_height_m: null, tide_phase: null, wind_speed_kmh: null, wind_gust_kmh: null, wind_relative: null, wave_height_m: null,
      sea_temp_c: null, precip_prob_pct: null, river_flow_m3s: null })], ["2026-10-10T17:00:00Z"]);
    expect(summarise(conditions_snapshot!)).toEqual({ hours: 1, tide: null, windKmh: null, gustKmh: null, windRelative: null,
      waveM: null, seaTempC: null, rainPct: null, flowM3s: null });
  });
});
