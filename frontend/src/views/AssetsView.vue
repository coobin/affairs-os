<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { api, download } from "../api";
import AppIcon from "../components/AppIcon.vue";
import StatusPill from "../components/StatusPill.vue";
import type { Asset, Lookups, Paginated } from "../types";

const props = defineProps<{ lookups: Lookups | null; canManage: boolean }>();
const emit = defineEmits<{ navigate: [path: string] }>();

type AssetListState = {
  query?: string;
  status?: string;
  classType?: string;
  category?: string;
  location?: string;
  page?: number;
};

const LIST_STATE_KEY = "asset-list-state";
function readListState(): AssetListState {
  try { return JSON.parse(window.sessionStorage.getItem(LIST_STATE_KEY) || "{}"); }
  catch { return {}; }
}

const savedState = readListState();
const urlParams = new URLSearchParams(window.location.search);

const assets = ref<Asset[]>([]);
const total = ref(0);
const loading = ref(true);
const error = ref("");
const query = ref(urlParams.get("q") ?? savedState.query ?? "");
const status = ref(urlParams.get("status") ?? savedState.status ?? "");
const classType = ref(savedState.classType ?? "");
const category = ref(savedState.category ?? "");
const location = ref(savedState.location ?? "");
const page = ref(Number.isInteger(savedState.page) && Number(savedState.page) > 0 ? Number(savedState.page) : 1);
const savedPageSize = Number(window.localStorage.getItem("asset-page-size"));
const pageSize = ref([20, 50, 100].includes(savedPageSize) ? savedPageSize : 20);
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
const firstVisible = computed(() => (page.value - 1) * pageSize.value + 1);
const lastVisible = computed(() => Math.min(page.value * pageSize.value, total.value));
let debounceTimer = 0;

const hasFilters = computed(() => query.value || status.value || classType.value || category.value || location.value);

function saveListState() {
  window.sessionStorage.setItem(LIST_STATE_KEY, JSON.stringify({
    query: query.value,
    status: status.value,
    classType: classType.value,
    category: String(category.value || ""),
    location: String(location.value || ""),
    page: page.value,
  } satisfies AssetListState));
}

async function loadAssets() {
  loading.value = true;
  error.value = "";
  const params = new URLSearchParams();
  if (query.value) params.set("q", query.value);
  if (status.value) params.set("status", status.value);
  if (classType.value) params.set("class_type", classType.value);
  if (category.value) params.set("category", category.value);
  if (location.value) params.set("location", location.value);
  if (page.value > 1) params.set("page", page.value.toString());
  params.set("page_size", pageSize.value.toString());
  try {
    const result = await api<Paginated<Asset>>(`/assets/?${params}`);
    assets.value = result.results;
    total.value = result.count;
  } catch {
    error.value = "资产列表暂时无法加载，请刷新重试。";
  } finally {
    loading.value = false;
  }
}


function clearFilters() {
  query.value = "";
  status.value = "";
  classType.value = "";
  category.value = "";
  location.value = "";
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN").format(new Date(`${value}T00:00:00`));
}

function openAssetDetail(assetId: number) {
  const selection = window.getSelection();
  if (selection && !selection.isCollapsed && selection.toString().trim()) return;
  emit("navigate", `/assets/${assetId}`);
}

function resetAndLoad() {
  page.value = 1;
  saveListState();
  loadAssets();
}

async function exportAssets() {
  const params = new URLSearchParams();
  if (query.value) params.set("q", query.value);
  if (status.value) params.set("status", status.value);
  if (classType.value) params.set("class_type", classType.value);
  if (category.value) params.set("category", category.value);
  if (location.value) params.set("location", location.value);

  try {
    await download(`/assets/export/?${params}`);
  } catch (err) {
    alert("导出失败，请重试");
  }
}

watch([status, classType, category, location], resetAndLoad);
watch(pageSize, () => {
  window.localStorage.setItem("asset-page-size", String(pageSize.value));
  resetAndLoad();
});
watch(query, () => {
  window.clearTimeout(debounceTimer);
  page.value = 1;
  saveListState();
  debounceTimer = window.setTimeout(loadAssets, 260);
});
watch(page, () => { saveListState(); loadAssets(); });
onMounted(loadAssets);
</script>

