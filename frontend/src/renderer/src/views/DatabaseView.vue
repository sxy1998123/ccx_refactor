<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  ElAlert,
  ElButton,
  ElCard,
  ElDatePicker,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElSpace,
  ElTabPane,
  ElTable,
  ElTableColumn,
  ElTabs,
  ElTag,
} from "element-plus";
import {
  createDatabaseRecord,
  deleteDatabaseRecord,
  getDatabaseSchema,
  getPreprocessResult,
  listDatabaseRecords,
  type DatabaseField,
  type DatabaseRecord,
  type DatabaseSchema,
  type HazardMetricsSummary,
} from "../services/api";

type DatabaseTabKey = "towers" | "geology_records";
type InputType = "number" | "text";
type ViewMode = "list" | "create" | "detail";

const AUTO_FIELDS = new Set(["created_at", "updated_at"]);
const EXAMPLE_FIELDS = ["example1", "example2", "example3", "example4", "example5"] as const;

const props = defineProps<{
  apiBaseUrl: string;
  preprocessTaskId: string;
}>();

const tabs: Array<{ key: DatabaseTabKey; label: string; description: string }> = [
  { key: "towers", label: "杆塔表", description: "线路、坐标、高度、杆塔属性、风险等级与图片" },
  { key: "geology_records", label: "地质表", description: "采样窗口环境数据、采集时间与图片" },
];

const activeTab = ref<DatabaseTabKey>("towers");
const viewMode = ref<ViewMode>("list");
const schema = ref<DatabaseSchema | null>(null);
const isLoadingSchema = ref(false);
const schemaError = ref("");
const records = ref<DatabaseRecord[]>([]);
const isLoadingRecords = ref(false);
const recordsError = ref("");
const listNotice = ref("");
const formValues = ref<Record<string, string>>({});
const imageDisplayNames = ref<Record<string, string>>({});
const isSubmittingRecord = ref(false);
const deletingRowid = ref<number | null>(null);
const submitError = ref("");
const selectedRecord = ref<DatabaseRecord | null>(null);
const detailImagePreviews = ref<Record<string, string>>({});
const isOpeningHazardData = ref(false);
const hazardMetrics = ref<HazardMetricsSummary | null>(null);
const isLoadingHazardMetrics = ref(false);
const hazardMetricsError = ref("");

const activeTable = computed(() => tabs.find((tab) => tab.key === activeTab.value) ?? tabs[0]);
const viewModeTitle = computed(() => {
  if (viewMode.value === "create") {
    return "添加数据";
  }

  if (viewMode.value === "detail") {
    return "数据详情";
  }

  return "数据列表";
});
const activeFields = computed(() => schema.value?.tables[activeTab.value]?.fields ?? []);
const activeFormFields = computed(() => activeFields.value.filter((field) => !AUTO_FIELDS.has(field.name)));
const baseFormFields = computed(() => activeFormFields.value.filter((field) => !isImageField(field)));
const imageFormFields = computed(() => activeFormFields.value.filter(isImageField));
const detailBaseFields = computed(() => activeFields.value.filter((field) => !isImageField(field)));
const detailImageFields = computed(() => activeFields.value.filter(isImageField));
const selectedExamplePaths = computed(() =>
  EXAMPLE_FIELDS.map((fieldName) => formValues.value[fieldName]).filter((value) => Boolean(value)),
);
const detailImageCount = computed(() =>
  detailImageFields.value.filter((field) => hasRecordValue(selectedRecord.value, field.name)).length,
);
const hazardMetricRows = computed(() => hazardMetrics.value?.overall ?? []);
const hasHazardMetrics = computed(() => Boolean(hazardMetrics.value?.available && hazardMetricRows.value.length));

