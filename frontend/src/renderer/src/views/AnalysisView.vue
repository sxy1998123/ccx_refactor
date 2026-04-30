<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import PointCloudViewer from "../components/PointCloudViewer.vue";
import { getPreprocessResult, type PreprocessResult } from "../services/api";

type PageKey = "input" | "analysis" | "database" | "risk";

const props = defineProps<{
  apiBaseUrl: string;
  hasAnalysisResult: boolean;
  preprocessTaskId: string;
}>();

const emit = defineEmits<{
  navigate: [page: PageKey];
}>();

const preprocessResult = ref<PreprocessResult | null>(null);
const imagePreviewUrls = ref<string[]>([]);
const resultError = ref("");
const isLoadingResult = ref(false);
const isImageDialogOpen = ref(false);
const isPointCloudDialogOpen = ref(false);

const analysisPlaceholderSteps = ["输入线路编号", "选择 TXT、图片和点云文件", "点击开始预处理", "生成数据分析结果"];

const environmentNameMap: Record<string, string> = {
  EnvironmentHumidity: "湿度",
  EnvironmentLight: "光照",
  EnvironmentPress: "气压",
  EnvironmentRainfall: "环境降雨量",
  EnvironmentTemperature: "环境温度",
  EnvironmentWinddirection: "环境风向",
  EnvironmentWindspeed: "风速",
  SoilHumidity: "土壤湿度",
  SoilTemperature: "土壤温度",
};

const imageFiles = computed(() => preprocessResult.value?.inputs?.image_files ?? []);
const pointCloudFiles = computed(() => preprocessResult.value?.inputs?.point_cloud_files ?? []);
const hasImages = computed(() => imageFiles.value.length > 0);
const hasPointCloud = computed(() => pointCloudFiles.value.length > 0);
const hasMedia = computed(() => hasImages.value || hasPointCloud.value);
const pointCloudManifestPath = computed(() =>
  props.preprocessTaskId ? `/api/preprocess/tasks/${props.preprocessTaskId}/pointcloud/potree/manifest` : "",
);

