<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { api, ApiError } from "../api";
import PersonSearchSelect from "../components/PersonSearchSelect.vue";
import type { User } from "../types";

const props = defineProps<{ isSuperuser: boolean }>();
const emit = defineEmits<{ "refresh-lookups": [] }>();
type BaseKind = "categories" | "locations" | "departments" | "asset-statuses" | "expense-categories" | "contract-types";
type Kind = BaseKind | "managers" | "modules" | "logs" | "emails";
type Row = { id: number; name: string; code: string; is_active: boolean; is_system?: boolean; kind?: string; address?: string; description?: string; class_type_label?: string; enabled?: boolean };
type Module = { value: string; label: string };
type OperationLog = {
  id: number; username: string; display_name: string; module: string; module_label: string;
  action: string; action_label: string; target_type: string; target_id: string; target_label: string;
  method: string; path: string; status_code: number; succeeded: boolean; ip_address: string | null; occurred_at: string;
};
type LogResponse = {
  count: number; next: string | null; previous: string | null; results: OperationLog[];
  filters: { users: { username: string; display_name: string }[]; modules: Module[]; actions: Module[] };
};
type EmailNotification = {
  id: number; event_type: string; event_type_label: string; recipient_name: string; recipient_email: string;
  subject: string; body: string; status: string; status_label: string; attempts: number; last_error: string;
  created_at: string; sent_at: string | null;
};
type EmailResponse = {
  count: number; next: string | null; previous: string | null; results: EmailNotification[];
  filters: { statuses: Module[]; event_types: Module[] };
};

const tab = ref<Kind>("categories");
const rows = reactive<Record<BaseKind, Row[]>>({ categories: [], locations: [], departments: [], "asset-statuses": [], "expense-categories": [], "contract-types": [] });
const moduleRows = ref<Row[]>([]);
const managerUsers = ref<User[]>([]);
const modules = ref<Module[]>([]);
const operationLogs = ref<OperationLog[]>([]);
const logCount = ref(0);
const logPage = ref(1);
const logNext = ref<string | null>(null);
const logPrevious = ref<string | null>(null);
const logLoading = ref(false);
const logOptions = reactive<{ users: { username: string; display_name: string }[]; modules: Module[]; actions: Module[] }>({ users: [], modules: [], actions: [] });
const logFilters = reactive({ username: "", module: "", action: "", result: "", date_from: "", date_to: "", q: "" });
const emailNotifications = ref<EmailNotification[]>([]);
const emailCount = ref(0);
const emailPage = ref(1);
const emailNext = ref<string | null>(null);
const emailPrevious = ref<string | null>(null);
const emailLoading = ref(false);
const emailOptions = reactive<{ statuses: Module[]; event_types: Module[] }>({ statuses: [], event_types: [] });
const emailFilters = reactive({ status: "", event_type: "", date_from: "", date_to: "", q: "" });
const selectedEmail = ref<EmailNotification | null>(null);
const managerUserId = ref("");
const error = ref("");
const savedUser = ref<number | null>(null);
const form = reactive({ name: "", code: "", kind: "office", address: "", description: "", class_type: "IT" });
const labels: Record<Kind, string> = { categories: "资产类型", locations: "地点与库房", departments: "组织部门", "asset-statuses": "资产状态", "expense-categories": "费用类别", "contract-types": "合同类型", managers: "板块管理员", modules: "模块开关", logs: "操作日志", emails: "邮件记录" };
const current = computed(() => {
  if (tab.value === "managers" || tab.value === "logs" || tab.value === "emails") return [];
  if (tab.value === "modules") return moduleRows.value;
  return rows[tab.value];
});
const selectedManager = computed(() =>
  managerUsers.value.find((user) => String(user.id) === String(managerUserId.value)) || null,
);
const authorizedManagers = computed(() => [...managerUsers.value]
  .filter((user) => user.is_superuser || user.management_scopes.length > 0)
  .sort((left, right) => left.display_name.localeCompare(right.display_name, "zh-CN")));
