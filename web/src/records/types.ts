// Shapes of a fishing record. They mirror schemas/sql/records.sql.

export interface Catch { species: string; count: number | null; size_cm: number | null }

/** One hour of conditions as stored in the conditions_hourly table. */
export interface HistoryRow {
  time_utc: string;
  tide_height_m: number | null;
  tide_phase: "rising" | "falling" | null;
  air_temp_c: number | null;
  precip_prob_pct: number | null;
  weather_code: number | null;
  wind_speed_kmh: number | null;
  wind_gust_kmh: number | null;
  wind_dir_deg: number | null;
  wind_relative: "onshore" | "offshore" | "cross" | null;
  wave_height_m: number | null;
  swell_height_m: number | null;
  sea_temp_c: number | null;
  is_daylight: boolean;
  river_flow_m3s: number | null;
  score: number | null;
  ruleset_version: number | null;
}

/** What a record keeps about each hour of the trip: the conditions, without the score. */
export type ConditionsHour = Omit<HistoryRow, "score" | "ruleset_version">;

export interface ScoreSnapshot {
  hours: { time_utc: string; score: number; ruleset_version: number | null }[];
  mean_score: number;
  ruleset_version: number | null;
}

/** What the form collects. */
export interface RecordInput {
  spot_id: string;
  started_at: string; // UTC ISO
  ended_at: string;
  outcome: "catch" | "blank";
  catches: Catch[];
  bait_and_rig: string | null;
  notes: string | null;
  photos: string[]; // paths inside the photo bucket
  video_url: string | null;
}

export interface FishingRecord extends RecordInput {
  id: string;
  conditions_snapshot: ConditionsHour[] | null;
  score_snapshot: ScoreSnapshot | null;
  created_at: string;
  updated_at: string;
}