const towerTypeName = computed(() => {
  const towerType = preprocessResult.value?.tower_type;
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

const environmentMetrics = computed(() => {
  const metrics = preprocessResult.value?.environment?.metrics;
  if (!metrics) {
    return [];
  }

  return Object.entries(environmentNameMap)
    .filter(([key]) => metrics[key])
    .map(([key, label]) => [label, formatMetric(metrics[key].value, metrics[key].unit)] as [string, string]);
});

const gnssMetrics = computed(() => {
  const summary = preprocessResult.value?.tower_summary;
  return [
    ["平均纬度", formatNullable(summary?.mean_lat, "", 10)],
    ["平均经度", formatNullable(summary?.mean_lon, "", 10)],
    ["平均海拔", formatNullable(summary?.mean_alt_m, "m", 3)],
  ];
});

const displacementMetrics = computed(() => {
  const displacement = preprocessResult.value?.tower_summary?.ccx_displacement_m;
  return [
    ["X 坐标位移", formatNullable(displacement?.x, "m", 6)],
    ["Y 坐标位移", formatNullable(displacement?.y, "m", 6)],
    ["Z 坐标位移", formatNullable(displacement?.z, "m", 6)],
  ];
});

const towerRows = computed(() => {
  const results = preprocessResult.value?.tower_results ?? {};
  return Object.entries(results).map(([slot, result]) => ({
    slot,
    fileName: result.file_name,
    targetDate: result.target_date,
    x: formatNullable(result.imu.x_drift_m, "m", 6),
    y: formatNullable(result.imu.y_drift_m, "m", 6),
    z: formatNullable(result.imu.z_drift_m, "m", 6),
  }));
});

const overviewCards = computed(() => {
  const result = preprocessResult.value;
  const summary = result?.tower_summary;
  const environment = result?.environment;
  return [
    ["线路编号", result?.route_id || "--"],
    ["杆塔类型", towerTypeName.value],
    ["塔基文件", `${summary?.tower_count ?? (towerRows.value.length || 0)}/4`],
    ["环境记录", environment?.record_count ? `${environment.record_count} 条` : "--"],
    ["最大沉降", formatNullable(summary?.max_total_drift_mm, "mm", 3)],
    ["采样结束", environment?.end_time || "--"],
  ];
});

function formatMetric(value: number, unit: string): string {
  return `${value.toFixed(4)}${unit ? ` ${unit}` : ""}`;
}

function formatNullable(value: number | null | undefined, unit: string, digits: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${value.toFixed(digits)}${unit ? ` ${unit}` : ""}`;
}

function getFileName(filePath: string): string {
  return filePath.split(/[\\/]/).filter(Boolean).at(-1) ?? filePath;
}

async function loadResult(): Promise<void> {
  if (!props.apiBaseUrl || !props.preprocessTaskId) {
    return;
  }

  isLoadingResult.value = true;
  resultError.value = "";
  try {
    const result = await getPreprocessResult(props.apiBaseUrl, props.preprocessTaskId);
    preprocessResult.value = result;
    await loadImagePreviews(result.inputs?.image_files ?? []);
  } catch (error) {
    resultError.value = error instanceof Error ? error.message : String(error);
  } finally {
    isLoadingResult.value = false;
  }
}

async function loadImagePreviews(paths: string[]): Promise<void> {
  imagePreviewUrls.value = [];
  if (!paths.length) {
    return;
  }

  const previews = await Promise.all(paths.slice(0, 6).map((path) => window.ccx.createImagePreview(path)));
  imagePreviewUrls.value = previews.filter(Boolean);
}

onMounted(loadResult);
watch(() => [props.apiBaseUrl, props.preprocessTaskId], loadResult);
</script>

<template>
  <section class="page-grid analysis-page">
    <template v-if="!hasAnalysisResult">
      <div class="wide-panel empty-state-panel analysis-empty">
        <div class="empty-copy">
          <span class="empty-eyebrow">等待分析</span>
          <h2>尚未生成数据分析结果</h2>
          <p>完成输入数据页的线路编号、TXT 文件、图片和点云文件选择后，点击开始预处理。</p>
          <div class="empty-actions">
            <button type="button" class="primary-button" @click="emit('navigate', 'input')">返回输入数据</button>
            <button type="button" class="ghost-button" disabled>生成评估报告</button>
          </div>
        </div>

        <div class="skeleton-workspace" aria-label="数据分析占位骨架">
          <div class="skeleton-toolbar">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <div class="skeleton-stage">
            <div class="skeleton-canvas">
              <div class="tower-wire one"></div>
              <div class="tower-wire two"></div>
              <div class="tower-shape"></div>
              <div class="ground-cloud"></div>
            </div>
            <div class="skeleton-metrics">
              <span></span>
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </div>

      <div class="wide-panel placeholder-steps">
        <article v-for="(step, index) in analysisPlaceholderSteps" :key="step">
          <span>{{ index + 1 }}</span>
          <strong>{{ step }}</strong>
        </article>
      </div>
    </template>

    <template v-else>
      <div v-if="isLoadingResult || resultError" class="wide-panel task-status" :class="{ error: resultError }">
        <span>{{ resultError || "正在加载预处理结果..." }}</span>
      </div>

      <div class="wide-panel analysis-overview-panel">
        <div class="panel-title">
          <div>
            <span>预处理结果</span>
            <h2>数据分析总览</h2>
          </div>
          <strong>{{ preprocessResult?.status || "loading" }}</strong>
        </div>
        <div class="analysis-overview-grid">
          <article v-for="[name, value] in overviewCards" :key="name">
            <span>{{ name }}</span>
            <strong>{{ value }}</strong>
          </article>
        </div>
      </div>

      <div class="wide-panel analysis-metrics-panel">
        <section class="analysis-metric-card environment-card">
          <div class="compact-section-title">
            <span>环境采样</span>
            <strong>{{ preprocessResult?.environment?.end_time || "--" }}</strong>
          </div>
          <dl class="compact-metric-grid">
            <div v-for="[name, value] in environmentMetrics" :key="name">
              <dt>{{ name }}</dt>
              <dd>{{ value }}</dd>
            </div>
          </dl>
        </section>

        <section class="analysis-metric-card position-card">
          <div class="compact-section-title">
            <span>位置与沉降</span>
            <strong>XYZ</strong>
          </div>
          <div class="compact-detail-columns">
            <dl>
              <div v-for="[name, value] in gnssMetrics" :key="name">
                <dt>{{ name }}</dt>
                <dd>{{ value }}</dd>
              </div>
            </dl>
            <dl>
              <div v-for="[name, value] in displacementMetrics" :key="name">
                <dt>{{ name }}</dt>
                <dd>{{ value }}</dd>
              </div>
            </dl>
          </div>
        </section>

        <section class="analysis-metric-card tower-card">
          <div class="compact-section-title">
            <span>塔基端预处理</span>
            <strong>{{ towerRows.length }}/4</strong>
          </div>
          <div class="analysis-table compact-analysis-table">
            <div class="analysis-table-row header">
              <span>端点</span>
              <span>文件</span>
              <span>日期</span>
              <span>X</span>
              <span>Y</span>
              <span>Z</span>
            </div>
            <div v-for="row in towerRows" :key="row.slot" class="analysis-table-row">
              <span>{{ row.slot }}</span>
              <span>{{ row.fileName }}</span>
              <span>{{ row.targetDate }}</span>
              <span>{{ row.x }}</span>
              <span>{{ row.y }}</span>
              <span>{{ row.z }}</span>
            </div>
          </div>
        </section>
      </div>

      <div v-if="hasMedia" class="wide-panel analysis-media-panel" :class="{ 'single-media': !hasImages || !hasPointCloud }">
        <section v-if="hasImages" class="analysis-media-card">
          <div class="compact-section-title">
            <span>现场图片</span>
            <div class="compact-section-actions">
              <strong>{{ imageFiles.length }} 张</strong>
              <button type="button" @click="isImageDialogOpen = true">查看图片</button>
            </div>
          </div>
          <div class="analysis-image-grid">
            <figure v-for="(previewUrl, index) in imagePreviewUrls" :key="previewUrl">
              <img :src="previewUrl" :alt="getFileName(imageFiles[index])" />
              <figcaption>{{ getFileName(imageFiles[index]) }}</figcaption>
            </figure>
          </div>
        </section>

        <section v-if="hasPointCloud" class="analysis-media-card">
          <div class="compact-section-title">
            <span>点云预览</span>
            <div class="compact-section-actions">
              <strong>PCD / Potree</strong>
              <button type="button" @click="isPointCloudDialogOpen = true">查看点云</button>
            </div>
          </div>
          <PointCloudViewer :base-url="apiBaseUrl" :manifest-path="pointCloudManifestPath" />
        </section>
      </div>

      <Teleport to="body">
        <div v-if="isImageDialogOpen" class="analysis-dialog-backdrop" @click.self="isImageDialogOpen = false">
          <section class="analysis-dialog image-dialog" role="dialog" aria-modal="true" aria-label="查看图片">
            <header class="analysis-dialog-header">
              <div>
                <span>现场图片</span>
                <h2>图片列表</h2>
              </div>
              <button type="button" @click="isImageDialogOpen = false">关闭</button>
            </header>

            <div class="dialog-image-list">
              <figure v-for="(previewUrl, index) in imagePreviewUrls" :key="previewUrl">
                <div class="dialog-image-stage">
                  <img :src="previewUrl" :alt="getFileName(imageFiles[index])" />
                </div>
                <figcaption>{{ getFileName(imageFiles[index]) }}</figcaption>
              </figure>
            </div>
          </section>
        </div>

        <div v-if="isPointCloudDialogOpen" class="analysis-dialog-backdrop" @click.self="isPointCloudDialogOpen = false">
          <section class="analysis-dialog pointcloud-dialog" role="dialog" aria-modal="true" aria-label="查看点云">
            <header class="analysis-dialog-header">
              <div>
                <span>点云预览</span>
                <h2>点云显示详情</h2>
              </div>
              <button type="button" @click="isPointCloudDialogOpen = false">关闭</button>
            </header>

            <div class="dialog-file-list">
              <span v-for="filePath in pointCloudFiles" :key="filePath">{{ getFileName(filePath) }}</span>
            </div>

            <div class="dialog-pointcloud-stage">
              <PointCloudViewer :base-url="apiBaseUrl" :manifest-path="pointCloudManifestPath" />
            </div>
          </section>
        </div>
      </Teleport>
    </template>
  </section>
</template>
