// Site settings that are not data. Change values here; no other file needs to know.

/** YouTube video shown at the top, e.g. "dQw4w9WgXcQ" from https://www.youtube.com/watch?v=dQw4w9WgXcQ. Empty = no video yet. */
export const VIDEO_ID = "";

/** Where the published JSON files live (public Supabase bucket). Set VITE_DATA_BASE_URL; see .env.example. */
export const DATA_BASE_URL: string = (import.meta.env.VITE_DATA_BASE_URL ?? "").replace(/\/+$/, "");

/** Hours after which a block is flagged as possibly out of date. */
export const STALE_AFTER_HOURS = { forecast: 6, flow: 12 } as const;

/** Hours shown at once in the conditions chart before swiping. */
export const CHART_VISIBLE_HOURS = 36;
