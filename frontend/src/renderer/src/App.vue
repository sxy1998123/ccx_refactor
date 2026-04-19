<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElConfigProvider } from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import { getAppInfo, type AppInfo } from "./services/api";
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
const hasRiskReport = ref(false);

const pages: Array<{ key: PageKey; title: string; subtitle: string }> = [
  { key: "input", title: "输入数据", subtitle: "线路号、影像、SD 卡与点云文件" },
  { key: "analysis", title: "数据分析", subtitle: "位置、沉降、地表与点云结果" },
  { key: "database", title: "数据库", subtitle: "杆塔表、地质表与字段说明" },
  { key: "risk", title: "风险评估", subtitle: "杆塔参数、受力结果与处置建议" },
];

const activePageMeta = computed(() => pages.find((page) => page.key === activePage.value) ?? pages[0]);

function handleNavigate(page: PageKey): void {
  activePage.value = page;
}

function handleAnalysisCompleted(): void {
  hasAnalysisResult.value = true;
  hasRiskReport.value = true;
  activePage.value = "analysis";
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
            @analysis-completed="handleAnalysisCompleted"
          />
          <AnalysisView
            v-else-if="activePage === 'analysis'"
            :api-base-url="apiBaseUrl"
            :has-analysis-result="hasAnalysisResult"
            @navigate="handleNavigate"
          />
          <DatabaseView v-else-if="activePage === 'database'" :api-base-url="apiBaseUrl" />
          <RiskView v-else :has-risk-report="hasRiskReport" @navigate="handleNavigate" />
        </section>
      </section>
    </main>
  </ElConfigProvider>
</template>
