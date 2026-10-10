import { useEffect, useRef } from "react";
import type { EChartsCoreOption } from "echarts/core";

// ECharts is loaded only when the first chart scrolls near the screen, so it never slows the first paint.
const loadEcharts = () => import("./echartsBundle").then((m) => m.echarts);
let echartsPromise: ReturnType<typeof loadEcharts> | null = null;

export function EChart({ option, height, label }: { option: EChartsCoreOption; height: number; label: string }) {
  const holder = useRef<HTMLDivElement>(null);
  const chart = useRef<{ setOption: (o: EChartsCoreOption, notMerge?: boolean) => void; resize: () => void; dispose: () => void } | null>(null);
  const latest = useRef(option);
  latest.current = option;

  useEffect(() => {
    const el = holder.current;
    if (!el) return;
    let disposed = false;
    let resizer: ResizeObserver | null = null;
    const start = () => {
      echartsPromise ??= loadEcharts();
      echartsPromise.then((echarts) => {
        if (disposed) return;
        chart.current = echarts.init(el);
        chart.current.setOption(latest.current, true);
        resizer = new ResizeObserver(() => chart.current?.resize());
        resizer.observe(el);
      });
    };
    const watcher = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { watcher.disconnect(); start(); }
    }, { rootMargin: "300px" });
    watcher.observe(el);
    return () => { disposed = true; watcher.disconnect(); resizer?.disconnect(); chart.current?.dispose(); chart.current = null; };
  }, []);

  useEffect(() => { chart.current?.setOption(option, true); }, [option]);

  return <div ref={holder} className="chart" style={{ height }} role="img" aria-label={label} />;
}
