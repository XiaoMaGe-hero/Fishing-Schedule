import { copy } from "../copy";
import { moonPhaseIndex } from "../data/derive";
import type { Conditions } from "../data/generated/types";
import { formatDateKey, formatTime, nzDateKey } from "../data/time";

function Moon({ fraction }: { fraction: number }) {
  // lit part of the disc: 0 = new (dark), 0.5 = full; drawn as two half-ellipses
  const lit = fraction <= 0.5 ? fraction * 2 : (1 - fraction) * 2;
  const waxing = fraction <= 0.5;
  const rx = Math.abs(1 - lit * 2) * 7;
  const outer = waxing ? "M8,1 A7,7 0 0,1 8,15" : "M8,1 A7,7 0 0,0 8,15";
  const inner = `A${rx.toFixed(2)},7 0 0,${(lit > 0.5) === waxing ? 0 : 1} 8,1`;
  return (
    <svg className="moon" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="7" className="moon__dark" />
      <path d={`${outer} ${inner} Z`} className="moon__lit" />
    </svg>
  );
}

/** Official high and low tides, sunrise, sunset and moon for each day. */
export function TideTable({ conditions }: { conditions: Conditions }) {
  return (
    <div className="table-wrap">
      <table className="tides">
        <tbody>
          {conditions.days.map((day) => {
            const events = conditions.tide_events.filter((e) => nzDateKey(new Date(e.time_utc)) === day.date_local);
            return (
              <tr key={day.date_local}>
                <th scope="row">{formatDateKey(day.date_local)}</th>
                <td>
                  <ul className="tides__events">
                    {events.map((e) => (
                      <li key={e.time_utc} className={`tides__event tides__event--${e.type}`}>
                        <span className="tides__type">{e.type === "high" ? copy.tideTable.high : copy.tideTable.low}</span>{" "}
                        <span className="tides__time">{formatTime(new Date(e.time_utc))}</span>{" "}
                        <span className="tides__height">{e.height_m.toFixed(1)} m</span>
                      </li>
                    ))}
                  </ul>
                  <p className="tides__sun">
                    {copy.tideTable.sunrise} {formatTime(new Date(day.sunrise_utc))}, {copy.tideTable.sunset.toLowerCase()} {formatTime(new Date(day.sunset_utc))}
                    <span className="tides__moon"><Moon fraction={day.moon_phase} /> {copy.moonPhases[moonPhaseIndex(day.moon_phase)]}</span>
                  </p>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {conditions.tide_offset_assumed && <p className="note">{copy.tideTable.offsetAssumed}</p>}
    </div>
  );
}
