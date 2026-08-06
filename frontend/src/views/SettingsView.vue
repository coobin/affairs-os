<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { api, ApiError } from "../api";
import type { User } from "../types";

const props = defineProps<{ isSuperuser: boolean }>();
type BaseKind = "categories" | "locations" | "departments" | "asset-statuses" | "expense-categories" | "contract-types";
type Kind = BaseKind | "managers";
type Row = { id: number; name: string; code: string; is_active: boolean; is_system?: boolean; kind?: string; address?: string; description?: string; class_type_label?: string };
type Module = { value: string; label: string };

const tab = ref<Kind>("categories");
const rows = reactive<Record<BaseKind, Row[]>>({ categories: [], locations: [], departments: [], "asset-statuses": [], "expense-categories": [], "contract-types": [] });
const managerUsers = ref<User[]>([]);
const modules = ref<Module[]>([]);
const managerSearch = ref("");
const error = ref("");
const savedUser = ref<number | null>(null);
const form = reactive({ name: "", code: "", kind: "office", address: "", description: "", class_type: "IT" });
const labels: Record<Kind, string> = { categories: "资产类型", locations: "地点与库房", departments: "组织部门", "asset-statuses": "资产状态", "expense-categories": "费用类别", "contract-types": "合同类型", managers: "板块管理员" };
const current = computed(() => tab.value === "managers" ? [] : rows[tab.value]);
const filteredUsers = computed(() => {
  const query = managerSearch.value.trim();
  if (!query) return managerUsers.value;
  return managerUsers.value.filter((user) => user.display_name.includes(query));
});

async function load(kind: BaseKind) { rows[kind] = await api<Row[]>(`/${kind}/?page_size=500`); }
async function loadManagers() {
  if (!props.isSuperuser) return;
  const data = await api<{ modules: Module[]; users: User[] }>("/settings/managers/");
  modules.value = data.modules.filter((item) => item.value !== "stocktake");
  managerUsers.value = data.users;
}
async function create() {
  if (tab.value === "managers") return;
  const payload: Record<string, unknown> = { name: form.name, code: form.code, is_active: true };
  if (tab.value === "locations") Object.assign(payload, { kind: form.kind, address: form.address });
  if (tab.value === "categories") Object.assign(payload, { class_type: form.class_type, description: form.description, icon: "box", custom_fields: [] });
  try {
    await api(`/${tab.value}/`, { method: "POST", body: JSON.stringify(payload) });
    Object.assign(form, { name: "", code: "", kind: "office", address: "", description: "", class_type: "IT" });
    await load(tab.value);
  } catch (err) {
    error.value = err instanceof ApiError ? Object.values(err.errors).flat().join(" ") || err.message : "基础资料未保存。";
  }
}
async function toggle(row: Row) {
  if (tab.value === "managers" || row.is_system) return;
  await api(`/${tab.value}/${row.id}/`, { method: "PATCH", body: JSON.stringify({ is_active: !row.is_active }) });
  await load(tab.value);
}
async function remove(row: Row) {
  if (tab.value === "managers" || row.is_system) return;
  if (!window.confirm(`确认删除“${row.name}（${row.code}）”？删除后无法恢复。`)) return;
  try {
    await api(`/${tab.value}/${row.id}/`, { method: "DELETE" });
    await load(tab.value);
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "删除失败。";
  }
}
async function select(next: Kind) {
  tab.value = next;
  error.value = "";
  if (next === "managers") await loadManagers(); else await load(next);
}
async function toggleScope(user: User, scope: string) {
  if (user.is_superuser) return;
  const scopes = user.management_scopes.includes(scope)
    ? user.management_scopes.filter((item) => item !== scope)
    : [...user.management_scopes, scope];
  const updated = await api<User>("/settings/managers/", { method: "PATCH", body: JSON.stringify({ user_id: user.id, scopes }) });
  const index = managerUsers.value.findIndex((item) => item.id === user.id);
  if (index >= 0) managerUsers.value[index] = updated;
  savedUser.value = user.id;
  window.setTimeout(() => { if (savedUser.value === user.id) savedUser.value = null; }, 1400);
}

