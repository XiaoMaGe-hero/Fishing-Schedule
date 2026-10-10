import type { Sky } from "../data/derive";

const sun = <circle cx="12" cy="12" r="5" className="wx__sun" />;
const cloud = <path d="M7 18h10a4 4 0 0 0 .6-7.95A5.5 5.5 0 0 0 7.1 9.6 4.2 4.2 0 0 0 7 18z" className="wx__cloud" />;
const drops = (n: number) => Array.from({ length: n }, (_, i) => (
  <path key={i} d={`M${9 + i * 3} 19.5l-1 2.5`} className="wx__drop" />
));

/** A small drawing of the sky for a WMO weather code group. */
export function WeatherIcon({ sky }: { sky: Sky | null }) {
  if (!sky) return <span className="wx wx--none" />;
  return (
    <svg className="wx" viewBox="0 0 24 24" role="img" aria-label={sky}>
      {sky === "clear" && sun}
      {sky === "partly" && <><circle cx="9" cy="9" r="4" className="wx__sun" />{cloud}</>}
      {(sky === "cloud" || sky === "fog") && cloud}
      {sky === "fog" && <path d="M5 21h14" className="wx__drop" />}
      {sky === "drizzle" && <>{cloud}{drops(2)}</>}
      {sky === "rain" && <>{cloud}{drops(3)}</>}
      {sky === "snow" && <>{cloud}<path d="M9 21h.01M12 22h.01M15 21h.01" className="wx__snow" /></>}
      {sky === "storm" && <>{cloud}<path d="M12 18l-2 3h3l-1.5 2.5" className="wx__bolt" /></>}
    </svg>
  );
}
