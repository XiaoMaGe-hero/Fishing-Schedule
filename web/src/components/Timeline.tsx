import { useMemo, useState } from "react";
import type { EChartsCoreOption } from "echarts/core";
import { CHART_VISIBLE_HOURS } from "../config";
import { copy } from "../copy";
import { axisPosition, dayStarts, type Hour, type Window } from "../data/derive";
import { formatDateKey, formatTime } from "../data/time";
import { theme } from "../theme";
import { EChart } from "./EChart";

type Lower = "wind" | "waves";

/** Everything the chart draws, worked out from plain data. Labels are NZ time, set here, not by the browser. */
export function timelineOption(hours: Hour[], windows: Window[], lower: Lower): EChartsCoreOption {
  const labels = hours.map((h) => formatTime(new Date(h.time_utc)));
  const days = dayStarts(hours);
  const nights: [{ xAxis: number }, { xAxis: number }][] = [];
  let from: number | null = null;
  hours.forEach((h, i) => {
    if (!h.is_daylight && from === null) from = i;
    if ((h.is_daylight || i === hours.length - 1) && from !== null) { nights.push([{ xAxis: from }, { xAxis: h.is_daylight ? i : i + 1 }]); from = null; }
  });
  const good = windows
    .map((w) => [axisPosition(hours, w.start_utc), axisPosition(hours, w.end_utc)] as const)
    .filter((p): p is readonly [number, number] => p[0] !== null && p[1] !== null)
    .map(([a, b]) => [{ xAxis: Math.round(a) }, { xAxis: Math.round(b) }]);
  const dayLines = days.filter((d) => d.index > 0).map((d) => ({
    xAxis: d.index, label: { formatter: formatDateKey(d.dateKey), position: "insideEndTop" as const, color: theme.muted, fontSize: 11 },
  }));
  const axisBase = {
    type: "category" as const, data: labels, boundaryGap: false,
    axisLine: { lineStyle: { color: theme.line } }, axisTick: { show: false },
  };
  const yBase = { splitLine: { lineStyle: { color: theme.line, type: "dashed" as const } }, axisLabel: { color: theme.muted, fontSize: 11 } };
  const lowerSeries = lower === "wind" ? [
    { name: copy.timeline.rain, type: "bar", xAxisIndex: 1, yAxisIndex: 2, data: hours.map((h) => h.precip_prob_pct),
      itemStyle: { color: "rgba(47,127,158,0.28)" }, barWidth: "70%" },
    { name: copy.timeline.wind, type: "line", xAxisIndex: 1, yAxisIndex: 1, data: hours.map((h) => h.wind_speed_kmh),
      showSymbol: false, smooth: true, lineStyle: { color: theme.deep, width: 2 }, itemStyle: { color: theme.deep } },
    { name: copy.timeline.gust, type: "line", xAxisIndex: 1, yAxisIndex: 1, data: hours.map((h) => h.wind_gust_kmh),
      showSymbol: false, smooth: true, lineStyle: { color: theme.stop, width: 1.5, type: "dashed" }, itemStyle: { color: theme.stop } },
  ] : [
    { name: copy.timeline.wave, type: "line", xAxisIndex: 1, yAxisIndex: 1, data: hours.map((h) => h.wave_height_m),
      showSymbol: false, smooth: true, lineStyle: { color: theme.deep, width: 2 }, itemStyle: { color: theme.deep } },
    { name: copy.timeline.swell, type: "line", xAxisIndex: 1, yAxisIndex: 1, data: hours.map((h) => h.swell_height_m),
      showSymbol: false, smooth: true, lineStyle: { color: theme.tide, width: 1.5, type: "dashed" }, itemStyle: { color: theme.tide } },
  ];
  return {
    animation: false,
    textStyle: { fontFamily: "inherit" },
    grid: [{ left: 34, right: 34, top: 26, height: 96 }, { left: 34, right: 34, top: 168, height: 110 }],
    legend: { top: 136, right: 30, itemWidth: 14, itemHeight: 8, textStyle: { color: theme.muted, fontSize: 11 },
              data: lowerSeries.map((s) => s.name), selectedMode: false },
    tooltip: { trigger: "axis", confine: true, axisPointer: { type: "line", lineStyle: { color: theme.muted } },
               textStyle: { fontSize: 12 } },
    axisPointer: { link: [{ xAxisIndex: [0, 1] }] },
    dataZoom: [{ type: "inside", xAxisIndex: [0, 1], startValue: 0, endValue: Math.min(CHART_VISIBLE_HOURS, hours.length - 1),
                 zoomLock: true, moveOnMouseMove: true, moveOnMouseWheel: false, preventDefaultMouseMove: false }],
    xAxis: [
      { ...axisBase, gridIndex: 0, axisLabel: { show: false } },
      { ...axisBase, gridIndex: 1, axisLabel: { color: theme.muted, fontSize: 11, interval: 5 } },
    ],
    yAxis: [
      { ...yBase, gridIndex: 0, type: "value", name: copy.timeline.tide, nameTextStyle: { color: theme.muted, fontSize: 11, align: "left" }, min: 0 },
      { ...yBase, gridIndex: 1, type: "value", name: lower === "wind" ? "km/h" : "m", nameTextStyle: { color: theme.muted, fontSize: 11 }, min: 0 },
      { gridIndex: 1, type: "value", min: 0, max: 100, show: lower === "wind", position: "right", splitLine: { show: false },
        axisLabel: { color: theme.muted, fontSize: 11, formatter: "{value}%" } },
    ],
    series: [
      { name: copy.timeline.tide, type: "line", xAxisIndex: 0, yAxisIndex: 0, data: hours.map((h) => h.tide_height_m),
        showSymbol: false, smooth: true, lineStyle: { color: theme.tide, width: 2 }, itemStyle: { color: theme.tide },
        areaStyle: { color: "rgba(47,127,158,0.18)" },
        markArea: { silent: true, data: [
          ...nights.map((n) => [{ ...n[0], itemStyle: { color: theme.night } }, n[1]]),
          ...good.map((g) => [{ ...g[0], itemStyle: { color: theme.goWash } }, g[1]]),
        ] },
        markLine: { silent: true, symbol: "none", lineStyle: { color: theme.muted, type: "solid", width: 1, opacity: 0.5 }, data: dayLines } },
      ...lowerSeries,
    ],
  };
}

/** Tide on top, wind and rain (or waves) below, on one shared time axis that swipes through the week. */
export function Timeline({ hours, windows }: { hours: Hour[]; windows: Window[] }) {
  const [lower, setLower] = useState<Lower>("wind");
  const option = useMemo(() => timelineOption(hours, windows, lower), [hours, windows, lower]);
  return (
    <div className="timeline">
      <div className="segmented" role="group" aria-label={copy.timeline.heading}>
        <button type="button" aria-pressed={lower === "wind"} onClick={() => setLower("wind")}>{copy.timeline.showWind}</button>
        <button type="button" aria-pressed={lower === "waves"} onClick={() => setLower("waves")}>{copy.timeline.showWaves}</button>
      </div>
      <EChart option={option} height={310} label={copy.timeline.heading} />
      <p className="keys">
        <span className="key key--go">{copy.timeline.recommended}</span>
        <span className="key key--night">{copy.timeline.night}</span>
      </p>
      <p className="note">{copy.timeline.swipeHint} {copy.timeline.tideEstimated}</p>
    </div>
  );
}
