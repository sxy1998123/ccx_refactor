<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import StressCloudViewer from "../components/StressCloudViewer.vue";
import { getRiskResult, getRiskTask, type RainfallRiskCase, type RiskResult, type RiskTaskResponse } from "../services/api";

type PageKey = "input" | "analysis" | "database" | "risk";

const props = defineProps<{
  apiBaseUrl: string;
  hasRiskReport: boolean;
  preprocessTaskId: string;
}>();

const emit = defineEmits<{
  navigate: [page: PageKey];
}>();

const riskPlaceholderItems = ["等待数据分析完成", "生成风险评估报告", "查看风险等级与处置建议"];

const riskTask = ref<RiskTaskResponse | null>(null);
const riskResult = ref<RiskResult | null>(null);
const riskError = ref("");
const isLoadingRisk = ref(false);
let riskPollTimer: number | undefined;
let riskPollRunId = 0;

const hasRiskResult = computed(() => riskResult.value?.status === "completed");
const isRiskRunning = computed(() => riskTask.value?.status === "queued" || riskTask.value?.status === "running");

const towerTypeName = computed(() => {
  const towerType = riskResult.value?.tower_type || riskTask.value?.tower_type;
  if (towerType === "guxing") {
    return "鼓型塔";
  }
  if (towerType === "jiubei") {
    return "酒杯塔";
  }
  if (towerType === "maotouying") {
    return "猫头鹰";
  }
  return towerType || "--";
});

const riskFactors = computed(() => {
  const base = riskResult.value?.base;
  return [
    { label: "杆塔种类", value: towerTypeName.value },
    { label: "风险等级", value: riskResult.value?.report?.risk_level || "--" },
    { label: "风险指数", value: formatRiskIndex(base?.risk_index) },
    { label: "base 最大应力", value: formatStress(base?.max_abs_stress) },
  ];
});

const riskScore = computed(() => {
  const riskIndex = riskResult.value?.base?.risk_index;
  if (riskIndex === null || riskIndex === undefined || Number.isNaN(riskIndex)) {
    return "--";
  }
  return String(Math.round(riskIndex * 100));
});

const rainfallCases = computed<RainfallRiskCase[]>(() => {
  const summary = riskResult.value?.full?.summary;
  const cases = summary?.cases?.length ? summary.cases : summary?.over_limit_cases ?? [];
  return [...cases].sort((left, right) => {
    const leftRainfall = left.rainfall_mm ?? 0;
    const rightRainfall = right.rainfall_mm ?? 0;
    if (leftRainfall !== rightRainfall) {
      return leftRainfall - rightRainfall;
    }
    return (left.day ?? 0) - (right.day ?? 0);
  });
});

watch(
  () => [props.apiBaseUrl, props.preprocessTaskId] as const,
  ([baseUrl, taskId]) => {
    stopRiskPolling();
    riskTask.value = null;
    riskResult.value = null;
    riskError.value = "";

    if (!baseUrl || !taskId) {
      return;
    }
    startRiskPolling(taskId);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  stopRiskPolling();
});

function startRiskPolling(taskId: string): void {
  stopRiskPolling();
  const runId = riskPollRunId;

  const poll = async (): Promise<void> => {
    if (runId !== riskPollRunId) {
      return;
    }

    isLoadingRisk.value = true;
    try {
      const task = await getRiskTask(props.apiBaseUrl, taskId);
      if (runId !== riskPollRunId) {
        return;
      }

      riskTask.value = task;
      riskError.value = "";

      if (task.status === "completed") {
        riskResult.value = await getRiskResult(props.apiBaseUrl, taskId);
        stopRiskPolling();
        return;
      }

      if (task.status === "failed") {
        riskError.value = task.message || "风险评估失败";
        stopRiskPolling();
        return;
      }

      riskPollTimer = window.setTimeout(poll, 1500);
    } catch (error) {
      if (runId !== riskPollRunId) {
        return;
      }
      const message = error instanceof Error ? error.message : String(error);
      riskError.value = message.includes("不存在") ? "" : message;
      riskPollTimer = window.setTimeout(poll, 2000);
    } finally {
      isLoadingRisk.value = false;
    }
  };

  void poll();
}

function stopRiskPolling(): void {
  riskPollRunId += 1;
  if (riskPollTimer !== undefined) {
    window.clearTimeout(riskPollTimer);
    riskPollTimer = undefined;
  }
}

function formatStress(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${(value / 1_000_000).toFixed(2)} MPa`;
}

function formatRiskIndex(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(3);
}

function formatRainfallCase(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${value.toFixed(value % 1 === 0 ? 0 : 1)}mm`;
}

