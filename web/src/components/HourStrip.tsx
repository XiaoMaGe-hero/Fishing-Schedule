import type { ReactNode } from "react";
import { dayStarts, type Hour } from "../data/derive";
import { formatDateKey, formatTime } from "../data/time";

/** A sideways-scrolling strip with one column per hour and a label where each day begins. */
export function HourStrip({ hours, label, renderHour }: { hours: Hour[]; label: string; renderHour: (hour: Hour) => ReactNode }) {
  const starts = new Map(dayStarts(hours).map((d) => [d.index, d.dateKey]));
  return (
    <div className="strip" role="group" aria-label={label} tabIndex={0}>
      {hours.map((hour, i) => (
        <div key={hour.time_utc} className={`strip__hour ${starts.has(i) ? "strip__hour--newday" : ""} ${hour.is_daylight ? "" : "strip__hour--night"}`}>
          <span className="strip__day">{starts.has(i) ? formatDateKey(starts.get(i)!) : ""}</span>
          <span className="strip__time">{formatTime(new Date(hour.time_utc))}</span>
          {renderHour(hour)}
        </div>
      ))}
    </div>
  );
}
