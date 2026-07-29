<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { api, ApiError, download } from "../api";
import AppIcon from "../components/AppIcon.vue";
import PersonSearchSelect from "../components/PersonSearchSelect.vue";
import type { Contract, ContractAttachment, ExpenseCategory, Lookups, Supplier } from "../types";

const props = defineProps<{ lookups: Lookups | null }>();
const rows = ref<Contract[]>([]);
const suppliers = ref<Supplier[]>([]);
const categories = ref<ExpenseCategory[]>([]);
const showForm = ref(false);
const error = ref("");
const editing = ref<Contract | null>(null);
const selectedContract = ref<Contract | null>(null);
const fileUploading = ref(false);
const fileError = ref("");
const documentType = ref("original");
const form = reactive({
  contract_no: "", name: "", supplier: "", category: "", department: "", owner: "",
  status: "draft", start_date: "", end_date: "", amount: "", renewal_notice_days: 30,
  auto_renew: false, kingdee_code: "", external_id: "", notes: "",
});

const due = computed(() => rows.value.filter(
  (item) => item.status === "active" && item.days_to_expiry !== null && item.days_to_expiry <= item.renewal_notice_days,
));

async function load() {
  try {
    [rows.value, suppliers.value, categories.value] = await Promise.all([
      api<Contract[]>("/contracts/"),
      api<Supplier[]>("/suppliers/"),
      api<ExpenseCategory[]>("/expense-categories/"),
    ]);
    if (selectedContract.value) {
      selectedContract.value = rows.value.find((item) => item.id === selectedContract.value?.id) || null;
    }
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "合同暂时无法加载。";
  }
}

function openForm(item?: Contract) {
  editing.value = item || null;
  Object.assign(form, item ? {
    contract_no: item.contract_no, name: item.name, supplier: item.supplier || "",
    category: item.category || "", department: item.department || "", owner: item.owner || "",
    status: item.status, start_date: item.start_date || "", end_date: item.end_date || "",
    amount: item.amount, renewal_notice_days: item.renewal_notice_days, auto_renew: item.auto_renew,
    kingdee_code: item.kingdee_code, external_id: item.external_id, notes: item.notes,
  } : {
    contract_no: "", name: "", supplier: "", category: "", department: "", owner: "",
    status: "draft", start_date: "", end_date: "", amount: "", renewal_notice_days: 30,
    auto_renew: false, kingdee_code: "", external_id: "", notes: "",
  });
  showForm.value = true;
}

async function saveContract() {
  try {
    await api(editing.value ? `/contracts/${editing.value.id}/` : "/contracts/", {
      method: editing.value ? "PATCH" : "POST",
      body: JSON.stringify({
        ...form,
        supplier: form.supplier ? Number(form.supplier) : null,
        category: form.category ? Number(form.category) : null,
        department: form.department ? Number(form.department) : null,
        owner: form.owner ? Number(form.owner) : null,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
      }),
    });
    showForm.value = false;
    await load();
  } catch (err) {
    error.value = err instanceof ApiError
      ? Object.values(err.errors).flat().join(" ") || err.message
      : "合同未保存。";
  }
}

function openFiles(item: Contract) {
  selectedContract.value = item;
  documentType.value = "original";
  fileError.value = "";
}

async function uploadFiles(event: Event) {
  if (!selectedContract.value) return;
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  if (!files.length) return;
  fileUploading.value = true;
  fileError.value = "";
  try {
    for (const file of files) {
      const body = new FormData();
      body.append("file", file);
      body.append("document_type", documentType.value);
      await api(`/contracts/${selectedContract.value.id}/files/`, { method: "POST", body });
    }
    await load();
  } catch (err) {
    fileError.value = err instanceof ApiError ? err.message : "合同文件上传失败，请重试。";
  } finally {
    fileUploading.value = false;
    input.value = "";
  }
}

async function downloadFile(file: ContractAttachment) {
  if (!selectedContract.value) return;
  try {
    await download(file.content_url, {}, file.original_name);
  } catch {
    fileError.value = "合同文件暂时无法下载，请重试。";
  }
}

async function deleteFile(file: ContractAttachment) {
  if (!selectedContract.value || !window.confirm(`确认删除“${file.original_name}”？`)) return;
  try {
    await api(file.content_url, { method: "DELETE" });
    await load();
  } catch (err) {
    fileError.value = err instanceof ApiError ? err.message : "合同文件删除失败，请重试。";
  }
}

function money(value: string | number) {
  return `¥${Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`;
}

function fileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

onMounted(load);
</script>

