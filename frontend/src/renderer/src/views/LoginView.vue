<script setup lang="ts">
import { computed, ref } from "vue";

type AuthSession = {
  username: string;
  displayName: string;
  loginAt: string;
};

const emit = defineEmits<{
  "login-success": [session: AuthSession];
}>();

const username = ref("admin");
const password = ref("");
const errorMessage = ref("");
const isSubmitting = ref(false);

const canSubmit = computed(() => username.value.trim().length > 0 && password.value.length > 0 && !isSubmitting.value);

async function handleSubmit(): Promise<void> {
  if (!canSubmit.value) {
    return;
  }

  errorMessage.value = "";
  isSubmitting.value = true;

  try {
    const result = await window.ccx.login(username.value, password.value);
    if (result.ok) {
      password.value = "";
      emit("login-success", result.session);
      return;
    }

    errorMessage.value = result.message;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "登录失败";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <main class="login-shell">
    <section class="login-brand-panel" aria-label="系统信息">
      <div class="login-brand-block">
        <div class="brand-mark login-brand-mark">安</div>
        <div>
          <span>输电线路智能巡检</span>
          <strong>杆塔失稳风险快速评估系统</strong>
        </div>
      </div>

      <div class="login-status-grid" aria-label="系统状态">
        <article>
          <span>数据处理</span>
          <strong>图像 / SD / 点云</strong>
        </article>
        <article>
          <span>评估流程</span>
          <strong>分析 / 数据库 / 风险</strong>
        </article>
      </div>
    </section>

    <section class="login-form-panel" aria-label="登录">
      <form class="login-form" @submit.prevent="handleSubmit">
        <div class="login-form-title">
          <span>本地账号</span>
          <h1>登录系统</h1>
        </div>

        <label class="login-field">
          <span>用户名</span>
          <input v-model.trim="username" type="text" autocomplete="username" autofocus />
        </label>

        <label class="login-field">
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" />
        </label>

        <p v-if="errorMessage" class="login-error">{{ errorMessage }}</p>

        <button class="login-submit" type="submit" :disabled="!canSubmit">
          {{ isSubmitting ? "登录中" : "登录" }}
        </button>
      </form>
    </section>
  </main>
</template>
