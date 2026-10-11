// The only file that talks to Supabase for fishing records: sign-in, the records table, photos, the history table.
// The Supabase library is loaded only when this part of the page is used, so it never slows the forecast down.
import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { PHOTO_BUCKET, PHOTO_MAX_EDGE, SUPABASE_ANON_KEY, SUPABASE_URL } from "../config";
import { fitWithin } from "./form";
import { buildSnapshots, tripHours } from "./snapshot";
import type { FishingRecord, HistoryRow, RecordInput } from "./types";

export const recordsConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

let clientPromise: Promise<SupabaseClient> | null = null;
function client(): Promise<SupabaseClient> {
  if (!recordsConfigured) return Promise.reject(new Error("not-configured"));
  clientPromise ??= import("@supabase/supabase-js").then(({ createClient }) => createClient(SUPABASE_URL, SUPABASE_ANON_KEY));
  return clientPromise;
}

const fail = (error: { message: string } | null) => { if (error) throw new Error(error.message); };

// --- sign-in ---

export async function currentEmail(): Promise<string | null> {
  const { data } = await (await client()).auth.getSession();
  return data.session?.user.email ?? null;
}

/** Calls back whenever someone signs in or out (also in another tab). Returns a function that stops listening. */
export async function onSignInChange(callback: (email: string | null) => void): Promise<() => void> {
  const { data } = (await client()).auth.onAuthStateChange((_event: string, session: Session | null) => callback(session?.user.email ?? null));
  return () => data.subscription.unsubscribe();
}

export async function signIn(email: string, password: string): Promise<void> {
  fail((await (await client()).auth.signInWithPassword({ email, password })).error);
}

export async function signOut(): Promise<void> {
  fail((await (await client()).auth.signOut()).error);
}

// --- records ---

export async function listRecords(): Promise<FishingRecord[]> {
  const { data, error } = await (await client()).from("records").select("*").order("started_at", { ascending: false });
  fail(error);
  return (data ?? []) as FishingRecord[];
}

const HISTORY_COLUMNS = "time_utc,tide_height_m,tide_phase,air_temp_c,precip_prob_pct,weather_code,wind_speed_kmh,wind_gust_kmh," +
  "wind_dir_deg,wind_relative,wave_height_m,swell_height_m,sea_temp_c,is_daylight,river_flow_m3s,score,ruleset_version";

/** What the history table holds for this spot during the trip. A failed read is an error: saving must not silently drop the snapshot. */
async function snapshotsFor(input: RecordInput) {
  const hours = tripHours(input.started_at, input.ended_at);
  const { data, error } = await (await client()).from("conditions_hourly").select(HISTORY_COLUMNS)
    .eq("spot_id", input.spot_id).gte("time_utc", hours[0]).lte("time_utc", hours[hours.length - 1]).order("time_utc");
  fail(error);
  return buildSnapshots((data ?? []) as unknown as HistoryRow[], hours);
}

/** Add a record. The snapshots are taken now, for the hours of the trip (not for the moment of saving). */
export async function createRecord(id: string, input: RecordInput): Promise<void> {
  const snapshots = await snapshotsFor(input);
  fail((await (await client()).from("records").insert({ id, ...input, ...snapshots })).error);
}

/**
 * Change a record. The snapshots are taken again only when the spot or the times changed;
 * otherwise the ones saved with the record stay exactly as they were.
 */
export async function updateRecord(before: FishingRecord, input: RecordInput): Promise<void> {
  const same = (a: string, b: string) => new Date(a).getTime() === new Date(b).getTime();
  const moved = before.spot_id !== input.spot_id || !same(before.started_at, input.started_at) || !same(before.ended_at, input.ended_at);
  const snapshots = moved ? await snapshotsFor(input) : {};
  const { error } = await (await client()).from("records")
    .update({ ...input, ...snapshots, updated_at: new Date().toISOString() }).eq("id", before.id);
  fail(error);
  const dropped = before.photos.filter((p) => !input.photos.includes(p));
  if (dropped.length) await removePhotos(dropped);
}

/** Delete a record and its photo files. Photos go first: if that fails the record is still there and can be deleted again. */
export async function deleteRecord(record: FishingRecord): Promise<void> {
  if (record.photos.length) await removePhotos(record.photos);
  fail((await (await client()).from("records").delete().eq("id", record.id)).error);
}

// --- photos ---

export const photoUrl = (path: string) => `${SUPABASE_URL}/storage/v1/object/public/${PHOTO_BUCKET}/${path}`;

export async function removePhotos(paths: string[]): Promise<void> {
  fail((await (await client()).storage.from(PHOTO_BUCKET).remove(paths)).error);
}

/** Shrink a photo in the browser to at most PHOTO_MAX_EDGE on its longer side and re-encode it as JPEG. */
export async function shrinkPhoto(file: Blob): Promise<Blob> {
  // "from-image" applies the rotation phones store in the file, so portrait photos stay upright
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const { width, height } = fitWithin(bitmap.width, bitmap.height, PHOTO_MAX_EDGE);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("photo could not be encoded"))), "image/jpeg", 0.82));
}

/** Shrink and upload one photo for a record. Returns its path inside the bucket. */
export async function uploadPhoto(recordId: string, file: Blob): Promise<string> {
  const small = await shrinkPhoto(file);
  const path = `${recordId}/${crypto.randomUUID()}.jpg`;
  fail((await (await client()).storage.from(PHOTO_BUCKET).upload(path, small, { contentType: "image/jpeg", cacheControl: "31536000" })).error);
  return path;
}
