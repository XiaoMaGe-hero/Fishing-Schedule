// Add or edit one trip. Built to be finished with a thumb in under a minute: the times are already filled in
// for "the last three hours", and a blank trip needs only the spot and one tap on "Blank".
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { copy } from "../copy";
import type { Spot } from "../data/derive";
import { createRecord, photoUrl, removePhotos, updateRecord, uploadPhoto } from "../records/api";
import { draftFrom, emptyDraft, toInput, type CatchDraft, type Draft } from "../records/form";
import type { FishingRecord } from "../records/types";

interface Props { spots: Spot[]; now: Date; record: FishingRecord | null; onSaved: () => void; onCancel: () => void }

export function RecordForm({ spots, now, record, onSaved, onCancel }: Props) {
  const c = copy.form;
  const [draft, setDraft] = useState<Draft>(() => (record ? draftFrom(record) : emptyDraft(spots[0]?.id ?? "", now)));
  const [kept, setKept] = useState<string[]>(record?.photos ?? []); // photos already uploaded that stay
  const [added, setAdded] = useState<File[]>([]);                    // photos chosen now, not uploaded yet
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState("");

  const previews = useMemo(() => added.map((file) => URL.createObjectURL(file)), [added]);
  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews]);

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const setCatch = (index: number, change: Partial<CatchDraft>) =>
    set("catches", draft.catches.map((line, i) => (i === index ? { ...line, ...change } : line)));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const checked = toInput(draft, kept);
    if ("problem" in checked) { setProblem(c.problems[checked.problem]); return; }
    setProblem("");
    setSaving(true);
    const id = record?.id ?? crypto.randomUUID();
    const uploaded: string[] = [];
    try {
      for (const file of added) uploaded.push(await uploadPhoto(id, file));
      const input = { ...checked.input, photos: [...kept, ...uploaded] };
      if (record) await updateRecord(record, input); else await createRecord(id, input);
      onSaved();
    } catch (error) {
      // the trip was not saved, so the photos just uploaded for it must not be left behind
      if (uploaded.length) await removePhotos(uploaded).catch(() => undefined);
      setProblem(c.saveFailed(error instanceof Error ? error.message : String(error)));
      setSaving(false);
    }
  }

  return (
    <form className="form" onSubmit={submit} aria-label={record ? c.editHeading : c.newHeading}>
      <h3>{record ? c.editHeading : c.newHeading}</h3>

      <label className="field"><span>{c.spot}</span>
        <select value={draft.spot_id} onChange={(e) => set("spot_id", e.target.value)}>
          {spots.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select></label>

      <div className="form__when">
        <label className="field"><span>{c.date}</span><input type="date" required value={draft.date} onChange={(e) => set("date", e.target.value)} /></label>
        <label className="field"><span>{c.start}</span><input type="time" required value={draft.start} onChange={(e) => set("start", e.target.value)} /></label>
        <label className="field"><span>{c.end}</span><input type="time" required value={draft.end} onChange={(e) => set("end", e.target.value)} /></label>
      </div>
      <p className="note">{c.nzTime}</p>

      <div className="field"><span id="outcome-label">{c.outcome}</span>
        <div className="segmented" role="group" aria-labelledby="outcome-label">
          {(["catch", "blank"] as const).map((o) => (
            <button key={o} type="button" aria-pressed={draft.outcome === o} onClick={() => set("outcome", o)}>{copy.records.outcome[o]}</button>
          ))}
        </div></div>

      {draft.outcome === "catch" && (
        <fieldset className="form__catches">
          <legend>{c.catches}</legend>
          {draft.catches.map((line, i) => (
            <div className="form__catch" key={i}>
              <label className="field field--wide"><span>{c.species}</span><input type="text" value={line.species} onChange={(e) => setCatch(i, { species: e.target.value })} /></label>
              <label className="field"><span>{c.count}</span><input type="number" inputMode="numeric" min="0" step="1" value={line.count} onChange={(e) => setCatch(i, { count: e.target.value })} /></label>
              <label className="field"><span>{c.size}</span><input type="number" inputMode="decimal" min="0" step="any" value={line.size} onChange={(e) => setCatch(i, { size: e.target.value })} /></label>
              {draft.catches.length > 1 && (
                <button type="button" className="link form__catch-remove" onClick={() => set("catches", draft.catches.filter((_, j) => j !== i))}>{c.removeCatch}</button>
              )}
            </div>
          ))}
          <button type="button" className="link" onClick={() => set("catches", [...draft.catches, { species: "", count: "", size: "" }])}>{c.addCatch}</button>
        </fieldset>
      )}

      <label className="field"><span>{c.bait}</span><input type="text" value={draft.bait} onChange={(e) => set("bait", e.target.value)} /></label>
      <label className="field"><span>{c.notes}</span><textarea rows={3} value={draft.notes} onChange={(e) => set("notes", e.target.value)} /></label>

      <div className="field"><label htmlFor="record-photos">{c.photos}</label>
        {(kept.length > 0 || added.length > 0) && (
          <ul className="form__photos">
            {kept.map((path) => (
              <li key={path}><img src={photoUrl(path)} alt="" />
                <button type="button" aria-label={c.removePhoto} onClick={() => setKept(kept.filter((p) => p !== path))}>×</button></li>
            ))}
            {added.map((file, i) => (
              <li key={previews[i]}><img src={previews[i]} alt="" />
                <button type="button" aria-label={c.removePhoto} onClick={() => setAdded(added.filter((f) => f !== file))}>×</button></li>
            ))}
          </ul>
        )}
        <input id="record-photos" type="file" accept="image/*" multiple
               onChange={(e) => { setAdded([...added, ...Array.from(e.target.files ?? [])]); e.target.value = ""; }} />
        <p className="note">{c.photosHint}</p></div>

      <label className="field"><span>{c.video}</span>
        <input type="url" inputMode="url" placeholder="https://youtu.be/…" value={draft.video} onChange={(e) => set("video", e.target.value)} /></label>

      {problem && <p className="form__problem" role="alert">{problem}</p>}
      <div className="form__actions">
        <button type="submit" className="button button--solid" disabled={saving}>{saving ? c.saving : c.save}</button>
        <button type="button" className="button" disabled={saving} onClick={onCancel}>{c.cancel}</button>
      </div>
    </form>
  );
}
