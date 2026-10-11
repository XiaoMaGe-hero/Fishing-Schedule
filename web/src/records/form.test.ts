import { describe, expect, it } from "vitest";
import { draftFrom, emptyDraft, fitWithin, isYouTubeUrl, nzToUtc, toInput, utcToNz, type Draft } from "./form";
import type { FishingRecord } from "./types";

const iso = (d: Date) => d.toISOString();

describe("New Zealand clock times", () => {
  it("converts in summer time (UTC+13) and winter time (UTC+12)", () => {
    expect(iso(nzToUtc("2026-10-11", "06:30"))).toBe("2026-10-10T17:30:00.000Z");
    expect(iso(nzToUtc("2026-07-01", "06:30"))).toBe("2026-06-30T18:30:00.000Z");
  });
  it("is right on both sides of the daylight-saving switches", () => {
    // clocks go forward 02:00 -> 03:00 on Sun 27 Sep 2026, back 03:00 -> 02:00 on Sun 4 Apr 2027
    expect(iso(nzToUtc("2026-09-27", "01:30"))).toBe("2026-09-26T13:30:00.000Z");
    expect(iso(nzToUtc("2026-09-27", "03:30"))).toBe("2026-09-26T14:30:00.000Z");
    expect(iso(nzToUtc("2027-04-04", "01:30"))).toBe("2027-04-03T12:30:00.000Z");
    expect(iso(nzToUtc("2027-04-04", "04:00"))).toBe("2027-04-03T16:00:00.000Z");
  });
  it("round-trips", () => {
    expect(utcToNz("2026-10-10T17:30:00Z")).toEqual({ date: "2026-10-11", time: "06:30" });
    expect(utcToNz(nzToUtc("2026-12-31", "23:45"))).toEqual({ date: "2026-12-31", time: "23:45" });
  });
});

const draft = (over: Partial<Draft> = {}): Draft => ({
  spot_id: "new-brighton-pier", date: "2026-10-11", start: "06:30", end: "09:15", outcome: "catch",
  catches: [{ species: " Kahawai ", count: "2", size: "45" }, { species: "", count: "", size: "" }],
  bait: " pilchard ", notes: "", video: "", ...over,
});

describe("toInput", () => {
  it("builds what gets saved, in UTC, dropping empty catch lines", () => {
    expect(toInput(draft(), ["a/b.jpg"])).toEqual({ input: {
      spot_id: "new-brighton-pier", started_at: "2026-10-10T17:30:00Z", ended_at: "2026-10-10T20:15:00Z", outcome: "catch",
      catches: [{ species: "Kahawai", count: 2, size_cm: 45 }], bait_and_rig: "pilchard", notes: null, photos: ["a/b.jpg"], video_url: null,
    } });
  });
  it("saves a blank trip with no catches, whatever was typed in the catch lines", () => {
    const result = toInput(draft({ outcome: "blank" }), []);
    expect("input" in result && result.input.catches).toEqual([]);
    expect("input" in result && result.input.outcome).toBe("blank");
  });
  it("allows a catch with the species, count and size left empty", () => {
    const result = toInput(draft({ catches: [{ species: "", count: "", size: "" }] }), []);
    expect("input" in result && result.input.catches).toEqual([]);
  });
  it("names the problem instead of saving something wrong", () => {
    expect(toInput(draft({ end: "06:30" }), [])).toEqual({ problem: "time-order" });
    expect(toInput(draft({ end: "05:00" }), [])).toEqual({ problem: "time-order" });
    expect(toInput(draft({ date: "" }), [])).toEqual({ problem: "date" });
    expect(toInput(draft({ video: "https://vimeo.com/1" }), [])).toEqual({ problem: "video" });
    expect(toInput(draft({ catches: [{ species: "Cod", count: "two", size: "" }] }), [])).toEqual({ problem: "catch-number" });
  });
  it("accepts YouTube links only", () => {
    expect(isYouTubeUrl("https://youtu.be/abc")).toBe(true);
    expect(isYouTubeUrl("https://www.youtube.com/watch?v=abc")).toBe(true);
    expect(isYouTubeUrl("http://youtube.com/watch?v=abc")).toBe(false);
    expect(isYouTubeUrl("https://youtube.com.evil.example/")).toBe(false);
  });
});

describe("drafts", () => {
  it("starts a new record as the last three hours", () => {
    const d = emptyDraft("southshore", new Date("2026-10-10T20:22:00Z")); // 09:22 NZDT
    expect([d.date, d.start, d.end]).toEqual(["2026-10-11", "06:15", "09:15"]);
  });
  it("opens an existing record with the same values it was saved with", () => {
    const saved = toInput(draft(), []);
    if (!("input" in saved)) throw new Error("expected input");
    const record = { ...saved.input, id: "x", conditions_snapshot: null, score_snapshot: null, created_at: "", updated_at: "" } as FishingRecord;
    const reopened = toInput(draftFrom(record), []);
    expect(reopened).toEqual(saved);
  });
});

describe("fitWithin", () => {
  it("shrinks so the longer side is at most the limit, keeping the shape", () => {
    expect(fitWithin(4032, 3024, 1600)).toEqual({ width: 1600, height: 1200 });
    expect(fitWithin(3024, 4032, 1600)).toEqual({ width: 1200, height: 1600 });
  });
  it("never enlarges a small photo", () => {
    expect(fitWithin(800, 600, 1600)).toEqual({ width: 800, height: 600 });
    expect(fitWithin(1600, 900, 1600)).toEqual({ width: 1600, height: 900 });
  });
});
