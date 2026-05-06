<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { submitPreprocessTask, type PreprocessTaskResponse, type RiskTaskResponse } from "../services/api";

type TowerTxtKey = "tower1" | "tower2" | "tower3" | "tower4";

type TowerTypeOption = {
  label: string;
  value: string;
  inpFile: string;
};

type PersistedInputFormState = {
  routeId: string;
  towerType: string;
  towerTxtFiles: Record<TowerTxtKey, string>;
  envTxtFile: string;
  imageFiles: string[];
  pointCloudFiles: string[];
  updatedAt: string;
};

const INPUT_FORM_STORAGE_KEY = "ccx.inputFormState";

const props = defineProps<{
  apiBaseUrl: string;
  hasAnalysisResult: boolean;
  preprocessTask: PreprocessTaskResponse | null;
  riskTask: RiskTaskResponse | null;
}>();

const emit = defineEmits<{
  analysisSubmitted: [task: PreprocessTaskResponse];
}>();

const towerTypes: TowerTypeOption[] = [
  { label: "猫头鹰", value: "maotouying", inpFile: "Maotouyin_tower-mm-14B-MPa.inp" },
  { label: "鼓型塔", value: "guxing", inpFile: "Guxing_tower-m-9B-Pa.inp" },
  { label: "酒杯塔", value: "jiubei", inpFile: "Jiubei_tower-mm-2B-MPa.inp" },
];

const towerTxtSlots: Array<{ key: TowerTxtKey; label: string; expectedName: string }> = [
  { key: "tower1", label: "塔基端 1 号", expectedName: "1号.TXT" },
  { key: "tower2", label: "塔基端 2 号", expectedName: "2号.TXT" },
  { key: "tower3", label: "塔基端 3 号", expectedName: "3号.TXT" },
  { key: "tower4", label: "塔基端 4 号", expectedName: "4号.TXT" },
];

const routeId = ref("");
const towerType = ref(towerTypes[0].value);
const towerTxtFiles = ref<Record<TowerTxtKey, string>>({
  tower1: "",
  tower2: "",
  tower3: "",
  tower4: "",
});
const envTxtFile = ref("");
const imagePreviewUrl = ref("");
const imageFiles = ref<string[]>([]);
const pointCloudFiles = ref<string[]>([]);
const isSubmittingRequest = ref(false);
const analysisSubmitMessage = ref("");
const analysisSubmitError = ref("");
let isClearingPersistedForm = false;

