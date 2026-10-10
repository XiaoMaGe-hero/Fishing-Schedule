// Only the parts of ECharts this site draws with. Imported lazily by EChart.tsx.
import { BarChart, LineChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, DataZoomComponent, MarkAreaComponent,
             MarkLineComponent, LegendComponent, CanvasRenderer]);

export { echarts };
