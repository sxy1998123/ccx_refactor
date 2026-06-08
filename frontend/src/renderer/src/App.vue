<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ElConfigProvider } from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import { getAppInfo, getPreprocessTask, getRiskTask, type AppInfo, type PreprocessTaskResponse, type RiskTaskResponse } from "./services/api";
import AnalysisView from "./views/AnalysisView.vue";
import DatabaseView from "./views/DatabaseView.vue";
import InputView from "./views/InputView.vue";
import RiskView from "./views/RiskView.vue";

type PageKey = "input" | "analysis" | "database" | "risk";

const apiBaseUrl = ref("");
const backendStatus = ref("连接中");
const appInfo = ref<AppInfo | null>(null);
const activePage = ref<PageKey>("input");
const hasAnalysisResult = ref(false);
const hasRiskReport = ref(true);
const preprocessTask = ref<PreprocessTaskResponse | null>(null);
const riskTask = ref<RiskTaskResponse | null>(null);

const PREPROCESS_TASK_STORAGE_KEY = "ccx.preprocessTask";
const INPUT_FORM_STORAGE_KEY = "ccx.inputFormState";
let preprocessPollTimer: number | undefined;
let preprocessPollRunId = 0;
let riskPollTimer: number | undefined;
let riskPollRunId = 0;

const pages: Array<{ key: PageKey; title: string; subtitle: string }> = [
  { key: "input", title: "输入数据", subtitle: "线路号、影像、SD 卡与点云文件" },
  { key: "analysis", title: "数据分析", subtitle: "位置、沉降、地表与点云结果" },
  { key: "database", title: "数据库", subtitle: "查看历史地质灾害数据、结合历史数据对当前数据结果综合分析" },
  { key: "risk", title: "风险评估", subtitle: "杆塔参数、受力结果与处置建议" },
];

const activePageMeta = computed(() => pages.find((page) => page.key === activePage.value) ?? pages[0]);
const preprocessTaskId = computed(() => preprocessTask.value?.task_id ?? "");

function handleNavigate(page: PageKey): void {
  activePage.value = page;
}

function handleAnalysisSubmitted(task: PreprocessTaskResponse): void {
  setPreprocessTask(task);
  if (task.status === "queued" || task.status === "running") {
    hasAnalysisResult.value = false;
    startPreprocessPolling(task.task_id);
    return;
  }

  if (task.status === "completed" && activePage.value === "input") {
    activePage.value = "analysis";
  }
}

function setPreprocessTask(task: PreprocessTaskResponse): void {
  preprocessTask.value = task;
  savePreprocessTask(task);

  if (task.status === "completed") {
    hasAnalysisResult.value = true;
    hasRiskReport.value = true;
    startRiskPolling(task.task_id);
  }
}

function savePreprocessTask(task: PreprocessTaskResponse): void {
  localStorage.setItem(PREPROCESS_TASK_STORAGE_KEY, JSON.stringify(task));
}

function restorePreprocessTask(): PreprocessTaskResponse | null {
  const rawTask = localStorage.getItem(PREPROCESS_TASK_STORAGE_KEY);
  if (!rawTask) {
    return null;
  }

  try {
    return JSON.parse(rawTask) as PreprocessTaskResponse;
  } catch (error) {
    localStorage.removeItem(PREPROCESS_TASK_STORAGE_KEY);
    console.error(error);
    return null;
  }
}

function stopPreprocessPolling(): void {
  preprocessPollRunId += 1;
  if (preprocessPollTimer !== undefined) {
    window.clearTimeout(preprocessPollTimer);
    preprocessPollTimer = undefined;
  }
}

