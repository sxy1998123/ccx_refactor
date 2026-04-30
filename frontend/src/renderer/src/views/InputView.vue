<script setup lang="ts">
import { computed, ref } from "vue";
import { getPreprocessTask, submitPreprocessTask } from "../services/api";

type TowerTxtKey = "tower1" | "tower2" | "tower3" | "tower4";

type TowerTypeOption = {
  label: string;
  value: string;
  inpFile: string;
};

const props = defineProps<{
  apiBaseUrl: string;
  hasAnalysisResult: boolean;
}>();

const emit = defineEmits<{
  analysisCompleted: [taskId: string];
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
const isSubmittingAnalysis = ref(false);
const analysisSubmitMessage = ref("");
const analysisSubmitError = ref("");

const selectedTowerType = computed(() => towerTypes.find((item) => item.value === towerType.value) ?? towerTypes[0]);
const selectedTowerCount = computed(() => Object.values(towerTxtFiles.value).filter(Boolean).length);
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

  isSubmittingAnalysis.value = true;
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
    const completedTask = await waitForPreprocessTask(task.task_id);
    if (completedTask.status === "failed") {
      throw new Error(completedTask.message || "预处理任务失败");
    }
    analysisSubmitMessage.value = "预处理完成，正在进入数据分析页...";
    emit("analysisCompleted", task.task_id);
  } catch (error) {
    analysisSubmitError.value = error instanceof Error ? error.message : String(error);
  } finally {
    isSubmittingAnalysis.value = false;
  }
}

async function waitForPreprocessTask(taskId: string) {
  for (;;) {
    const task = await getPreprocessTask(props.apiBaseUrl, taskId);
    if (task.status === "completed" || task.status === "failed") {
      return task;
    }
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
}
</script>

<template>
  <section class="page-grid input-page">
    <div class="wide-panel route-panel import-form-panel">
      <div class="panel-title">
        <div>
          <span>采集批次</span>
          <h2>预处理数据导入</h2>
        </div>
        <strong>{{ isSubmittingAnalysis ? "处理中" : hasAnalysisResult ? "已完成" : "未开始" }}</strong>
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
          <div v-if="analysisSubmitMessage || analysisSubmitError" class="task-status" :class="{ error: analysisSubmitError }">
            <span>{{ analysisSubmitError || analysisSubmitMessage }}</span>
          </div>
          <button type="button" :disabled="isSubmittingAnalysis" @click="handleSubmitPreprocess">
            {{ isSubmittingAnalysis ? "请等待" : "开始预处理" }}
          </button>
        </div>
      </div>

      <div class="step-strip">
        <span>1. 基础信息</span>
        <span>2. TXT 文件校验</span>
        <span>3. 预处理任务</span>
        <span>4. 数据分析</span>
      </div>
    </div>
  </section>
</template>