<template>
  <div class="page">
    <header class="page-intro">
      <div>
        <p class="eyebrow">资产台账 · {{ total }} 件</p>
        <h1>每件资产，都能找到</h1>
      </div>
      <div class="page-actions">
        <button v-if="hasFilters" class="secondary-button" @click="clearFilters">清空条件</button>
        <button class="secondary-button" @click="exportAssets">
          <AppIcon name="download" :size="18" />
          <span>导出资产</span>
        </button>
        <button v-if="props.canManage" class="secondary-button" @click="emit('navigate', '/assets/import')">
          <AppIcon name="upload" :size="18" />
          <span>Excel 导入</span>
        </button>
        <button v-if="props.canManage" class="primary-button" @click="emit('navigate', '/assets/new')">
          <AppIcon name="plus" :size="18" />
          <span>登记资产</span>
        </button>
      </div>
    </header>

    <section class="filter-bar">
      <label class="search-field">
        <AppIcon name="search" :size="19" />
        <input v-model="query" placeholder="搜索资产编号、金蝶编码、序列号、型号或责任人" />
      </label>
      <select v-model="status" aria-label="按状态筛选">
        <option value="">全部状态</option>
        <option v-for="item in lookups?.statuses || []" :key="item.value" :value="item.value">
          {{ item.label }}
        </option>
      </select>
      <select v-model="classType" aria-label="按资产分类筛选">
        <option value="">全部资产分类</option>
        <option value="IT">IT资产</option>
        <option value="ADMIN">行政资产</option>
      </select>
      <select v-model="category" aria-label="按资产类型筛选">
        <option value="">全部资产类型</option>
        <option v-for="item in (lookups?.categories || []).filter((item) => !classType || item.class_type === classType)" :key="item.id" :value="item.id">
          {{ item.name }}
        </option>
      </select>
      <select v-model="location" aria-label="按地点筛选">
        <option value="">全部地点</option>
        <option v-for="item in lookups?.locations || []" :key="item.id" :value="item.id">
          {{ item.name }}
        </option>
      </select>
      <button v-if="hasFilters" class="text-button" @click="clearFilters">清除筛选</button>
    </section>

    <section class="asset-table-panel">
      <div v-if="!loading && !error && assets.length" class="asset-list-pagination top">
        <span class="asset-range">显示 {{ firstVisible }}–{{ lastVisible }}，共 {{ total }} 件</span>
        <div class="pagination-nav" aria-label="资产列表上方分页">
          <button class="secondary-button" :disabled="page <= 1" @click="page--">
            <AppIcon name="chevron-left" :size="15" />上一页
          </button>
          <strong>第 {{ page }} / {{ totalPages }} 页</strong>
          <button class="secondary-button" :disabled="page >= totalPages" @click="page++">
            下一页<AppIcon name="chevron-right" :size="15" />
          </button>
        </div>
        <label class="page-size-control">
          <span>每页</span>
          <select v-model.number="pageSize" aria-label="每页显示数量">
            <option :value="20">20 件</option>
            <option :value="50">50 件</option>
            <option :value="100">100 件</option>
          </select>
        </label>
      </div>
      <div v-if="loading" class="loading-block">正在查找资产…</div>
      <div v-else-if="error" class="error-block">{{ error }}</div>
      <div v-else-if="!assets.length" class="empty-state large">
        <strong>没有找到符合条件的资产</strong>
        <p>调整筛选条件，或登记一件新资产。</p>
        <button v-if="hasFilters" class="secondary-button" @click="clearFilters">清除筛选</button>
      </div>

      <div v-else class="asset-table-wrap">
        <table class="asset-table compact">
          <thead>
            <tr>
              <th>资产标签</th>
              <th>资产</th>
              <th>状态</th>
              <th>责任人 / 部门</th>
              <th>当前地点</th>
              <th>金蝶编码</th>
              <th><span class="sr-only">打开</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="asset in assets" :key="asset.id" @click="openAssetDetail(asset.id)">
              <td>
                <span class="table-tag">
                  <i></i><strong>{{ asset.asset_tag }}</strong><small>{{ asset.category_code }}</small>
                </span>
              </td>
              <td><strong>{{ asset.name }}</strong><small>{{ asset.category_class_type_label }} · {{ asset.category_name }}</small></td>
              <td><StatusPill :status="asset.status" :label="asset.status_label" /></td>
              <td><strong>{{ asset.assignee_name || "—" }}</strong><small>{{ asset.department_name || "暂无归属部门" }}</small></td>
              <td>{{ asset.location_name || "未设置" }}</td>
              <td><strong>{{ asset.kingdee_code || "—" }}</strong><small v-if="asset.expected_return_at" class="loan-date">应还 {{ formatDate(asset.expected_return_at) }}</small></td>
              <td><AppIcon name="chevron-right" :size="18" /></td>
            </tr>
          </tbody>
        </table>

        <div class="asset-list-pagination bottom">
          <span class="asset-range">显示 {{ firstVisible }}–{{ lastVisible }}，共 {{ total }} 件</span>
          <div class="pagination-nav" aria-label="资产列表下方分页">
            <button class="secondary-button" :disabled="page <= 1" @click="page--">
              <AppIcon name="chevron-left" :size="15" />上一页
            </button>
            <strong>第 {{ page }} / {{ totalPages }} 页</strong>
            <button class="secondary-button" :disabled="page >= totalPages" @click="page++">
              下一页<AppIcon name="chevron-right" :size="15" />
            </button>
          </div>
          <label class="page-size-control">
            <span>每页</span>
            <select v-model.number="pageSize" aria-label="每页显示数量">
              <option :value="20">20 件</option>
              <option :value="50">50 件</option>
              <option :value="100">100 件</option>
            </select>
          </label>
        </div>
      </div>
    </section>
  </div>
</template>