const selectedTowerType = computed(() => towerTypes.find((item) => item.value === towerType.value) ?? towerTypes[0]);
const selectedTowerCount = computed(() => Object.values(towerTxtFiles.value).filter(Boolean).length);
const isTaskRunning = computed(() => props.preprocessTask?.status === "queued" || props.preprocessTask?.status === "running");
const shouldShowTaskState = computed(
  () => props.preprocessTask?.status === "queued" || props.preprocessTask?.status === "running" || props.preprocessTask?.status === "failed",
);
const isSubmittingAnalysis = computed(() => isSubmittingRequest.value || isTaskRunning.value);
const panelStatusLabel = computed(() => {
  if (isSubmittingAnalysis.value) {
    return "处理中";
  }
  if (props.preprocessTask?.status === "failed") {
    return "失败";
  }
  return "未开始";
});
const taskStatusText = computed(() => {
  if (analysisSubmitError.value) {
    return analysisSubmitError.value;
  }
  if (shouldShowTaskState.value) {
    return props.preprocessTask?.message || analysisSubmitMessage.value || "";
  }
  if (props.riskTask?.status === "queued" || props.riskTask?.status === "running") {
    return props.riskTask.message || "正在执行风险评估";
  }
  if (props.riskTask?.status === "failed") {
    return props.riskTask.message || "风险评估失败";
  }
  return analysisSubmitMessage.value;
});
const taskStatusHasError = computed(() => Boolean(analysisSubmitError.value) || props.preprocessTask?.status === "failed" || props.riskTask?.status === "failed");
const taskMetaItems = computed(() => {
  if (props.riskTask?.status === "queued" || props.riskTask?.status === "running") {
    const progress = props.riskTask.progress;
    const progressText = progress?.total ? `进度：${progress.current}/${progress.total}` : "进度：准备中";
    return [
      `任务号：${props.riskTask.task_id}`,
      `线路号：${props.riskTask.route_id || "--"}`,
      `状态：风险评估中`,
      progressText,
    ];
  }

  if (!props.preprocessTask || !shouldShowTaskState.value) {
    return [];
  }

  return [
    `任务号：${props.preprocessTask.task_id}`,
    `线路号：${props.preprocessTask.route_id || "--"}`,
    `状态：${props.preprocessTask.status}`,
  ];
});
const workflowSteps = computed(() => {
  const preprocessStatus = props.preprocessTask?.status;
  const riskStatus = props.riskTask?.status;
  const isTxtReady = selectedTowerCount.value === 4 && Boolean(envTxtFile.value);
  return [
    {
      key: "basic",
      label: "基础信息",
      status: preprocessStatus ? "done" : routeId.value.trim() && towerType.value ? "done" : "active",
      loading: false,
    },
    {
      key: "txt",
      label: "TXT 文件校验",
      status: preprocessStatus ? "done" : isTxtReady ? "done" : "pending",
      loading: false,
    },
    {
      key: "preprocess",
      label: "预处理",
      status: preprocessStatus === "failed" ? "error" : preprocessStatus === "completed" ? "done" : isSubmittingAnalysis.value ? "active" : "pending",
      loading: preprocessStatus === "queued" || preprocessStatus === "running" || isSubmittingRequest.value,
    },
    {
      key: "analysis",
      label: "数据分析",
      status: props.hasAnalysisResult ? "done" : "pending",
      loading: false,
    },
    {
      key: "risk",
      label: "风险评估",
      status: riskStatus === "failed" ? "error" : riskStatus === "completed" ? "done" : riskStatus === "queued" || riskStatus === "running" ? "active" : "pending",
      loading: riskStatus === "queued" || riskStatus === "running",
    },
  ];
});

function getCurrentFormState(): PersistedInputFormState {
  return {
    routeId: routeId.value,
    towerType: towerType.value,
    towerTxtFiles: { ...towerTxtFiles.value },
    envTxtFile: envTxtFile.value,
    imageFiles: [...imageFiles.value],
    pointCloudFiles: [...pointCloudFiles.value],
    updatedAt: new Date().toISOString(),
  };
}

function saveInputFormState(): void {
  if (isClearingPersistedForm) {
    return;
  }

  localStorage.setItem(INPUT_FORM_STORAGE_KEY, JSON.stringify(getCurrentFormState()));
}

function restoreInputFormState(): PersistedInputFormState | null {
  const rawState = localStorage.getItem(INPUT_FORM_STORAGE_KEY);
  if (!rawState) {
    return null;
  }

  try {
    return JSON.parse(rawState) as PersistedInputFormState;
  } catch (error) {
    localStorage.removeItem(INPUT_FORM_STORAGE_KEY);
    console.error(error);
    return null;
  }
}

async function applyInputFormState(state: PersistedInputFormState): Promise<void> {
  routeId.value = state.routeId ?? "";
  towerType.value = towerTypes.some((item) => item.value === state.towerType) ? state.towerType : towerTypes[0].value;
  towerTxtFiles.value = {
    tower1: state.towerTxtFiles?.tower1 ?? "",
    tower2: state.towerTxtFiles?.tower2 ?? "",
    tower3: state.towerTxtFiles?.tower3 ?? "",
    tower4: state.towerTxtFiles?.tower4 ?? "",
  };
  envTxtFile.value = state.envTxtFile ?? "";
  imageFiles.value = Array.isArray(state.imageFiles) ? state.imageFiles : [];
  pointCloudFiles.value = Array.isArray(state.pointCloudFiles) ? state.pointCloudFiles : [];

  if (imageFiles.value[0]) {
    imagePreviewUrl.value = await window.ccx.createImagePreview(imageFiles.value[0]).catch(() => "");
  }
}

