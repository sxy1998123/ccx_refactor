<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import analysisPreview from "./assets/mock/analysis-preview.jpeg";
import riskPreview from "./assets/mock/risk-preview.jpeg";
import { getAppInfo, type AppInfo } from "./services/api";

type PageKey = "input" | "analysis" | "database" | "risk";
type UploadKey = "images" | "towerSd" | "groundSd" | "pointCloud";

const apiBaseUrl = ref("");
const backendStatus = ref("连接中");
const appInfo = ref<AppInfo | null>(null);
const activePage = ref<PageKey>("input");
const imagePreviewUrl = ref("");
const hasAnalysisResult = ref(false);
const hasRiskReport = ref(false);
const selectedInputs = ref<Record<UploadKey, string[]>>({
  images: [],
  towerSd: [],
  groundSd: [],
  pointCloud: [],
});

const pages: Array<{ key: PageKey; title: string; subtitle: string }> = [
  { key: "input", title: "输入数据", subtitle: "线路号、影像、SD 卡与点云文件" },
  { key: "analysis", title: "数据分析", subtitle: "位置、沉降、地表与点云结果" },
  { key: "database", title: "数据库", subtitle: "线路、杆塔、文件与风险等级" },
  { key: "risk", title: "风险评估", subtitle: "杆塔参数、受力结果与处置建议" },
];

const activePageMeta = computed(() => pages.find((page) => page.key === activePage.value) ?? pages[0]);

const analysisPlaceholderSteps = ["输入线路编号", "选择图片和采集文件", "点击开始分析", "生成三维结果"];
const riskPlaceholderItems = ["等待数据分析完成", "生成风险评估报告", "查看风险等级与处置建议"];

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

const environmentMetrics = [
  ["湿度", "40.13 %"],
  ["光照", "3699.18 Lux"],
  ["气压", "101.15 kPa"],
  ["风速", "0.59 m/s"],
  ["土壤湿度", "0.00 %"],
  ["土壤温度", "-5.65 C"],
];

const towerRows = [
  { date: "2026-04-17", line: "1-1", tower: "20200422009", type: "直角", material: "无缝", project: "CRP", status: "运行中", risk: "常规" },
  { date: "2026-04-17", line: "1-1", tower: "20200422010", type: "耐张", material: "角钢", project: "AFP", status: "运行中", risk: "急促" },
  { date: "2026-04-17", line: "1-1", tower: "20200422011", type: "直线", material: "无缝", project: "SAA", status: "待复核", risk: "关注" },
  { date: "2026-04-17", line: "1-1", tower: "20200422012", type: "终端", material: "钢管", project: "Fr", status: "已完成", risk: "常规" },
];

const riskFactors = [
  { label: "杆塔种类", value: "耐张塔" },
  { label: "杆塔材料", value: "角钢" },
  { label: "杆塔倾角", value: "2.8 deg" },
  { label: "杆塔应力", value: "64.2 MPa" },
];

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

onMounted(async () => {
  try {
    const config = await window.ccx.getApiConfig();
    apiBaseUrl.value = config.baseUrl;
    appInfo.value = await getAppInfo(config.baseUrl);
    backendStatus.value = "已连接";
  } catch (error) {
    backendStatus.value = "连接失败";
    console.error(error);
  }
});
</script>

