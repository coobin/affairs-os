<script setup lang="ts">
import { computed, ref } from "vue";

import { api, ApiError, download } from "../api";
import AppIcon from "../components/AppIcon.vue";

type InventoryImportRow = {
  row_number: number;
  action: "create" | "update";
  errors: string[];
  warnings: string[];
  sku: string;
  name: string;
  kind: string;
  brand_model: string;
  quantity: number;
  unit: string;
  unit_price: string;
  purchase_channel: string;
  location: string;
};

type InventoryImportPreview = {
  total: number;
  create: number;
  update: number;
  invalid: number;
  warning: number;
  rows: InventoryImportRow[];
  truncated: boolean;
};

const emit = defineEmits<{ navigate: [path: string] }>();
const file = ref<File | null>(null);
const preview = ref<InventoryImportPreview | null>(null);
const loading = ref(false);
const error = ref("");
const finished = ref<{ created: number; updated: number; adjusted: number; total: number; warning: number } | null>(null);
const canImport = computed(() => preview.value && preview.value.invalid === 0 && !loading.value);

function selectFile(event: Event) {
  const input = event.target as HTMLInputElement;
  file.value = input.files?.[0] || null;
  preview.value = null;
  finished.value = null;
  error.value = "";
}

async function upload(commit = false) {
  if (!file.value) return;
  loading.value = true;
  error.value = "";
  const body = new FormData();
  body.append("file", file.value);
  if (commit) body.append("commit", "true");
  try {
    if (commit) {
      finished.value = await api("/inventory/import/", { method: "POST", body });
      preview.value = null;
    } else {
      preview.value = await api<InventoryImportPreview>("/inventory/import/", { method: "POST", body });
    }
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "Excel 读取失败，请检查文件后重试。";
  } finally {
    loading.value = false;
  }
}

async function downloadTemplate() {
  error.value = "";
  try { await download("/inventory/import-template/", {}, "库存导入模板.xlsx"); }
  catch { error.value = "模板暂时无法下载。"; }
}
</script>

<template>
  <div class="page import-page">
    <header class="page-intro">
      <div>
        <button class="back-link" @click="emit('navigate', '/inventory')"><AppIcon name="arrow-left" :size="16" />返回库存</button>
        <p class="eyebrow">批量建库</p>
        <h1>从 Excel 导入库存</h1>
      </div>
      <button class="secondary-button" @click="downloadTemplate"><AppIcon name="download" :size="18" />下载库存模板</button>
    </header>

    <section v-if="finished" class="import-success">
      <span class="success-mark">✓</span>
      <div>
        <p class="eyebrow">导入完成</p>
        <h2>已处理 {{ finished.total }} 种物品</h2>
        <p>新增 {{ finished.created }} 种，更新 {{ finished.updated }} 种，生成 {{ finished.adjusted }} 条库存校准流水。</p>
      </div>
      <button class="primary-button" @click="emit('navigate', '/inventory')">查看库存</button>
    </section>

    <template v-else>
      <section class="import-upload-card">
        <div class="import-step">01</div>
        <div class="import-upload-copy">
          <h2>选择库存表</h2>
        </div>
        <label class="file-picker">
          <input type="file" accept=".xlsx" @change="selectFile" />
          <AppIcon name="upload" :size="22" />
          <span v-if="file"><strong>{{ file.name }}</strong><small>点击可重新选择</small></span>
          <span v-else><strong>选择 Excel 文件</strong><small>使用下载的模板最稳妥</small></span>
        </label>
        <button class="primary-button" :disabled="!file || loading" @click="upload(false)">{{ loading ? "正在检查…" : "检查数据" }}</button>
      </section>

      <div v-if="error" class="error-block">{{ error }}</div>

      <section v-if="preview" class="import-preview">
        <div class="import-preview-head">
          <div><p class="eyebrow">02 · 导入预检</p><h2>确认这批库存</h2></div>
          <div class="import-stats">
            <span><strong>{{ preview.total }}</strong>总行数</span>
            <span class="create"><strong>{{ preview.create }}</strong>新增</span>
            <span class="update"><strong>{{ preview.update }}</strong>更新</span>
            <span :class="{ warning: preview.warning }"><strong>{{ preview.warning }}</strong>可导入提示</span>
            <span :class="{ invalid: preview.invalid }"><strong>{{ preview.invalid }}</strong>阻止导入</span>
          </div>
        </div>

        <div class="asset-table-wrap">
          <table class="asset-table import-table inventory-import-table">
            <thead><tr><th>行</th><th>处理</th><th>物品编码</th><th>物品</th><th>分类</th><th>数量</th><th>单价</th><th>采购途径</th><th>存放地点</th><th>检查结果</th></tr></thead>
            <tbody>
              <tr v-for="row in preview.rows" :key="row.row_number" :class="{ 'row-invalid': row.errors.length, 'row-warning': !row.errors.length && row.warnings.length }">
                <td>{{ row.row_number }}</td>
                <td><span class="import-action" :class="row.action">{{ row.action === "create" ? "新增" : "更新" }}</span></td>
                <td><strong>{{ row.sku }}</strong></td>
                <td><strong>{{ row.name || "—" }}</strong><small>{{ row.brand_model || "未填品牌型号" }}</small></td>
                <td>{{ row.kind }}</td>
                <td><strong>{{ row.quantity }}</strong> {{ row.unit }}</td>
                <td>{{ row.unit_price ? `¥${row.unit_price}` : "—" }}</td>
                <td>{{ row.purchase_channel }}</td>
                <td>{{ row.location || "—" }}</td>
                <td>
                  <span v-if="!row.errors.length && !row.warnings.length" class="check-ok">可以导入</span>
                  <template v-else-if="!row.errors.length"><span class="check-warning">可以导入</span><ul class="row-warnings"><li v-for="message in row.warnings" :key="message">{{ message }}</li></ul></template>
                  <ul v-else class="row-errors"><li v-for="message in row.errors" :key="message">{{ message }}</li></ul>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="preview.truncated" class="preview-note">页面只展示前 100 行，正式导入会处理全部数据。</p>
        <div class="import-confirm">
          <p v-if="preview.invalid">有 {{ preview.invalid }} 行需要修正。系统不会写入任何一行。</p>
          <p v-else>检查通过。更新已有编码时，数量差额会自动记录为入库或报损流水。</p>
          <button class="primary-button" :disabled="!canImport" @click="upload(true)">{{ loading ? "正在导入…" : `确认导入 ${preview.total} 种` }}</button>
        </div>
      </section>
    </template>
  </div>
</template>
