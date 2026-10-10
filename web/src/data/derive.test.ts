import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { axisPosition, dayStarts, freshness, moonPhaseIndex, skyOf, todayCards, weekDays, type Spot } from "./derive";
import type { Conditions, Meta, Recommendations } from "./generated/types";

const SPOTS: Spot[] = [
  { id: "pier", name: "Pier", lat: -43.5, lon: 172.7, notes: "" },
  { id: "south", name: "South", lat: -43.55, lon: 172.75, notes: "" },
];
const win = (spot: string, start: string, end: string, score: number, confidence: "high" | "low" = "high") => ({
  spot_id: spot, start_utc: start, end_utc: end, score, confidence, ruleset_version: 2,
  reasons: [{ rule: "tide", score: 1, weight: 3, reason: "inside the best window" }],
});
// NZ day Sat 10 Oct 2026 runs from 2026-10-09T11:00Z to 2026-10-10T11:00Z
const recs: Recommendations = {
  schema_version: 1, generated_at: "2026-10-09T18:00:00Z", ruleset_version: 2,
  spots: [
    { spot_id: "pier", hourly: [], windows: [
      win("pier", "2026-10-09T17:00:00Z", "2026-10-09T20:00:00Z", 70),      // Sat 06:00-09:00
      win("pier", "2026-10-10T03:00:00Z", "2026-10-10T07:00:00Z", 88),      // Sat 16:00-20:00
      win("pier", "2026-10-13T17:00:00Z", "2026-10-13T22:00:00Z", 91, "low"), // Wed
    ] },
    { spot_id: "south", hourly: [], windows: [win("south", "2026-10-10T17:00:00Z", "2026-10-10T21:00:00Z", 80)] }, // Sun
  ],
};

describe("today's cards", () => {
  it("picks the best window still open today", () => {
    const cards = todayCards(SPOTS, recs, {}, new Date("2026-10-09T18:30:00Z")); // Sat 07:30
    expect(cards[0].window?.score).toBe(88);
    expect(cards[1].window).toBeNull();
    expect(cards[1].passed).toBe(false);
  });
  it("drops a window once it has ended, and says so when all of today's are over", () => {
    expect(todayCards(SPOTS, recs, {}, new Date("2026-10-09T21:00:00Z"))[0].window?.score).toBe(88);
    const late = todayCards(SPOTS, recs, {}, new Date("2026-10-10T08:00:00Z"))[0];      // Sat 21:00
    expect(late.window).toBeNull();
    expect(late.passed).toBe(true);
  });
  it("uses the New Zealand day, not the UTC day", () => {
    // 2026-10-10T11:30Z is already Sunday in NZ: Saturday's windows are no longer "today"
    const cards = todayCards(SPOTS, recs, {}, new Date("2026-10-10T11:30:00Z"));
    expect(cards[0].window).toBeNull();
    expect(cards[0].passed).toBe(false);
    expect(cards[1].window?.score).toBe(80);
  });
});

describe("the week list", () => {
  it("groups by NZ day in time order and marks today and tomorrow", () => {
    const days = weekDays(SPOTS, recs, new Date("2026-10-09T18:30:00Z"));
    expect(days.map((d) => [d.dateKey, d.relative])).toEqual([
      ["2026-10-10", "today"], ["2026-10-11", "tomorrow"], ["2026-10-14", null]]);
    expect(days[0].windows.map((w) => w.window.score)).toEqual([70, 88]);
    expect(days[2].windows[0].window.confidence).toBe("low");
  });
  it("leaves out windows that have ended", () => {
    const days = weekDays(SPOTS, recs, new Date("2026-10-09T20:00:00Z"));
    expect(days[0].windows.map((w) => w.window.score)).toEqual([88]);
  });
});

describe("freshness", () => {
  const source = (status: "ok" | "failed", last: string | null) => ({ status, last_success_utc: last, last_attempt_utc: "2026-10-10T12:00:00Z", error: null });
  const meta = (over: Partial<Meta["sources"]> = {}): Meta => ({
    schema_version: 1, generated_at: "2026-10-10T12:00:00Z",
    sources: { linz_tides: source("ok", "2026-10-10T12:00:00Z"), open_meteo_forecast: source("ok", "2026-10-10T12:00:00Z"),
               open_meteo_marine: source("ok", "2026-10-10T12:00:00Z"), ecan_flow: source("ok", "2026-10-10T12:00:00Z"), ...over },
  });
  it("is fresh within the limits: 6 hours for forecasts, 12 for river flow", () => {
    expect(freshness(meta(), "forecast", new Date("2026-10-10T17:59:00Z")).state).toBe("fresh");
    expect(freshness(meta(), "forecast", new Date("2026-10-10T18:01:00Z")).state).toBe("stale");
    expect(freshness(meta(), "flow", new Date("2026-10-10T23:59:00Z")).state).toBe("fresh");
    expect(freshness(meta(), "flow", new Date("2026-10-11T00:01:00Z")).state).toBe("stale");
  });
  it("goes by the older of the two forecast sources", () => {
    const m = meta({ open_meteo_marine: source("ok", "2026-10-10T04:00:00Z") });
    const f = freshness(m, "forecast", new Date("2026-10-10T12:30:00Z"));
    expect(f.state).toBe("stale");
    expect(f.age).toEqual({ unit: "hours", value: 9 });
  });
  it("says so when the last update failed, or when there has never been data", () => {
    expect(freshness(meta({ ecan_flow: source("failed", "2026-10-10T09:00:00Z") }), "flow", new Date("2026-10-10T12:30:00Z")).state).toBe("failed");
    expect(freshness(meta({ ecan_flow: source("failed", null) }), "flow", new Date("2026-10-10T12:30:00Z")).state).toBe("never");
    expect(freshness(null, "forecast", new Date()).state).toBe("never");
  });
});

describe("small helpers", () => {
  const hours = Array.from({ length: 30 }, (_, i) => ({ time_utc: new Date(Date.UTC(2026, 9, 10, 5 + i)).toISOString().replace(".000", "") })) as Conditions["hourly"];
  it("finds where each NZ day starts on the hourly axis", () => {
    expect(dayStarts(hours)).toEqual([{ index: 0, dateKey: "2026-10-10" }, { index: 6, dateKey: "2026-10-11" }]);
  });
  it("places an instant on the hourly axis", () => {
    expect(axisPosition(hours, "2026-10-10T07:30:00Z")).toBe(2.5);
    expect(axisPosition(hours, "2026-10-09T07:30:00Z")).toBeNull();
  });
  it("names moon phases and skies", () => {
    expect([0, 0.25, 0.5, 0.75, 0.97].map(moonPhaseIndex)).toEqual([0, 2, 4, 6, 0]);
    expect([0, 2, 3, 45, 53, 63, 81, 73, 95, null].map(skyOf)).toEqual(
      ["clear", "partly", "cloud", "fog", "drizzle", "rain", "rain", "snow", "storm", null]);
  });
});

describe("module boundary", () => {
  it("no component makes a network request of its own", () => {
    const dir = join(__dirname, "..", "components");
    for (const file of readdirSync(dir)) {
      const source = readFileSync(join(dir, file), "utf8");
      expect(source, file).not.toMatch(/\bfetch\s*\(|XMLHttpRequest|axios|\.\.\/data\/api|navigator\.sendBeacon/);
    }
  });
});