<template>
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
        <div class="header-actions">
          <button type="button" class="ghost-button">导入记录</button>
          <button type="button" class="primary-button">新建任务</button>
        </div>
      </header>

      <section class="content-stage">
        <section v-if="activePage === 'input'" class="page-grid input-page">
          <div class="wide-panel route-panel import-form-panel">
            <div class="panel-title">
              <div>
                <span>线路信息</span>
                <h2>采集批次导入</h2>
              </div>
              <strong>未开始</strong>
            </div>

            <div class="import-form">
              <div class="route-field">
                <label class="field-label required" for="route-id">线路号</label>
                <div class="route-input">
                  <input id="route-id" type="text" placeholder="请输入线路号，例如 YX-2026-04-17" aria-label="线路号" />
                  <button type="button">校验线路</button>
                </div>
                <p class="field-hint">请先输入线路号，系统会按线路号归档图片、SD 卡文件和点云文件。</p>
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

        <section v-else-if="activePage === 'analysis'" class="page-grid analysis-page">
          <template v-if="!hasAnalysisResult">
            <div class="wide-panel empty-state-panel analysis-empty">
              <div class="empty-copy">
                <span class="empty-eyebrow">等待分析</span>
                <h2>尚未生成数据分析结果</h2>
                <p>完成输入数据页的线路编号、图片、SD 卡文件和点云文件选择后，点击开始分析。分析完成后，这里会显示杆塔三维模型、点云预览和关键指标。</p>
                <div class="empty-actions">
                  <button type="button" class="primary-button" @click="activePage = 'input'">返回输入数据</button>
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
            <div class="metric-panel">
              <div class="panel-title">
                <div>
                  <span>环境均值</span>
                  <h2>采样窗口</h2>
                </div>
                <strong>16:34:48</strong>
              </div>
              <dl class="metric-list">
                <div v-for="[name, value] in environmentMetrics" :key="name">
                  <dt>{{ name }}</dt>
                  <dd>{{ value }}</dd>
                </div>
              </dl>
            </div>

            <div class="visual-panel">
              <div class="panel-title">
                <div>
                  <span>点云图</span>
                  <h2>杆塔与地表</h2>
                </div>
                <strong>有效点 984</strong>
              </div>
              <img :src="analysisPreview" alt="点云分析预览" />
            </div>

            <div class="wide-panel analysis-summary">
              <div>
                <span>平均纬度</span>
                <strong>45.728432664</strong>
              </div>
              <div>
                <span>平均经度</span>
                <strong>126.624992828</strong>
              </div>
              <div>
                <span>平均海拔</span>
                <strong>141.107317 m</strong>
              </div>
              <div>
                <span>高度变化</span>
                <strong>0.009745 m</strong>
              </div>
            </div>
          </template>
        </section>

        <section v-else-if="activePage === 'database'" class="database-page">
          <div class="table-toolbar">
            <div class="status-legend">
              <span class="dot normal"></span>常规
              <span class="dot urgent"></span>急促
              <span class="dot concern"></span>关注
              <span class="dot abnormal"></span>异常
            </div>
            <div class="table-actions">
              <button type="button">打印</button>
              <button type="button">上传</button>
              <button type="button">查找</button>
              <button type="button" disabled>删除</button>
            </div>
          </div>

          <div class="data-table">
            <table>
              <thead>
                <tr>
                  <th>提交时间</th>
                  <th>杆塔-架位</th>
                  <th>杆塔 ID</th>
                  <th>杆塔类型</th>
                  <th>杆塔材料</th>
                  <th>项目</th>
                  <th>检测状态</th>
                  <th>风险等级</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in towerRows" :key="row.tower">
                  <td>{{ row.date }}</td>
                  <td>{{ row.line }}</td>
                  <td>{{ row.tower }}</td>
                  <td>{{ row.type }}</td>
                  <td>{{ row.material }}</td>
                  <td>{{ row.project }}</td>
                  <td>{{ row.status }}</td>
                  <td>
                    <span class="risk-pill">{{ row.risk }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <footer class="table-footer">
            <span>共 6 页</span>
            <div>
              <button type="button">上一页</button>
              <button type="button" class="active">1</button>
              <button type="button">2</button>
              <button type="button">3</button>
              <button type="button">下一页</button>
            </div>
          </footer>
        </section>

        <section v-else class="page-grid risk-page">
          <template v-if="!hasRiskReport">
            <div class="wide-panel empty-state-panel risk-empty">
              <div class="empty-copy">
                <span class="empty-eyebrow">等待报告</span>
                <h2>尚未生成风险评估报告</h2>
                <p>风险评估需要先完成数据分析。生成报告后，这里会展示风险等级、风险指数、风险因子和处置建议。</p>
                <div class="empty-actions">
                  <button type="button" class="primary-button" @click="activePage = 'analysis'">查看数据分析</button>
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
            <div class="risk-controls">
              <article v-for="factor in riskFactors" :key="factor.label" class="factor-tile">
                <span>{{ factor.label }}</span>
                <strong>{{ factor.value }}</strong>
              </article>
              <button type="button" class="risk-action">生成风险评估</button>
            </div>

            <div class="visual-panel">
              <div class="panel-title">
                <div>
                  <span>结构结果</span>
                  <h2>杆塔应力云图</h2>
                </div>
                <strong>中风险</strong>
              </div>
              <img :src="riskPreview" alt="杆塔风险评估预览" />
            </div>

            <div class="wide-panel risk-result">
              <div class="score-block">
                <span>风险指数</span>
                <strong>72</strong>
              </div>
              <p>
                当前杆塔存在持续沉降与受力偏移叠加风险。建议安排复核测量，重点检查塔基周边土体含水率、拉线状态与横担连接点。
              </p>
            </div>
          </template>
        </section>
      </section>
    </section>
  </main>
</template>
