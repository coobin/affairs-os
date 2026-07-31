<script setup lang="ts">
import { reactive, ref } from "vue";

import { api, ApiError, setSession } from "../api";
import AppIcon from "../components/AppIcon.vue";

defineProps<{ error?: string; loading?: boolean }>();
const localMode = ref(window.location.pathname === "/passwordLogin");
const localLoading = ref(false);
const localError = ref("");
const credentials = reactive({ username: "admin", password: "" });

function login() {
  window.location.assign("/api/v1/auth/oidc/login/");
}

function showOidcLogin() {
  window.location.assign("/");
}

async function localLogin() {
  localLoading.value = true;
  localError.value = "";
  try {
    const result = await api<{ token: string; user: unknown }>(
      "/auth/local/login/",
      { method: "POST", body: JSON.stringify(credentials) },
      false,
    );
    setSession(result.token, result.user);
    window.location.assign("/");
  } catch (error) {
    localError.value = error instanceof ApiError ? error.message : "登录未完成，请重试。";
  } finally {
    localLoading.value = false;
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-story">
      <div class="login-brand">
        <span class="brand-mark large"><i></i><i></i><i></i></span>
        <span><strong>AffairsOS</strong><small>开源行政事务管理平台</small></span>
      </div>
      <div class="login-thesis">
        <p class="eyebrow light">ASSET REGISTER · 2026</p>
        <h1>每件资产，<br />都有清楚的去向。</h1>
        <p>从申请、分配到归还，用公司账号进入，每一次流转都自动留痕。</p>
      </div>
      <div class="tag-specimen" aria-hidden="true">
        <span class="tag-notch"></span>
        <div class="tag-code">IT-LT-2026-123</div>
        <div class="tag-lines"><i></i><i></i><i></i><i></i><i></i></div>
        <div class="tag-meta"><span>THINKBOOK 14</span><span>在用 · 已登记</span></div>
      </div>
      <p class="login-footnote">公司单点登录 · 一物一码 · 全程留痕</p>
    </section>

    <section class="login-panel">
      <div v-if="!localMode" class="login-form">
        <div>
          <p class="eyebrow">ORGANIZATION ACCOUNT</p>
          <h2>登录行政工作台</h2>
        </div>
        <p v-if="error" class="form-error oidc-error">{{ error }}</p>
        <button class="primary-button full oidc-button" :disabled="loading" @click="login">
          {{ loading ? "正在完成登录…" : "统一认证登录" }}
          <AppIcon name="chevron-right" :size="18" />
        </button>
      </div>
      <form v-else class="login-form" @submit.prevent="localLogin">
        <div>
          <p class="eyebrow">LOCAL TEST ACCOUNT</p>
          <h2>账户密码登录</h2>
          <p>仅限本地测试环境使用。</p>
        </div>
        <label><span>账户</span><input v-model="credentials.username" autocomplete="username" required /></label>
        <label><span>密码</span><input v-model="credentials.password" type="password" autocomplete="current-password" required autofocus /></label>
        <p v-if="localError" class="form-error">{{ localError }}</p>
        <button class="primary-button full" :disabled="localLoading">{{ localLoading ? "正在登录…" : "登录" }}</button>
        <button class="text-button local-login-return" type="button" @click="showOidcLogin">返回统一认证</button>
      </form>
    </section>
  </main>
</template>
