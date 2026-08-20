<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { api, ApiError, download } from "../api";
import AppIcon from "../components/AppIcon.vue";

defineProps<{ isSuperuser: boolean }>();

type SupplierFile = {
  id: number;
  original_name?: string;
  name?: string;
  content_type?: string;
  size_bytes?: number;
  created_at?: string;
  uploaded_by_name?: string;
};

type SupplierRecord = {
  id: number;
  code: string;
  name: string;
  category: string;
  category_label?: string;
  channel: string;
  channel_label?: string;
  contact_name: string;
  contact_phone: string;
  contact_email: string;
  tax_number: string;
  address: string;
  business_license_status: string;
  business_license_status_label?: string;
  notes: string;
  is_active: boolean;
  files: SupplierFile[];
};

type ListPayload<T> = T[] | { results: T[] };

const rows = ref<SupplierRecord[]>([]);
const loading = ref(false);
const error = ref("");
const formError = ref("");
const showForm = ref(false);
const editing = ref<SupplierRecord | null>(null);
const filters = reactive({ q: "", category: "", channel: "", active: "" });

const dossierSupplier = ref<SupplierRecord | null>(null);
const dossierFiles = ref<SupplierFile[]>([]);
const dossierLoading = ref(false);
const fileUploading = ref(false);
const fileError = ref("");

const form = reactive({
  code: "",
  name: "",
  category: "",
  channel: "cooperative",
  contact_name: "",
  contact_phone: "",
  contact_email: "",
  tax_number: "",
  address: "",
  business_license_status: "unknown",
  notes: "",
  is_active: true,
});

const categoryNames: Record<string, string> = {
  goods: "物资供应",
  service: "服务商",
  rental: "租赁及物业",
  vehicle: "车辆服务",
  office: "行政办公",
  other: "其他",
};

const licenseNames: Record<string, string> = {
  registered: "已登记",
  missing: "待补营业执照",
  unknown: "待核对",
};

const categoryOptions = computed(() => uniqueOptions("category", "category_label"));
const channelOptions = computed(() => uniqueOptions("channel", "channel_label"));
const filteredRows = computed(() => {
  const keyword = filters.q.trim().toLocaleLowerCase("zh-CN");
  return rows.value.filter((item) => {
    const searchable = [
      item.code, item.name, item.category_label, item.category, item.channel_label, item.channel,
      item.contact_name, item.contact_phone, item.contact_email, item.tax_number, item.address,
    ].filter(Boolean).join(" ").toLocaleLowerCase("zh-CN");
    if (keyword && !searchable.includes(keyword)) return false;
    if (filters.category && item.category !== filters.category) return false;
    if (filters.channel && item.channel !== filters.channel) return false;
    if (filters.active === "true" && !item.is_active) return false;
    if (filters.active === "false" && item.is_active) return false;
    return true;
  });
});
const activeCount = computed(() => rows.value.filter((item) => item.is_active).length);
const licensedCount = computed(() => rows.value.filter((item) =>
  item.business_license_status === "registered"
  || Boolean(item.files?.length),
).length);

function unwrap<T>(value: ListPayload<T>) {
  return Array.isArray(value) ? value : value.results;
}

function uniqueOptions(valueKey: "category" | "channel", labelKey: "category_label" | "channel_label") {
  const options = new Map<string, string>();
  for (const item of rows.value) {
    const value = item[valueKey];
    if (!value) continue;
    options.set(value, item[labelKey] || categoryNames[value] || value);
  }
  return [...options].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label, "zh-CN"));
}

function errorText(err: unknown, fallback: string) {
  if (!(err instanceof ApiError)) return fallback;
  if (typeof err.errors === "string") return err.errors || err.message;
  const messages = Object.values(err.errors || {}).flatMap((value) =>
    Array.isArray(value) ? value.map(String) : value ? [String(value)] : [],
  );
  return messages.join(" ") || err.message || fallback;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const payload = await api<ListPayload<SupplierRecord>>("/suppliers/");
    rows.value = unwrap(payload).map((item) => ({ ...item, files: item.files || [] }));
  } catch (err) {
    error.value = errorText(err, "供应商名册暂时无法加载。");
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  Object.assign(filters, { q: "", category: "", channel: "", active: "" });
}

