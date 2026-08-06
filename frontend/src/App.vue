<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

import { api, clearSession, getStoredUser, getToken, setSession } from "./api";
import AppIcon from "./components/AppIcon.vue";
import type { Lookups, User } from "./types";
import AssetDetailView from "./views/AssetDetailView.vue";
import AssetFormView from "./views/AssetFormView.vue";
import AssetImportView from "./views/AssetImportView.vue";
import AssetsView from "./views/AssetsView.vue";
import DashboardView from "./views/DashboardView.vue";
import LoginView from "./views/LoginView.vue";
import InventoryImportView from "./views/InventoryImportView.vue";
import InventoryView from "./views/InventoryView.vue";
import VehiclesView from "./views/VehiclesView.vue";
import ExpensesView from "./views/ExpensesView.vue";
import ProcurementView from "./views/ProcurementView.vue";
import ContractsView from "./views/ContractsView.vue";
import PlaceholderView from "./views/PlaceholderView.vue";
import ReportsView from "./views/ReportsView.vue";
import RequestsView from "./views/RequestsView.vue";
import SettingsView from "./views/SettingsView.vue";

const user = ref<User | null>(getStoredUser());
const path = ref(window.location.pathname);
const lookups = ref<Lookups | null>(null);
const authLoading = ref(false);
const authError = ref("");

function hasScope(scope: string) {
  return Boolean(user.value?.management_scopes?.includes(scope));
}

const homePath = computed(() => user.value?.management_scopes?.length ? "/" : "/requests");
const navItems = computed(() => [
  ...(user.value?.management_scopes?.length ? [{ path: "/", label: "首页", icon: "home" }] : []),
  { path: "/requests", label: "领用借用", icon: "request" },
  { path: "/vehicles", label: "车辆", icon: "asset" },
  { path: "/procurement", label: "采购", icon: "inventory" },
  ...(hasScope("assets") ? [{ path: "/assets", label: "资产", icon: "asset" }] : []),
  ...(hasScope("inventory") ? [{ path: "/inventory", label: "库存", icon: "inventory" }] : []),
  ...(hasScope("expenses") ? [{ path: "/expenses", label: "费用", icon: "chart" }] : []),
  ...(hasScope("contracts") ? [{ path: "/contracts", label: "合同", icon: "request" }] : []),
  ...(hasScope("reports") ? [{ path: "/reports", label: "报表", icon: "chart" }] : []),
  ...(hasScope("settings") ? [{ path: "/settings", label: "设置", icon: "settings" }] : []),
]);

const route = computed<{ name: string; id?: number; section?: string }>(() => {
  if (path.value === "/requests") return { name: "requests" };
  if (path.value === "/vehicles") return { name: "vehicles" };
  if (path.value === "/procurement") return { name: "procurement" };
  if (path.value === "/expenses" && hasScope("expenses")) return { name: "expenses" };
  if (path.value === "/contracts" && hasScope("contracts")) return { name: "contracts" };
  if (path.value === "/" && user.value?.management_scopes?.length) return { name: "dashboard" };
  if (path.value === "/assets" && hasScope("assets")) return { name: "assets" };
  if (path.value === "/assets/new" && hasScope("assets")) return { name: "asset-new" };
  if (path.value === "/assets/import" && hasScope("assets")) return { name: "asset-import" };
  if (path.value === "/inventory" && hasScope("inventory")) return { name: "inventory" };
  if (path.value === "/inventory/import" && hasScope("inventory")) return { name: "inventory-import" };
  if (path.value === "/reports" && hasScope("reports")) return { name: "reports" };
  if (path.value === "/settings" && hasScope("settings")) return { name: "settings" };
  const editMatch = path.value.match(/^\/assets\/(\d+)\/edit$/);
  if (editMatch && hasScope("assets")) return { name: "asset-edit", id: Number(editMatch[1]) };
  const match = path.value.match(/^\/assets\/(\d+)$/);
  if (match && hasScope("assets")) return { name: "asset-detail", id: Number(match[1]) };
  return { name: "requests" };
});

