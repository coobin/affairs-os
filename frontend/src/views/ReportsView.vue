<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { api, ApiError } from "../api";
import AppIcon from "../components/AppIcon.vue";
import AppModal from "../components/AppModal.vue";
import type { Asset, Lookups, Reports } from "../types";

type DetailKind = "import_warnings" | "missing_category" | "missing_location" | "missing_serial" | "department";
type DetailAsset = Asset & { import_warnings?: string[] };
type DetailResponse = { kind: DetailKind; title: string; count: number; results: DetailAsset[] };

const props = defineProps<{ lookups: Lookups | null; canManageAssets: boolean }>();
const emit = defineEmits<{ navigate: [path: string] }>();
const data = ref<Reports | null>(null);
const error = ref("");
const detail = ref<DetailResponse | null>(null);
const detailLoading = ref(false);
const detailError = ref("");
const saving = ref(false);
const selected = ref<number[]>([]);
const categoryId = ref("");
const locationId = ref("");
const openedDepartmentId = ref<number | null>(null);
const serialNumbers = reactive<Record<number, string>>({});

const maxCategory = computed(() => Math.max(1, ...(data.value?.by_category.map((x) => x.total) || [1])));
const selectedCount = computed(() => selected.value.length);
const allSelected = computed(() => Boolean(detail.value?.results.length) && selected.value.length === detail.value?.results.length);
const canBatch = computed(() => props.canManageAssets && detail.value?.kind !== "department");
const money = (value: string) => new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 0 }).format(Number(value));

async function loadReports() {
  try { data.value = await api<Reports>("/reports/"); }
  catch { error.value = "报表暂时无法加载。"; }
}

async function openDetail(kind: DetailKind, sourceDepartmentId?: number | null) {
  openedDepartmentId.value = kind === "department" ? (sourceDepartmentId || null) : null;
  detail.value = { kind, title: "正在读取…", count: 0, results: [] };
  detailLoading.value = true;
  detailError.value = "";
  selected.value = [];
  categoryId.value = "";
  locationId.value = "";
  Object.keys(serialNumbers).forEach((key) => delete serialNumbers[Number(key)]);
  const params = new URLSearchParams({ kind });
  if (sourceDepartmentId) params.set("department_id", String(sourceDepartmentId));
  try {
    detail.value = await api<DetailResponse>(`/reports/assets/?${params}`);
    detail.value.results.forEach((asset) => { serialNumbers[asset.id] = asset.serial_number || ""; });
  } catch {
    detailError.value = "明细暂时无法加载，请重试。";
  } finally {
    detailLoading.value = false;
  }
}

function closeDetail() { detail.value = null; }
function openAsset(assetId: number) {
  if (props.canManageAssets) emit("navigate", `/assets/${assetId}`);
}
function toggleAll() { selected.value = allSelected.value ? [] : (detail.value?.results.map((asset) => asset.id) || []); }
function issueText(asset: DetailAsset) {
  if (detail.value?.kind === "import_warnings") return asset.import_warnings?.join("；") || "导入资料需要确认";
  if (detail.value?.kind === "missing_category") return "未设置有效的资产类型";
  if (detail.value?.kind === "missing_location") return "未设置当前地点";
  if (detail.value?.kind === "missing_serial") return "未填写设备序列号";
  return asset.location_name || "未设置地点";
}

async function saveBatch() {
  if (!detail.value || !selected.value.length) return;
  detailError.value = "";
  const payload: Record<string, unknown> = { kind: detail.value.kind, asset_ids: selected.value };
  if (detail.value.kind === "missing_category") payload.category_id = categoryId.value;
  if (detail.value.kind === "missing_location") payload.location_id = locationId.value;
  if (detail.value.kind === "missing_serial") {
    payload.serial_numbers = Object.fromEntries(selected.value.map((id) => [String(id), serialNumbers[id] || ""]));
  }
  saving.value = true;
  try {
    await api("/reports/assets/", { method: "POST", body: JSON.stringify(payload) });
    const currentKind = detail.value.kind;
    const currentDepartmentId = openedDepartmentId.value;
    await loadReports();
    await openDetail(currentKind, currentDepartmentId);
  } catch (err) {
    detailError.value = err instanceof ApiError ? err.message : "批量补齐失败，请重试。";
  } finally {
    saving.value = false;
  }
}

onMounted(loadReports);
</script>

