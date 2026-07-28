<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api, ApiError } from "../api";
import AppIcon from "../components/AppIcon.vue";
import type { Lookups, StocktakeTask } from "../types";

const props = defineProps<{ lookups: Lookups | null; canManage: boolean }>();
const tasks = ref<StocktakeTask[]>([]);
const active = ref<StocktakeTask | null>(null);
const error = ref("");
const showNew = ref(false);
const form = reactive({ name: "", scope_location: "" });
const scan = reactive({ asset_tag: "", actual_location_id: "" });
const progress = computed(() => active.value?.snapshot_count ? Math.round(active.value.scanned_count / active.value.snapshot_count * 100) : 0);
async function load() { tasks.value = await api<StocktakeTask[]>("/stocktakes/?page_size=100"); }
async function openTask(id: number) { active.value = await api<StocktakeTask>(`/stocktakes/${id}/`); error.value = ""; }
async function createTask() {
  const task = await api<StocktakeTask>("/stocktakes/", { method: "POST", body: JSON.stringify({ name: form.name, scope_location: form.scope_location ? Number(form.scope_location) : null }) });
  showNew.value = false; form.name = ""; form.scope_location = ""; await load(); await openTask(task.id);
}
async function scanAsset() {
  if (!active.value) return;
  try {
    active.value = await api<StocktakeTask>(`/stocktakes/${active.value.id}/scan/`, { method: "POST", body: JSON.stringify({ asset_tag: scan.asset_tag, actual_location_id: scan.actual_location_id || null }) });
    scan.asset_tag = ""; error.value = "";
  } catch (err) { error.value = err instanceof ApiError ? err.message : "没有识别到这件资产。"; }
}
async function complete() {
  if (!active.value || !confirm("完成后，所有未扫描资产将记为“未盘到”。确认完成吗？")) return;
  active.value = await api<StocktakeTask>(`/stocktakes/${active.value.id}/complete/`, { method: "POST", body: JSON.stringify({}) }); await load();
}
onMounted(load);
</script>
<template>
  <div class="page module-page">
    <header class="page-intro"><div><p class="eyebrow">资产盘点</p><h1>逐件确认，差异留痕</h1><p>创建任务时冻结账面清单，完成后生成未盘到和位置差异。</p></div><button v-if="canManage" class="primary-button" @click="showNew = !showNew"><AppIcon name="plus" />创建盘点</button></header>
    <form v-if="showNew" class="inline-editor stocktake-create" @submit.prevent="createTask"><input v-model="form.name" required placeholder="例如 2026 年 7 月 IT 库房盘点" /><select v-model="form.scope_location"><option value="">全部地点</option><option v-for="loc in lookups?.locations || []" :key="loc.id" :value="loc.id">{{ loc.name }}</option></select><button class="primary-button">创建并开始</button></form>
    <div class="stocktake-layout">
      <aside class="task-list-panel"><p class="eyebrow">盘点任务</p><button v-for="task in tasks" :key="task.id" :class="{ active: active?.id === task.id }" @click="openTask(task.id)"><span><strong>{{ task.name }}</strong><small>{{ task.location_name || "全部地点" }} · {{ task.status_label }}</small></span><b>{{ task.scanned_count }}/{{ task.snapshot_count }}</b></button><div v-if="!tasks.length" class="empty-state">还没有盘点任务。</div></aside>
      <section v-if="active" class="stocktake-workspace">
        <div class="stocktake-head"><div><p class="eyebrow">{{ active.status_label }}</p><h2>{{ active.name }}</h2><p>{{ active.location_name || "全部地点" }} · 应盘 {{ active.snapshot_count }} 件</p></div><strong>{{ progress }}%</strong></div>
        <div class="progress-rail"><i :style="{ width: `${progress}%` }"></i></div>
        <form v-if="active.status === 'in_progress'" class="scan-desk" @submit.prevent="scanAsset"><AppIcon name="scan" :size="25" /><input v-model="scan.asset_tag" autofocus required placeholder="扫描或输入资产编号后回车" /><select v-model="scan.actual_location_id"><option value="">按账面地点确认</option><option v-for="loc in lookups?.locations || []" :key="loc.id" :value="loc.id">实际在 {{ loc.name }}</option></select><button class="primary-button">确认盘到</button></form>
        <div v-if="error" class="error-block">{{ error }}</div>
        <div class="record-table-wrap"><table class="asset-table"><thead><tr><th>资产编号</th><th>资产</th><th>账面地点</th><th>责任人</th><th>结果</th></tr></thead><tbody><tr v-for="row in active.records" :key="row.id"><td><strong>{{ row.asset_tag }}</strong></td><td>{{ row.asset_name }}</td><td>{{ row.expected_location_name || "—" }}</td><td>{{ row.expected_user_name || "—" }}</td><td><span class="record-result" :class="row.result">{{ row.result_label }}</span></td></tr></tbody></table></div>
        <footer v-if="active.status === 'in_progress'" class="stocktake-footer"><span>已盘 {{ active.scanned_count }}，还剩 {{ active.snapshot_count - active.scanned_count }}</span><button class="danger-button" @click="complete">完成盘点</button></footer>
      </section>
      <section v-else class="stocktake-empty"><AppIcon name="scan" :size="40" /><h2>选择一项盘点任务</h2><p>或创建新任务开始逐件确认。</p></section>
    </div>
  </div>
</template>
