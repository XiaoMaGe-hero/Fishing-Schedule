/** The day's tide as a small curve, with the recommended window marked on it. */
export function TideSpark({ tide, windowStart, windowEnd }: {
  tide: { time: string; height: number | null }[]; windowStart?: string; windowEnd?: string;
}) {
  const points = tide.filter((p): p is { time: string; height: number } => p.height !== null);
  if (points.length < 3) return null;
  const W = 300, H = 56, pad = 4;
  const t0 = new Date(points[0].time).getTime();
  const t1 = new Date(points[points.length - 1].time).getTime();
  const lo = Math.min(...points.map((p) => p.height)), hi = Math.max(...points.map((p) => p.height));
  const x = (iso: string) => ((new Date(iso).getTime() - t0) / Math.max(1, t1 - t0)) * W;
  const y = (h: number) => H - pad - ((h - lo) / Math.max(0.01, hi - lo)) * (H - pad * 2);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(p.time).toFixed(1)},${y(p.height).toFixed(1)}`).join(" ");
  const clamp = (v: number) => Math.min(W, Math.max(0, v));
  const a = windowStart ? clamp(x(windowStart)) : null, b = windowEnd ? clamp(x(windowEnd)) : null;
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
      {a !== null && b !== null && b > a && <rect className="spark__window" x={a} y={0} width={b - a} height={H} />}
      <path className="spark__fill" d={`${line} L${W},${H} L0,${H} Z`} />
      <path className="spark__line" d={line} />
    </svg>
  );
}
