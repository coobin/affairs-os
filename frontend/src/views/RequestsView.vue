<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { api, ApiError } from "../api";
import AppIcon from "../components/AppIcon.vue";
import StatusPill from "../components/StatusPill.vue";
import type { Asset, AssetRequest, DeviceOption } from "../types";

const props = defineProps<{ canManage: boolean }>();
const requests = ref<AssetRequest[]>([]);
const myLoanedAssets = ref<Asset[]>([]);
const devices = ref<DeviceOption[]>([]);
const candidates = reactive<Record<number, Asset[]>>({});
const selection = reactive<Record<number, number | "">>({});
const today = (() => {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
})();
const form = reactive({ needed_at: today, expected_return_at: "", reason: "" });
const itemSearch = ref("");
const selectedOption = ref<DeviceOption | null>(null);
const searchFocused = ref(false);
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const managerMode = ref<"manage" | "apply">("manage");

const isManaging = computed(() => props.canManage && managerMode.value === "manage");
const pending = computed(() => requests.value.filter((item) => item.status === "pending"));
const history = computed(() => requests.value.filter((item) => item.status !== "pending"));
const searchableOptions = computed(() => {
  const query = itemSearch.value.trim().toLowerCase();
  return devices.value
    .filter((item) => !query || `${item.name} ${item.description}`.toLowerCase().includes(query))
    .slice(0, 10);
});

function formatDate(value: string | null, withTime = false) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", withTime ? { dateStyle: "medium", timeStyle: "short" } : { dateStyle: "medium" }).format(new Date(value.length === 10 ? `${value}T00:00:00` : value));
}

async function load() {
  loading.value = true;
  try {
    const [loadedRequests, loadedDevices, loadedLoans] = await Promise.all([
      api<AssetRequest[]>(props.canManage && managerMode.value === "apply" ? "/requests/?mine=1" : "/requests/"),
      api<DeviceOption[]>("/requests/device-options/"),
      api<Asset[]>("/requests/my-loaned-assets/"),
    ]);
    requests.value = loadedRequests;
    devices.value = loadedDevices.filter((item) => item.item_type === "asset");
    myLoanedAssets.value = loadedLoans;
  } finally { loading.value = false; }
}

async function switchMode(mode: "manage" | "apply") {
  if (managerMode.value === mode) return;
  managerMode.value = mode;
  error.value = "";
  notice.value = "";
  await load();
}

function chooseOption(option: DeviceOption) {
  selectedOption.value = option;
  itemSearch.value = option.name;
  searchFocused.value = false;
}

function clearOption() {
  selectedOption.value = null;
  itemSearch.value = "";
}

async function submit() {
  error.value = "";
  notice.value = "";
  if (!selectedOption.value) {
    error.value = "请搜索并选择需要借用的资产。";
    return;
  }
  saving.value = true;
  try {
    await api("/requests/", {
      method: "POST",
      body: JSON.stringify({
        request_type: "loan",
        requested_item_type: "asset",
        requested_name: selectedOption.value.name,
        inventory_item: null,
        requested_quantity: 1,
        needed_at: form.needed_at,
        expected_return_at: form.expected_return_at,
        reason: form.reason,
      }),
    });
    form.reason = "";
    form.needed_at = today;
    form.expected_return_at = "";
    clearOption();
    notice.value = "申请已提交，管理员处理后会通知你。";
    await load();
  } catch (err) {
    error.value = err instanceof ApiError ? Object.values(err.errors).flat().join(" ") || err.message : "申请未提交。";
  } finally { saving.value = false; }
}

async function loadCandidates(item: AssetRequest) {
  if (candidates[item.id]) return;
  candidates[item.id] = await api<Asset[]>(`/requests/${item.id}/candidates/`);
  if (candidates[item.id].length) selection[item.id] = candidates[item.id][0].id;
}

