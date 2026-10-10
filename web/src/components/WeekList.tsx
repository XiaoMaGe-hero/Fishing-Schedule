import { useState } from "react";
import { copy } from "../copy";
import type { WeekDay } from "../data/derive";
import { formatDateKey, formatTime } from "../data/time";

/** The week's recommended windows, day by day. Tap one to see how its score was reached. */
export function WeekList({ days }: { days: WeekDay[] }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!days.length) return <p className="empty">{copy.week.empty}</p>;
  return (
    <ol className="week">
      {days.map((day) => (
        <li key={day.dateKey} className="week__day">
          <h3>
            {day.relative === "today" ? copy.week.today : day.relative === "tomorrow" ? copy.week.tomorrow : formatDateKey(day.dateKey)}
            {day.relative && <span className="week__date"> {formatDateKey(day.dateKey)}</span>}
          </h3>
          <ul>
            {day.windows.map(({ spot, window }) => {
              const id = `${spot.id}-${window.start_utc}`;
              const expanded = open === id;
              return (
                <li key={id} className="window" data-confidence={window.confidence}>
                  <button type="button" className="window__row" aria-expanded={expanded} onClick={() => setOpen(expanded ? null : id)}>
                    <span className="window__time">{formatTime(new Date(window.start_utc))}–{formatTime(new Date(window.end_utc))}</span>
                    <span className="window__spot">{spot.name}</span>
                    {window.confidence === "low" && <span className="badge badge--low">{copy.week.lowConfidence}</span>}
                    <span className="window__score">{Math.round(window.score)}</span>
                  </button>
                  {expanded && (
                    <div className="window__why">
                      <h4>{copy.week.whyHeading}</h4>
                      {window.confidence === "low" && <p className="window__lowhint">{copy.week.lowConfidenceHint}</p>}
                      <table>
                        <tbody>
                          {window.reasons.map((r) => (
                            <tr key={r.rule}>
                              <th scope="row">{r.rule}</th>
                              <td className="window__bar">
                                {r.score === null ? copy.week.skipped
                                  : <span style={{ width: `${Math.round(r.score * 100)}%` }} title={`${Math.round(r.score * 100)} / 100`} />}
                              </td>
                              <td>{r.reason}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </li>
      ))}
    </ol>
  );
}