function formatDay(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return value === 0 ? "基础" : `${value}d`;
}
</script>

<template>
  <section class="page-grid risk-page">
    <template v-if="!preprocessTaskId">
      <div class="wide-panel empty-state-panel risk-empty">
        <div class="empty-copy">
          <span class="empty-eyebrow">等待报告</span>
          <h2>尚未生成风险评估报告</h2>
          <p>风险评估需要先完成数据分析。生成报告后，这里会展示风险等级、风险指数、风险因素和处置建议。</p>
          <div class="empty-actions">
            <button type="button" class="primary-button" @click="emit('navigate', 'analysis')">查看数据分析</button>
            <button type="button" class="ghost-button" disabled>导出报告</button>
          </div>
        </div>

        <div class="report-skeleton" aria-label="风险评估报告占位骨架">
          <div class="report-header-skeleton">
            <span></span>
            <span></span>
          </div>
          <div class="report-score-skeleton">
            <strong>--</strong>
            <span>风险指数</span>
          </div>
          <div class="report-lines">
            <span></span>
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>

      <div class="wide-panel placeholder-steps report-placeholder-steps">
        <article v-for="(item, index) in riskPlaceholderItems" :key="item">
          <span>{{ index + 1 }}</span>
          <strong>{{ item }}</strong>
        </article>
      </div>
    </template>

    <template v-else>
      <div v-if="isRiskRunning || riskError || isLoadingRisk" class="wide-panel task-status" :class="{ error: riskError }">
        <span>{{ riskError || riskTask?.message || "正在等待风险评估结果..." }}</span>
      </div>

      <template v-if="!hasRiskResult">
        <div class="wide-panel empty-state-panel risk-empty">
          <div class="empty-copy">
            <span class="empty-eyebrow">风险评估</span>
            <h2>{{ isRiskRunning ? "正在生成风险评估报告" : "尚未生成风险评估报告" }}</h2>
            <p>{{ riskTask?.stage_label || "预处理完成后，后端会自动执行有限元风险评估。" }}</p>
            <div class="empty-actions">
              <button type="button" class="primary-button" @click="emit('navigate', 'analysis')">查看数据分析</button>
              <button type="button" class="ghost-button" disabled>导出报告</button>
            </div>
          </div>

          <div class="report-skeleton" aria-label="风险评估报告占位骨架">
            <div class="report-header-skeleton">
              <span></span>
              <span></span>
            </div>
            <div class="report-score-skeleton">
              <strong>--</strong>
              <span>风险指数</span>
            </div>
            <div class="report-lines">
              <span></span>
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </template>

      <template v-else>
      <div class="risk-dashboard">
      <div class="risk-controls">
        <article v-for="factor in riskFactors" :key="factor.label" class="factor-tile">
          <span>{{ factor.label }}</span>
          <strong>{{ factor.value }}</strong>
        </article>
      </div>

      <div class="visual-panel stress-panel">
        <div class="panel-title">
          <div>
            <span>结构结果</span>
            <h2>应力云图</h2>
          </div>
          <!-- <strong>Three.js</strong> -->
        </div>
        <StressCloudViewer :base-url="apiBaseUrl" :task-id="preprocessTaskId" />
      </div>

      <div class="wide-panel risk-result">
        <div class="score-block">
          <span>风险指数</span>
          <strong>{{ riskScore }}</strong>
        </div>
        <div class="risk-result-conclusion">
          <p>{{ riskResult?.report?.description }}</p>
          <p>{{ riskResult?.report?.collapse_prediction }}</p>
          <p>{{ riskResult?.report?.recommendation }}</p>
        </div>
      </div>
      <div class="wide-panel rainfall-risk-panel">
        <div class="panel-title compact-title">
          <div>
            <span>降雨工况</span>
            <h2>工况风险</h2>
          </div>
          <strong>{{ rainfallCases.length }} 项</strong>
        </div>
        <div class="rainfall-risk-table">
          <table>
            <thead>
              <tr>
                <th>降雨</th>
                <th>持续</th>
                <th>风险</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in rainfallCases" :key="item.case" :class="{ danger: item.stress_over_limit }">
                <td>{{ formatRainfallCase(item.rainfall_mm) }}</td>
                <td>{{ formatDay(item.day) }}</td>
                <td>{{ formatRiskIndex(item.risk_index) }}</td>
                <td>{{ item.stress_over_limit ? "超限" : "正常" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      </div>
      </template>
    </template>
  </section>
</template>