async function loadSchema(): Promise<void> {
  if (!props.apiBaseUrl) {
    schemaError.value = "后端服务尚未连接，无法读取数据库结构。";
    return;
  }

  isLoadingSchema.value = true;
  schemaError.value = "";

  try {
    schema.value = await getDatabaseSchema(props.apiBaseUrl);
  } catch (error) {
    schemaError.value = error instanceof Error ? error.message : String(error);
  } finally {
    isLoadingSchema.value = false;
  }
}

async function loadRecords(): Promise<void> {
  if (!props.apiBaseUrl) {
    records.value = [];
    return;
  }

  isLoadingRecords.value = true;
  recordsError.value = "";

  try {
    const result = await listDatabaseRecords(props.apiBaseUrl, activeTab.value);
    records.value = result.records;
  } catch (error) {
    recordsError.value = error instanceof Error ? error.message : String(error);
  } finally {
    isLoadingRecords.value = false;
  }
}

async function loadHazardMetrics(): Promise<void> {
  hazardMetrics.value = null;
  hazardMetricsError.value = "";
  if (!props.apiBaseUrl || !props.preprocessTaskId) {
    return;
  }

  isLoadingHazardMetrics.value = true;
  try {
    const result = await getPreprocessResult(props.apiBaseUrl, props.preprocessTaskId);
    hazardMetrics.value = result.hazard_metrics ?? null;
    if (hazardMetrics.value?.available === false) {
      hazardMetricsError.value = hazardMetrics.value.message ?? "历史地质灾害指标不可用";
    }
  } catch (error) {
    hazardMetricsError.value = error instanceof Error ? error.message : String(error);
  } finally {
    isLoadingHazardMetrics.value = false;
  }
}

function enterCreateMode(): void {
  listNotice.value = "";
  submitError.value = "";
  syncFormValues(true);
  viewMode.value = "create";
}

function returnToList(): void {
  submitError.value = "";
  selectedRecord.value = null;
  detailImagePreviews.value = {};
  viewMode.value = "list";
}

function getInputType(field: DatabaseField): InputType {
  return field.type === "REAL" ? "number" : "text";
}

function getInputStep(field: DatabaseField): string | undefined {
  return field.type === "REAL" ? "0.000001" : undefined;
}

function isImageField(field: DatabaseField): boolean {
  return EXAMPLE_FIELDS.includes(field.name as (typeof EXAMPLE_FIELDS)[number]);
}

function isDateTimeField(field: DatabaseField): boolean {
  return field.name === "collected_at";
}

function getInputPlaceholder(field: DatabaseField): string {
  if (isDateTimeField(field)) {
    return `请选择${field.display_name}`;
  }

  return isImageField(field) ? "请选择图片，将以 base64 保存" : `请输入${field.display_name}`;
}

function formatRecordValue(record: DatabaseRecord, field: DatabaseField): string {
  const value = record[field.name];
  if (value === null || value === undefined || value === "") {
    return "--";
  }

  return isImageField(field) ? formatImageLabel(String(value)) : String(value);
}

function formatMetricValue(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 4 });
}

function formatThresholdSummary(row: { thresholds?: Array<{ hazard: string; expression: string }> }): string {
  const thresholds = row.thresholds ?? [];
  if (!thresholds.length) {
    return "--";
  }
  return thresholds.map((item) => `${item.hazard}${item.expression}`).join("；");
}

function formatTriggeredThresholds(row: { triggered_thresholds?: Array<{ hazard: string; expression: string }> }): string {
  const thresholds = row.triggered_thresholds ?? [];
  if (!thresholds.length) {
    return "未命中";
  }
  return thresholds.map((item) => `${item.hazard}${item.expression}`).join("；");
}

function getHazardMetricRowClassName({ row }: { row: { threshold_status?: string } }): string {
  return row.threshold_status === "warning" ? "hazard-metric-warning-row" : "";
}

function getTagType(field: DatabaseField, record: DatabaseRecord): "info" | "success" {
  const value = record[field.name];
  return value === null || value === undefined || value === "" ? "info" : "success";
}

