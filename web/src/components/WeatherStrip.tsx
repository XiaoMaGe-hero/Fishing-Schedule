import { copy } from "../copy";
import { skyOf, type Hour } from "../data/derive";
import { HourStrip } from "./HourStrip";
import { WeatherIcon } from "./WeatherIcon";

/** Hour by hour: sky, air temperature and chance of rain. */
export function WeatherStrip({ hours }: { hours: Hour[] }) {
  return (
    <HourStrip hours={hours} label={copy.weather.heading} renderHour={(h) => (
      <>
        <WeatherIcon sky={skyOf(h.weather_code)} />
        <span className="strip__main">{h.air_temp_c === null ? "–" : `${Math.round(h.air_temp_c)}°`}</span>
        <span className={`strip__sub ${(h.precip_prob_pct ?? 0) >= 40 ? "strip__sub--wet" : ""}`}>
          {h.precip_prob_pct === null ? "" : `${Math.round(h.precip_prob_pct)}%`}
        </span>
      </>
    )} />
  );
}
