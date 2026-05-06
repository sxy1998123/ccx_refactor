<script setup lang="ts">
import StressCloudViewer from "../components/StressCloudViewer.vue";

type PageKey = "input" | "analysis" | "database" | "risk";

defineProps<{
  apiBaseUrl: string;
  hasRiskReport: boolean;
}>();

const emit = defineEmits<{
  navigate: [page: PageKey];
}>();

const riskPlaceholderItems = ["等待数据分析完成", "生成风险评估报告", "查看风险等级与处置建议"];

const riskFactors = [
  { label: "杆塔种类", value: "耐张塔" },
  { label: "杆塔材料", value: "角钢" },
  { label: "杆塔倾角", value: "0.0007 deg" },
  { label: "base 最大应力", value: "53.42 MPa" },
];
</script>

<template>
  <section class="page-grid risk-page">
    <template v-if="!hasRiskReport">
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
      <div class="risk-controls">
        <article v-for="factor in riskFactors" :key="factor.label" class="factor-tile">
          <span>{{ factor.label }}</span>
          <strong>{{ factor.value }}</strong>
        </article>
      </div>

      <div class="visual-panel stress-panel">
        <div class="panel-title">
          <div>
            <span>结构结果</span>
            <h2>base h5 应力云图</h2>
          </div>
          <strong>Three.js</strong>
        </div>
        <StressCloudViewer :base-url="apiBaseUrl" />
      </div>

      <div class="wide-panel risk-result">
        <div class="score-block">
          <span>风险指数</span>
          <strong>17</strong>
        </div>
        <p>
          当前 base 工况最大应力约 53.42 MPa，暂未超过 315 MPa 控制阈值。后续正式接入风险任务后，将根据
          core.py 输出的 summary CSV 汇总降雨工况、首次超限天数、最大风险工况和 base h5 应力云图，生成完整评估结论。
        </p>
      </div>
    </template>
  </section>
</template>