function getRecordRowid(record: DatabaseRecord): number {
  return Number(record.rowid);
}

function hasRecordValue(record: DatabaseRecord | null, fieldName: string): boolean {
  const value = record?.[fieldName];
  return value !== null && value !== undefined && String(value).trim() !== "";
}

function getFileName(filePath: string): string {
  return filePath.split(/[\\/]/).filter(Boolean).at(-1) ?? filePath;
}

function isBase64ImageValue(value: string): boolean {
  return value.startsWith("data:image/");
}

function formatImageLabel(value: string): string {
  if (!value) {
    return "--";
  }

  return isBase64ImageValue(value) ? "Base64 图片" : getFileName(value);
}

function getImageFieldDisplay(fieldName: string): string {
  const value = formValues.value[fieldName];
  if (!value) {
    return "";
  }

  return imageDisplayNames.value[fieldName] ?? formatImageLabel(value);
}

function clearImageField(fieldName: string): void {
  const nextFormValues = { ...formValues.value };
  nextFormValues[fieldName] = "";
  formValues.value = nextFormValues;

  const nextDisplayNames = { ...imageDisplayNames.value };
  delete nextDisplayNames[fieldName];
  imageDisplayNames.value = nextDisplayNames;
}

function getRecordValue(record: DatabaseRecord | null, field: DatabaseField): string {
  const value = record?.[field.name];
  if (value === null || value === undefined || value === "") {
    return "--";
  }

  return String(value);
}

function getRecordImagePath(record: DatabaseRecord | null, field: DatabaseField): string {
  const value = record?.[field.name];
  return value === null || value === undefined ? "" : String(value);
}

function getRecordImageLabel(record: DatabaseRecord | null, field: DatabaseField): string {
  const value = getRecordImagePath(record, field);
  return value ? formatImageLabel(value) : "无图片";
}

function getRecordImageTitle(record: DatabaseRecord | null, field: DatabaseField): string {
  const value = getRecordImagePath(record, field);
  if (!value) {
    return "无图片";
  }

  return isBase64ImageValue(value) ? "Base64 图片已保存到数据库" : value;
}

async function loadDetailImagePreviews(record: DatabaseRecord): Promise<void> {
  const previewEntries = await Promise.all(
    detailImageFields.value.map(async (field) => {
      const imageValue = getRecordImagePath(record, field).trim();
      if (!imageValue) {
        return [field.name, ""] as const;
      }

      if (isBase64ImageValue(imageValue)) {
        return [field.name, imageValue] as const;
      }

      try {
        return [field.name, await window.ccx.createImagePreview(imageValue)] as const;
      } catch {
        return [field.name, ""] as const;
      }
    }),
  );

  if (selectedRecord.value !== record) {
    return;
  }

  detailImagePreviews.value = Object.fromEntries(previewEntries);
}

function enterDetailMode(record: DatabaseRecord): void {
  selectedRecord.value = record;
  submitError.value = "";
  detailImagePreviews.value = {};
  viewMode.value = "detail";
  void loadDetailImagePreviews(record);
}

function syncFormValues(reset: boolean): void {
  const nextValues: Record<string, string> = {};
  for (const field of activeFormFields.value) {
    nextValues[field.name] = reset ? "" : (formValues.value[field.name] ?? "");
  }
  formValues.value = nextValues;

  if (reset) {
    imageDisplayNames.value = {};
  }
}

function buildRecordPayload(): Record<string, string> {
  const payload: Record<string, string> = {};
  for (const field of activeFormFields.value) {
    const value = formValues.value[field.name]?.trim();
    if (value) {
      payload[field.name] = value;
    }
  }
  return payload;
}

