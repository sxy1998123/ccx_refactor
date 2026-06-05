<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import StressCloudViewer from "../components/StressCloudViewer.vue";
import { getRiskResult, getRiskTask, type RainfallRiskCase, type RiskResult, type RiskTaskResponse } from "../services/api";

type PageKey = "input" | "analysis" | "database" | "risk";
type RiskCaseView = {
  case: string;
  label: string;
  rainfallMm: number | null;
  day: number | null;
  maxAbsStressPa: number | null;
  riskIndex: number | null;
  stressOverLimit: boolean;
};
type RainfallGroup = {
  key: string;
  title: string;
  subtitle: string;
  cases: RiskCaseView[];
  maxRiskIndex: number | null;
  category: string;
};

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
const selectedRainfallKey = ref("base");
const selectedCaseKey = ref("base");
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

const allRiskCases = computed<RiskCaseView[]>(() => {
  const base = riskResult.value?.base;
  const cases: RiskCaseView[] = [];
  if (base) {
    cases.push({
      case: "base",
      label: "Base 当前工况",
      rainfallMm: 0,
      day: 0,
      maxAbsStressPa: base.max_abs_stress ?? null,
      riskIndex: base.risk_index ?? null,
      stressOverLimit: Boolean((base.risk_index ?? 0) >= 1),
    });
  }

  for (const item of rainfallCases.value) {
    if (item.case === "base") {
      continue;
    }
    cases.push({
      case: item.case,
      label: item.label,
      rainfallMm: item.rainfall_mm,
      day: item.day,
      maxAbsStressPa: item.max_abs_stress_pa,
      riskIndex: item.risk_index,
      stressOverLimit: item.stress_over_limit,
    });
  }
  return cases;
});

const rainfallGroups = computed<RainfallGroup[]>(() => {
  const baseCase = allRiskCases.value.find((item) => item.case === "base");
  const groups = new Map<string, RiskCaseView[]>();

  for (const item of allRiskCases.value) {
    if (item.case === "base") {
      continue;
    }
    const key = rainfallKey(item.rainfallMm);
    const existing = groups.get(key) ?? [];
    existing.push(item);
    groups.set(key, existing);
  }

  const result: RainfallGroup[] = [];
  if (baseCase) {
    result.push({
      key: "base",
      title: "Base",
      subtitle: "当前基础工况",
      cases: [baseCase],
      maxRiskIndex: baseCase.riskIndex,
      category: "基础",
    });
  }

  for (const [key, cases] of groups) {
    const rainfall = cases[0]?.rainfallMm ?? null;
    const sortedCases = [...cases].sort((left, right) => (left.day ?? 0) - (right.day ?? 0));
    result.push({
      key,
      title: formatRainfallCase(rainfall),
      subtitle: `${sortedCases.length} 个持续时间`,
      cases: sortedCases,
      maxRiskIndex: maxRiskIndex(sortedCases),
      category: rainfallCategory(rainfall),
    });
  }

  return result.sort((left, right) => {
    if (left.key === "base") {
      return -1;
    }
    if (right.key === "base") {
      return 1;
    }
    return Number(left.key) - Number(right.key);
  });
});

const selectedGroup = computed(() => rainfallGroups.value.find((group) => group.key === selectedRainfallKey.value) ?? rainfallGroups.value[0]);
const selectedCase = computed(() => {
  const group = selectedGroup.value;
  return group?.cases.find((item) => item.case === selectedCaseKey.value) ?? group?.cases[0] ?? null;
});

const riskFactors = computed(() => {
  const current = selectedCase.value;
  return [
    { label: "杆塔种类", value: towerTypeName.value },
    { label: "当前工况", value: current?.label || "--" },
    { label: "风险等级", value: riskLevel(current?.riskIndex) },
    { label: "阈值占比", value: formatRiskPercent(current?.riskIndex) },
    { label: "最大应力", value: formatStress(current?.maxAbsStressPa) },
  ];
});

const riskScore = computed(() => {
  const riskIndex = selectedCase.value?.riskIndex;
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

const selectedCaseAdvice = computed(() => buildCaseAdvice(selectedCase.value));
const selectedRiskLevelClass = computed(() => riskLevelClass(selectedCase.value?.riskIndex));

watch(
  () => [props.apiBaseUrl, props.preprocessTaskId] as const,
  ([baseUrl, taskId]) => {
    stopRiskPolling();
    riskTask.value = null;
    riskResult.value = null;
    riskError.value = "";
    selectedRainfallKey.value = "base";
    selectedCaseKey.value = "base";

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

function selectRainfallGroup(group: RainfallGroup): void {
  selectedRainfallKey.value = group.key;
  if (group.key === "base") {
    selectedCaseKey.value = "base";
    return;
  }

  const highestRiskCase = [...group.cases].sort((left, right) => (right.riskIndex ?? -1) - (left.riskIndex ?? -1))[0];
  selectedCaseKey.value = highestRiskCase?.case ?? group.cases[0]?.case ?? "base";
}

function selectCase(item: RiskCaseView): void {
  selectedCaseKey.value = item.case;
}

function rainfallKey(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "unknown";
  }
  return String(value);
}

function maxRiskIndex(cases: RiskCaseView[]): number | null {
  const values = cases
    .map((item) => item.riskIndex)
    .filter((value): value is number => value !== null && value !== undefined && !Number.isNaN(value));
  return values.length ? Math.max(...values) : null;
}

function rainfallCategory(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "基础";
  }
  if (value >= 180) {
    return "极端降雨";
  }
  if (value >= 110) {
    return "强降雨";
  }
  return "常规降雨";
}

function riskLevel(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "待复核";
  }
  if (value >= 1) {
    return "高风险";
  }
  if (value >= 0.8) {
    return "中风险";
  }
  if (value >= 0.5) {
    return "关注";
  }
  return "低风险";
}

function riskLevelClass(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "unknown";
  }
  if (value >= 1) {
    return "high";
  }
  if (value >= 0.8) {
    return "medium";
  }
  if (value >= 0.5) {
    return "watch";
  }
  return "low";
}