<template>
  <div class="page module-page admin-module-page">
    <header class="page-intro">
      <div><p class="eyebrow">合同与周期事项</p><h1>合同履约与到期提醒</h1><p>供应商、费用科目、负责人和合同源文件统一留档。</p></div>
      <div class="page-actions"><button class="primary-button" @click="openForm()">登记合同</button></div>
    </header>

    <section class="admin-kpi-strip">
      <div><span>履行中合同</span><strong>{{ rows.filter((item) => item.status === 'active').length }}</strong></div>
      <div><span>临近到期</span><strong>{{ due.length }}</strong></div>
      <div><span>合同文件</span><strong>{{ rows.reduce((total, item) => total + item.attachments.length, 0) }}</strong></div>
      <div><span>合同总额</span><strong class="money-kpi">{{ money(rows.filter((item) => item.status === 'active').reduce((sum, item) => sum + Number(item.amount), 0)) }}</strong></div>
    </section>

    <div v-if="error" class="error-block">{{ error }}</div>
    <section class="contract-grid">
      <article v-for="item in rows" :key="item.id" :class="{ due: item.days_to_expiry !== null && item.days_to_expiry <= item.renewal_notice_days && item.status === 'active' }">
        <header><span class="record-status" :data-status="item.status">{{ item.status_label }}</span><small>{{ item.contract_no }}</small></header>
        <h2>{{ item.name }}</h2>
        <p>{{ item.supplier_name || '未设置供应商' }} · {{ item.category_name || '未设置费用类别' }}</p>
        <div class="contract-amount">{{ money(item.amount) }}</div>
        <dl>
          <div><dt>履约期间</dt><dd>{{ item.start_date || '—' }} 至 {{ item.end_date || '—' }}</dd></div>
          <div><dt>负责人</dt><dd>{{ item.owner_name || '未设置' }}</dd></div>
          <div><dt>归属部门</dt><dd>{{ item.department_name || '未设置' }}</dd></div>
          <div><dt>源文件</dt><dd>{{ item.attachments.length }} 个</dd></div>
        </dl>
        <footer><span v-if="item.days_to_expiry !== null">{{ item.days_to_expiry < 0 ? `已到期 ${-item.days_to_expiry} 天` : `距到期 ${item.days_to_expiry} 天` }}</span><span v-else>未设置到期日</span><span>{{ item.auto_renew ? '自动续签' : '不自动续签' }}</span></footer>
        <div class="contract-card-actions">
          <button class="secondary-button" @click="openFiles(item)"><AppIcon name="request" :size="16" />文件 {{ item.attachments.length }}</button>
          <button class="text-button" @click="openForm(item)">编辑合同</button>
        </div>
      </article>
      <div v-if="!rows.length" class="empty-state large">还没有合同记录。</div>
    </section>

    <div v-if="showForm" class="modal-backdrop" @click.self="showForm = false">
      <form class="modal-panel admin-form-modal" @submit.prevent="saveContract">
        <header><div><p class="eyebrow">合同台账</p><h2>{{ editing ? '编辑行政合同' : '登记行政合同' }}</h2></div><button type="button" class="icon-button" @click="showForm = false">×</button></header>
        <div class="form-grid">
          <label><span>合同编号</span><input v-model="form.contract_no" required /></label>
          <label><span>合同名称</span><input v-model="form.name" required /></label>
          <label><span>供应商</span><select v-model="form.supplier"><option value="">未设置</option><option v-for="item in suppliers" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
          <label><span>费用类别</span><select v-model="form.category"><option value="">未设置</option><option v-for="item in categories" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
          <label><span>归属部门</span><select v-model="form.department"><option value="">未设置</option><option v-for="item in lookups?.departments || []" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
          <label><span>负责人</span><PersonSearchSelect v-model="form.owner" :users="lookups?.users || []" /></label>
          <label><span>开始日期</span><input v-model="form.start_date" type="date" /></label>
          <label><span>结束日期</span><input v-model="form.end_date" type="date" /></label>
          <label><span>合同金额</span><input v-model="form.amount" type="number" min="0" step="0.01" required /></label>
          <label><span>到期提前提醒</span><input v-model.number="form.renewal_notice_days" type="number" min="1" /><small>天</small></label>
          <label><span>状态</span><select v-model="form.status"><option value="draft">草稿</option><option value="active">履行中</option><option value="completed">已完成</option><option value="terminated">已终止</option></select></label>
          <label class="checkbox-label"><input v-model="form.auto_renew" type="checkbox" /><span>自动续签</span></label>
          <label><span>金蝶编码</span><input v-model="form.kingdee_code" /></label>
          <label><span>预算系统标识</span><input v-model="form.external_id" /></label>
          <label class="wide"><span>备注</span><textarea v-model="form.notes"></textarea></label>
        </div>
        <button class="primary-button full">保存合同</button>
      </form>
    </div>

    <div v-if="selectedContract" class="modal-backdrop" @click.self="selectedContract = null">
      <section class="modal-panel file-vault-modal">
        <header>
          <div><p class="eyebrow">合同文件 · {{ selectedContract.contract_no }}</p><h2>{{ selectedContract.name }}</h2></div>
          <button type="button" class="icon-button" @click="selectedContract = null">×</button>
        </header>
        <div class="contract-upload-desk">
          <label><span>文件类别</span><select v-model="documentType"><option value="original">合同原件</option><option value="signed">盖章扫描件</option><option value="supplement">补充协议</option><option value="quotation">报价单</option><option value="other">其他</option></select></label>
          <label class="primary-button contract-file-picker">
            <AppIcon name="upload" :size="18" />{{ fileUploading ? '正在上传…' : '选择合同文件' }}
            <input type="file" multiple :disabled="fileUploading" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.webp,.zip,.rar,.7z,.ofd,.wps" @change="uploadFiles" />
          </label>
          <small>单个文件最大 100MB，文件安全存储在公司 Nextcloud。</small>
        </div>
        <p v-if="fileError" class="form-error file-vault-error">{{ fileError }}</p>
        <div v-if="selectedContract.attachments.length" class="contract-file-list">
          <article v-for="file in selectedContract.attachments" :key="file.id">
            <span class="file-kind">{{ file.original_name.split('.').pop()?.slice(0, 4).toUpperCase() }}</span>
            <div><strong>{{ file.original_name }}</strong><small>{{ file.document_type_label }} · {{ fileSize(file.size_bytes) }} · {{ file.uploaded_by_name }}</small></div>
            <button class="secondary-button" @click="downloadFile(file)"><AppIcon name="download" :size="16" />下载</button>
            <button class="text-button danger" @click="deleteFile(file)">删除</button>
          </article>
        </div>
        <div v-else class="file-vault-empty"><strong>还没有合同源文件</strong><span>上传原始可编辑文件、盖章扫描件或补充协议。</span></div>
      </section>
    </div>
  </div>
</template>
