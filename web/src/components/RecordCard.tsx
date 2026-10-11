import { useState } from "react";
import { copy } from "../copy";
import type { Spot } from "../data/derive";
import { formatDay, formatTime } from "../data/time";
import { photoUrl } from "../records/api";
import { summarise, tripHours } from "../records/snapshot";
import type { Catch, FishingRecord } from "../records/types";

const one = (n: number) => (Math.round(n * 10) / 10).toFixed(1);
const whole = (n: number) => String(Math.round(n));

function catchText(c: Catch): string {
  const name = c.species || copy.records.unnamed;
  const head = c.count !== null ? `${c.count} × ${name}` : name;
  return c.size_cm !== null ? `${head}, ${c.size_cm} cm` : head;
}

/** The conditions saved with the record, as a short table. They are forecast values for the hours of the trip. */
function Conditions({ record }: { record: FishingRecord }) {
  const c = copy.records;
  const snapshot = record.conditions_snapshot;
  if (!snapshot?.length) return <p className="record__nosnap">{c.noSnapshot}</p>;
  const s = summarise(snapshot);
  const all = tripHours(record.started_at, record.ended_at).length;
  const score = record.score_snapshot;
  const rows: [string, string][] = [];
  rows.push([c.score, score ? `${whole(score.mean_score)} ${c.scoreNote(score.ruleset_version)}` : c.notScored]);
  if (s.tide) rows.push([c.tide, `${one(s.tide.from)} → ${one(s.tide.to)} m, ${c.tidePhase[s.tide.phase]}`]);
  if (s.windKmh !== null) {
    const parts = [`${whole(s.windKmh)} km/h`];
    if (s.gustKmh !== null) parts.push(`${c.gusts} ${whole(s.gustKmh)}`);
    if (s.windRelative) parts.push(copy.windTable[s.windRelative].toLowerCase());
    rows.push([c.wind, parts.join(", ")]);
  }
  if (s.waveM !== null) rows.push([c.waves, `${one(s.waveM)} m`]);
  if (s.seaTempC !== null) rows.push([c.sea, `${one(s.seaTempC)} °C`]);
  if (s.rainPct !== null) rows.push([c.rain, `${whole(s.rainPct)}%`]);
  if (s.flowM3s !== null) rows.push([c.river, `${whole(s.flowM3s)} ${copy.river.unit}`]);
  return (
    <div className="record__conditions">
      <h4>{c.conditionsHeading}</h4>
      <dl>{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      <p className="note">{s.hours < all ? `${c.partial(s.hours, all)} ` : ""}{c.conditionsNote}</p>
    </div>
  );
}

interface Props { record: FishingRecord; spots: Spot[]; canEdit: boolean; onEdit: () => void; onDelete: () => Promise<void> }

export function RecordCard({ record, spots, canEdit, onEdit, onDelete }: Props) {
  const c = copy.records;
  const [asking, setAsking] = useState(false);
  const [removing, setRemoving] = useState(false);
  const start = new Date(record.started_at), end = new Date(record.ended_at);
  const spot = spots.find((s) => s.id === record.spot_id)?.name ?? record.spot_id;

  return (
    <article className={`record record--${record.outcome}`}>
      <header className="record__head">
        <div>
          <h3>{formatDay(start)}</h3>
          <p className="record__when">{formatTime(start)}<span aria-hidden="true">–</span><span className="visually-hidden"> to </span>{formatTime(end)} · {spot}</p>
        </div>
        <span className={`record__outcome record__outcome--${record.outcome}`}>{c.outcome[record.outcome]}</span>
      </header>

      {record.catches.length > 0 && <ul className="record__catches">{record.catches.map((x, i) => <li key={i}>{catchText(x)}</li>)}</ul>}
      {record.bait_and_rig && <p className="record__line"><span>{c.bait}</span> {record.bait_and_rig}</p>}
      {record.notes && <p className="record__notes">{record.notes}</p>}

      {record.photos.length > 0 && (
        <ul className="record__photos">
          {record.photos.map((path, i) => (
            <li key={path}><a href={photoUrl(path)} target="_blank" rel="noreferrer"><img src={photoUrl(path)} alt={c.photoAlt(i + 1)} loading="lazy" /></a></li>
          ))}
        </ul>
      )}
      {record.video_url && <p className="record__video"><a href={record.video_url} target="_blank" rel="noreferrer">{c.video}</a></p>}

      <Conditions record={record} />

      {canEdit && (
        <div className="record__actions">
          {asking ? (
            <>
              <span>{c.removeAsk}</span>
              <button type="button" className="button button--warn" disabled={removing}
                      onClick={() => { setRemoving(true); onDelete().finally(() => { setRemoving(false); setAsking(false); }); }}>
                {removing ? c.removing : c.removeYes}
              </button>
              <button type="button" className="button" disabled={removing} onClick={() => setAsking(false)}>{c.removeNo}</button>
            </>
          ) : (
            <>
              <button type="button" className="button" onClick={onEdit}>{c.edit}</button>
              <button type="button" className="button button--warn" onClick={() => setAsking(true)}>{c.remove}</button>
            </>
          )}
        </div>
      )}
    </article>
  );
}