function buildCaseAdvice(item: RiskCaseView | null): string[] {
  if (!item || item.riskIndex === null || item.riskIndex === undefined || Number.isNaN(item.riskIndex)) {
    return ["当前工况缺少有效应力结果，建议复核有限元输入、求解日志和 h5 输出。"];
  }

  const condition = item.case === "base" ? "基础工况" : `${formatRainfallCase(item.rainfallMm)} 连续 ${formatDay(item.day)}`;
  const stressText = formatStress(item.maxAbsStressPa);
  const ratioText = formatRiskPercent(item.riskIndex);
  const level = riskLevel(item.riskIndex);
  const messages = [
    `${condition}下最大应力约 ${stressText}，阈值占比 ${ratioText}，判定为${level}。`,
  ];

  if (item.case !== "base" && item.rainfallMm !== null && item.rainfallMm !== undefined && item.rainfallMm >= 180) {
    messages.push("该工况属于极端降雨情景，建议作为专项预案和极端天气校核依据，不直接覆盖当前基础风险等级。");
  }

  if (item.riskIndex >= 1) {
    messages.push("建议立即安排现场复核，重点检查塔基沉降、杆件连接和基础周边排水，并评估加固或卸载措施。");
  } else if (item.riskIndex >= 0.8) {
    messages.push("建议提高巡检频率，在强降雨或大风后复测位移与沉降，并关注风险指数接近阈值的构件。");
  } else if (item.riskIndex >= 0.5) {
    messages.push("建议纳入关注清单，结合降雨预报安排复测，持续跟踪应力和位移变化。");
  } else {
    messages.push("当前工况未接近控制阈值，建议维持常规监测，并在强降雨或大风后复测。");
  }

  return messages;
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

function formatRiskPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${Math.round(value * 100)}%`;
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
      <aside class="risk-case-sidebar wide-panel">
        <div class="panel-title compact-title">
          <div>
            <span>工况分类</span>
            <h2>降雨量</h2>
          </div>
          <strong>{{ rainfallGroups.length }} 组</strong>
        </div>
        <div class="risk-case-list">
          <button
            v-for="group in rainfallGroups"
            :key="group.key"
            type="button"
            :class="{ active: selectedRainfallKey === group.key, danger: (group.maxRiskIndex ?? 0) >= 1 }"
            @click="selectRainfallGroup(group)"
          >
            <span>{{ group.title }}</span>
            <strong>{{ riskLevel(group.maxRiskIndex) }}</strong>
            <small>{{ group.category }} · 最高 {{ formatRiskPercent(group.maxRiskIndex) }}</small>
          </button>
        </div>
      </aside>

      <section class="risk-case-main">
      <div class="risk-controls">
        <article v-for="factor in riskFactors" :key="factor.label" class="factor-tile">
          <span>{{ factor.label }}</span>
          <strong>{{ factor.value }}</strong>
        </article>
      </div>

      <div v-if="selectedGroup && selectedGroup.cases.length > 1" class="wide-panel risk-day-selector">
        <div class="compact-section-title">
          <span>{{ selectedGroup.title }} 持续时间</span>
          <strong>默认显示最高风险工况</strong>
        </div>
        <div class="risk-day-buttons">
          <button
            v-for="item in selectedGroup.cases"
            :key="item.case"
            type="button"
            :class="{ active: selectedCaseKey === item.case, danger: item.stressOverLimit }"
            @click="selectCase(item)"
          >
            <span>{{ formatDay(item.day) }}</span>
            <strong>{{ formatRiskPercent(item.riskIndex) }}</strong>
          </button>
        </div>
      </div>

      <div class="visual-panel stress-panel">
        <div class="panel-title">
          <div>
            <span>结构结果</span>
            <h2>{{ selectedCase?.label || "应力云图" }}</h2>
          </div>
          <strong>{{ riskLevel(selectedCase?.riskIndex) }}</strong>
        </div>
        <StressCloudViewer :base-url="apiBaseUrl" :task-id="preprocessTaskId" :case-name="selectedCase?.case || 'base'" />
      </div>

      <div class="wide-panel risk-result">
        <div class="score-block" :class="selectedRiskLevelClass">
          <span>应力阈值占比</span>
          <strong>{{ riskScore }}</strong>
        </div>
        <div class="risk-result-conclusion">
          <p v-for="item in selectedCaseAdvice" :key="item">{{ item }}</p>
        </div>
      </div>
      <div class="wide-panel rainfall-risk-panel">
        <div class="panel-title compact-title">
          <div>
            <span>全部工况</span>
            <h2>风险明细</h2>
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
              <tr v-for="item in rainfallCases" :key="item.case" :class="{ danger: item.stress_over_limit, selected: selectedCaseKey === item.case }">
                <td>{{ formatRainfallCase(item.rainfall_mm) }}</td>
                <td>{{ formatDay(item.day) }}</td>
                <td>{{ formatRiskIndex(item.risk_index) }}</td>
                <td>{{ item.stress_over_limit ? "超限" : "正常" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      </section>
      </div>
      </template>
    </template>
  </section>
</template>
