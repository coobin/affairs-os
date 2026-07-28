<script setup lang="ts">
import { computed, ref } from "vue";

import { api, ApiError, getToken } from "../api";
import AppIcon from "../components/AppIcon.vue";
import type { AssetImportPreview } from "../types";

const emit = defineEmits<{ navigate: [path: string] }>();

const file = ref<File | null>(null);
const preview = ref<AssetImportPreview | null>(null);
const loading = ref(false);
const error = ref("");
const finished = ref<{ created: number; updated: number; total: number; warning: number } | null>(null);

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
      finished.value = await api<{ created: number; updated: number; total: number; warning: number }>(
        "/assets/import/",
        { method: "POST", body },
      );
      preview.value = null;
    } else {
      preview.value = await api<AssetImportPreview>("/assets/import/", {
        method: "POST",
        body,
      });
    }
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "Excel 读取失败，请检查文件后重试。";
  } finally {
    loading.value = false;
  }
}

async function downloadTemplate() {
  error.value = "";
  const response = await fetch("/api/v1/assets/import-template/", {
    headers: { Authorization: `Token ${getToken()}` },
  });
  if (!response.ok) {
    error.value = "模板暂时无法下载。";
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "资产导入模板.xlsx";
  link.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <div class="page import-page">
    <header class="page-intro">
      <div>
        <button class="back-link" @click="emit('navigate', '/assets')">
          <AppIcon name="arrow-left" :size="16" />返回资产台账
        </button>
        <p class="eyebrow">批量登记</p>
        <h1>从 Excel 导入资产</h1>
        <p>兼容你现有的 IT 资产统计表，先检查、再正式写入。</p>
      </div>
      <button class="secondary-button" @click="downloadTemplate">
        <AppIcon name="download" :size="18" />下载模板
      </button>
    </header>

    <section v-if="finished" class="import-success">
      <span class="success-mark">✓</span>
      <div>
        <p class="eyebrow">导入完成</p>
        <h2>已处理 {{ finished.total }} 件资产</h2>
        <p>
          新增 {{ finished.created }} 件，更新 {{ finished.updated }} 件。
          <template v-if="finished.warning">其中 {{ finished.warning }} 件已标记为待完善。</template>
          每件资产都已记录导入历史。
        </p>
      </div>
      <button class="primary-button" @click="emit('navigate', '/assets')">查看资产台账</button>
    </section>

    <template v-else>
      <section class="import-upload-card">
        <div class="import-step">01</div>
        <div class="import-upload-copy">
          <h2>选择资产表</h2>
          <p>支持 .xlsx，单次最多 2,000 行、5MB。资产编号由系统生成；相同序列号或金蝶编码会更新原记录。</p>
        </div>
        <label class="file-picker">
          <input type="file" accept=".xlsx" @change="selectFile" />
          <AppIcon name="upload" :size="22" />
          <span v-if="file"><strong>{{ file.name }}</strong><small>点击可重新选择</small></span>
          <span v-else><strong>选择 Excel 文件</strong><small>或将文件拖到这里</small></span>
        </label>
        <button class="primary-button" :disabled="!file || loading" @click="upload(false)">
          {{ loading ? "正在检查…" : "检查数据" }}
        </button>
      </section>

      <div v-if="error" class="error-block">{{ error }}</div>

      <section v-if="preview" class="import-preview">
        <div class="import-preview-head">
          <div>
            <p class="eyebrow">02 · 导入预检</p>
            <h2>确认这批数据</h2>
          </div>
          <div class="import-stats">
            <span><strong>{{ preview.total }}</strong>总行数</span>
            <span class="create"><strong>{{ preview.create }}</strong>新增</span>
            <span class="update"><strong>{{ preview.update }}</strong>更新</span>
            <span :class="{ warning: preview.warning }"><strong>{{ preview.warning }}</strong>可导入待完善</span>
            <span :class="{ invalid: preview.invalid }"><strong>{{ preview.invalid }}</strong>阻止导入</span>
          </div>
        </div>

        <div class="asset-table-wrap">
          <table class="asset-table import-table">
            <thead>
              <tr><th>行</th><th>处理</th><th>资产编号</th><th>自动显示名称 / 分类 / 类型</th><th>责任人</th><th>状态</th><th>检查结果</th></tr>
            </thead>
            <tbody>
              <tr
                v-for="row in preview.rows"
                :key="row.row_number"
                :class="{ 'row-invalid': row.errors.length, 'row-warning': !row.errors.length && row.warnings.length }"
              >
                <td>{{ row.row_number }}</td>
                <td><span class="import-action" :class="row.action">{{ row.action === "create" ? "新增" : "更新" }}</span></td>
                <td><strong>{{ row.asset_tag || "—" }}</strong></td>
                <td><strong>{{ row.name || "—" }}</strong><small>{{ row.class_type || "IT资产" }} · {{ row.category || "待分类" }}</small></td>
                <td>{{ row.assignee || "—" }}</td>
                <td>{{ row.status }}</td>
                <td>
                  <span v-if="!row.errors.length && !row.warnings.length" class="check-ok">可以导入</span>
                  <template v-else-if="!row.errors.length">
                    <span class="check-warning">可导入，之后完善</span>
                    <ul class="row-warnings"><li v-for="message in row.warnings" :key="message">{{ message }}</li></ul>
                  </template>
                  <ul v-else class="row-errors"><li v-for="message in row.errors" :key="message">{{ message }}</li></ul>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="preview.truncated" class="preview-note">页面只展示前 100 行，正式导入会处理全部数据。</p>
        <div class="import-confirm">
          <p v-if="preview.invalid">有 {{ preview.invalid }} 行需要修正。系统不会写入任何一行，请修改 Excel 后重新检查。</p>
          <p v-else-if="preview.warning">
            可以导入。{{ preview.warning }} 行会标记为“待完善”，导入后可在资产详情中逐项修正。
          </p>
          <p v-else>检查通过。确认后将一次性写入，并自动生成资产历史记录。</p>
          <button class="primary-button" :disabled="!canImport" @click="upload(true)">
            {{ loading ? "正在导入…" : `确认导入 ${preview.total} 件` }}
          </button>
        </div>
      </section>
    </template>
  </div>
</template>