function openNew() {
  editing.value = null;
  Object.assign(form, {
    code: "", name: "", category: "", channel: "cooperative", contact_name: "", contact_phone: "",
    contact_email: "", tax_number: "", address: "", business_license_status: "unknown",
    notes: "", is_active: true,
  });
  formError.value = "";
  showForm.value = true;
}

function openEdit(item: SupplierRecord) {
  editing.value = item;
  Object.assign(form, {
    code: item.code || "", name: item.name || "", category: item.category || "", channel: item.channel || "",
    contact_name: item.contact_name || "", contact_phone: item.contact_phone || "",
    contact_email: item.contact_email || "", tax_number: item.tax_number || "", address: item.address || "",
    business_license_status: item.business_license_status || "unknown", notes: item.notes || "",
    is_active: item.is_active,
  });
  formError.value = "";
  showForm.value = true;
}

async function saveSupplier() {
  formError.value = "";
  const payload = Object.fromEntries(Object.entries(form).map(([key, value]) =>
    [key, typeof value === "string" ? value.trim() : value],
  ));
  try {
    if (editing.value) {
      await api(`/suppliers/${editing.value.id}/`, { method: "PATCH", body: JSON.stringify(payload) });
    } else {
      await api("/suppliers/", { method: "POST", body: JSON.stringify(payload) });
    }
    showForm.value = false;
    await load();
  } catch (err) {
    formError.value = errorText(err, "供应商资料未保存。");
  }
}

async function deleteSupplier(item: SupplierRecord) {
  if (!window.confirm(`确认删除供应商“${item.name}”？删除后无法恢复。`)) return;
  try {
    await api(`/suppliers/${item.id}/`, { method: "DELETE" });
    await load();
  } catch (err) {
    error.value = errorText(err, "供应商删除失败。");
  }
}

async function openDossier(item: SupplierRecord) {
  dossierSupplier.value = item;
  dossierFiles.value = item.files || [];
  dossierLoading.value = true;
  fileError.value = "";
  try {
    const payload = await api<ListPayload<SupplierFile>>(`/suppliers/${item.id}/files/`);
    dossierFiles.value = unwrap(payload);
  } catch (err) {
    fileError.value = errorText(err, "营业执照档案暂时无法加载。");
  } finally {
    dossierLoading.value = false;
  }
}

async function refreshDossier() {
  if (!dossierSupplier.value) return;
  const payload = await api<ListPayload<SupplierFile>>(`/suppliers/${dossierSupplier.value.id}/files/`);
  dossierFiles.value = unwrap(payload);
}

async function uploadLicense(event: Event) {
  if (!dossierSupplier.value) return;
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  if (!files.length) return;
  fileUploading.value = true;
  fileError.value = "";
  try {
    for (const file of files) {
      const body = new FormData();
      body.append("file", file);
      await api(`/suppliers/${dossierSupplier.value.id}/files/`, { method: "POST", body });
    }
    await Promise.all([refreshDossier(), load()]);
  } catch (err) {
    fileError.value = errorText(err, "营业执照上传失败，请检查格式后重试。");
  } finally {
    fileUploading.value = false;
    input.value = "";
  }
}

async function downloadFile(file: SupplierFile) {
  if (!dossierSupplier.value) return;
  try {
    await download(
      `/suppliers/${dossierSupplier.value.id}/files/${file.id}/`,
      {},
      fileName(file),
    );
  } catch {
    fileError.value = "营业执照暂时无法下载，请重试。";
  }
}

async function deleteFile(file: SupplierFile) {
  if (!dossierSupplier.value || !window.confirm(`确认删除“${fileName(file)}”？`)) return;
  try {
    await api(`/suppliers/${dossierSupplier.value.id}/files/${file.id}/`, { method: "DELETE" });
    await Promise.all([refreshDossier(), load()]);
  } catch (err) {
    fileError.value = errorText(err, "营业执照删除失败。");
  }
}

