import { useMemo } from "react";
import type { EChartsCoreOption } from "echarts/core";
import { copy } from "../copy";
import { dayStarts, type Hour } from "../data/derive";
import { formatDateKey, formatTime } from "../data/time";
import { theme } from "../theme";
import { EChart } from "./EChart";

export function seaTempOption(hours: Hour[]): EChartsCoreOption {
  const values = hours.map((h) => h.sea_temp_c);
  const known = values.filter((v): v is number => v !== null);
  const days = dayStarts(hours);
  return {
    animation: false,
    textStyle: { fontFamily: "inherit" },
    grid: { left: 34, right: 16, top: 14, bottom: 24 },
    tooltip: { trigger: "axis", confine: true, valueFormatter: (v: unknown) => (v == null ? "" : `${v} °C`),
               formatter: undefined },
    xAxis: { type: "category", boundaryGap: false, data: hours.map((h) => formatTime(new Date(h.time_utc))),
             axisTick: { show: false }, axisLine: { lineStyle: { color: theme.line } },
             axisLabel: { color: theme.muted, fontSize: 11, interval: (i: number) => days.some((d) => d.index === i),
                          formatter: (_: string, i: number) => formatDateKey(days.find((d) => d.index === i)?.dateKey ?? "").split(" ").slice(0, 2).join(" ") } },
    yAxis: { type: "value", min: known.length ? Math.floor(Math.min(...known) - 0.5) : 0, max: known.length ? Math.ceil(Math.max(...known) + 0.5) : 1,
             axisLabel: { color: theme.muted, fontSize: 11, formatter: "{value}°" }, splitLine: { lineStyle: { color: theme.line, type: "dashed" } } },
    series: [{ name: copy.seaTemp.heading, type: "line", data: values, showSymbol: false, smooth: true,
               lineStyle: { color: theme.tide, width: 2 }, itemStyle: { color: theme.tide } }],
  };
}

/** Sea surface temperature over the week. */
export function SeaTemp({ hours }: { hours: Hour[] }) {
  const option = useMemo(() => seaTempOption(hours), [hours]);
  const now = hours.find((h) => h.sea_temp_c !== null)?.sea_temp_c;
  return (
    <div>
      {now != null && <p className="figure"><strong>{now.toFixed(1)}</strong> °C</p>}
      <EChart option={option} height={140} label={copy.seaTemp.heading} />
      <p className="note">{copy.seaTemp.note}</p>
    </div>
  );
}
