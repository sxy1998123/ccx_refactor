<script setup lang="ts">
import towerStressPreview from "../assets/mock/tower-stress-cloud.jpeg";

type PageKey = "input" | "analysis" | "database" | "risk";

defineProps<{
  hasRiskReport: boolean;
}>();

const emit = defineEmits<{
  navigate: [page: PageKey];
}>();

const riskPlaceholderItems = ["等待数据分析完成", "生成风险评估报告", "查看风险等级与处置建议"];

const riskFactors = [
  { label: "杆塔种类", value: "耐张塔" },
  { label: "杆塔材料", value: "角钢" },
  { label: "杆塔倾角", value: "2.8 deg" },
  { label: "杆塔应力", value: "64.2 MPa" },
];
</script>

<template>
  <section class="page-grid risk-page">
    <template v-if="!hasRiskReport">
      <div class="wide-panel empty-state-panel risk-empty">
        <div class="empty-copy">
          <span class="empty-eyebrow">等待报告</span>
          <h2>尚未生成风险评估报告</h2>
          <p>风险评估需要先完成数据分析。生成报告后，这里会展示风险等级、风险指数、风险因子和处置建议。</p>
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

      <div class="visual-panel">
        <div class="panel-title">
          <div>
            <span>结构结果</span>
            <h2>杆塔应力云图</h2>
          </div>
          <strong>中风险</strong>
        </div>
        <img :src="towerStressPreview" alt="杆塔应力云图" />
      </div>

      <div class="wide-panel risk-result">
        <div class="score-block">
          <span>风险指数</span>
          <strong>72</strong>
        </div>
        <p>
          当前杆塔存在持续沉降与受力偏移叠加风险，塔基周边土体含水率变化会进一步放大结构倾斜和局部应力集中。
          建议安排复核测量，重点检查塔基周边土体、拉线状态与横担连接点。根据演示模型推算，如果遇到 8 级及以上级别大风、暴雨级大雨，持续 2 天，将发生倒坍风险，应提前采取塔基加固、排水疏导和现场警戒措施。
        </p>
      </div>
    </template>
  </section>
</template>
