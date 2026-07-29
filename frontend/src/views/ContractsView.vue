<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { api, ApiError, download } from "../api";
import AppIcon from "../components/AppIcon.vue";
import PersonSearchSelect from "../components/PersonSearchSelect.vue";
import type { Contract, ContractAttachment, ContractType, ExpenseCategory, Lookups, Supplier } from "../types";

const props = defineProps<{ lookups: Lookups | null }>();
const rows = ref<Contract[]>([]);
const suppliers = ref<Supplier[]>([]);
const categories = ref<ExpenseCategory[]>([]);
const contractTypes = ref<ContractType[]>([]);
const error = ref("");
const loading = ref(false);
const filters = reactive({ q: "", contract_type: "", status: "" });

const showForm = ref(false);
const formMode = ref<"create" | "edit" | "renew">("create");
const editing = ref<Contract | null>(null);
const renewingFrom = ref<Contract | null>(null);
const selectedContract = ref<Contract | null>(null);
const historyContract = ref<Contract | null>(null);
const changeContract = ref<Contract | null>(null);
const fileUploading = ref(false);
const fileError = ref("");
const documentType = ref("original");
const fileChange = ref("");

const form = reactive({
  contract_no: "", name: "", contract_type: "", supplier: "", category: "", department: "", owner: "",
  status: "draft", start_date: "", end_date: "", amount: "", renewal_notice_days: 30,
  auto_renew: false, kingdee_code: "", external_id: "", notes: "",
});
const changeForm = reactive({
  change_type: "extension", changed_on: new Date().toISOString().slice(0, 10),
  new_start_date: "", new_end_date: "", new_amount: "", notes: "",
});

const due = computed(() => rows.value.filter((item) =>
  ["active", "expired"].includes(item.status)
  && item.days_to_expiry !== null
  && item.days_to_expiry <= item.renewal_notice_days,
));
const activeAmount = computed(() => rows.value
  .filter((item) => item.status === "active")
  .reduce((sum, item) => sum + Number(item.amount), 0));
const attachmentGroups = computed(() => {
  if (!selectedContract.value) return [];
  const contract = selectedContract.value;
  const groups = [{ key: "initial", label: "初始合同文件", files: contract.attachments.filter((file) => !file.change) }];
  for (const change of [...contract.changes].reverse()) {
    groups.push({
      key: String(change.id),
      label: `${change.changed_on} · ${change.change_type_label}`,
      files: contract.attachments.filter((file) => file.change === change.id),
    });
  }
  return groups.filter((group) => group.files.length || group.key === "initial");
});

function queryPath() {
  const params = new URLSearchParams();
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.contract_type) params.set("contract_type", filters.contract_type);
  if (filters.status) params.set("status", filters.status);
  const query = params.toString();
  return `/contracts/${query ? `?${query}` : ""}`;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    [rows.value, suppliers.value, categories.value, contractTypes.value] = await Promise.all([
      api<Contract[]>(queryPath()), api<Supplier[]>("/suppliers/"),
      api<ExpenseCategory[]>("/expense-categories/"), api<ContractType[]>("/contract-types/"),
    ]);
    const refresh = (current: Contract | null) => rows.value.find((item) => item.id === current?.id) || null;
    if (selectedContract.value) selectedContract.value = refresh(selectedContract.value);
    if (historyContract.value) historyContract.value = refresh(historyContract.value);
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "合同暂时无法加载。";
  } finally {
    loading.value = false;
  }
}

function clearFilters() {
  Object.assign(filters, { q: "", contract_type: "", status: "" });
  void load();
}

function assignForm(item?: Contract) {
  Object.assign(form, item ? {
    contract_no: item.contract_no, name: item.name, contract_type: item.contract_type || "",
    supplier: item.supplier || "", category: item.category || "", department: item.department || "", owner: item.owner || "",
    status: item.status, start_date: item.start_date || "", end_date: item.end_date || "", amount: item.amount,
    renewal_notice_days: item.renewal_notice_days, auto_renew: item.auto_renew,
    kingdee_code: item.kingdee_code, external_id: item.external_id, notes: item.notes,
  } : {
    contract_no: "", name: "", contract_type: "", supplier: "", category: "", department: "", owner: "",
    status: "draft", start_date: "", end_date: "", amount: "", renewal_notice_days: 30,
    auto_renew: false, kingdee_code: "", external_id: "", notes: "",
  });
}