function categoryText(item: SupplierRecord) {
  return item.category_label || categoryNames[item.category] || item.category || "未分类";
}

function channelText(item: SupplierRecord) {
  return item.channel_label || item.channel || "未记录渠道";
}

function licenseText(item: SupplierRecord) {
  return item.business_license_status_label
    || licenseNames[item.business_license_status]
    || item.business_license_status
    || "待补营业执照";
}

function licenseComplete(item: SupplierRecord) {
  return ["uploaded", "verified", "not_required"].includes(item.business_license_status)
    || item.business_license_status === "registered"
    || Boolean(item.files?.length);
}

function fileName(file: SupplierFile) {
  return file.original_name || file.name || `供应商文件-${file.id}`;
}

function fileSize(bytes = 0) {
  if (!bytes) return "大小未知";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

onMounted(load);
</script>

<template>
  <div class="page module-page admin-module-page supplier-register-page">
    <header class="page-intro supplier-intro">
      <div>
        <p class="eyebrow">供应协作档案</p>
        <h1>供应商与营业资质</h1>
        <p>联系人、来源渠道和营业执照统一留档，合作时能快速核验。</p>
      </div>
      <button class="primary-button" @click="openNew">
        <AppIcon name="plus" :size="18" />登记供应商
      </button>
    </header>

    <section class="admin-kpi-strip supplier-kpis" aria-label="供应商概览">
      <div><span>供应商总数</span><strong>{{ rows.length }}</strong></div>
      <div><span>当前合作</span><strong>{{ activeCount }}</strong></div>
      <div><span>营业资质已覆盖</span><strong>{{ licensedCount }}</strong></div>
      <div><span>供应类别</span><strong>{{ categoryOptions.length }}</strong></div>
    </section>

    <section class="supplier-filter-bar" aria-label="筛选供应商">
      <label class="supplier-search">
        <AppIcon name="search" :size="18" />
        <span class="sr-only">搜索供应商</span>
        <input v-model="filters.q" placeholder="搜索名称、联系人、电话、税号或地址" />
      </label>
      <select v-model="filters.category" aria-label="供应类别">
        <option value="">全部类别</option>
        <option v-for="item in categoryOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
      <select v-model="filters.channel" aria-label="供应商来源">
        <option value="">全部来源</option>
        <option v-for="item in channelOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
      <select v-model="filters.active" aria-label="合作状态">
        <option value="">全部状态</option>
        <option value="true">当前合作</option>
        <option value="false">已停用</option>
      </select>
      <button v-if="filters.q || filters.category || filters.channel || filters.active" class="text-button" @click="resetFilters">清除条件</button>
      <span class="supplier-result-count">显示 {{ filteredRows.length }} / {{ rows.length }}</span>
    </section>

    <div v-if="error" class="error-block">{{ error }}</div>
    <div v-else-if="loading" class="loading-block">正在整理供应商名册…</div>
    <section v-else-if="filteredRows.length" class="supplier-dossier-grid">
      <article v-for="item in filteredRows" :key="item.id" class="supplier-card" :class="{ inactive: !item.is_active }">
        <header>
          <span class="supplier-code">{{ item.code || `SUP-${item.id}` }}</span>
          <span class="supplier-state" :class="item.is_active ? 'on' : 'off'">{{ item.is_active ? "合作中" : "已停用" }}</span>
        </header>
        <div class="supplier-card-title">
          <span>{{ categoryText(item) }}</span>
          <h2>{{ item.name }}</h2>
          <p>{{ channelText(item) }}</p>
        </div>
        <dl>
          <div><dt>联系人</dt><dd>{{ item.contact_name || "未设置" }}</dd></div>
          <div><dt>联系电话</dt><dd>{{ item.contact_phone || "未设置" }}</dd></div>
          <div class="wide"><dt>税号</dt><dd>{{ item.tax_number || "未设置" }}</dd></div>
          <div class="wide"><dt>地址</dt><dd>{{ item.address || "未设置" }}</dd></div>
        </dl>
        <footer>
          <button class="license-button" :class="{ complete: licenseComplete(item) }" @click="openDossier(item)">
            <AppIcon :name="licenseComplete(item) ? 'download' : 'upload'" :size="16" />
            <span><strong>{{ licenseText(item) }}</strong><small>{{ item.files?.length || 0 }} 个档案文件</small></span>
          </button>
          <div class="supplier-card-actions">
            <button class="text-button" @click="openEdit(item)">编辑</button>
            <button v-if="isSuperuser" class="text-button danger" @click="deleteSupplier(item)">删除</button>
          </div>
        </footer>
      </article>
    </section>
    <div v-else class="empty-state large">
      <strong>没有符合条件的供应商</strong>
      <p>可以清除筛选条件，或登记新的合作单位。</p>
      <button class="primary-button" @click="openNew">登记供应商</button>
    </div>

    <div v-if="showForm" class="modal-backdrop" @click.self="showForm = false">
      <form class="modal-panel admin-form-modal supplier-form-modal" @submit.prevent="saveSupplier">
        <header>
          <div><p class="eyebrow">供应商名册</p><h2>{{ editing ? "编辑供应商资料" : "登记供应商" }}</h2></div>
          <button type="button" class="icon-button" aria-label="关闭" @click="showForm = false"><AppIcon name="close" /></button>
        </header>
        <p v-if="formError" class="form-error supplier-form-error">{{ formError }}</p>
        <div class="form-grid">
          <label><span>供应商编码</span><input v-model="form.code" required placeholder="例如 SUP-0001" /></label>
          <label><span>供应商名称</span><input v-model="form.name" required /></label>
          <label><span>供应类别</span><input v-model="form.category" required list="supplier-category-options" placeholder="例如 服务商、租赁及物业" /></label>
          <label><span>采购途径</span><select v-model="form.channel"><option value="cooperative">合作供应商</option><option value="ecommerce">电商</option><option value="other">其他</option></select></label>
          <label><span>联系人</span><input v-model="form.contact_name" /></label>
          <label><span>联系电话</span><input v-model="form.contact_phone" inputmode="tel" /></label>
          <label><span>联系邮箱</span><input v-model="form.contact_email" type="email" /></label>
          <label><span>统一社会信用代码 / 税号</span><input v-model="form.tax_number" /></label>
          <label><span>营业执照状态</span><select v-model="form.business_license_status"><option value="registered">已登记</option><option value="missing">未登记</option><option value="unknown">待核对</option></select></label>
          <label class="supplier-active-field"><input v-model="form.is_active" type="checkbox" /><span><strong>当前合作</strong><small>停用后仍保留历史资料</small></span></label>
          <label class="wide"><span>地址</span><input v-model="form.address" /></label>
          <label class="wide"><span>备注</span><textarea v-model="form.notes" placeholder="记录服务范围、结算习惯或合作注意事项"></textarea></label>
        </div>
        <datalist id="supplier-category-options"><option v-for="item in categoryOptions" :key="item.value" :value="item.value">{{ item.label }}</option></datalist>
        <button class="primary-button full">{{ editing ? "保存修改" : "保存供应商" }}</button>
      </form>
    </div>

    <div v-if="dossierSupplier" class="modal-backdrop" @click.self="dossierSupplier = null">
      <section class="modal-panel supplier-vault-modal">
        <header class="modal-header">
          <div><p class="eyebrow">营业资质档案</p><h2>{{ dossierSupplier.name }}</h2><p>{{ dossierSupplier.code }} · {{ licenseText(dossierSupplier) }}</p></div>
          <button type="button" class="icon-button" aria-label="关闭" @click="dossierSupplier = null"><AppIcon name="close" /></button>
        </header>
        <div class="supplier-vault-body">
          <div class="license-upload-desk">
            <div><strong>上传营业执照</strong><p>支持 PDF、图片或 Office 文档，可保留更新前后的多份版本。</p></div>
            <label class="primary-button license-file-picker">
              <AppIcon name="upload" :size="18" />{{ fileUploading ? "正在上传…" : "选择文件" }}
              <input type="file" multiple :disabled="fileUploading" accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx" @change="uploadLicense" />
            </label>
          </div>
          <p v-if="fileError" class="form-error">{{ fileError }}</p>
          <div v-if="dossierLoading" class="supplier-vault-empty">正在读取营业执照档案…</div>
          <div v-else-if="dossierFiles.length" class="license-file-list">
            <article v-for="file in dossierFiles" :key="file.id">
              <span class="file-kind">{{ fileName(file).split('.').pop()?.slice(0, 4).toUpperCase() || "FILE" }}</span>
              <div><strong>{{ fileName(file) }}</strong><small>{{ fileSize(file.size_bytes) }}<template v-if="file.uploaded_by_name"> · {{ file.uploaded_by_name }}</template><template v-if="file.created_at"> · {{ file.created_at.slice(0, 10) }}</template></small></div>
              <button class="secondary-button" @click="downloadFile(file)"><AppIcon name="download" :size="16" />下载</button>
              <button class="text-button danger" @click="deleteFile(file)">删除</button>
            </article>
          </div>
          <div v-else class="supplier-vault-empty"><strong>还没有营业执照文件</strong><span>选择文件后会归档到当前供应商名下。</span></div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.supplier-intro > div { max-width: 760px; }
.supplier-kpis { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.supplier-filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.9);
}
.supplier-filter-bar select {
  min-height: 42px;
  padding: 0 34px 0 12px;
  border: 1px solid var(--line-dark);
  border-radius: 9px;
  color: var(--ink);
  background: #fff;
}
.supplier-search {
  display: flex;
  min-width: 280px;
  flex: 1;
  align-items: center;
  gap: 9px;
  min-height: 42px;
  padding: 0 12px;
  color: var(--ink-soft);
  border: 1px solid var(--line-dark);
  border-radius: 9px;
  background: #fff;
}
.supplier-search:focus-within { border-color: var(--blue); box-shadow: 0 0 0 3px rgba(25, 95, 164, 0.12); }
.supplier-search input { width: 100%; border: 0; background: transparent; color: var(--ink); }
.supplier-result-count { margin-left: auto; padding-right: 5px; color: var(--ink-soft); font-size: 12px; white-space: nowrap; }
.supplier-dossier-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.supplier-card {
  position: relative;
  display: flex;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 17px;
  background: #fff;
  box-shadow: 0 8px 28px rgba(28, 49, 65, 0.045);
  transition: border-color 150ms ease, transform 150ms ease, box-shadow 150ms ease;
}
.supplier-card::before { position: absolute; top: 0; left: 22px; width: 76px; height: 5px; border-radius: 0 0 4px 4px; background: var(--admin-teal); content: ""; }
.supplier-card:hover { border-color: #a9c5cb; transform: translateY(-2px); box-shadow: 0 16px 34px rgba(28, 49, 65, 0.08); }
.supplier-card.inactive { background: #f8fafb; opacity: 0.82; }
.supplier-card > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.supplier-code { color: var(--ink-soft); font: 700 12px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 0.05em; }
.supplier-state { font-size: 12px; font-weight: 800; }
.supplier-state.on { color: var(--green); }
.supplier-state.off { color: var(--red); }
.supplier-card-title { min-height: 98px; padding: 24px 0 16px; border-bottom: 1px solid var(--line); }
.supplier-card-title > span { color: var(--admin-teal); font-size: 12px; font-weight: 800; }
.supplier-card-title h2 { margin: 7px 0 5px; font-size: 20px; line-height: 1.35; }
.supplier-card-title p { margin: 0; color: var(--ink-soft); font-size: 12px; }
.supplier-card dl { display: grid; grid-template-columns: 1fr 1fr; gap: 13px 16px; margin: 18px 0; }
.supplier-card dl div { min-width: 0; }
.supplier-card dl .wide { grid-column: 1 / -1; }
.supplier-card dt { color: var(--ink-soft); font-size: 11px; }
.supplier-card dd { margin: 4px 0 0; overflow-wrap: anywhere; color: #263d47; font-size: 13px; font-weight: 700; line-height: 1.5; }
.supplier-card > footer { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 10px; margin-top: auto; padding-top: 15px; border-top: 1px solid var(--line); }
.license-button { display: flex; min-width: 0; align-items: center; gap: 9px; padding: 0; color: #9a5e19; background: transparent; text-align: left; }
.license-button.complete { color: var(--green); }
.license-button span { min-width: 0; }
.license-button strong, .license-button small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.license-button strong { font-size: 12px; }
.license-button small { margin-top: 3px; color: var(--ink-soft); font-size: 11px; }
.supplier-card-actions { display: flex; gap: 10px; }
.supplier-card-actions .text-button { font-size: 12px; }
.text-button.danger { color: var(--red); }
.supplier-form-modal { width: min(820px, 94vw); }
.supplier-form-error { margin: 18px 24px 0; padding: 11px 13px; border-radius: 9px; background: #fff1f0; }
.supplier-active-field { min-height: 43px; align-self: end; flex-direction: row !important; align-items: center; gap: 10px !important; padding: 8px 12px; border: 1px solid #cbd7dc; border-radius: 10px; }
.supplier-active-field input { width: 17px !important; min-height: 17px !important; accent-color: var(--green); }
.supplier-active-field span { display: grid; }
.supplier-active-field small { color: var(--ink-soft); font-size: 11px; font-weight: 400; }
.supplier-vault-modal { width: min(760px, 94vw); }
.supplier-vault-body { padding: 24px 28px 28px; }
.license-upload-desk { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 18px; border: 1px dashed #9dbbc2; border-radius: 13px; background: #f3f8f9; }
.license-upload-desk p { margin: 5px 0 0; color: var(--ink-soft); font-size: 12px; }
.license-file-picker { position: relative; overflow: hidden; flex: 0 0 auto; cursor: pointer; }
.license-file-picker input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.license-file-list { display: grid; gap: 9px; margin-top: 18px; }
.license-file-list article { display: grid; grid-template-columns: 44px minmax(0, 1fr) auto auto; align-items: center; gap: 12px; padding: 13px; border: 1px solid var(--line); border-radius: 11px; }
.license-file-list article > div { min-width: 0; }
.license-file-list article strong, .license-file-list article small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.license-file-list article small { margin-top: 4px; color: var(--ink-soft); font-size: 11px; }
.file-kind { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 9px; color: #fff; background: var(--admin-ink); font: 800 10px ui-monospace, monospace; }
.supplier-vault-empty { display: grid; min-height: 150px; place-items: center; align-content: center; gap: 6px; margin-top: 18px; color: var(--ink-soft); border: 1px dashed var(--line-dark); border-radius: 12px; text-align: center; }
.supplier-vault-empty strong { color: var(--ink); }
@media (max-width: 1050px) {
  .supplier-dossier-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .supplier-filter-bar { flex-wrap: wrap; }
  .supplier-search { min-width: min(100%, 420px); }
}
@media (max-width: 680px) {
  .supplier-intro { align-items: stretch; }
  .supplier-intro .primary-button { width: 100%; }
  .supplier-kpis, .supplier-dossier-grid { grid-template-columns: 1fr; }
  .supplier-filter-bar { align-items: stretch; }
  .supplier-filter-bar select, .supplier-search { width: 100%; min-width: 0; }
  .supplier-result-count { width: 100%; margin-left: 0; }
  .supplier-card > footer { grid-template-columns: 1fr; }
  .supplier-card-actions { justify-content: flex-end; }
  .license-upload-desk { align-items: stretch; flex-direction: column; }
  .license-file-picker { width: 100%; }
  .license-file-list article { grid-template-columns: 42px minmax(0, 1fr); }
  .license-file-list article .secondary-button, .license-file-list article .text-button { width: 100%; }
}
</style>
