// Site settings that are not data. Change values here; no other file needs to know.

/** YouTube video shown at the top, e.g. "dQw4w9WgXcQ" from https://www.youtube.com/watch?v=dQw4w9WgXcQ. Empty = no video yet. */
export const VIDEO_ID = "";

/** Where the published JSON files live (public Supabase bucket). Set VITE_DATA_BASE_URL; see .env.example. */
export const DATA_BASE_URL: string = (import.meta.env.VITE_DATA_BASE_URL ?? "").replace(/\/+$/, "");

/** Hours after which a block is flagged as possibly out of date. */
export const STALE_AFTER_HOURS = { forecast: 6, flow: 12 } as const;

/** Hours shown at once in the conditions chart before swiping. */
export const CHART_VISIBLE_HOURS = 36;

/** Fishing records live in Supabase. Both values are public; see .env.example. Empty = records are switched off. */
export const SUPABASE_URL: string = (import.meta.env.VITE_SUPABASE_URL ?? "").replace(/\/+$/, "");
export const SUPABASE_ANON_KEY: string = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";

/** Photos are shrunk in the browser so the longer side is at most this many pixels before upload. */
export const PHOTO_MAX_EDGE = 1600;
export const PHOTO_BUCKET = "record-photos";