function clearInputFormState(): void {
  isClearingPersistedForm = true;
  localStorage.removeItem(INPUT_FORM_STORAGE_KEY);
  routeId.value = "";
  towerType.value = towerTypes[0].value;
  towerTxtFiles.value = {
    tower1: "",
    tower2: "",
    tower3: "",
    tower4: "",
  };
  envTxtFile.value = "";
  imagePreviewUrl.value = "";
  imageFiles.value = [];
  pointCloudFiles.value = [];
  analysisSubmitMessage.value = "";
  analysisSubmitError.value = "";

  window.setTimeout(() => {
    isClearingPersistedForm = false;
    localStorage.removeItem(INPUT_FORM_STORAGE_KEY);
  }, 0);
}

function getFileName(filePath: string): string {
  return filePath.split(/[\\/]/).filter(Boolean).at(-1) ?? filePath;
}

function formatSelectionDetail(filePaths: string[], emptyText: string): string {
  if (!filePaths.length) {
    return emptyText;
  }

  const fileNames = filePaths.slice(0, 2).map(getFileName);
  const extraCount = filePaths.length - fileNames.length;
  return extraCount > 0 ? `${fileNames.join("、")} 等 ${filePaths.length} 项` : fileNames.join("、");
}

function isTxtFile(filePath: string): boolean {
  return /\.txt$/i.test(filePath);
}

function isPcdFile(filePath: string): boolean {
  return /\.pcd$/i.test(filePath);
}

function getFileStatus(filePath: string, expectedName?: string): "empty" | "ok" | "warning" {
  if (!filePath) {
    return "empty";
  }
  if (!isTxtFile(filePath)) {
    return "warning";
  }
  if (expectedName && getFileName(filePath).toLowerCase() !== expectedName.toLowerCase()) {
    return "warning";
  }
  return "ok";
}

function getFileDetail(filePath: string, expectedName: string): string {
  if (!filePath) {
    return `等待选择 ${expectedName}`;
  }
  const fileName = getFileName(filePath);
  if (!isTxtFile(filePath)) {
    return "文件扩展名不是 TXT";
  }
  if (fileName.toLowerCase() !== expectedName.toLowerCase()) {
    return `已选 ${fileName}，请核对是否对应 ${expectedName}`;
  }
  return filePath;
}

async function selectTowerTxt(slot: TowerTxtKey, expectedName: string): Promise<void> {
  const selectedPaths = await window.ccx.selectTxtFile(`选择 ${expectedName}`);
  const selectedPath = selectedPaths[0];
  if (!selectedPath) {
    return;
  }

  towerTxtFiles.value = {
    ...towerTxtFiles.value,
    [slot]: selectedPath,
  };
}

async function selectEnvTxt(): Promise<void> {
  const selectedPaths = await window.ccx.selectTxtFile("选择 env.TXT");
  const selectedPath = selectedPaths[0];
  if (!selectedPath) {
    return;
  }

  envTxtFile.value = selectedPath;
}

async function selectImages(): Promise<void> {
  const result = await window.ccx.selectImages();
  imageFiles.value = result.paths;
  imagePreviewUrl.value = result.previewUrl;
}

async function selectPointCloud(): Promise<void> {
  const selectedPaths = await window.ccx.selectPointCloud();
  if (!selectedPaths.length) {
    return;
  }

  if (!isPcdFile(selectedPaths[0])) {
    analysisSubmitError.value = "点云文件只支持 PCD 格式。";
    analysisSubmitMessage.value = "";
    return;
  }

  pointCloudFiles.value = selectedPaths;
}