async function handleSelectImageField(fieldName: string): Promise<void> {
  try {
    const result = await window.ccx.selectImages();
    const selectedImage = result.images?.[0];
    const selectedValue = selectedImage?.dataUrl || (isBase64ImageValue(result.previewUrl) ? result.previewUrl : "");
    if (!selectedValue) {
      if ((result.paths?.length ?? 0) > 0 || result.previewUrl) {
        ElMessage.error("图片未能转换为 base64，请重启应用后重新选择图片。");
      }
      return;
    }

    formValues.value = {
      ...formValues.value,
      [fieldName]: selectedValue,
    };
    imageDisplayNames.value = {
      ...imageDisplayNames.value,
      [fieldName]: selectedImage?.name ?? "Base64 图片",
    };
  } catch (error) {
    ElMessage.error(`选择图片失败：${error instanceof Error ? error.message : String(error)}`);
  }
}

async function handleOpenHazardDataWorkbook(): Promise<void> {
  isOpeningHazardData.value = true;
  try {
    await window.ccx.openHazardDataWorkbook();
    // ElMessage.success("已调用系统打开历史地质灾害数据");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : String(error));
  } finally {
    isOpeningHazardData.value = false;
  }
}

async function handleSubmitRecord(): Promise<void> {
  if (!props.apiBaseUrl) {
    submitError.value = "后端服务尚未连接，无法录入数据。";
    return;
  }

  isSubmittingRecord.value = true;
  submitError.value = "";

  try {
    const result = await createDatabaseRecord(props.apiBaseUrl, activeTab.value, buildRecordPayload());
    syncFormValues(true);
    await loadRecords();
    listNotice.value = `${activeTable.value.label}已录入，记录 rowid：${result.rowid}`;
    ElMessage.success(listNotice.value);
    viewMode.value = "list";
  } catch (error) {
    submitError.value = error instanceof Error ? error.message : String(error);
  } finally {
    isSubmittingRecord.value = false;
  }
}

async function handleDeleteRecord(record: DatabaseRecord): Promise<void> {
  if (!props.apiBaseUrl) {
    ElMessage.error("后端服务尚未连接，无法删除数据。");
    return;
  }

  const rowid = getRecordRowid(record);
  if (!Number.isInteger(rowid) || rowid < 1) {
    ElMessage.error("记录 rowid 无效，无法删除。");
    return;
  }

  try {
    await ElMessageBox.confirm(`确定删除 ${activeTable.value.label} 中 rowid=${rowid} 的记录吗？`, "确认删除", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
      confirmButtonClass: "el-button--danger",
    });
  } catch {
    return;
  }

  deletingRowid.value = rowid;

  try {
    const result = await deleteDatabaseRecord(props.apiBaseUrl, activeTab.value, rowid);
    if (selectedRecord.value && getRecordRowid(selectedRecord.value) === rowid) {
      selectedRecord.value = null;
      detailImagePreviews.value = {};
      viewMode.value = "list";
    }
    await loadRecords();
    listNotice.value = `${activeTable.value.label}已删除，记录 rowid：${result.rowid}`;
    ElMessage.success(listNotice.value);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : String(error));
  } finally {
    deletingRowid.value = null;
  }
}

watch(
  () => props.apiBaseUrl,
  (baseUrl) => {
    if (baseUrl) {
      void loadSchema();
      void loadRecords();
      void loadHazardMetrics();
    }
  },
  { immediate: true },
);

watch(
  () => props.preprocessTaskId,
  () => {
    void loadHazardMetrics();
  },
);

watch(
  () => activeTab.value,
  () => {
    viewMode.value = "list";
    selectedRecord.value = null;
    detailImagePreviews.value = {};
    listNotice.value = "";
    submitError.value = "";
    syncFormValues(true);
    void loadRecords();
  },
);

watch(
  () => activeFormFields.value.map((field) => field.name).join("|"),
  () => {
    syncFormValues(false);
  },
  { immediate: true },
);
</script>