function openForm(item?: Contract) {
  formMode.value = item ? "edit" : "create";
  editing.value = item || null;
  renewingFrom.value = null;
  assignForm(item);
  showForm.value = true;
}

function openRenew(item: Contract) {
  formMode.value = "renew";
  editing.value = null;
  renewingFrom.value = item;
  assignForm(item);
  Object.assign(form, { contract_no: "", status: "active", start_date: "", end_date: "", kingdee_code: "", external_id: "" });
  showForm.value = true;
}

async function saveContract() {
  const payload = {
    ...form,
    contract_type: form.contract_type ? Number(form.contract_type) : null,
    supplier: form.supplier ? Number(form.supplier) : null,
    category: form.category ? Number(form.category) : null,
    department: form.department ? Number(form.department) : null,
    owner: form.owner ? Number(form.owner) : null,
    start_date: form.start_date || null, end_date: form.end_date || null,
  };
  try {
    const path = formMode.value === "renew"
      ? `/contracts/${renewingFrom.value?.id}/renew/`
      : editing.value ? `/contracts/${editing.value.id}/` : "/contracts/";
    await api(path, { method: editing.value ? "PATCH" : "POST", body: JSON.stringify(payload) });
    showForm.value = false;
    await load();
  } catch (err) {
    error.value = err instanceof ApiError ? Object.values(err.errors).flat().join(" ") || err.message : "合同未保存。";
  }
}

function openChange(item: Contract) {
  changeContract.value = item;
  Object.assign(changeForm, {
    change_type: "extension", changed_on: new Date().toISOString().slice(0, 10),
    new_start_date: "", new_end_date: "", new_amount: "", notes: "",
  });
}

async function saveChange() {
  if (!changeContract.value) return;
  try {
    await api(`/contracts/${changeContract.value.id}/changes/`, {
      method: "POST",
      body: JSON.stringify({
        ...changeForm,
        new_start_date: changeForm.new_start_date || null,
        new_end_date: changeForm.new_end_date || null,
        new_amount: changeForm.new_amount === "" ? null : changeForm.new_amount,
      }),
    });
    changeContract.value = null;
    await load();
  } catch (err) {
    error.value = err instanceof ApiError ? Object.values(err.errors).flat().join(" ") || err.message : "合同变更未保存。";
  }
}

function openFiles(item: Contract) {
  selectedContract.value = item;
  documentType.value = "original";
  fileChange.value = "";
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
      if (fileChange.value) body.append("change_id", fileChange.value);
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
  try { await download(file.content_url, {}, file.original_name); }
  catch { fileError.value = "合同文件暂时无法下载，请重试。"; }
}

async function deleteFile(file: ContractAttachment) {
  if (!window.confirm(`确认删除“${file.original_name}”？`)) return;
  try { await api(file.content_url, { method: "DELETE" }); await load(); }
  catch (err) { fileError.value = err instanceof ApiError ? err.message : "合同文件删除失败，请重试。"; }
}

function money(value: string | number) {
  return `¥${Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`;
}
function fileSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
function dueText(item: Contract) {
  if (item.days_to_expiry === null) return "未设置到期日";
  if (item.days_to_expiry < 0) return `已到期 ${-item.days_to_expiry} 天`;
  return `距到期 ${item.days_to_expiry} 天`;
}

onMounted(load);
</script>

