// The page. This file decides what data each part gets; the parts in components/ only draw what they are given.
import { useEffect, useMemo, useState } from "react";
import { Footer } from "./components/Footer";
import { Freshness } from "./components/Freshness";
import { Hero } from "./components/Hero";
import { RiverFlow } from "./components/RiverFlow";
import { SeaTemp } from "./components/SeaTemp";
import { SpotMap } from "./components/SpotMap";
import { TideTable } from "./components/TideTable";
import { Timeline } from "./components/Timeline";
import { TodayCards } from "./components/TodayCards";
import { WeatherStrip } from "./components/WeatherStrip";
import { WeekList } from "./components/WeekList";
import { WindStrip } from "./components/WindStrip";
import { VIDEO_ID } from "./config";
import { copy } from "./copy";
import { freshness, todayCards, upcomingHours, weekDays, type Block } from "./data/derive";
import { SPOTS, useForecast, useRiverFlow } from "./data/useForecast";

/** The current time, refreshed every minute. `?now=2026-10-10T02:00:00Z` pins it, for testing. */
function useNow(): Date {
  const pinned = useMemo(() => {
    const value = new URLSearchParams(window.location.search).get("now");
    const date = value ? new Date(value) : null;
    return date && !Number.isNaN(date.getTime()) ? date : null;
  }, []);
  const [now, setNow] = useState(() => pinned ?? new Date());
  useEffect(() => {
    if (pinned) return;
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, [pinned]);
  return now;
}

export function App() {
  const now = useNow();
  const forecast = useForecast();
  const river = useRiverFlow();
  const [spotId, setSpotId] = useState(SPOTS[0]?.id ?? "");

  const fresh = useMemo(() => Object.fromEntries(
    (["tide", "forecast", "flow"] as Block[]).map((b) => [b, freshness(forecast.meta, b, now)]),
  ) as Record<Block, ReturnType<typeof freshness>>, [forecast.meta, now]);

  if (forecast.status !== "ready") {
    return (
      <main className="page">
        <Hero videoId={VIDEO_ID} />
        {forecast.status === "loading" ? (
          <p className="status" role="status">{copy.loading}</p>
        ) : (
          <section className="problem" role="alert">
            <h2>{copy.errors.loadTitle}</h2>
            <p>{forecast.errorKind === "not-configured" ? copy.errors.notConfigured : copy.errors.loadBody}</p>
            {forecast.errorKind !== "not-configured" && <button type="button" className="button" onClick={forecast.reload}>{copy.errors.retry}</button>}
          </section>
        )}
      </main>
    );
  }

  const conditions = forecast.conditions[spotId];
  const windows = forecast.recommendations?.spots.find((s) => s.spot_id === spotId)?.windows ?? [];
  // the current hour onwards; falls back to everything if the data is so old that no hour is left
  const left = conditions ? upcomingHours(conditions.hourly, now) : [];
  const upcoming = left.length ? left : conditions?.hourly ?? [];
  const startIndex = conditions ? conditions.hourly.length - upcoming.length : 0;

  return (
    <main className="page">
      <Hero videoId={VIDEO_ID} />

      {forecast.recommendations ? (
        <>
          <TodayCards cards={todayCards(SPOTS, forecast.recommendations, forecast.conditions, now)} />
          <section className="section" aria-labelledby="week-heading">
            <h2 id="week-heading">{copy.week.heading}</h2>
            <WeekList days={weekDays(SPOTS, forecast.recommendations, now)} />
            <Freshness info={fresh.forecast} />
            <SpotMap spots={SPOTS} />
          </section>
        </>
      ) : (
        <p className="problem problem--inline" role="alert">{copy.errors.partial}</p>
      )}

      {conditions && (
        <section className="section" aria-labelledby="conditions-heading">
          <h2 id="conditions-heading">{copy.timeline.heading}</h2>
          <div className="segmented segmented--spots" role="group" aria-label={copy.timeline.chooseSpot}>
            {SPOTS.map((s) => (
              <button key={s.id} type="button" aria-pressed={s.id === spotId} onClick={() => setSpotId(s.id)}>{s.name}</button>
            ))}
          </div>
          <Timeline hours={conditions.hourly} windows={windows} startIndex={startIndex} />
          <Freshness info={fresh.forecast} />

          <h3>{copy.tideTable.heading}</h3>
          <TideTable conditions={conditions} />
          <Freshness info={fresh.tide} />

          <h3>{copy.seaTemp.heading}</h3>
          <SeaTemp hours={upcoming} />

          <h3>{copy.weather.heading}</h3>
          <WeatherStrip hours={upcoming} />

          <h3>{copy.windTable.heading}</h3>
          <WindStrip hours={upcoming} />
          <Freshness info={fresh.forecast} />
        </section>
      )}

      <RiverFlow status={river.status} data={river.data} freshness={fresh.flow} onOpen={river.load} />
      <Footer freshness={fresh} />
    </main>
  );
}
