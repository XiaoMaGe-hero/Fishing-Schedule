import { copy } from "../copy";
import type { Freshness as FreshnessInfo } from "../data/derive";

export function ageText(f: FreshnessInfo): string {
  if (!f.age) return "";
  const c = copy.freshness;
  return f.age.unit === "minutes" ? c.minutes(f.age.value) : f.age.unit === "hours" ? c.hours(f.age.value) : c.days(f.age.value);
}

/** "Updated 2 hours ago", turning to a warning when the data is old or the last update failed. */
export function Freshness({ info }: { info: FreshnessInfo }) {
  const c = copy.freshness;
  const text = info.state === "never" ? c.never
    : info.state === "failed" ? c.failed(ageText(info))
    : info.state === "stale" ? c.stale(ageText(info))
    : c.updated(ageText(info));
  return <p className={`freshness freshness--${info.state}`} data-freshness={info.state}>{text}</p>;
}
