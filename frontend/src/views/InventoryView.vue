<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api, ApiError, download } from "../api";
import AppIcon from "../components/AppIcon.vue";
import PersonSearchSelect from "../components/PersonSearchSelect.vue";
import type { InventoryItem, Lookups } from "../types";

const props = defineProps<{ lookups: Lookups | null; canManage: boolean; isSuperuser: boolean }>();
const emit = defineEmits<{ navigate: [path: string] }>();
const items = ref<InventoryItem[]>([]);
const selected = ref<InventoryItem | null>(null);
const loading = ref(true);
const error = ref("");
const showNew = ref(false);
const form = reactive({ sku: "", name: "", kind: "accessory", brand: "", model_name: "", unit: "个", unit_price: "", purchase_channel: "", initial_quantity: 0, minimum_quantity: 0, location: "", notes: "" });
const movement = reactive({ action: "inbound", quantity: 1, recipient_id: "", notes: "" });
const totalUnits = computed(() => items.value.reduce((sum, item) => sum + item.quantity, 0));
const lowCount = computed(() => items.value.filter((item) => item.low_stock).length);

async function load() {
  loading.value = true;
  try { items.value = await api<InventoryItem[]>("/inventory/?page_size=200"); }
  catch { error.value = "库存暂时无法加载。"; }
  finally { loading.value = false; }
}
async function createItem() {
  try {
    await api("/inventory/", { method: "POST", body: JSON.stringify({ ...form, unit_price: form.unit_price === "" ? null : form.unit_price, location: form.location ? Number(form.location) : null }) });
    showNew.value = false; Object.assign(form, { sku: "", name: "", kind: "accessory", brand: "", model_name: "", unit: "个", unit_price: "", purchase_channel: "", initial_quantity: 0, minimum_quantity: 0, location: "", notes: "" }); await load();
  } catch (err) { error.value = err instanceof ApiError ? err.message : "库存品未保存。"; }
}
async function transact() {
  if (!selected.value) return;
  try {
    selected.value = await api<InventoryItem>(`/inventory/${selected.value.id}/transactions/`, {
      method: "POST",
      body: JSON.stringify({ ...movement, recipient_id: movement.recipient_id ? Number(movement.recipient_id) : null }),
    });
    Object.assign(movement, { action: "inbound", quantity: 1, recipient_id: "", notes: "" }); await load();
  } catch (err) { error.value = err instanceof ApiError ? err.message : "库存操作未完成。"; }
}
function openMovement(item: InventoryItem) { selected.value = item; error.value = ""; }
async function deleteItem(item: InventoryItem) {
  if (!window.confirm(`确认删除库存品“${item.name}（${item.sku}）”？删除后无法恢复。`)) return;
  try {
    await api(`/inventory/${item.id}/`, { method: "DELETE" });
    await load();
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "库存品删除失败。";
  }
}
function formatTime(value: string) { return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value)); }
function formatPrice(value: string | null) { return value === null ? "未设置单价" : `¥${Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; }
async function exportInventory() {
  error.value = "";
  try { await download("/inventory/export/"); }
  catch { error.value = "库存导出失败，请重试。"; }
}
async function exportPurchaseList() {
  error.value = "";
  try { await download("/inventory/purchase-export/", {}, "采购清单.xlsx"); }
  catch { error.value = "采购清单导出失败，请重试。"; }
}
onMounted(load);
</script>

<template>
  <div class="page module-page">
    <header class="page-intro">
      <div><p class="eyebrow">数量库存</p><h1>配件、耗材和许可</h1></div>
      <div class="page-actions">
        <button class="secondary-button" @click="exportPurchaseList"><AppIcon name="download" :size="18" />采购清单</button>
        <button class="secondary-button" @click="exportInventory"><AppIcon name="download" :size="18" />导出库存</button>
        <button v-if="canManage" class="secondary-button" @click="emit('navigate', '/inventory/import')"><AppIcon name="upload" :size="18" />Excel 导入</button>
        <button v-if="canManage" class="primary-button" @click="showNew = !showNew"><AppIcon name="plus" :size="18" />新增库存品</button>
      </div>
    </header>
    <section class="module-strip"><span><strong>{{ items.length }}</strong>种物品</span><span><strong>{{ totalUnits }}</strong>库存总量</span><span :class="{ hot: lowCount }"><strong>{{ lowCount }}</strong>低于预警</span></section>
    <form v-if="showNew" class="inline-editor inventory-editor" @submit.prevent="createItem">
      <input v-model="form.sku" required placeholder="物品编码" /><input v-model="form.name" required placeholder="物品名称" />
      <select v-model="form.kind"><option value="accessory">配件</option><option value="consumable">耗材</option><option value="license">软件许可</option><option value="other">其他</option></select>
      <input v-model="form.brand" placeholder="品牌（选填）" /><input v-model="form.model_name" placeholder="型号（选填）" />
      <input v-model="form.unit" required placeholder="单位" /><input v-model.number="form.initial_quantity" type="number" min="0" placeholder="期初库存" />
      <input v-model="form.unit_price" type="number" min="0" step="0.01" placeholder="单价（选填）" />
      <input v-model.number="form.minimum_quantity" type="number" min="0" placeholder="保障数量" />
      <select v-model="form.purchase_channel"><option value="">未设置采购途径</option><option value="supplier">合作供应商</option><option value="ecommerce">电商</option><option value="other">其他</option></select>
      <select v-model="form.location"><option value="">未设置地点</option><option v-for="loc in lookups?.locations || []" :key="loc.id" :value="loc.id">{{ loc.name }}</option></select>
      <input v-model="form.notes" placeholder="备注（选填）" />
      <button class="primary-button">保存库存品</button>
    </form>
    <div v-if="error" class="error-block">{{ error }}</div>
    <div v-if="loading" class="loading-block">正在读取库存…</div>
    <section v-else class="inventory-grid">
      <article v-for="item in items" :key="item.id" class="inventory-card" :class="{ low: item.low_stock }">
        <div class="inventory-card-head"><span>{{ item.kind_label }}</span><small>{{ item.sku }}</small></div>
        <h2>{{ item.name }}</h2><p>{{ [item.brand, item.model_name].filter(Boolean).join(" ") || "未设置品牌型号" }} · {{ item.location_name || "未设置地点" }}</p>
        <div class="stock-figure"><strong>{{ item.quantity }}</strong><span>{{ item.unit }}<small>保障数量 {{ item.minimum_quantity }}</small></span></div>
        <p class="inventory-price">{{ formatPrice(item.unit_price) }} · {{ item.purchase_channel_label || "未设置采购途径" }}</p>
        <button v-if="canManage" class="secondary-button full" @click="openMovement(item)">办理出入库</button>
        <button v-if="isSuperuser" class="text-button danger" @click="deleteItem(item)">删除</button>
      </article>
      <div v-if="!items.length" class="empty-state large">还没有库存品。配件、耗材和软件许可从这里开始登记。</div>
    </section>
    <div v-if="selected" class="modal-backdrop" @click.self="selected = null">
      <section class="modal-panel inventory-modal">
        <header class="modal-header"><div><p class="eyebrow">{{ selected.sku }}</p><h2>{{ selected.name }}</h2><p>当前库存 {{ selected.quantity }} {{ selected.unit }}</p></div><button class="icon-button" @click="selected = null"><AppIcon name="close" /></button></header>
        <form class="modal-body action-form" @submit.prevent="transact">
          <label><span>操作</span><select v-model="movement.action"><option value="inbound">入库</option><option value="issue">发放</option><option value="return">退回</option><option value="writeoff">报损</option></select></label>
          <label><span>数量</span><input v-model.number="movement.quantity" type="number" min="1" required /></label>
          <label v-if="movement.action === 'issue'"><span>领用人</span><PersonSearchSelect v-model="movement.recipient_id" :users="lookups?.users || []" placeholder="输入中文姓名搜索（可不指定）" /></label>
          <label><span>说明</span><input v-model="movement.notes" placeholder="用途、批次或原因" /></label>
          <button class="primary-button">确认{{ { inbound: "入库", issue: "发放", return: "退回", writeoff: "报损" }[movement.action] }}</button>
        </form>
        <div class="mini-ledger"><p class="eyebrow">最近流水</p><div v-for="tx in selected.transactions.slice(0, 8)" :key="tx.id"><strong>{{ tx.action_label }} {{ tx.quantity }}</strong><span>余 {{ tx.balance_after }} · {{ tx.actor_name }} · {{ formatTime(tx.happened_at) }}</span></div></div>
      </section>
    </div>
  </div>
</template>