const logPageCount = computed(() => Math.max(1, Math.ceil(logCount.value / 50)));
const emailPageCount = computed(() => Math.max(1, Math.ceil(emailCount.value / 50)));

function managerScopeLabels(user: User) {
  if (user.is_superuser) return ["全部板块"];
  const labelsByScope = new Map(modules.value.map((item) => [item.value, item.label]));
  return user.management_scopes.map((scope) => labelsByScope.get(scope) || scope);
}

function editManager(user: User) {
  managerUserId.value = String(user.id);
}

async function load(kind: BaseKind) { rows[kind] = await api<Row[]>(`/${kind}/?page_size=500`); }
async function loadModules() {
  if (!props.isSuperuser) return;
  const data = await api<{ code: string; label: string; enabled: boolean }[]>("/settings/modules/");
  moduleRows.value = data.map((item) => ({ id: 0, name: item.label, code: item.code, enabled: item.enabled, is_active: item.enabled }));
}
async function loadManagers() {
  if (!props.isSuperuser) return;
  const data = await api<{ modules: Module[]; users: User[] }>("/settings/managers/");
  modules.value = data.modules;
  managerUsers.value = data.users;
}
async function loadLogs(page = 1) {
  if (!props.isSuperuser) return;
  logLoading.value = true;
  error.value = "";
  const params = new URLSearchParams({ page: String(page), page_size: "50" });
  Object.entries(logFilters).forEach(([key, value]) => { if (value) params.set(key, value); });
  try {
    const data = await api<LogResponse>(`/settings/operation-logs/?${params.toString()}`);
    operationLogs.value = data.results;
    logCount.value = data.count;
    logPage.value = page;
    logNext.value = data.next;
    logPrevious.value = data.previous;
    Object.assign(logOptions, data.filters);
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "操作日志暂时无法加载。";
  } finally {
    logLoading.value = false;
  }
}
function resetLogFilters() {
  Object.assign(logFilters, { username: "", module: "", action: "", result: "", date_from: "", date_to: "", q: "" });
  loadLogs(1);
}
async function loadEmails(page = 1) {
  if (!props.isSuperuser) return;
  emailLoading.value = true;
  error.value = "";
  const params = new URLSearchParams({ page: String(page), page_size: "50" });
  Object.entries(emailFilters).forEach(([key, value]) => { if (value) params.set(key, value); });
  try {
    const data = await api<EmailResponse>(`/settings/email-notifications/?${params.toString()}`);
    emailNotifications.value = data.results;
    emailCount.value = data.count;
    emailPage.value = page;
    emailNext.value = data.next;
    emailPrevious.value = data.previous;
    Object.assign(emailOptions, data.filters);
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "邮件记录暂时无法加载。";
  } finally {
    emailLoading.value = false;
  }
}
function resetEmailFilters() {
  Object.assign(emailFilters, { status: "", event_type: "", date_from: "", date_to: "", q: "" });
  loadEmails(1);
}
function formatLogTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
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
  else if (next === "logs") await loadLogs(1);
  else if (next === "emails") await loadEmails(1);
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
      <button v-if="isSuperuser" :class="{ active: tab === 'managers' }" @click="select('managers')">板块管理员<span>{{ authorizedManagers.length }}</span>
      </button>
      <button v-if="isSuperuser" :class="{ active: tab === 'logs' }" @click="select('logs')">操作日志<span>{{ logCount }}</span></button>
      <button v-if="isSuperuser" :class="{ active: tab === 'emails' }" @click="select('emails')">邮件记录<span>{{ emailCount }}</span></button>
    </nav>

    <section v-if="tab === 'logs'" class="operation-log-settings">
      <header class="operation-log-head"><div><p class="eyebrow">AUDIT TRAIL</p><h2>用户操作记录</h2><p>记录登录及所有会改变数据的操作，不保存密码、令牌和文件内容。</p></div><strong>{{ logCount }} 条</strong></header>
      <form class="operation-log-filter-bar" @submit.prevent="loadLogs(1)">
        <input v-model.trim="logFilters.q" placeholder="搜索姓名、对象或接口" />
        <select v-model="logFilters.username"><option value="">全部用户</option><option v-for="item in logOptions.users" :key="item.username" :value="item.username">{{ item.display_name }}（{{ item.username }}）</option></select>
        <select v-model="logFilters.module"><option value="">全部模块</option><option v-for="item in logOptions.modules" :key="item.value" :value="item.value">{{ item.label }}</option></select>
        <select v-model="logFilters.action"><option value="">全部操作</option><option v-for="item in logOptions.actions" :key="item.value" :value="item.value">{{ item.label }}</option></select>
        <select v-model="logFilters.result"><option value="">全部结果</option><option value="success">成功</option><option value="failed">失败</option></select>
        <label><span>开始日期</span><input v-model="logFilters.date_from" type="date" /></label>
        <label><span>结束日期</span><input v-model="logFilters.date_to" type="date" /></label>
        <button class="primary-button">查询</button><button type="button" class="text-button" @click="resetLogFilters">重置</button>
      </form>
      <p v-if="error" class="form-error operation-log-error">{{ error }}</p>
      <div class="operation-log-table-wrap">
        <table class="admin-table operation-log-table"><thead><tr><th>操作时间</th><th>使用人</th><th>模块与操作</th><th>操作对象</th><th>结果</th></tr></thead><tbody>
          <tr v-for="item in operationLogs" :key="item.id"><td><strong>{{ formatLogTime(item.occurred_at) }}</strong></td><td><strong>{{ item.display_name }}</strong><small>{{ item.username }}</small></td><td><strong>{{ item.module_label }} · {{ item.action_label }}</strong><small>{{ item.method }} {{ item.path }}</small></td><td><strong>{{ item.target_label || '未返回对象名称' }}</strong><small v-if="item.target_id">记录 ID：{{ item.target_id }}</small></td><td><span class="operation-result" :class="item.succeeded ? 'success' : 'failed'">{{ item.succeeded ? '成功' : '失败' }} · {{ item.status_code }}</span><small>{{ item.ip_address || '未识别来源 IP' }}</small></td></tr>
        </tbody></table>
        <div v-if="logLoading" class="operation-log-empty">正在读取操作日志…</div><div v-else-if="!operationLogs.length" class="operation-log-empty">当前筛选条件下没有操作记录。</div>
      </div>
      <footer class="operation-log-pagination"><span>第 {{ logPage }} / {{ logPageCount }} 页</span><div><button class="text-button" :disabled="!logPrevious || logLoading" @click="loadLogs(logPage - 1)">上一页</button><button class="text-button" :disabled="!logNext || logLoading" @click="loadLogs(logPage + 1)">下一页</button></div></footer>
    </section>

    <section v-else-if="tab === 'emails'" class="operation-log-settings email-log-settings">
      <header class="operation-log-head"><div><p class="eyebrow">MAIL DELIVERY</p><h2>邮件发送记录</h2><p>记录邮件排队、发送结果和正文内容，仅超级管理员可查看。</p></div><strong>{{ emailCount }} 条</strong></header>
      <form class="operation-log-filter-bar email-log-filter-bar" @submit.prevent="loadEmails(1)">
        <input v-model.trim="emailFilters.q" placeholder="搜索收件人、主题或正文" />
        <select v-model="emailFilters.status"><option value="">全部状态</option><option v-for="item in emailOptions.statuses" :key="item.value" :value="item.value">{{ item.label }}</option></select>
        <select v-model="emailFilters.event_type"><option value="">全部类型</option><option v-for="item in emailOptions.event_types" :key="item.value" :value="item.value">{{ item.label }}</option></select>
        <label><span>开始日期</span><input v-model="emailFilters.date_from" type="date" /></label>
        <label><span>结束日期</span><input v-model="emailFilters.date_to" type="date" /></label>
        <button class="primary-button">查询</button><button type="button" class="text-button" @click="resetEmailFilters">重置</button>
      </form>
      <p v-if="error" class="form-error operation-log-error">{{ error }}</p>
      <div class="operation-log-table-wrap">
        <table class="admin-table operation-log-table email-log-table"><thead><tr><th>记录时间</th><th>收件人</th><th>邮件类型与主题</th><th>发送状态</th><th>发送时间</th><th></th></tr></thead><tbody>
          <tr v-for="item in emailNotifications" :key="item.id"><td><strong>{{ formatLogTime(item.created_at) }}</strong></td><td><strong>{{ item.recipient_name || '未关联用户' }}</strong><small>{{ item.recipient_email }}</small></td><td><strong>{{ item.event_type_label }}</strong><small>{{ item.subject }}</small></td><td><span class="operation-result" :class="item.status === 'sent' ? 'success' : item.status === 'failed' ? 'failed' : ''">{{ item.status_label }}</span><small>尝试 {{ item.attempts }} 次</small></td><td>{{ item.sent_at ? formatLogTime(item.sent_at) : '—' }}</td><td><button type="button" class="text-button" @click="selectedEmail = item">查看邮件</button></td></tr>
        </tbody></table>
        <div v-if="emailLoading" class="operation-log-empty">正在读取邮件记录…</div><div v-else-if="!emailNotifications.length" class="operation-log-empty">当前筛选条件下没有邮件记录。</div>
      </div>
      <footer class="operation-log-pagination"><span>第 {{ emailPage }} / {{ emailPageCount }} 页</span><div><button class="text-button" :disabled="!emailPrevious || emailLoading" @click="loadEmails(emailPage - 1)">上一页</button><button class="text-button" :disabled="!emailNext || emailLoading" @click="loadEmails(emailPage + 1)">下一页</button></div></footer>
    </section>

    <section v-else-if="tab === 'managers'" class="manager-settings">
      <header class="manager-settings-head"><div><p class="eyebrow">MANAGEMENT SCOPE</p><h2>按板块分配管理权限</h2><p>先搜索选择人员，再勾选其管理的板块。</p></div></header>
      <div class="manager-editor">
        <section class="authorized-manager-section">
          <header><div><strong>已授权管理员</strong><span>点击人员可直接调整授权</span></div><b>{{ authorizedManagers.length }} 人</b></header>
          <div v-if="authorizedManagers.length" class="authorized-manager-list">
            <button v-for="user in authorizedManagers" :key="user.id" type="button" :class="{ active: selectedManager?.id === user.id }" @click="editManager(user)">
              <span class="authorized-manager-avatar">{{ user.display_name.slice(0, 1) }}</span>
              <span class="authorized-manager-info"><strong>{{ user.display_name }}</strong><small>{{ user.department_name || '未设置部门' }} · {{ user.employee_no || user.username }}</small></span>
              <span class="authorized-manager-scopes"><i v-for="scope in managerScopeLabels(user)" :key="scope">{{ scope }}</i></span>
            </button>
          </div>
          <p v-else class="manager-note">还没有已授权的板块管理员。</p>
        </section>
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
    <div v-if="selectedEmail" class="modal-backdrop" @click.self="selectedEmail = null">
      <section class="modal-panel email-detail-modal" role="dialog" aria-modal="true" aria-labelledby="email-detail-title">
        <header class="modal-header"><div><p class="eyebrow">MAIL CONTENT</p><h2 id="email-detail-title">{{ selectedEmail.subject }}</h2></div><button type="button" class="icon-button" aria-label="关闭" @click="selectedEmail = null">×</button></header>
        <div class="email-detail-meta"><div><span>收件人</span><strong>{{ selectedEmail.recipient_name || '未关联用户' }} · {{ selectedEmail.recipient_email }}</strong></div><div><span>发送状态</span><strong>{{ selectedEmail.status_label }}<template v-if="selectedEmail.sent_at"> · {{ formatLogTime(selectedEmail.sent_at) }}</template></strong></div><div><span>邮件类型</span><strong>{{ selectedEmail.event_type_label }}</strong></div></div>
        <pre class="email-detail-body">{{ selectedEmail.body }}</pre>
        <p v-if="selectedEmail.last_error" class="form-error email-detail-error">最后错误：{{ selectedEmail.last_error }}</p>
      </section>
    </div>
  </div>
</template>