function startPreprocessPolling(taskId: string): void {
  stopPreprocessPolling();
  const runId = preprocessPollRunId;

  const poll = async (): Promise<void> => {
    if (runId !== preprocessPollRunId) {
      return;
    }

    if (!apiBaseUrl.value) {
      preprocessPollTimer = window.setTimeout(poll, 800);
      return;
    }

    try {
      const task = await getPreprocessTask(apiBaseUrl.value, taskId);
      if (runId !== preprocessPollRunId) {
        return;
      }

      setPreprocessTask(task);

      if (task.status === "completed") {
        stopPreprocessPolling();
        if (activePage.value === "input") {
          activePage.value = "analysis";
        }
        return;
      }

      if (task.status === "failed") {
        stopPreprocessPolling();
        return;
      }

      preprocessPollTimer = window.setTimeout(poll, 800);
    } catch (error) {
      if (runId !== preprocessPollRunId) {
        return;
      }

      const currentTask = preprocessTask.value;
      if (currentTask?.task_id === taskId) {
        setPreprocessTask({
          ...currentTask,
          status: "failed",
          updated_at: new Date().toISOString(),
          message: error instanceof Error ? error.message : String(error),
        });
      }
      stopPreprocessPolling();
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

function startRiskPolling(taskId: string): void {
  stopRiskPolling();
  const runId = riskPollRunId;

  const poll = async (): Promise<void> => {
    if (runId !== riskPollRunId || !apiBaseUrl.value) {
      return;
    }

    try {
      const task = await getRiskTask(apiBaseUrl.value, taskId);
      if (runId !== riskPollRunId) {
        return;
      }
      riskTask.value = task;
      if (task.status === "completed") {
        localStorage.removeItem(INPUT_FORM_STORAGE_KEY);
        stopRiskPolling();
        return;
      }
      if (task.status === "failed") {
        stopRiskPolling();
        return;
      }
      riskPollTimer = window.setTimeout(poll, 1500);
    } catch {
      riskPollTimer = window.setTimeout(poll, 1500);
    }
  };

  void poll();
}

onMounted(async () => {
  const restoredTask = restorePreprocessTask();
  if (restoredTask) {
    setPreprocessTask(restoredTask);
  }

  try {
    const config = await window.ccx.getApiConfig();
    apiBaseUrl.value = config.baseUrl;
    appInfo.value = await getAppInfo(config.baseUrl);
    if (restoredTask?.status === "queued" || restoredTask?.status === "running") {
      startPreprocessPolling(restoredTask.task_id);
    } else if (restoredTask?.status === "completed") {
      startRiskPolling(restoredTask.task_id);
    }
    backendStatus.value = "已连接";
  } catch (error) {
    backendStatus.value = "连接失败";
    console.error(error);
  }
});

onBeforeUnmount(() => {
  stopPreprocessPolling();
  stopRiskPolling();
});
</script>

<template>
  <ElConfigProvider :locale="zhCn">
    <main class="app-shell">
      <aside class="app-rail">
        <div class="brand-block">
          <div class="brand-mark">安</div>
          <div>
            <strong>杆塔安全评估</strong>
          </div>
        </div>

        <nav class="page-nav" aria-label="主导航">
          <button
            v-for="page in pages"
            :key="page.key"
            type="button"
            :class="{ active: activePage === page.key }"
            @click="activePage = page.key"
          >
            <strong>{{ page.title }}</strong>
            <span>{{ page.subtitle }}</span>
          </button>
        </nav>

        <div class="system-card">
          <span>后端服务</span>
          <strong>{{ backendStatus }}</strong>
          <small>{{ appInfo ? `${appInfo.app_name} ${appInfo.version}` : "等待服务信息" }}</small>
          <small>{{ apiBaseUrl || "等待服务地址" }}</small>
        </div>
      </aside>

      <section class="app-main">
        <header class="app-header">
          <div>
            <p class="section-kicker">输电线路智能巡检</p>
            <h1>{{ activePageMeta.title }}</h1>
            <span>{{ activePageMeta.subtitle }}</span>
          </div>
        </header>

        <section class="content-stage">
          <InputView
            v-if="activePage === 'input'"
            :api-base-url="apiBaseUrl"
            :has-analysis-result="hasAnalysisResult"
            :preprocess-task="preprocessTask"
            :risk-task="riskTask"
            @analysis-submitted="handleAnalysisSubmitted"
          />
          <AnalysisView
            v-else-if="activePage === 'analysis'"
            :api-base-url="apiBaseUrl"
            :has-analysis-result="hasAnalysisResult"
            :preprocess-task-id="preprocessTaskId"
            @navigate="handleNavigate"
          />
          <DatabaseView v-else-if="activePage === 'database'" :api-base-url="apiBaseUrl" />
          <RiskView
            v-else
            :api-base-url="apiBaseUrl"
            :has-risk-report="hasRiskReport"
            :preprocess-task-id="preprocessTaskId"
            @navigate="handleNavigate"
          />
        </section>
      </section>
    </main>
  </ElConfigProvider>
</template>
