import { useMemo } from "react";
import type { EChartsCoreOption } from "echarts/core";
import { copy } from "../copy";
import type { Freshness as FreshnessInfo } from "../data/derive";
import type { RiverFlow as RiverFlowData } from "../data/generated/types";
import { formatDay, formatTime, nzDateKey } from "../data/time";
import { theme } from "../theme";
import { EChart } from "./EChart";
import { Freshness } from "./Freshness";

export function riverOption(series: RiverFlowData["series"]): EChartsCoreOption {
  const points = series.filter((_, i) => i % 6 === 0 || i === series.length - 1); // every 30 minutes is plenty for a phone
  const firstOfDay = new Set<number>();
  let last = "";
  points.forEach((p, i) => { const k = nzDateKey(new Date(p.time_utc)); if (k !== last) firstOfDay.add(i); last = k; });
  return {
    animation: false,
    textStyle: { fontFamily: "inherit" },
    grid: { left: 40, right: 16, top: 14, bottom: 24 },
    tooltip: { trigger: "axis", confine: true, valueFormatter: (v: unknown) => (v == null ? "" : `${v} m³/s`) },
    xAxis: { type: "category", boundaryGap: false, axisTick: { show: false }, axisLine: { lineStyle: { color: theme.line } },
             data: points.map((p) => `${formatDay(new Date(p.time_utc))} ${formatTime(new Date(p.time_utc))}`),
             axisLabel: { color: theme.muted, fontSize: 11, interval: (i: number) => firstOfDay.has(i) && i > 0,
                          formatter: (v: string) => v.split(" ").slice(0, 2).join(" ") } },
    yAxis: { type: "value", scale: true, axisLabel: { color: theme.muted, fontSize: 11 },
             splitLine: { lineStyle: { color: theme.line, type: "dashed" } } },
    series: [{ name: copy.river.heading, type: "line", data: points.map((p) => p.flow_m3s), showSymbol: false,
               lineStyle: { color: theme.deep, width: 2 }, itemStyle: { color: theme.deep }, areaStyle: { color: "rgba(14,58,74,0.08)" } }],
  };
}

/** Closed until asked for. Opening it is what triggers the download, through `onOpen`. */
export function RiverFlow({ status, data, freshness, onOpen }: {
  status: "idle" | "loading" | "ready" | "error"; data: RiverFlowData | null; freshness: FreshnessInfo; onOpen: () => void;
}) {
  const option = useMemo(() => (data ? riverOption(data.series) : null), [data]);
  const latest = data?.series.length ? data.series[data.series.length - 1] : null;
  return (
    <section className="river" aria-labelledby="river-heading">
      <h2 id="river-heading">{copy.river.heading}</h2>
      {status === "idle" && <button type="button" className="button" onClick={onOpen}>{copy.river.show}</button>}
      {status === "loading" && <p className="note" role="status">{copy.river.loading}</p>}
      {status === "error" && <button type="button" className="button button--warn" onClick={onOpen}>{copy.river.failed}</button>}
      {status === "ready" && option && (
        <>
          {latest && latest.flow_m3s !== null && (
            <p className="figure"><strong>{latest.flow_m3s.toFixed(1)}</strong> {copy.river.unit}
              <span className="figure__when"> {copy.river.latest.toLowerCase()}, {formatTime(new Date(latest.time_utc))}</span></p>
          )}
          <EChart option={option} height={170} label={copy.river.heading} />
          <p className="note">{copy.river.site}</p>
          <Freshness info={freshness} />
        </>
      )}
    </section>
  );
}