function navigate(to: string) {
  const destination = to === "/stocktake" ? homePath.value : to;
  if (destination === path.value) return;
  window.history.pushState({}, "", destination);
  path.value = destination;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function onPopState() {
  const destination = window.location.pathname === "/stocktake"
    ? homePath.value
    : window.location.pathname;
  if (destination !== window.location.pathname) {
    window.history.replaceState({}, "", destination);
  }
  path.value = destination;
}

async function loadLookups() {
  if (!getToken()) return;
  lookups.value = await api<Lookups>("/lookups/");
}

async function logout() {
  try { await api("/auth/logout/", { method: "POST" }); } catch { /* 本地会话仍要清理 */ }
  clearSession();
  user.value = null;
  lookups.value = null;
  navigate("/");
}

function onSessionExpired() {
  user.value = null;
  lookups.value = null;
}

onMounted(async () => {
  window.addEventListener("popstate", onPopState);
  window.addEventListener("session-expired", onSessionExpired);
  const query = new URLSearchParams(window.location.search);
  const oidcCode = query.get("oidc_code");
  authError.value = query.get("oidc_error") || "";
  if (oidcCode) {
    authLoading.value = true;
    try {
      const result = await api<{ token: string; user: User }>(
        "/auth/oidc/complete/",
        { method: "POST", body: JSON.stringify({ code: oidcCode }) },
        false,
      );
      setSession(result.token, result.user);
      user.value = result.user;
      window.history.replaceState({}, "", result.user.management_scopes.length ? "/" : "/requests");
      path.value = window.location.pathname;
    } catch (error) {
      authError.value = error instanceof Error ? error.message : "登录未完成，请重试。";
      clearSession();
      user.value = null;
      window.history.replaceState({}, "", "/");
      path.value = "/";
    } finally {
      authLoading.value = false;
    }
  }
  if (user.value && getToken()) {
    try {
      user.value = await api<User>("/auth/me/");
      setSession(getToken(), user.value);
      await loadLookups();
      if (path.value === "/stocktake") {
        window.history.replaceState({}, "", homePath.value);
        path.value = homePath.value;
      }
      if (!user.value?.management_scopes?.length && path.value === "/") navigate("/requests");
    } catch {
      logout();
    }
  }
});

onUnmounted(() => {
  window.removeEventListener("popstate", onPopState);
  window.removeEventListener("session-expired", onSessionExpired);
});
</script>

<template>
  <LoginView v-if="!user" :error="authError" :loading="authLoading" />

  <div v-else class="app-shell">
    <header class="masthead">
      <button class="brand" aria-label="返回首页" @click="navigate(homePath)">
        <span class="brand-mark"><i></i><i></i><i></i></span>
        <span><strong>AffairsOS</strong><small>资源有账，事务有序</small></span>
      </button>

      <nav class="primary-nav" aria-label="主导航">
        <button
          v-for="item in navItems"
          :key="item.path"
          :class="{ active: item.path === '/' ? path === '/' : path.startsWith(item.path) }"
          @click="navigate(item.path)"
        >
          <AppIcon :name="item.icon" :size="18" />
          {{ item.label }}
        </button>
      </nav>

      <div class="masthead-actions">
        <div class="user-menu">
          <span class="avatar">{{ user.display_name.slice(0, 1) }}</span>
          <span class="user-copy">
            <strong>{{ user.display_name }}</strong>
            <small>{{ user.is_superuser ? "超级管理员" : user.management_scopes.length ? "板块管理员" : user.department_name || "员工" }}</small>
          </span>
          <button class="logout-button" title="退出登录" @click="logout">
            <AppIcon name="logout" :size="18" />
          </button>
        </div>
      </div>
    </header>

    <main class="app-main">
      <DashboardView v-if="route.name === 'dashboard'" :scopes="user.management_scopes" @navigate="navigate" />
      <RequestsView v-else-if="route.name === 'requests'" :can-manage="hasScope('assets') || hasScope('inventory')" />
      <VehiclesView v-else-if="route.name === 'vehicles'" :lookups="lookups" :can-manage="hasScope('vehicles')" />
      <ProcurementView v-else-if="route.name === 'procurement'" :can-manage="hasScope('procurement')" />
      <ExpensesView v-else-if="route.name === 'expenses'" :lookups="lookups" />
      <ContractsView v-else-if="route.name === 'contracts'" :lookups="lookups" :is-superuser="user.is_superuser" />
      <AssetsView
        v-else-if="route.name === 'assets'"
        :lookups="lookups"
        :can-manage="hasScope('assets')"
        :is-superuser="user.is_superuser"
        @navigate="navigate"
      />
      <AssetFormView
        v-else-if="route.name === 'asset-new'"
        :lookups="lookups"
        @navigate="navigate"
      />
      <AssetImportView
        v-else-if="route.name === 'asset-import'"
        @navigate="navigate"
      />
      <InventoryView
        v-else-if="route.name === 'inventory'"
        :lookups="lookups"
        :can-manage="hasScope('inventory')"
        :is-superuser="user.is_superuser"
        @navigate="navigate"
      />
      <InventoryImportView
        v-else-if="route.name === 'inventory-import'"
        @navigate="navigate"
      />
      <ReportsView
        v-else-if="route.name === 'reports'"
        :lookups="lookups"
        :can-manage-assets="hasScope('assets')"
        @navigate="navigate"
      />
      <SettingsView v-else-if="route.name === 'settings'" :is-superuser="user.is_superuser" />
      <AssetFormView
        v-else-if="route.name === 'asset-edit'"
        :asset-id="route.id!"
        :lookups="lookups"
        @navigate="navigate"
      />
      <AssetDetailView
        v-else-if="route.name === 'asset-detail'"
        :asset-id="route.id!"
        :lookups="lookups"
        :can-manage="hasScope('assets')"
        @navigate="navigate"
      />
      <PlaceholderView
        v-else
        :section="route.section!"
        @navigate="navigate"
      />
    </main>
  </div>
</template>