<template>
  <div class="page module-page admin-module-page contract-register-page">
    <header class="page-intro">
      <div><p class="eyebrow">合同履约台账</p><h1>合同、周期和历次变更</h1><p>续签形成新合同，延期和金额调整保留变更前后的完整记录。</p></div>
      <div class="page-actions"><button class="primary-button" @click="openForm()">登记合同</button></div>
    </header>

    <section class="admin-kpi-strip contract-kpis">
      <div><span>当前结果</span><strong>{{ rows.length }}</strong></div>
      <div><span>履行中</span><strong>{{ rows.filter((item) => item.status === 'active').length }}</strong></div>
      <div><span>临近或已经到期</span><strong>{{ due.length }}</strong></div>
      <div><span>履行中金额</span><strong class="money-kpi">{{ money(activeAmount) }}</strong></div>
    </section>

    <form class="contract-filter-bar" @submit.prevent="load">
      <label class="contract-search"><AppIcon name="search" :size="18" /><input v-model="filters.q" placeholder="搜索合同编号、名称、供应商或负责人" /></label>
      <select v-model="filters.contract_type" @change="load"><option value="">全部合同类型</option><option v-for="item in contractTypes.filter((x) => x.is_active)" :key="item.id" :value="item.id">{{ item.name }}</option></select>
      <select v-model="filters.status" @change="load"><option value="">全部状态</option><option value="draft">草稿</option><option value="active">履行中</option><option value="expired">已到期未处理</option><option value="completed">已完成</option><option value="terminated">已终止</option></select>
      <button class="secondary-button" type="submit">搜索</button>
      <button v-if="filters.q || filters.contract_type || filters.status" class="text-button" type="button" @click="clearFilters">清除条件</button>
    </form>

    <div v-if="error" class="error-block">{{ error }}</div>
    <section class="contract-ledger-shell" :class="{ loading }">
      <table class="contract-ledger">
        <thead><tr><th>合同</th><th>类型 / 相对方</th><th>履约期间</th><th>金额 / 科目</th><th>负责人</th><th>状态</th><th>档案</th><th></th></tr></thead>
        <tbody>
          <tr v-for="item in rows" :key="item.id" :class="{ due: due.includes(item), expired: item.status === 'expired' }">
            <td data-label="合同"><strong>{{ item.name }}</strong><small>{{ item.contract_no }}</small><span v-if="item.previous_contract_no" class="lineage-tag">续自 {{ item.previous_contract_no }}</span><span v-else-if="item.renewal_contracts.length" class="lineage-tag">已续签 {{ item.renewal_contracts[0].contract_no }}</span></td>
            <td data-label="类型 / 相对方"><strong>{{ item.contract_type_name || '未分类' }}</strong><small>{{ item.supplier_name || '未设置供应商' }}</small></td>
            <td data-label="履约期间"><strong>{{ item.start_date || '—' }} → {{ item.end_date || '—' }}</strong><small :class="{ 'due-copy': due.includes(item) }">{{ dueText(item) }}</small></td>
            <td data-label="金额 / 科目"><strong>{{ money(item.amount) }}</strong><small>{{ item.category_name || '未设置费用类别' }}</small></td>
            <td data-label="负责人"><strong>{{ item.owner_name || '未设置' }}</strong><small>{{ item.department_name || '未设置部门' }}</small></td>
            <td data-label="状态"><span class="record-status" :data-status="item.status">{{ item.status_label }}</span><small>{{ item.auto_renew ? '约定自动续期' : '到期人工处理' }}</small></td>
            <td data-label="档案"><strong>{{ item.attachments.length }} 个文件</strong><small>{{ item.changes.length }} 次变更</small></td>
            <td class="contract-row-actions"><button class="text-button" @click="historyContract = item">历史</button><button class="text-button" @click="openFiles(item)">文件</button><button class="text-button" @click="openForm(item)">编辑</button><button v-if="!item.renewal_contracts.length && !['terminated'].includes(item.status)" class="text-button" @click="openRenew(item)">续签</button><button v-if="!['completed','terminated'].includes(item.status)" class="text-button" @click="openChange(item)">变更</button></td>
          </tr>
        </tbody>
      </table>
      <div v-if="!rows.length && !loading" class="empty-state large">没有符合条件的合同。可以调整搜索条件或登记新合同。</div>
    </section>

    <div v-if="showForm" class="modal-backdrop" @click.self="showForm = false">
      <form class="modal-panel admin-form-modal" @submit.prevent="saveContract">
        <header><div><p class="eyebrow">{{ formMode === 'renew' ? `续签自 ${renewingFrom?.contract_no}` : '合同台账' }}</p><h2>{{ formMode === 'edit' ? '编辑合同基础资料' : formMode === 'renew' ? '建立下一期合同' : '登记行政合同' }}</h2></div><button type="button" class="icon-button" @click="showForm = false">×</button></header>
        <p v-if="formMode === 'edit'" class="modal-guidance">合同期限和金额需要通过“登记变更”调整，系统会保留调整前的数据。</p>
        <div class="form-grid">
          <label><span>合同编号</span><input v-model="form.contract_no" required /></label>
          <label><span>合同名称</span><input v-model="form.name" required /></label>
          <label><span>合同类型</span><select v-model="form.contract_type"><option value="">未分类</option><option v-for="item in contractTypes.filter((x) => x.is_active)" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
          <label><span>供应商</span><select v-model="form.supplier"><option value="">未设置</option><option v-for="item in suppliers" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
          <label><span>费用类别</span><select v-model="form.category"><option value="">未设置</option><option v-for="item in categories" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
          <label><span>归属部门</span><select v-model="form.department"><option value="">未设置</option><option v-for="item in lookups?.departments || []" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
          <label><span>负责人</span><PersonSearchSelect v-model="form.owner" :users="lookups?.users || []" /></label>
          <label><span>开始日期</span><input v-model="form.start_date" type="date" :disabled="formMode === 'edit'" /></label>
          <label><span>结束日期</span><input v-model="form.end_date" type="date" :disabled="formMode === 'edit'" /></label>
          <label><span>合同金额</span><input v-model="form.amount" type="number" min="0" step="0.01" required :disabled="formMode === 'edit'" /></label>
          <label><span>到期提前提醒</span><input v-model.number="form.renewal_notice_days" type="number" min="1" /><small>天</small></label>
          <label><span>状态</span><select v-model="form.status"><option value="draft">草稿</option><option value="active">履行中</option><option value="expired">已到期未处理</option><option value="completed">已完成</option><option value="terminated">已终止</option></select></label>
          <label class="checkbox-label"><input v-model="form.auto_renew" type="checkbox" /><span>合同约定自动续期</span></label>
          <label><span>金蝶编码</span><input v-model="form.kingdee_code" /></label>
          <label><span>预算系统标识</span><input v-model="form.external_id" /></label>
          <label class="wide"><span>备注</span><textarea v-model="form.notes"></textarea></label>
        </div>
        <button class="primary-button full">{{ formMode === 'renew' ? '建立续签合同' : '保存合同' }}</button>
      </form>
    </div>

    <div v-if="changeContract" class="modal-backdrop" @click.self="changeContract = null">
      <form class="modal-panel admin-form-modal contract-change-modal" @submit.prevent="saveChange">
        <header><div><p class="eyebrow">{{ changeContract.contract_no }}</p><h2>登记合同变更</h2></div><button type="button" class="icon-button" @click="changeContract = null">×</button></header>
        <p class="modal-guidance">保存后会更新当前有效值，同时永久保留原期限、原金额和本次说明。</p>
        <div class="form-grid">
          <label><span>变更类型</span><select v-model="changeForm.change_type"><option value="extension">延期续约</option><option value="supplement">补充协议</option><option value="amount">金额调整</option><option value="termination">提前终止</option><option value="other">其他变更</option></select></label>
          <label><span>生效日期</span><input v-model="changeForm.changed_on" type="date" required /></label>
          <label><span>新开始日期</span><input v-model="changeForm.new_start_date" type="date" /></label>
          <label><span>新结束日期</span><input v-model="changeForm.new_end_date" type="date" :required="changeForm.change_type === 'extension'" /></label>
          <label><span>新合同金额</span><input v-model="changeForm.new_amount" type="number" min="0" step="0.01" :required="changeForm.change_type === 'amount'" /></label>
          <label class="wide"><span>变更说明</span><textarea v-model="changeForm.notes" required placeholder="说明延期、调价、终止或补充约定的原因"></textarea></label>
        </div>
        <button class="primary-button full">保存变更记录</button>
      </form>
    </div>

    <div v-if="historyContract" class="modal-backdrop" @click.self="historyContract = null">
      <section class="modal-panel contract-history-modal">
        <header><div><p class="eyebrow">合同历史 · {{ historyContract.contract_no }}</p><h2>{{ historyContract.name }}</h2></div><button type="button" class="icon-button" @click="historyContract = null">×</button></header>
        <div class="contract-lineage">
          <div v-if="historyContract.previous_contract_no"><span>上一期</span><strong>{{ historyContract.previous_contract_no }}</strong></div>
          <div class="current"><span>当前合同</span><strong>{{ historyContract.contract_no }}</strong><small>{{ historyContract.start_date || '—' }} 至 {{ historyContract.end_date || '—' }}</small></div>
          <div v-for="renewal in historyContract.renewal_contracts" :key="renewal.id"><span>下一期</span><strong>{{ renewal.contract_no }}</strong><small>{{ renewal.start_date || '—' }} 至 {{ renewal.end_date || '—' }}</small></div>
        </div>
        <div class="contract-change-timeline">
          <article v-for="change in historyContract.changes" :key="change.id">
            <i></i><div><header><strong>{{ change.change_type_label }}</strong><time>{{ change.changed_on }}</time></header><p>{{ change.notes }}</p><dl><div v-if="change.old_end_date !== change.new_end_date && change.new_end_date"><dt>结束日期</dt><dd>{{ change.old_end_date || '—' }} → {{ change.new_end_date }}</dd></div><div v-if="change.old_amount !== change.new_amount && change.new_amount"><dt>合同金额</dt><dd>{{ money(change.old_amount || 0) }} → {{ money(change.new_amount) }}</dd></div></dl><small>{{ change.created_by_name }} · {{ historyContract.attachments.filter((file) => file.change === change.id).length }} 个关联文件</small></div>
          </article>
          <div v-if="!historyContract.changes.length" class="empty-state">这份合同还没有延期、调价或补充协议记录。</div>
        </div>
      </section>
    </div>

    <div v-if="selectedContract" class="modal-backdrop" @click.self="selectedContract = null">
      <section class="modal-panel file-vault-modal">
        <header><div><p class="eyebrow">合同文件 · {{ selectedContract.contract_no }}</p><h2>{{ selectedContract.name }}</h2></div><button type="button" class="icon-button" @click="selectedContract = null">×</button></header>
        <div class="contract-upload-desk contract-upload-versioned">
          <label><span>归档位置</span><select v-model="fileChange"><option value="">初始合同</option><option v-for="change in [...selectedContract.changes].reverse()" :key="change.id" :value="change.id">{{ change.changed_on }} · {{ change.change_type_label }}</option></select></label>
          <label><span>文件类别</span><select v-model="documentType"><option value="original">合同原件</option><option value="signed">盖章扫描件</option><option value="supplement">补充协议</option><option value="quotation">报价单</option><option value="other">其他</option></select></label>
          <label class="primary-button contract-file-picker"><AppIcon name="upload" :size="18" />{{ fileUploading ? '正在上传…' : '选择合同文件' }}<input type="file" multiple :disabled="fileUploading" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.webp,.zip,.rar,.7z,.ofd,.wps" @change="uploadFiles" /></label>
          <small>文件存储在公司 Nextcloud，并按初始合同或具体变更分组。</small>
        </div>
        <p v-if="fileError" class="form-error file-vault-error">{{ fileError }}</p>
        <div v-if="selectedContract.attachments.length" class="contract-file-groups">
          <section v-for="group in attachmentGroups" :key="group.key"><header><strong>{{ group.label }}</strong><span>{{ group.files.length }} 个文件</span></header><div class="contract-file-list"><article v-for="file in group.files" :key="file.id"><span class="file-kind">{{ file.original_name.split('.').pop()?.slice(0, 4).toUpperCase() }}</span><div><strong>{{ file.original_name }}</strong><small>{{ file.document_type_label }} · {{ fileSize(file.size_bytes) }} · {{ file.uploaded_by_name }}</small></div><button class="secondary-button" @click="downloadFile(file)"><AppIcon name="download" :size="16" />下载</button><button class="text-button danger" @click="deleteFile(file)">删除</button></article></div></section>
        </div>
        <div v-else class="file-vault-empty"><strong>还没有合同文件</strong><span>上传初始合同文件，或先登记变更后归档补充协议。</span></div>
      </section>
    </div>
  </div>
</template>
