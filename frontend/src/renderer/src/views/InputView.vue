<script setup lang="ts">
import { computed, ref } from "vue";
import { submitDemoAnalysisTask } from "../services/api";

type UploadKey = "images" | "towerSd" | "groundSd" | "pointCloud";

const props = defineProps<{
  apiBaseUrl: string;
  hasAnalysisResult: boolean;
}>();

const emit = defineEmits<{
  analysisCompleted: [];
}>();

const imagePreviewUrl = ref("");
const routeId = ref("");
const isSubmittingAnalysis = ref(false);
const analysisSubmitMessage = ref("");
const analysisSubmitError = ref("");
const selectedInputs = ref<Record<UploadKey, string[]>>({
  images: [],
  towerSd: [],
  groundSd: [],
  pointCloud: [],
});

const uploadSources = computed(() => [
  {
    key: "images" as const,
    label: "航拍 / 手机图片",
    value: selectedInputs.value.images.length ? `${selectedInputs.value.images.length} 张图片` : "未选择图片",
    action: selectedInputs.value.images.length ? "重新选择" : "选择图片",
    detail: formatSelectionDetail(selectedInputs.value.images, "支持 JPG、PNG、TIFF、WEBP"),
    previewUrl: imagePreviewUrl.value,
  },
  {
    key: "towerSd" as const,
    label: "塔基端 SD 卡文件",
    value: `${selectedInputs.value.towerSd.length}/4 个采集端`,
    action: selectedInputs.value.towerSd.length ? "重新选择" : "选择目录",
    detail: formatSelectionDetail(selectedInputs.value.towerSd, "请选择 4 个塔基端 SD 卡目录"),
    previewUrl: "",
  },
  {
    key: "groundSd" as const,
    label: "探地端 SD 卡文件",
    value: `${selectedInputs.value.groundSd.length}/1 个采集端`,
    action: selectedInputs.value.groundSd.length ? "重新选择" : "选择目录",
    detail: formatSelectionDetail(selectedInputs.value.groundSd, "请选择 1 个探地端 SD 卡目录"),
    previewUrl: "",
  },
  {
    key: "pointCloud" as const,
    label: "点云文件",
    value: selectedInputs.value.pointCloud.length ? getFileName(selectedInputs.value.pointCloud[0]) : "未选择点云文件",
    action: selectedInputs.value.pointCloud.length ? "重新选择" : "选择文件",
    detail: formatSelectionDetail(selectedInputs.value.pointCloud, "支持 LAS、LAZ、PCD、PLY、E57"),
    previewUrl: "",
  },
]);

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

async function handleValidateRoute(): Promise<void> {
  if (isSubmittingAnalysis.value) {
    return;
  }

  if (!routeId.value.trim()) {
    routeId.value = "YX-2026-04-17";
  }

  if (!props.apiBaseUrl) {
    analysisSubmitError.value = "后端服务尚未连接，请稍后重试。";
    return;
  }

  isSubmittingAnalysis.value = true;
  analysisSubmitError.value = "";
  analysisSubmitMessage.value = "任务已提交，后端正在处理，请等待...";

  try {
    const result = await submitDemoAnalysisTask(props.apiBaseUrl, routeId.value);
    routeId.value = result.route_id;
    analysisSubmitMessage.value = "分析完成，正在进入数据分析页...";
    emit("analysisCompleted");
  } catch (error) {
    analysisSubmitError.value = error instanceof Error ? error.message : String(error);
  } finally {
    isSubmittingAnalysis.value = false;
  }
}

async function handleSelectUpload(key: UploadKey): Promise<void> {
  let selectedPaths: string[] = [];

  if (key === "images") {
    const result = await window.ccx.selectImages();
    selectedPaths = result.paths;
    if (result.previewUrl) {
      imagePreviewUrl.value = result.previewUrl;
    }
  } else if (key === "towerSd") {
    selectedPaths = await window.ccx.selectTowerSdDirectories();
  } else if (key === "groundSd") {
    selectedPaths = await window.ccx.selectGroundSdDirectory();
  } else {
    selectedPaths = await window.ccx.selectPointCloud();
  }

  if (!selectedPaths.length) {
    return;
  }

  selectedInputs.value = {
    ...selectedInputs.value,
    [key]: selectedPaths,
  };
}
</script>

<template>
  <section class="page-grid input-page">
    <div class="wide-panel route-panel import-form-panel">
      <div class="panel-title">
        <div>
          <span>线路信息</span>
          <h2>采集批次导入</h2>
        </div>
        <strong>{{ isSubmittingAnalysis ? "处理中" : hasAnalysisResult ? "已完成" : "未开始" }}</strong>
      </div>

      <div class="import-form">
        <div class="route-field">
          <label class="field-label required" for="route-id">线路号</label>
          <div class="route-input">
            <input
              id="route-id"
              v-model="routeId"
              type="text"
              placeholder="请输入线路号，例如 YX-2026-04-17"
              aria-label="线路号"
            />
            <button type="button" :disabled="isSubmittingAnalysis" @click="handleValidateRoute">
              {{ isSubmittingAnalysis ? "请等待" : "校验线路" }}
            </button>
          </div>
          <p class="field-hint">请先输入线路号，系统会按线路号归档图片、SD 卡文件和点云文件。</p>
          <div v-if="analysisSubmitMessage || analysisSubmitError" class="task-status" :class="{ error: analysisSubmitError }">
            <span>{{ analysisSubmitError || analysisSubmitMessage }}</span>
          </div>
        </div>

        <div class="upload-picker-grid">
          <article
            v-for="source in uploadSources"
            :key="source.key"
            class="upload-tile"
            :class="{ selected: selectedInputs[source.key].length > 0 }"
          >
            <div v-if="source.previewUrl" class="upload-preview">
              <img :src="source.previewUrl" alt="已选择图片预览" />
            </div>
            <span>{{ source.label }}</span>
            <strong>{{ source.value }}</strong>
            <small>{{ source.detail }}</small>
            <button type="button" @click="handleSelectUpload(source.key)">{{ source.action }}</button>
          </article>
        </div>
      </div>

      <div class="step-strip">
        <span>1. 基础信息</span>
        <span>2. 文件校验</span>
        <span>3. 任务入队</span>
        <span>4. 分析就绪</span>
      </div>
    </div>
  </section>
</template>