function validateForm(): string {
  if (!routeId.value.trim()) {
    return "请输入线路号。";
  }
  if (!towerType.value) {
    return "请选择杆塔类型。";
  }
  if (selectedTowerCount.value !== 4) {
    return "请完整选择 4 个塔基端 TXT 文件。";
  }
  if (!envTxtFile.value) {
    return "请选择探地端 env.TXT 文件。";
  }
  const nonTxtFile = [...Object.values(towerTxtFiles.value), envTxtFile.value].find((filePath) => !isTxtFile(filePath));
  if (nonTxtFile) {
    return `文件 ${getFileName(nonTxtFile)} 不是 TXT 格式。`;
  }
  const nonPcdFile = pointCloudFiles.value.find((filePath) => !isPcdFile(filePath));
  if (nonPcdFile) {
    return `点云文件 ${getFileName(nonPcdFile)} 不是 PCD 格式。`;
  }
  return "";
}

async function handleSubmitPreprocess(): Promise<void> {
  if (isSubmittingAnalysis.value) {
    return;
  }

  const validationError = validateForm();
  if (validationError) {
    analysisSubmitError.value = validationError;
    analysisSubmitMessage.value = "";
    return;
  }

  if (!props.apiBaseUrl) {
    analysisSubmitError.value = "后端服务尚未连接，请稍后重试。";
    analysisSubmitMessage.value = "";
    return;
  }

  isSubmittingRequest.value = true;
  analysisSubmitError.value = "";
  analysisSubmitMessage.value = "预处理任务已提交，后端正在处理采集文件...";

  try {
    const task = await submitPreprocessTask(props.apiBaseUrl, {
      route_id: routeId.value.trim(),
      tower_type: selectedTowerType.value.value,
      inp_file: selectedTowerType.value.inpFile,
      tower_txt_files: towerTxtFiles.value,
      env_txt_file: envTxtFile.value,
      image_files: imageFiles.value,
      point_cloud_files: pointCloudFiles.value,
    });
    analysisSubmitMessage.value = "预处理任务运行中，请等待...";
    saveInputFormState();
    emit("analysisSubmitted", task);
  } catch (error) {
    analysisSubmitError.value = error instanceof Error ? error.message : String(error);
  } finally {
    isSubmittingRequest.value = false;
  }
}

onMounted(() => {
  const restoredState = restoreInputFormState();
  if (restoredState) {
    void applyInputFormState(restoredState);
  }
});

watch(
  [routeId, towerType, towerTxtFiles, envTxtFile, imageFiles, pointCloudFiles],
  () => {
    saveInputFormState();
  },
  { deep: true },
);

watch(
  () => props.riskTask?.status,
  (status) => {
    if (status === "completed") {
      clearInputFormState();
    }
  },
);

</script>