<template>
  <section class="element-database-page">
    <ElCard class="element-database-card" shadow="never">
      <template #header>
        <div class="element-database-header">
          <div class="description">
            <span>{{ viewModeTitle }}</span>
            <h2>{{ activeTable.label }}</h2>
            <p>{{ activeTable.description }}</p>
          </div>

          <ElSpace>
            <ElButton v-if="viewMode === 'list'" :loading="isLoadingRecords" @click="loadRecords">刷新列表</ElButton>
            <ElButton v-if="viewMode === 'list'" :loading="isOpeningHazardData"  type="primary" @click="handleOpenHazardDataWorkbook">
              查看历史地质灾害数据
            </ElButton>
            <ElButton v-if="viewMode === 'list'" type="primary" @click="enterCreateMode">新增数据</ElButton>
            <ElButton v-else @click="returnToList">返回列表</ElButton>
          </ElSpace>
        </div>
      </template>

      <div v-if="viewMode === 'list'" class="hazard-metrics-panel">
        <div class="hazard-metrics-header">
          <div>
            <span>历史地质灾害指标</span>
            <strong>D-V 列整体统计</strong>
          </div>
          <small v-if="hazardMetrics?.generated_at">生成时间：{{ hazardMetrics.generated_at }}</small>
        </div>

        <ElAlert
          v-if="isLoadingHazardMetrics"
          class="element-database-alert"
          type="info"
          title="正在读取历史地质灾害指标..."
          show-icon
          :closable="false"
        />
        <ElAlert
          v-else-if="hazardMetricsError"
          class="element-database-alert"
          type="warning"
          title="历史地质灾害指标暂不可用"
          :description="hazardMetricsError"
          show-icon
          :closable="false"
        />
        <ElAlert
          v-else-if="!props.preprocessTaskId"
          class="element-database-alert"
          type="info"
          title="完成一次预处理后，将在这里显示历史地质灾害指标。"
          show-icon
          :closable="false"
        />
        <template v-else-if="hasHazardMetrics">
          <ElTable
            :data="hazardMetricRows"
            :row-class-name="getHazardMetricRowClassName"
            border
            stripe
            size="small"
            class="hazard-metrics-table"
          >
            <ElTableColumn prop="column" label="列" width="72" align="center" />
            <ElTableColumn prop="label" label="指标" min-width="190" show-overflow-tooltip />
            <ElTableColumn label="均值" min-width="120" align="right">
              <template #default="{ row }">
                <ElTag v-if="row.threshold_status === 'warning'" type="danger" effect="dark">
                  {{ formatMetricValue(row.mean) }}
                </ElTag>
                <span v-else>{{ formatMetricValue(row.mean) }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn label="最小值" min-width="120" align="right">
              <template #default="{ row }">{{ formatMetricValue(row.min) }}</template>
            </ElTableColumn>
            <ElTableColumn label="最大值" min-width="120" align="right">
              <template #default="{ row }">{{ formatMetricValue(row.max) }}</template>
            </ElTableColumn>
            <ElTableColumn label="样本数" min-width="110" align="right">
              <template #default="{ row }">{{ row.count.toLocaleString("zh-CN") }}</template>
            </ElTableColumn>
            <ElTableColumn label="指标阈值" min-width="260" show-overflow-tooltip>
              <template #default="{ row }">{{ formatThresholdSummary(row) }}</template>
            </ElTableColumn>
            <ElTableColumn label="颜色提示" min-width="190" show-overflow-tooltip>
              <template #default="{ row }">
                <ElTag v-if="row.threshold_status === 'warning'" type="danger">
                  {{ formatTriggeredThresholds(row) }}
                </ElTag>
                <ElTag v-else type="success">未超出阈值</ElTag>
              </template>
            </ElTableColumn>
          </ElTable>
          <p v-if="hazardMetrics?.summary" class="hazard-metrics-summary">{{ hazardMetrics.summary }}</p>
        </template>
        <ElAlert
          v-else
          class="element-database-alert"
          type="info"
          title="当前预处理结果尚未包含历史地质灾害指标，重新执行一次预处理后会生成。"
          show-icon
          :closable="false"
        />
      </div>

      <template v-if="viewMode === 'list'">
        <ElTabs v-model="activeTab" type="card" class="element-database-tabs">
          <ElTabPane v-for="tab in tabs" :key="tab.key" :name="tab.key">
            <template #label>
              <span class="element-tab-label">{{ tab.label }}</span>
            </template>
          </ElTabPane>
        </ElTabs>

        <ElAlert v-if="listNotice" class="element-database-alert" type="success" :title="listNotice" show-icon :closable="false" />
        <ElAlert
          v-if="schemaError"
          class="element-database-alert"
          type="error"
          title="数据库结构读取失败"
          :description="schemaError"
          show-icon
          :closable="false"
        />
        <ElAlert
          v-else-if="recordsError"
          class="element-database-alert"
          type="error"
          title="数据列表读取失败"
          :description="recordsError"
          show-icon
          :closable="false"
        />
        <ElAlert
          v-else-if="isLoadingSchema || isLoadingRecords"
          class="element-database-alert"
          type="info"
          :title="`正在读取${activeTable.label}数据...`"
          show-icon
          :closable="false"
        />

        <ElTable
          v-else-if="records.length"
          :data="records"
          border
          stripe
          class="element-record-table"
          empty-text="当前表还没有录入记录"
        >
          <ElTableColumn type="index" width="90" align="center" label="序号" />
          <ElTableColumn
            v-for="field in activeFields"
            :key="field.name"
            :label="field.display_name"
            min-width="140"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <ElTag v-if="isImageField(field)" :type="getTagType(field, row)" effect="plain">
                {{ formatRecordValue(row, field) }}
              </ElTag>
              <span v-else>{{ formatRecordValue(row, field) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="150" fixed="right" align="center">
            <template #default="{ row }">
              <ElSpace>
                <ElButton type="primary" link @click="enterDetailMode(row)">详情</ElButton>
                <ElButton
                  type="danger"
                  link
                  :loading="deletingRowid === getRecordRowid(row)"
                  @click="handleDeleteRecord(row)"
                >
                  删除
                </ElButton>
              </ElSpace>
            </template>
          </ElTableColumn>
        </ElTable>

        <ElEmpty v-else description="暂无数据" />
      </template>

      <template v-else-if="viewMode === 'detail'">
        <ElAlert
          v-if="schemaError"
          class="element-database-alert"
          type="error"
          title="数据库结构读取失败"
          :description="schemaError"
          show-icon
          :closable="false"
        />

        <div v-else-if="selectedRecord" class="element-detail-layout">
          <section class="element-detail-panel">
            <div class="element-form-section">
              <div>
                <span>字段信息</span>
                <strong>{{ detailBaseFields.length }} 项</strong>
              </div>
              <p>当前记录 rowid：{{ selectedRecord.rowid ?? "--" }}</p>
            </div>

            <div class="element-detail-grid">
              <article v-for="field in detailBaseFields" :key="field.name" class="element-detail-field">
                <span>
                  {{ field.display_name }}
                  <small>{{ field.name }}</small>
                </span>
                <strong>{{ getRecordValue(selectedRecord, field) }}</strong>
              </article>
            </div>
          </section>

          <aside class="element-detail-images">
            <div class="element-form-section">
              <div>
                <span>图片附件</span>
                <strong>{{ detailImageCount }}/5</strong>
              </div>
              <p>展示当前记录 example1 至 example5 的图片。</p>
            </div>

            <div class="element-detail-gallery">
              <article v-for="(field, index) in detailImageFields" :key="field.name" class="element-detail-image-card">
                <div class="element-detail-image-header">
                  <span>图片 {{ index + 1 }}</span>
                  <small>{{ field.name }}</small>
                </div>

                <div v-if="hasRecordValue(selectedRecord, field.name)" class="element-detail-image-preview">
                  <img
                    v-if="detailImagePreviews[field.name]"
                    :src="detailImagePreviews[field.name]"
                    :alt="`${field.display_name}预览`"
                  />
                  <span v-else>图片路径不可预览</span>
                </div>
                <div v-else class="element-detail-image-empty">未上传图片</div>

                <small class="element-detail-image-file" :title="getRecordImageTitle(selectedRecord, field)">
                  {{ getRecordImageLabel(selectedRecord, field) }}
                </small>
              </article>
            </div>
          </aside>
        </div>

        <ElEmpty v-else description="未选择记录" />
      </template>

      <template v-else>
        <ElAlert
          v-if="schemaError"
          class="element-database-alert"
          type="error"
          title="数据库结构读取失败"
          :description="schemaError"
          show-icon
          :closable="false"
        />

        <ElAlert
          v-if="submitError"
          class="element-database-alert"
          type="error"
          title="录入失败"
          :description="submitError"
          show-icon
          :closable="false"
        />

        <div v-if="!schemaError" class="element-record-layout">
          <section class="element-record-main">
            <div class="element-form-section">
              <div>
                <span>基础信息</span>
                <strong>{{ baseFormFields.length }} 项</strong>
              </div>
              <p>按当前 {{ activeTable.label }} 字段录入，创建时间与修改时间由系统自动写入。</p>
            </div>

            <ElForm label-position="top" class="element-record-form" @submit.prevent>
              <ElFormItem v-for="field in baseFormFields" :key="field.name" :required="field.required">
                <template #label>
                  <span class="element-form-label">
                    {{ field.display_name }}
                    <small>{{ field.name }}</small>
                  </span>
                </template>

                <ElDatePicker
                  v-if="isDateTimeField(field)"
                  v-model="formValues[field.name]"
                  class="element-date-picker"
                  type="datetime"
                  format="YYYY-MM-DD HH:mm"
                  value-format="YYYY-MM-DD HH:mm:ss"
                  :placeholder="getInputPlaceholder(field)"
                  clearable
                />
                <ElInput
                  v-else
                  v-model="formValues[field.name]"
                  :type="getInputType(field)"
                  :step="getInputStep(field)"
                  :placeholder="getInputPlaceholder(field)"
                  clearable
                />
              </ElFormItem>
            </ElForm>
          </section>

          <aside class="element-record-attachments">
            <div class="element-form-section">
              <div>
                <span>图片附件</span>
                <strong>{{ selectedExamplePaths.length }}/5</strong>
              </div>
              <p>每条记录最多选择 5 张图片，也可以直接粘贴图片路径。</p>
            </div>

            <div class="element-image-slots">
              <article v-for="(field, index) in imageFormFields" :key="field.name" class="element-image-slot">
                <div class="element-image-slot-header">
                  <span>图片 {{ index + 1 }}</span>
                  <small>{{ field.name }}</small>
                </div>

                <ElInput
                  :model-value="getImageFieldDisplay(field.name)"
                  class="element-image-input"
                  :placeholder="getInputPlaceholder(field)"
                  readonly
                  clearable
                  @clear="clearImageField(field.name)"
                >
                  <template #append>
                    <ElButton @click="handleSelectImageField(field.name)">选择</ElButton>
                  </template>
                </ElInput>

                <small class="element-image-file">
                  {{ formValues[field.name] ? "已转换为 base64，提交后写入数据库" : "尚未选择图片" }}
                </small>
              </article>
            </div>
          </aside>
        </div>

        <div v-if="!schemaError" class="element-form-actions">
          <ElButton @click="returnToList">取消</ElButton>
          <ElButton @click="syncFormValues(true)">清空表单</ElButton>
          <ElButton type="primary" :loading="isSubmittingRecord" @click="handleSubmitRecord">提交录入</ElButton>
        </div>
      </template>
    </ElCard>
  </section>
</template>
