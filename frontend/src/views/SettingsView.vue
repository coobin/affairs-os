<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { api, ApiError } from "../api";
import PersonSearchSelect from "../components/PersonSearchSelect.vue";
import type { User } from "../types";

const props = defineProps<{ isSuperuser: boolean }>();
const emit = defineEmits<{ "refresh-lookups": [] }>();
type BaseKind = "categories" | "locations" | "departments" | "asset-statuses" | "expense-categories" | "contract-types";
type Kind = BaseKind | "managers" | "modules";
type Row = { id: number; name: string; code: string; is_active: boolean; is_system?: boolean; kind?: string; address?: string; description?: string; class_type_label?: string; enabled?: boolean };
type Module = { value: string; label: string };

const tab = ref<Kind>("categories");
const rows = reactive<Record<BaseKind, Row[]>>({ categories: [], locations: [], departments: [], "asset-statuses": [], "expense-categories": [], "contract-types": [] });
const moduleRows = ref<Row[]>([]);
const managerUsers = ref<User[]>([]);
const modules = ref<Module[]>([]);
const managerUserId = ref("");
const error = ref("");
const savedUser = ref<number | null>(null);
const form = reactive({ name: "", code: "", kind: "office", address: "", description: "", class_type: "IT" });
const labels: Record<Kind, string> = { categories: "资产类型", locations: "地点与库房", departments: "组织部门", "asset-statuses": "资产状态", "expense-categories": "费用类别", "contract-types": "合同类型", managers: "板块管理员", modules: "模块开关" };
const current = computed(() => {
  if (tab.value === "managers") return [];
  if (tab.value === "modules") return moduleRows.value;
  return rows[tab.value];
});
const selectedManager = computed(() =>
  managerUsers.value.find((user) => String(user.id) === String(managerUserId.value)) || null,
);

async function load(kind: BaseKind) { rows[kind] = await api<Row[]>(`/${kind}/?page_size=500`); }
async function loadModules() {
  if (!props.isSuperuser) return;
  const data = await api<{ code: string; label: string; enabled: boolean }[]>("/settings/modules/");
  moduleRows.value = data.map((item) => ({ id: 0, name: item.label, code: item.code, enabled: item.enabled, is_active: item.enabled }));
}
async function loadManagers() {
  if (!props.isSuperuser) return;
  const data = await api<{ modules: Module[]; users: User[] }>("/settings/managers/");
  modules.value = data.modules.filter((item) => item.value !== "stocktake");
  managerUsers.value = data.users;
}
async function create() {
  if (tab.value === "managers" || tab.value === "modules") return;
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
async function toggleModule(row: Row) {
  if (tab.value !== "modules") return;
  const next = !row.enabled;
  try {
    await api("/settings/modules/", { method: "PATCH", body: JSON.stringify({ code: row.code, enabled: next }) });
    row.enabled = next;
    row.is_active = next;
    emit("refresh-lookups");
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "模块开关未保存。";
  }
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
  if (next === "managers") await loadManagers();
  else if (next === "modules") await loadModules();
  else await load(next);
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
      <button v-if="isSuperuser" :class="{ active: tab === 'modules' }" @click="select('modules')">模块开关<span>{{ moduleRows.filter((item) => item.enabled).length }}/{{ moduleRows.length }}</span></button>
      <button v-if="isSuperuser" :class="{ active: tab === 'managers' }" @click="select('managers')">板块管理员<span>{{ managerUsers.filter((item) => item.management_scopes.length).length }}</span>
      </button>
    </nav>

    <section v-if="tab === 'managers'" class="manager-settings">
      <header class="manager-settings-head"><div><p class="eyebrow">MANAGEMENT SCOPE</p><h2>按板块分配管理权限</h2><p>先搜索选择人员，再勾选其管理的板块。</p></div></header>
      <div class="manager-editor">
        <label class="manager-person-pick"><span>选择人员</span><PersonSearchSelect v-model="managerUserId" :users="managerUsers" placeholder="输入中文姓名搜索" /></label>
        <div v-if="selectedManager" class="manager-scope-card">
          <header><strong>{{ selectedManager.display_name }}</strong><small>{{ selectedManager.department_name || "未设置部门" }} · {{ selectedManager.employee_no || "无工号" }}</small><span v-if="selectedManager.is_superuser" class="manager-on">超级管理员</span></header>
          <p v-if="selectedManager.is_superuser" class="manager-note">超级管理员默认拥有全部板块权限，无需勾选。</p>
          <div v-else class="manager-module-grid">
            <label v-for="item in modules" :key="item.value" class="scope-check">
              <input type="checkbox" :checked="selectedManager.management_scopes.includes(item.value)" @change="toggleScope(selectedManager, item.value)" />
              <span></span>{{ item.label }}
            </label>
          </div>
          <p v-if="savedUser === selectedManager.id" class="saved-mark manager-saved">已保存</p>
        </div>
        <div v-else class="manager-empty">搜索并选择一名员工后，在这里配置其板块权限。</div>
      </div>
    </section>

    <section v-else class="settings-layout">
      <div class="settings-list"><header><p class="eyebrow">{{ labels[tab] }}</p><h2>现有项目</h2></header><div v-for="row in current" :key="`${row.code}-${row.id}`" class="setting-row" :class="{ inactive: tab === 'modules' ? !row.enabled : !row.is_active }"><span class="setting-code">{{ row.code }}</span><div><strong>{{ row.name }}</strong><small>{{ tab === 'modules' ? (row.enabled ? '模块已启用' : '模块已停用') : tab === 'categories' ? `${row.class_type_label || 'IT资产'} · ${row.description || (row.is_active ? '正在使用' : '已停用')}` : row.description || row.address || (row.is_system ? "系统内置状态" : row.is_active ? "正在使用" : "已停用") }}</small></div><button v-if="tab === 'modules'" class="text-button" @click="toggleModule(row)">{{ row.enabled ? '停用' : '启用' }}</button><template v-else><button class="text-button" :disabled="row.is_system" @click="toggle(row)">{{ row.is_system ? "内置" : row.is_active ? "停用" : "启用" }}</button><button v-if="isSuperuser && !row.is_system" class="text-button danger" @click="remove(row)">删除</button></template></div><div v-if="!current.length" class="empty-state">还没有{{ labels[tab] }}。</div></div>
      <form v-if="tab !== 'modules'" class="settings-editor" @submit.prevent="create"><p class="eyebrow">新增{{ labels[tab] }}</p><h2>建立基础资料</h2><label><span>名称</span><input v-model="form.name" required /></label><label><span>编码</span><input v-model="form.code" required placeholder="使用简短英文或数字" /></label><label v-if="tab === 'categories'"><span>资产分类</span><select v-model="form.class_type"><option value="IT">IT资产</option><option value="ADMIN">行政资产</option></select></label><label v-if="tab === 'locations'"><span>地点类型</span><select v-model="form.kind"><option value="office">办公室</option><option value="warehouse">库房</option><option value="repair">维修点</option><option value="other">其他</option></select></label><label v-if="tab === 'locations'"><span>地址</span><input v-model="form.address" /></label><label v-if="tab === 'categories'"><span>说明</span><input v-model="form.description" /></label><p v-if="error" class="form-error">{{ error }}</p><button class="primary-button full">保存{{ labels[tab] }}</button></form>
    </section>
  </div>
</template>
