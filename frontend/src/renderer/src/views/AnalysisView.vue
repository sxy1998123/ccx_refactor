<script setup lang="ts">
import PointCloudViewer from "../components/PointCloudViewer.vue";

type PageKey = "input" | "analysis" | "database" | "risk";

defineProps<{
  apiBaseUrl: string;
  hasAnalysisResult: boolean;
}>();

const emit = defineEmits<{
  navigate: [page: PageKey];
}>();

const analysisPlaceholderSteps = ["输入线路编号", "选择图片和采集文件", "点击开始分析", "生成三维结果"];

const environmentMetrics = [
  ["湿度", "40.1348 %"],
  ["光照", "3699.1814 Lux"],
  ["气压", "101.1453 kPa"],
  ["环境降雨量", "0.0000 mm"],
  ["环境温度", "-5.1495 C"],
  ["环境风向", "58.5088 deg"],
  ["风速", "0.5855 m/s"],
  ["土壤湿度", "0.00 %"],
  ["土壤温度", "-5.6451 C"],
];

const gnssMetrics = [
  ["平均纬度", "45.728432664"],
  ["平均经度", "126.624992828"],
  ["平均海拔高度", "141.107317 m"],
];

const imuMetrics = [
  ["最终 X 变化", "-0.005559 m"],
  ["最终 Y 变化", "-0.04544 m"],
  ["最终 Z 变化", "0.009745 m"],
];
</script>

<template>
  <section class="page-grid analysis-page">
    <template v-if="!hasAnalysisResult">
      <div class="wide-panel empty-state-panel analysis-empty">
        <div class="empty-copy">
          <span class="empty-eyebrow">等待分析</span>
          <h2>尚未生成数据分析结果</h2>
          <p>完成输入数据页的线路编号、图片、SD 卡文件和点云文件选择后，点击开始分析。分析完成后，这里会显示杆塔三维模型、点云预览和关键指标。</p>
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
            <span>渐进点云</span>
            <h2>杆塔与地表</h2>
          </div>
          <strong>Potree LOD</strong>
        </div>
        <PointCloudViewer :base-url="apiBaseUrl" />
      </div>

      <div class="wide-panel ppt-analysis-panel">
        <div class="panel-title">
          <div>
            <span>数据分析明细</span>
            <h2>位置、沉降与地表指标</h2>
          </div>
        </div>

        <div class="analysis-detail-grid">
          <section>
            <h3>GNSS 位置结果</h3>
            <dl>
              <div v-for="[name, value] in gnssMetrics" :key="name">
                <dt>{{ name }}</dt>
                <dd>{{ value }}</dd>
              </div>
            </dl>
          </section>

          <section>
            <h3>杆塔沉降情况</h3>
            <dl>
              <div v-for="[name, value] in imuMetrics" :key="name">
                <dt>{{ name }}</dt>
                <dd>{{ value }}</dd>
              </div>
            </dl>
          </section>
        </div>
      </div>
    </template>
  </section>
</template>