<template>
  <section class="page-grid input-page">
    <div class="wide-panel route-panel import-form-panel">
      <div class="panel-title">
        <div>
          <span>采集批次</span>
          <h2>预处理数据导入</h2>
        </div>
        <strong>{{ panelStatusLabel }}</strong>
      </div>

      <div class="import-form preprocess-form">
        <div class="route-field preprocess-basic">
          <div class="preprocess-basic-grid">
            <label class="form-control">
              <span class="field-label required">线路号</span>
              <input
                v-model="routeId"
                type="text"
                placeholder="请输入线路号，例如 YX-2026-04-17"
                :disabled="isSubmittingAnalysis"
              />
            </label>

            <label class="form-control">
              <span class="field-label">杆塔类型</span>
              <select v-model="towerType" :disabled="isSubmittingAnalysis">
                <option v-for="item in towerTypes" :key="item.value" :value="item.value">
                  {{ item.label }}
                </option>
              </select>
            </label>
          </div>
        </div>

        <div class="preprocess-section">
          <div class="section-heading">
            <div>
              <span>塔基端 SD 卡文件</span>
              <h3>4 个杆塔 TXT 文件</h3>
            </div>
            <strong>{{ selectedTowerCount }}/4</strong>
          </div>

          <div class="txt-file-grid">
            <article
              v-for="slot in towerTxtSlots"
              :key="slot.key"
              class="txt-file-tile"
              :class="getFileStatus(towerTxtFiles[slot.key], slot.expectedName)"
            >
              <div>
                <span>{{ slot.label }}</span>
                <strong>{{ towerTxtFiles[slot.key] ? getFileName(towerTxtFiles[slot.key]) : slot.expectedName }}</strong>
                <small>{{ getFileDetail(towerTxtFiles[slot.key], slot.expectedName) }}</small>
              </div>
              <button type="button" :disabled="isSubmittingAnalysis" @click="selectTowerTxt(slot.key, slot.expectedName)">
                {{ towerTxtFiles[slot.key] ? "重新选择" : "选择文件" }}
              </button>
            </article>
          </div>
        </div>

        <div class="preprocess-section env-section">
          <div class="section-heading">
            <div>
              <span>探地端 SD 卡文件</span>
              <h3>环境与地质监测 TXT</h3>
            </div>
            <strong>{{ envTxtFile ? "已选择" : "待选择" }}</strong>
          </div>

          <article class="txt-file-tile env-file-tile" :class="getFileStatus(envTxtFile, 'env.TXT')">
            <div>
              <span>探地端 env</span>
              <strong>{{ envTxtFile ? getFileName(envTxtFile) : "env.TXT" }}</strong>
              <small>{{ getFileDetail(envTxtFile, "env.TXT") }}</small>
            </div>
            <button type="button" :disabled="isSubmittingAnalysis" @click="selectEnvTxt">
              {{ envTxtFile ? "重新选择" : "选择文件" }}
            </button>
          </article>
        </div>

        <div class="preprocess-section optional-attachments">
          <div class="section-heading">
            <div>
              <span>辅助材料</span>
              <h3>图片与点云文件</h3>
            </div>
            <strong>可选</strong>
          </div>

          <div class="attachment-grid">
            <article class="attachment-tile" :class="{ selected: imageFiles.length > 0 }">
              <div v-if="imagePreviewUrl" class="upload-preview">
                <img :src="imagePreviewUrl" alt="已选择图片预览" />
              </div>
              <span>航拍 / 手机图片</span>
              <strong>{{ imageFiles.length ? `${imageFiles.length} 张图片` : "未选择图片" }}</strong>
              <small>{{ formatSelectionDetail(imageFiles, "支持 JPG、PNG、TIFF、WEBP") }}</small>
              <button type="button" :disabled="isSubmittingAnalysis" @click="selectImages">
                {{ imageFiles.length ? "重新选择" : "选择图片" }}
              </button>
            </article>

            <article class="attachment-tile" :class="{ selected: pointCloudFiles.length > 0 }">
              <span>点云文件</span>
              <strong>{{ pointCloudFiles.length ? getFileName(pointCloudFiles[0]) : "未选择点云文件" }}</strong>
              <small>{{ formatSelectionDetail(pointCloudFiles, "仅支持 PCD 格式") }}</small>
              <button type="button" :disabled="isSubmittingAnalysis" @click="selectPointCloud">
                {{ pointCloudFiles.length ? "重新选择" : "选择文件" }}
              </button>
            </article>
          </div>
        </div>

        <div class="preprocess-actions">
          <div v-if="taskStatusText" class="task-status" :class="{ error: taskStatusHasError }">
            <span>{{ taskStatusText }}</span>
            <small v-for="item in taskMetaItems" :key="item">{{ item }}</small>
          </div>
          <button type="button" :disabled="isSubmittingAnalysis" @click="handleSubmitPreprocess">
            {{ isSubmittingAnalysis ? "请等待" : "开始处理" }}
          </button>
        </div>
      </div>

      <div class="step-strip">
        <span
          v-for="(step, index) in workflowSteps"
          :key="step.key"
          :class="[step.status, { loading: step.loading }]"
        >
          <i v-if="step.loading" aria-hidden="true"></i>
          {{ index + 1 }}. {{ step.label }}
        </span>
      </div>
    </div>
  </section>
</template>

