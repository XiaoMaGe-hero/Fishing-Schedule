// What the record form needs that is not drawing: New Zealand clock times, tidying input, photo sizes. No network here.
import { nzParts } from "../data/time";
import type { Catch, FishingRecord, RecordInput } from "./types";

const pad = (n: number) => String(n).padStart(2, "0");

/**
 * The UTC instant of a New Zealand clock time, whatever zone the device is in.
 * "2026-10-11", "06:30" -> 2026-10-10T17:30:00Z. Works out the offset twice so the days daylight saving changes come out right.
 */
export function nzToUtc(dateKey: string, time: string): Date {
  const [y, m, d] = dateKey.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  const wall = Date.UTC(y, m - 1, d, hh, mm);
  let guess = wall;
  for (let i = 0; i < 2; i++) {
    const p = nzParts(new Date(guess));
    const [py, pm, pd] = p.dateKey.split("-").map(Number);
    guess += wall - Date.UTC(py, pm - 1, pd, p.hour, p.minute);
  }
  return new Date(guess);
}

/** The New Zealand date and clock time of an instant, in the form the date and time inputs use. */
export function utcToNz(iso: string | Date): { date: string; time: string } {
  const p = nzParts(new Date(iso));
  return { date: p.dateKey, time: `${pad(p.hour)}:${pad(p.minute)}` };
}

export interface CatchDraft { species: string; count: string; size: string }
export interface Draft {
  spot_id: string; date: string; start: string; end: string; outcome: "catch" | "blank";
  catches: CatchDraft[]; bait: string; notes: string; video: string;
}

/** A new record starts as "the last three hours, here": the usual case is logging a trip that has just ended. */
export function emptyDraft(spotId: string, now: Date): Draft {
  const end = new Date(Math.floor(now.getTime() / 900_000) * 900_000);
  const start = new Date(end.getTime() - 3 * 3_600_000);
  const s = utcToNz(start), e = utcToNz(end);
  // a trip is entered on one calendar day; just after midnight, start at 00:00 instead of yesterday
  return { spot_id: spotId, date: e.date, start: s.date === e.date ? s.time : "00:00", end: e.time, outcome: "catch",
           catches: [{ species: "", count: "", size: "" }], bait: "", notes: "", video: "" };
}

export function draftFrom(record: FishingRecord): Draft {
  const s = utcToNz(record.started_at), e = utcToNz(record.ended_at);
  return {
    spot_id: record.spot_id, date: s.date, start: s.time, end: e.time, outcome: record.outcome,
    catches: record.catches.length
      ? record.catches.map((c) => ({ species: c.species, count: c.count?.toString() ?? "", size: c.size_cm?.toString() ?? "" }))
      : [{ species: "", count: "", size: "" }],
    bait: record.bait_and_rig ?? "", notes: record.notes ?? "", video: record.video_url ?? "",
  };
}

/** The same test the database applies to video_url. */
export const isYouTubeUrl = (url: string) => /^https:\/\/(www\.)?(youtube\.com|youtu\.be)\//.test(url);

export type DraftProblem = "date" | "time-order" | "video" | "catch-number";

const number = (text: string): number | null | undefined => {
  if (!text.trim()) return null;
  const n = Number(text);
  return Number.isFinite(n) && n >= 0 ? n : undefined;
};

/** Check a draft and turn it into what gets saved. A blank trip never keeps catches; empty catch lines are dropped. */
export function toInput(draft: Draft, photos: string[]): { input: RecordInput } | { problem: DraftProblem } {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.date) || !/^\d{2}:\d{2}$/.test(draft.start) || !/^\d{2}:\d{2}$/.test(draft.end)) return { problem: "date" };
  const started = nzToUtc(draft.date, draft.start), ended = nzToUtc(draft.date, draft.end);
  if (!(ended.getTime() > started.getTime())) return { problem: "time-order" };
  const video = draft.video.trim();
  if (video && !isYouTubeUrl(video)) return { problem: "video" };

  const catches: Catch[] = [];
  if (draft.outcome === "catch") {
    for (const line of draft.catches) {
      const count = number(line.count), size = number(line.size);
      if (count === undefined || size === undefined) return { problem: "catch-number" };
      const species = line.species.trim();
      if (!species && count === null && size === null) continue;
      catches.push({ species, count, size_cm: size });
    }
  }
  const iso = (d: Date) => d.toISOString().replace(".000Z", "Z");
  return { input: {
    spot_id: draft.spot_id, started_at: iso(started), ended_at: iso(ended), outcome: draft.outcome, catches,
    bait_and_rig: draft.bait.trim() || null, notes: draft.notes.trim() || null, photos, video_url: video || null,
  } };
}

/** Size after shrinking so the longer side is at most `maxEdge`. Never enlarges. */
export function fitWithin(width: number, height: number, maxEdge: number): { width: number; height: number } {
  const longer = Math.max(width, height);
  if (longer <= maxEdge) return { width, height };
  const scale = maxEdge / longer;
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}