async function fulfill(item: AssetRequest) {
  if (item.requested_item_type === "asset" && !selection[item.id]) return;
  await api(`/requests/${item.id}/fulfill/`, {
    method: "POST",
    body: JSON.stringify(item.requested_item_type === "asset" ? { asset_id: selection[item.id] } : {}),
  });
  delete candidates[item.id];
  await load();
}

async function reject(item: AssetRequest) { await api(`/requests/${item.id}/reject/`, { method: "POST", body: JSON.stringify({}) }); await load(); }
async function cancel(item: AssetRequest) { await api(`/requests/${item.id}/cancel/`, { method: "POST", body: JSON.stringify({}) }); await load(); }

onMounted(load);
</script>

<template>
  <div class="page request-page">
    <header class="page-intro request-intro">
      <div><p class="eyebrow">借用服务台</p><h1>{{ isManaging ? "待处理借用申请" : "借用资产" }}</h1></div>
      <span class="request-counter"><strong>{{ pending.length }}</strong><small>{{ isManaging ? "待处理" : "进行中" }}</small></span>
    </header>

    <nav v-if="canManage" class="request-mode-tabs" aria-label="申请与处理切换">
      <button :class="{ active: managerMode === 'manage' }" @click="switchMode('manage')"><AppIcon name="request" :size="18" />处理申请</button>
      <button :class="{ active: managerMode === 'apply' }" @click="switchMode('apply')"><AppIcon name="plus" :size="18" />我要借用</button>
    </nav>

    <div v-if="loading" class="loading-block">正在读取申请…</div>
    <div v-else class="request-workspace" :class="{ managerial: isManaging }">
      <form v-if="!isManaging" class="request-form" @submit.prevent="submit">
        <header><p class="eyebrow">新申请</p><h2>你需要什么？</h2></header>
        <label class="request-item-search">
          <span>搜索资产</span>
          <div class="request-search-input"><AppIcon name="search" :size="18" /><input v-model="itemSearch" autocomplete="off" placeholder="输入笔记本、显示器等" required @focus="searchFocused = true" @input="selectedOption = null" /><button v-if="itemSearch" type="button" aria-label="清空选择" @click="clearOption"><AppIcon name="close" :size="16" /></button></div>
          <div v-if="searchFocused && !selectedOption" class="request-search-results"><button v-for="option in searchableOptions" :key="option.key" type="button" @mousedown.prevent="chooseOption(option)"><span><strong>{{ option.name }}</strong><small>{{ option.description }}</small></span><b>{{ option.available_count }} {{ option.unit }}</b></button><p v-if="!searchableOptions.length">没有找到当前可借用的资产</p></div>
          <small v-if="selectedOption" class="selected-request-item"><b>资产</b>{{ selectedOption.description }} · 可借用 {{ selectedOption.available_count }} {{ selectedOption.unit }}</small>
        </label>
        <label><span>借用日期</span><input v-model="form.needed_at" type="date" :min="today" required /></label>
        <label><span>预计归还 <b>*</b></span><input v-model="form.expected_return_at" type="date" :min="form.needed_at || today" required /></label>
        <label><span>用途说明 <b>*</b></span><textarea v-model="form.reason" rows="3" required placeholder="请说明借用用途"></textarea></label>
        <p v-if="!devices.length" class="form-error">当前没有可借用的资产。</p>
        <p v-if="error" class="form-error">{{ error }}</p><p v-if="notice" class="form-success">{{ notice }}</p>
        <button class="primary-button full" :disabled="saving || !devices.length || !selectedOption">{{ saving ? "正在提交…" : "提交申请" }}</button>
      </form>

      <section class="request-ledger">
        <header class="request-ledger-head"><div><p class="eyebrow">{{ isManaging ? "处理队列" : "我的申请" }}</p><h2>{{ isManaging ? "待处理" : "进度" }}</h2></div><span>{{ pending.length }} 项</span></header>
        <div v-if="!pending.length" class="empty-state">暂无待处理申请。</div>
        <article v-for="item in pending" :key="item.id" class="request-ticket">
          <span class="ticket-type">{{ item.request_type_label }} · {{ item.requested_item_type_label }}</span>
          <div class="ticket-main"><strong>{{ item.requested_name }}<template v-if="item.requested_item_type === 'inventory'"> × {{ item.requested_quantity }}</template></strong><p v-if="isManaging">{{ item.requester_name }}<span v-if="item.department_name"> · {{ item.department_name }}</span><span v-if="item.reason"> · {{ item.reason }}</span></p><p v-else-if="item.reason">{{ item.reason }}</p><small>{{ item.request_type === 'loan' ? '借用' : '领用' }} {{ formatDate(item.needed_at) }}<template v-if="item.expected_return_at"> · 预计 {{ formatDate(item.expected_return_at) }} 归还</template></small></div>
          <time>{{ formatDate(item.created_at, true) }}</time>
          <div v-if="isManaging" class="allocation-panel">
            <button v-if="item.requested_item_type === 'inventory'" class="primary-button" @click="fulfill(item)">确认发放 {{ item.requested_quantity }} 件</button>
            <button v-else-if="!candidates[item.id]" class="secondary-button" @click="loadCandidates(item)">选择具体资产</button>
            <template v-else-if="candidates[item.id].length"><select v-model="selection[item.id]"><option v-for="asset in candidates[item.id]" :key="asset.id" :value="asset.id">{{ asset.asset_tag }} · {{ asset.brand }} {{ asset.model_name }} · {{ asset.location_name || '未设地点' }}</option></select><button class="primary-button" @click="fulfill(item)">{{ item.request_type === 'loan' ? '确认借用' : '确认分配' }}</button></template>
            <span v-else class="form-error">当前已无可分配资产。</span>
            <button class="text-button reject-link" @click="reject(item)">驳回</button>
          </div>
          <button v-else class="text-button cancel-link" @click="cancel(item)">取消申请</button>
        </article>
        <details v-if="history.length" class="request-history"><summary>查看已处理申请（{{ history.length }}）</summary><article v-for="item in history" :key="item.id" class="request-ticket history"><StatusPill :status="item.status" :label="item.status_label" /><div class="ticket-main"><strong>{{ item.requested_name }}<template v-if="item.requested_item_type === 'inventory'"> × {{ item.requested_quantity }}</template></strong><p>{{ isManaging ? item.requester_name : item.request_type_label }}</p><small v-if="item.assigned_asset_tag">已分配 {{ item.assigned_asset_tag }}</small><small v-else-if="item.issued_inventory_transaction">库存物品已发放</small></div><time>{{ formatDate(item.handled_at || item.updated_at, true) }}</time></article></details>
      </section>
    </div>

    <section v-if="!isManaging" class="my-loaned-assets">
      <header class="request-ledger-head">
        <div><p class="eyebrow">当前持有</p><h2>我的借用资产</h2></div>
        <span>{{ myLoanedAssets.length }} 件</span>
      </header>
      <div v-if="!myLoanedAssets.length" class="empty-state">当前没有借用中的资产。</div>
      <div v-else class="my-loan-grid">
        <article v-for="asset in myLoanedAssets" :key="asset.id" class="my-loan-card">
          <div class="my-loan-card-head"><span class="ticket-type">借用中</span><strong>{{ asset.asset_tag }}</strong></div>
          <h3>{{ asset.name }}</h3>
          <p>{{ [asset.brand, asset.model_name].filter(Boolean).join(' ') || asset.category_name }}</p>
          <dl>
            <div><dt>资产类型</dt><dd>{{ asset.category_name }}</dd></div>
            <div><dt>当前位置</dt><dd>{{ asset.location_name || '未设置' }}</dd></div>
            <div><dt>序列号</dt><dd>{{ asset.serial_number || '未设置' }}</dd></div>
            <div><dt>预计归还</dt><dd :class="{ overdue: asset.expected_return_at && asset.expected_return_at < today }">{{ formatDate(asset.expected_return_at) }}</dd></div>
          </dl>
        </article>
      </div>
    </section>
  </div>
</template>
