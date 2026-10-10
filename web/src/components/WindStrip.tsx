import { copy } from "../copy";
import type { Hour } from "../data/derive";
import { HourStrip } from "./HourStrip";

/** Hour by hour: wind speed, gusts, direction, and whether it blows onshore, offshore or across. */
export function WindStrip({ hours }: { hours: Hour[] }) {
  const c = copy.windTable;
  return (
    <HourStrip hours={hours} label={c.heading} renderHour={(h) => (
      <>
        {h.wind_dir_deg === null ? <span className="arrow arrow--none" /> : (
          // the arrow points the way the wind is going; wind_dir_deg is where it comes from
          <svg className="arrow" viewBox="0 0 24 24" role="img" aria-label={`${c.from} ${Math.round(h.wind_dir_deg)}°`}
               style={{ transform: `rotate(${h.wind_dir_deg + 180}deg)` }}>
            <path d="M12 3l5 9h-3.5v9h-3v-9H7z" />
          </svg>
        )}
        <span className="strip__main">{h.wind_speed_kmh === null ? "–" : Math.round(h.wind_speed_kmh)}</span>
        <span className="strip__sub">{h.wind_gust_kmh === null ? "" : `${c.gust} ${Math.round(h.wind_gust_kmh)}`}</span>
        <span className={`strip__tag strip__tag--${h.wind_relative ?? "none"}`}>
          {h.wind_relative === "onshore" ? c.onshore : h.wind_relative === "offshore" ? c.offshore : h.wind_relative === "cross" ? c.cross : c.unknown}
        </span>
      </>
    )} />
  );
}