<template>
  <div class="page module-page">
    <header class="page-intro"><div><p class="eyebrow">资产报表</p><h1>从数量看到管理缺口</h1></div></header>
    <div v-if="error" class="error-block">{{ error }}</div>
    <div v-else-if="!data" class="loading-block">正在汇总报表…</div>
    <template v-else>
      <section class="report-ledger"><article><small>在册资产</small><strong>{{ data.summary.assets }}</strong><span>件</span></article><article><small>采购金额</small><strong>{{ money(data.summary.purchase_cost) }}</strong></article><article><small>已分配责任人</small><strong>{{ data.summary.in_use }}</strong><span>件</span></article><article><small>在库</small><strong>{{ data.summary.available }}</strong><span>件</span></article></section>
      <section class="report-grid">
        <article class="report-panel"><p class="eyebrow">分类分布</p><h2>资产构成</h2><div class="bar-list"><div v-for="row in data.by_category" :key="row.category__name || 'none'"><span>{{ row.category__name || "未分类" }}</span><i><b :style="{ width: `${row.total / maxCategory * 100}%` }"></b></i><strong>{{ row.total }}</strong></div></div></article>
        <article class="report-panel"><p class="eyebrow">数据质量</p><h2>需要补齐</h2><div class="quality-grid"><button @click="openDetail('import_warnings')"><strong>{{ data.quality.import_warnings }}</strong><span>导入待完善</span><AppIcon name="chevron-right" :size="18" /></button><button @click="openDetail('missing_category')"><strong>{{ data.quality.missing_category }}</strong><span>待分类</span><AppIcon name="chevron-right" :size="18" /></button><button @click="openDetail('missing_location')"><strong>{{ data.quality.missing_location }}</strong><span>缺少地点</span><AppIcon name="chevron-right" :size="18" /></button><button @click="openDetail('missing_serial')"><strong>{{ data.quality.missing_serial }}</strong><span>缺少序列号</span><AppIcon name="chevron-right" :size="18" /></button></div></article>
        <article class="report-panel"><p class="eyebrow">部门分布</p><h2>归属资产数量</h2><div class="rank-list clickable-ranks"><button v-for="(row, i) in data.by_department" :key="row.custodian_department_id || 'none'" @click="openDetail('department', row.custodian_department_id)"><b>{{ String(i + 1).padStart(2, '0') }}</b><span>{{ row.custodian_department__name || "未分配部门" }}</span><strong>{{ row.total }}</strong><AppIcon name="chevron-right" :size="16" /></button></div></article>
        <article class="report-panel"><p class="eyebrow">库存预警</p><h2>需要补货</h2><div v-if="data.low_stock.length" class="rank-list"><div v-for="item in data.low_stock" :key="item.id"><b>{{ item.sku }}</b><span>{{ item.name }}</span><strong>{{ item.quantity }} {{ item.unit }}</strong></div></div><div v-else class="empty-state">当前没有低库存项目。</div></article>
      </section>
    </template>

    <AppModal v-if="detail" :open="true" :wide="true" :title="detail.title" :description="`共 ${detail.count} 件资产`" @close="closeDetail">
      <div v-if="detailLoading" class="loading-block">正在读取资产明细…</div>
      <template v-else>
        <div v-if="canBatch && detail.results.length" class="batch-complete-bar">
          <label><input type="checkbox" :checked="allSelected" @change="toggleAll" />全选本页</label>
          <select v-if="detail.kind === 'missing_category'" v-model="categoryId"><option value="">统一设置资产类型</option><option v-for="item in lookups?.categories || []" :key="item.id" :value="item.id">{{ item.class_type_label }} · {{ item.name }}</option></select>
          <select v-if="detail.kind === 'missing_location'" v-model="locationId"><option value="">统一设置地点</option><option v-for="item in lookups?.locations || []" :key="item.id" :value="item.id">{{ item.name }}</option></select>
          <button class="primary-button" :disabled="!selectedCount || saving || (detail.kind === 'missing_category' && !categoryId) || (detail.kind === 'missing_location' && !locationId)" @click="saveBatch">{{ saving ? "正在保存…" : detail.kind === 'import_warnings' ? `确认已处理（${selectedCount}）` : `保存勾选（${selectedCount}）` }}</button>
        </div>
        <div v-if="detailError" class="error-block">{{ detailError }}</div>
        <div v-if="!detail.results.length" class="empty-state large">这里已经没有需要处理的资产。</div>
        <div v-else class="report-detail-list">
          <article v-for="asset in detail.results" :key="asset.id" :class="{ selected: selected.includes(asset.id) }">
            <label v-if="canBatch" class="report-select"><input v-model="selected" type="checkbox" :value="asset.id" /></label>
            <button class="report-asset-main" :disabled="!canManageAssets" @click="openAsset(asset.id)"><strong>{{ asset.asset_tag }}</strong><span>{{ asset.name }}</span><small>{{ asset.assignee_name || "无责任人" }} · {{ asset.department_name || "无部门" }}</small></button>
            <input v-if="detail.kind === 'missing_serial'" v-model="serialNumbers[asset.id]" class="serial-fill-input" placeholder="填写序列号" @click.stop />
            <span v-else class="report-issue">{{ issueText(asset) }}</span>
            <button v-if="canManageAssets" class="detail-open-button" title="查看资产" @click="openAsset(asset.id)"><AppIcon name="chevron-right" :size="18" /></button>
          </article>
        </div>
      </template>
    </AppModal>
  </div>
</template>
