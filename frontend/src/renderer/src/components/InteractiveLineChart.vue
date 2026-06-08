<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
  TooltipComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { ComposeOption } from "echarts/core";
import type { LineSeriesOption } from "echarts/charts";
import type {
  DataZoomComponentOption,
  GridComponentOption,
  LegendComponentOption,
  ToolboxComponentOption,
  TooltipComponentOption,
} from "echarts/components";

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, ToolboxComponent, CanvasRenderer]);

type ChartOption = ComposeOption<
  LineSeriesOption | GridComponentOption | TooltipComponentOption | LegendComponentOption | DataZoomComponentOption | ToolboxComponentOption
>;

export type InteractiveLineSeries = {
  name: string;
  color?: string;
  data: Array<[string, number]>;
};

const props = defineProps<{
  series: InteractiveLineSeries[];
  yUnit?: string;
  emptyText?: string;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

watch(
  () => [props.series, props.yUnit] as const,
  () => {
    void renderChart();
  },
  { deep: true },
);

onMounted(() => {
  void renderChart();
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
  chart?.dispose();
  chart = null;
});

async function renderChart(): Promise<void> {
  await nextTick();
  const target = chartRef.value;
  if (!target) {
    return;
  }

  if (!chart) {
    chart = echarts.init(target, undefined, { renderer: "canvas" });
    resizeObserver = new ResizeObserver(() => chart?.resize());
    resizeObserver.observe(target);
  }

  chart.setOption(buildOption(), true);
  chart.resize();
}

function buildOption(): ChartOption {
  const yUnit = props.yUnit ?? "";
  return {
    color: props.series.map((item) => item.color).filter(Boolean) as string[],
    animation: false,
    grid: {
      left: 46,
      right: 24,
      top: 42,
      bottom: 58,
      containLabel: true,
    },
    legend: {
      top: 8,
      left: "center",
      right: 72,
      itemWidth: 10,
      itemHeight: 8,
      textStyle: {
        color: "#314441",
        fontWeight: 700,
      },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "cross",
      },
      valueFormatter: (value) => formatValue(value, yUnit),
    },
    toolbox: {
      right: 8,
      top: 4,
      itemSize: 14,
      feature: {
        restore: { show: true, title: "还原" },
        saveAsImage: { show: true, title: "保存图片", pixelRatio: 2 },
      },
    },
    xAxis: {
      type: "time",
      axisLabel: {
        color: "#5f7370",
      },
      axisLine: {
        lineStyle: { color: "#cddfdb" },
      },
      splitLine: {
        show: false,
      },
    },
    yAxis: {
      type: "value",
      scale: true,
      name: yUnit,
      nameTextStyle: {
        color: "#5f7370",
        fontWeight: 700,
      },
      axisLabel: {
        color: "#5f7370",
        formatter: (value: number) => formatAxisValue(value),
      },
      splitLine: {
        lineStyle: {
          color: "#e1ece9",
        },
      },
    },
    dataZoom: [
      {
        type: "inside",
        filterMode: "none",
      },
      {
        type: "slider",
        height: 24,
        bottom: 12,
        filterMode: "none",
        brushSelect: true,
        borderColor: "#cddfdb",
        fillerColor: "rgba(47, 111, 102, 0.16)",
        handleStyle: {
          color: "#2f6f66",
        },
        textStyle: {
          color: "#5f7370",
        },
      },
    ],
    series: props.series.map((item) => ({
      name: item.name,
      type: "line",
      showSymbol: false,
      sampling: "lttb",
      lineStyle: {
        width: 2,
      },
      emphasis: {
        focus: "series",
      },
      data: item.data,
    })),
  };
}

function formatValue(value: unknown, unit: string): string {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "--";
  }
  return `${formatAxisValue(number)}${unit ? ` ${unit}` : ""}`;
}

function formatAxisValue(value: number): string {
  if (Math.abs(value) >= 100) {
    return value.toFixed(1);
  }
  if (Math.abs(value) >= 1) {
    return value.toFixed(3);
  }
  return value.toFixed(5);
}
</script>

<template>
  <div class="interactive-line-chart">
    <div v-if="series.some((item) => item.data.length > 1)" ref="chartRef" class="interactive-line-chart-canvas"></div>
    <div v-else class="analysis-chart-empty">{{ emptyText || "暂无曲线数据" }}</div>
  </div>
</template>