onMounted(() => Promise.all((["categories", "locations", "departments", "asset-statuses", "expense-categories", "contract-types"] as BaseKind[]).map(load)));
</script>

<template>
  <div class="page module-page">
    <header class="page-intro"><div><p class="eyebrow">基础设置</p><h1>让台账使用同一套名称</h1></div></header>
    <nav class="settings-tabs">
      <button v-for="key in (['categories','asset-statuses','locations','departments','expense-categories','contract-types'] as BaseKind[])" :key="key" :class="{ active: tab === key }" @click="select(key)">{{ labels[key] }}<span>{{ rows[key].length }}</span></button>
      <button v-if="isSuperuser" :class="{ active: tab === 'managers' }" @click="select('managers')">板块管理员<span>{{ managerUsers.filter((item) => item.management_scopes.length).length }}</span>
      </button>
    </nav>

    <section v-if="tab === 'managers'" class="manager-settings">
      <header class="manager-settings-head"><div><p class="eyebrow">MANAGEMENT SCOPE</p><h2>按板块分配管理权限</h2></div><input v-model="managerSearch" placeholder="输入中文姓名搜索" /></header>
      <div class="manager-matrix-wrap">
        <table class="manager-matrix">
          <thead><tr><th>人员</th><th>部门</th><th v-for="item in modules" :key="item.value">{{ item.label }}</th><th>状态</th></tr></thead>
          <tbody><tr v-for="person in filteredUsers" :key="person.id"><td><strong>{{ person.display_name }}</strong></td><td>{{ person.department_name || "未设置" }}</td><td v-for="item in modules" :key="item.value"><label class="scope-check"><input type="checkbox" :checked="person.management_scopes.includes(item.value)" :disabled="person.is_superuser" @change="toggleScope(person, item.value)" /><span></span></label></td><td><span v-if="savedUser === person.id" class="saved-mark">已保存</span><span v-else :class="person.management_scopes.length ? 'manager-on' : 'manager-off'">{{ person.is_superuser ? '超级管理员' : person.management_scopes.length ? '管理员' : '普通用户' }}</span></td></tr></tbody>
        </table>
      </div>
    </section>

    <section v-else class="settings-layout">
      <div class="settings-list"><header><p class="eyebrow">{{ labels[tab] }}</p><h2>现有项目</h2></header><div v-for="row in current" :key="row.id" class="setting-row" :class="{ inactive: !row.is_active }"><span class="setting-code">{{ row.code }}</span><div><strong>{{ row.name }}</strong><small>{{ tab === 'categories' ? `${row.class_type_label || 'IT资产'} · ${row.description || (row.is_active ? '正在使用' : '已停用')}` : row.description || row.address || (row.is_system ? "系统内置状态" : row.is_active ? "正在使用" : "已停用") }}</small></div><button class="text-button" :disabled="row.is_system" @click="toggle(row)">{{ row.is_system ? "内置" : row.is_active ? "停用" : "启用" }}</button><button v-if="isSuperuser && !row.is_system" class="text-button danger" @click="remove(row)">删除</button></div><div v-if="!current.length" class="empty-state">还没有{{ labels[tab] }}。</div></div>
      <form class="settings-editor" @submit.prevent="create"><p class="eyebrow">新增{{ labels[tab] }}</p><h2>建立基础资料</h2><label><span>名称</span><input v-model="form.name" required /></label><label><span>编码</span><input v-model="form.code" required placeholder="使用简短英文或数字" /></label><label v-if="tab === 'categories'"><span>资产分类</span><select v-model="form.class_type"><option value="IT">IT资产</option><option value="ADMIN">行政资产</option></select></label><label v-if="tab === 'locations'"><span>地点类型</span><select v-model="form.kind"><option value="office">办公室</option><option value="warehouse">库房</option><option value="repair">维修点</option><option value="other">其他</option></select></label><label v-if="tab === 'locations'"><span>地址</span><input v-model="form.address" /></label><label v-if="tab === 'categories'"><span>说明</span><input v-model="form.description" /></label><p v-if="error" class="form-error">{{ error }}</p><button class="primary-button full">保存{{ labels[tab] }}</button></form>
    </section>
  </div>
</template>
