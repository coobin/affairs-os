<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { api, ApiError, download } from "../api";
import AppIcon from "../components/AppIcon.vue";
import PersonSearchSelect from "../components/PersonSearchSelect.vue";
import type { Contract, ContractAttachment, ContractType, ExpenseCategory, Lookups, Supplier } from "../types";

const props = defineProps<{ lookups: Lookups | null; isSuperuser: boolean }>();
const rows = ref<Contract[]>([]);
const suppliers = ref<Supplier[]>([]);
const categories = ref<ExpenseCategory[]>([]);
const contractTypes = ref<ContractType[]>([]);
const offices = ref<{ id: number; code: string; name: string }[]>([]);
const error = ref("");
const formError = ref("");
const loading = ref(false);
const initialParams = new URLSearchParams(window.location.search);
const filters = reactive({
  q: initialParams.get("q") || "",
  contract_type: initialParams.get("contract_type") || "",
  status: initialParams.get("status") || "",
});
const dueOnly = ref(initialParams.get("due") === "1");

const showForm = ref(false);
const formMode = ref<"create" | "edit" | "renew">("create");
const editing = ref<Contract | null>(null);
const renewingFrom = ref<Contract | null>(null);
const selectedContract = ref<Contract | null>(null);
const historyContract = ref<Contract | null>(null);
const historyRecords = ref<Contract[]>([]);
const historyIndex = ref(0);
const historyLoading = ref(false);
const historyError = ref("");
const changeContract = ref<Contract | null>(null);
const changeError = ref("");
const fileUploading = ref(false);
const fileError = ref("");
const documentType = ref("signed");
const fileChange = ref("");

const form = reactive({
  contract_no: "", name: "", contract_type: "", supplier: "", office: "", category: "", department: "", owner: "",
  status: "draft", start_date: "", end_date: "", amount: "", amount_description: "", renewal_notice_days: 30,
  auto_renew: false, payment_method: "", payment_terms: "", service_content: "", kingdee_code: "", external_id: "", notes: "",
});
const changeForm = reactive({
  change_type: "extension", changed_on: new Date().toISOString().slice(0, 10),
  new_start_date: "", new_end_date: "", new_amount: "", notes: "",
});

const due = computed(() => dueOnly.value ? rows.value : rows.value.filter((item) =>
  ["active", "expired"].includes(item.status)
  && item.days_to_expiry !== null
  && item.days_to_expiry <= item.renewal_notice_days,
));
const activeAmount = computed(() => rows.value
  .filter((item) => item.status === "active" && !item.supplement_of)
  .reduce((sum, item) => sum + Number(item.total_amount), 0));
const activeHistory = computed(() => historyRecords.value[historyIndex.value] || null);
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
  if (dueOnly.value) params.set("due", "1");
  const query = params.toString();
  return `/contracts/${query ? `?${query}` : ""}`;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    [rows.value, suppliers.value, categories.value, contractTypes.value, offices.value] = await Promise.all([
      api<Contract[]>(queryPath()), api<Supplier[]>("/suppliers/"),
      api<ExpenseCategory[]>("/expense-categories/"), api<ContractType[]>("/contract-types/"),
      api<{ id: number; code: string; name: string }[]>("/offices/"),
    ]);
    const refresh = (current: Contract | null) => rows.value.find((item) => item.id === current?.id) || null;
    if (selectedContract.value) selectedContract.value = refresh(selectedContract.value);
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "合同暂时无法加载。";
  } finally {
    loading.value = false;
  }
}

function clearFilters() {
  Object.assign(filters, { q: "", contract_type: "", status: "" });
  dueOnly.value = false;
  window.history.replaceState({}, "", "/contracts");
  void load();
}

function errorText(err: unknown, fallback: string) {
  if (!(err instanceof ApiError)) return fallback;
  if (typeof err.errors === "string") return err.errors || err.message;
  if (err.errors && typeof err.errors === "object") {
    const parts = Object.values(err.errors).flat().filter(Boolean);
    if (parts.length) return parts.join(" ");
  }
  return err.message || fallback;
}

function assignForm(item?: Contract) {
  Object.assign(form, item ? {
    contract_no: item.contract_no, name: item.name, contract_type: item.contract_type || "",
    supplier: item.supplier || "", office: item.office || "", category: item.category || "", department: item.department || "", owner: item.owner || "",
    status: item.status, start_date: item.start_date || "", end_date: item.end_date || "", amount: item.amount, amount_description: item.amount_description || "",
    renewal_notice_days: item.renewal_notice_days, auto_renew: item.auto_renew,
    payment_method: item.payment_method || "", payment_terms: item.payment_terms || "", service_content: item.service_content || "",
    kingdee_code: item.kingdee_code, external_id: item.external_id, notes: item.notes,
  } : {
    contract_no: "", name: "", contract_type: "", supplier: "", office: "", category: "", department: "", owner: "",
    status: "draft", start_date: "", end_date: "", amount: "", amount_description: "", renewal_notice_days: 30,
    auto_renew: false, payment_method: "", payment_terms: "", service_content: "", kingdee_code: "", external_id: "", notes: "",
  });
}

function openForm(item?: Contract) {
  formMode.value = item ? "edit" : "create";
  editing.value = item || null;
  renewingFrom.value = null;
  assignForm(item);
  formError.value = "";
  showForm.value = true;
}

function openRenew(item: Contract) {
  formMode.value = "renew";
  editing.value = null;
  renewingFrom.value = item;
  assignForm(item);
  Object.assign(form, { contract_no: "", status: "active", start_date: "", end_date: "", kingdee_code: "", external_id: "" });
  formError.value = "";
  showForm.value = true;
}

async function saveContract() {
  formError.value = "";
  const { owner, ...formFields } = form;
  const payload = {
    ...formFields,
    contract_type: form.contract_type ? Number(form.contract_type) : null,
    supplier: form.supplier ? Number(form.supplier) : null,
    office: form.office ? Number(form.office) : null,
    category: form.category ? Number(form.category) : null,
    department: form.department ? Number(form.department) : null,
    ...(props.isSuperuser ? { owner: owner ? Number(owner) : null } : {}),
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
    formError.value = errorText(err, "合同未保存。");
  }
}

function openChange(item: Contract) {
  changeContract.value = item;
  changeError.value = "";
  Object.assign(changeForm, {
    change_type: "extension", changed_on: new Date().toISOString().slice(0, 10),
    new_start_date: "", new_end_date: "", new_amount: "", notes: "",
  });
}

async function saveChange() {
  if (!changeContract.value) return;
  changeError.value = "";
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
    changeError.value = errorText(err, "合同变更未保存。");
  }
}

async function deleteContract(item: Contract) {
  const supplementCount = item.supplement_contracts.length;
  const hint = supplementCount ? `该合同还有 ${supplementCount} 份附属补充协议合同，将一并删除。` : "";
  if (!window.confirm(`确认删除合同“${item.name}（${item.contract_no}）”？${hint}删除后无法恢复。`)) return;
  try {
    await api(`/contracts/${item.id}/`, { method: "DELETE" });
    await load();
  } catch (err) {
    error.value = errorText(err, "合同删除失败。");
  }
}

function openFiles(item: Contract) {
  selectedContract.value = item;
  documentType.value = "signed";
  fileChange.value = "";
  fileError.value = "";
}

async function openHistory(item: Contract) {
  historyContract.value = item;
  historyRecords.value = [];
  historyLoading.value = true;
  historyError.value = "";
  try {
    historyRecords.value = await api<Contract[]>(`/contracts/${item.id}/history/`);
    historyIndex.value = Math.max(0, historyRecords.value.length - 1);
  } catch (err) {
    historyError.value = err instanceof ApiError ? err.message : "合同历史暂时无法加载。";
  } finally {
    historyLoading.value = false;
  }
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
      <div><p class="eyebrow">合同履约台账</p><h1>合同、周期和历次变更</h1></div>
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
      <button v-if="filters.q || filters.contract_type || filters.status || dueOnly" class="text-button" type="button" @click="clearFilters">{{ dueOnly ? '显示全部合同' : '清除条件' }}</button>
    </form>

    <div v-if="error" class="error-block">{{ error }}</div>
    <section class="contract-ledger-shell" :class="{ loading }">
      <table class="contract-ledger">
        <thead><tr><th>合同与相对方</th><th>履约期间与状态</th><th>金额与科目</th><th>负责人</th><th>档案</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="item in rows" :key="item.id" :class="{ due: due.includes(item), expired: item.status === 'expired' }">
            <td data-label="合同与相对方"><div class="contract-title-line"><strong>{{ item.name }}</strong><span>{{ item.contract_type_name || '未分类' }}</span></div><small>{{ item.contract_no }} · {{ item.supplier_name || item.office_name || '未设置相对方' }}</small><span v-if="item.office_name" class="lineage-tag">关联 {{ item.office_name }}</span><span v-if="item.previous_contract_no" class="lineage-tag">续自 {{ item.previous_contract_no }}</span><span v-else-if="item.renewal_contracts.length" class="lineage-tag">已续签 {{ item.renewal_contracts[0].contract_no }}</span><span v-else-if="item.supplement_contracts.length" class="lineage-tag">含 {{ item.supplement_contracts.length }} 份补充协议</span></td>
            <td data-label="履约期间与状态"><strong>{{ item.start_date || '—' }} → {{ item.end_date || '—' }}</strong><div class="contract-status-line"><span class="record-status" :data-status="item.status">{{ item.status_label }}</span><small :class="{ 'due-copy': due.includes(item) }">{{ dueText(item) }}</small></div></td>
            <td data-label="金额与科目"><strong>{{ item.amount_description || money(item.total_amount) }}</strong><small>{{ item.category_name || '未设置费用类别' }}</small></td>
            <td data-label="负责人"><strong>{{ item.owner_name || '未设置' }}</strong><small>{{ item.department_name || '未设置部门' }}</small></td>
            <td data-label="档案"><strong>{{ item.attachments.length }} 个文件</strong><small>{{ item.changes.length }} 次变更 · {{ item.auto_renew ? '约定续期' : '人工处理' }}</small></td>
            <td class="contract-row-actions"><button class="contract-edit-button" @click="openForm(item)">编辑</button><button class="contract-action-button" @click="openFiles(item)">文件</button><button class="contract-action-button" @click="openHistory(item)">历史</button><button v-if="!item.supplement_of && !item.renewal_contracts.length && !['terminated'].includes(item.status)" class="contract-action-button" @click="openRenew(item)">续签</button><button v-if="!item.supplement_of && !['completed','terminated'].includes(item.status)" class="contract-action-button" @click="openChange(item)">变更</button><button v-if="props.isSuperuser" class="contract-action-button danger" @click="deleteContract(item)">删除</button></td>
          </tr>
        </tbody>
      </table>
      <div v-if="!rows.length && !loading" class="empty-state large">没有符合条件的合同。可以调整搜索条件或登记新合同。</div>
    </section>

    <div v-if="showForm" class="modal-backdrop" @click.self="showForm = false">
      <form class="modal-panel admin-form-modal contract-form-modal" @submit.prevent="saveContract">
        <header><div><p class="eyebrow">{{ formMode === 'renew' ? `续签自 ${renewingFrom?.contract_no}` : '合同台账' }}</p><h2>{{ formMode === 'edit' ? '编辑合同基础资料' : formMode === 'renew' ? '建立下一期合同' : '登记行政合同' }}</h2></div><button type="button" class="icon-button" @click="showForm = false">×</button></header>
        <div class="contract-form-body">
          <p v-if="formError" class="form-error">{{ formError }}</p>
          <p v-if="formMode === 'edit'" class="modal-guidance">这里可以直接修正合同资料；需要保留调整前后记录时，仍可使用“登记变更”。</p>
          <section class="contract-form-section">
            <header><div><strong>基础资料</strong><span>合同身份、分类和经办信息</span></div></header>
            <div class="contract-form-grid">
              <label><span>合同编号</span><input v-model="form.contract_no" required /></label>
              <label><span>合同名称</span><input v-model="form.name" required /></label>
              <label><span>合同类型</span><select v-model="form.contract_type"><option value="">未分类</option><option v-for="item in contractTypes.filter((x) => x.is_active)" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
              <label><span>供应商</span><select v-model="form.supplier"><option value="">未设置</option><option v-for="item in suppliers" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
              <label><span>关联办事处</span><select v-model="form.office"><option value="">未关联</option><option v-for="item in offices" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label>
              <label><span>费用类别</span><select v-model="form.category"><option value="">未设置</option><option v-for="item in categories" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
              <label><span>归属部门</span><select v-model="form.department"><option value="">未设置</option><option v-for="item in lookups?.departments || []" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
              <label v-if="props.isSuperuser"><span>负责人</span><PersonSearchSelect v-model="form.owner" :users="lookups?.users || []" /></label>
              <label v-else><span>负责人</span><input :value="editing?.owner_name || renewingFrom?.owner_name || '当前管理员（自动）'" disabled /><small>普通管理员登记的合同自动归本人负责</small></label>
              <label><span>状态</span><select v-model="form.status"><option value="draft">草稿</option><option value="active">履行中</option><option value="expired">已到期未处理</option><option value="completed">已完成</option><option value="terminated">已终止</option></select></label>
            </div>
          </section>
          <section class="contract-form-section">
            <header><div><strong>履约与金额</strong><span>合同有效期、金额和到期处理方式</span></div></header>
            <div class="contract-form-grid contract-term-grid">
              <label><span>开始日期</span><input v-model="form.start_date" type="date" /></label>
              <label><span>结束日期</span><input v-model="form.end_date" type="date" /></label>
              <label><span>合同金额</span><input v-model="form.amount" type="number" min="0" step="0.01" required /></label>
              <label class="wide"><span>费用金额说明</span><input v-model="form.amount_description" placeholder="例如：按实际结算、3500 元/月" /></label>
              <label><span>到期提前提醒</span><span class="contract-input-suffix"><input v-model.number="form.renewal_notice_days" type="number" min="1" /><b>天</b></span></label>
              <label class="contract-renew-toggle"><input v-model="form.auto_renew" type="checkbox" /><span><strong>合同约定自动续期</strong></span></label>
            </div>
          </section>
          <section class="contract-form-section">
            <header><div><strong>对接信息</strong><span>财务及预算系统编码</span></div></header>
            <div class="contract-form-grid">
              <label><span>金蝶编码</span><input v-model="form.kingdee_code" /></label>
              <label><span>预算系统标识</span><input v-model="form.external_id" /></label>
              <label><span>付款方式</span><input v-model="form.payment_method" /></label>
              <label class="wide"><span>付款要求</span><textarea v-model="form.payment_terms"></textarea></label>
              <label class="wide"><span>服务内容</span><textarea v-model="form.service_content"></textarea></label>
              <label class="wide"><span>备注</span><textarea v-model="form.notes"></textarea></label>
            </div>
          </section>
        </div>
        <footer class="contract-form-footer"><button type="button" class="secondary-button" @click="showForm = false">取消</button><button class="primary-button">{{ formMode === 'renew' ? '建立续签合同' : '保存合同' }}</button></footer>
      </form>
    </div>

    <div v-if="changeContract" class="modal-backdrop" @click.self="changeContract = null">
      <form class="modal-panel admin-form-modal contract-change-modal" @submit.prevent="saveChange">
        <header><div><p class="eyebrow">{{ changeContract.contract_no }}</p><h2>登记合同变更</h2></div><button type="button" class="icon-button" @click="changeContract = null">×</button></header>
        <p class="modal-guidance">{{ changeForm.change_type === 'supplement' ? '补充协议将登记为附属合同，合同列表会自动把本次补充金额合计到母合同金额。' : '保存后会更新当前有效值，同时永久保留原期限、原金额和本次说明。' }}</p>
        <p v-if="changeError" class="form-error change-form-error">{{ changeError }}</p>
        <div class="form-grid">
          <label><span>变更类型</span><select v-model="changeForm.change_type"><option value="extension">延期续约</option><option value="supplement">补充协议</option><option value="amount">金额调整</option><option value="termination">提前终止</option><option value="other">其他变更</option></select></label>
          <label><span>生效日期</span><input v-model="changeForm.changed_on" type="date" required /></label>
          <template v-if="changeForm.change_type === 'supplement'">
            <label><span>补充开始日期</span><input v-model="changeForm.new_start_date" type="date" required /></label>
            <label><span>补充结束日期</span><input v-model="changeForm.new_end_date" type="date" required /></label>
            <label><span>补充金额</span><input v-model="changeForm.new_amount" type="number" min="0" step="0.01" required /></label>
          </template>
          <template v-else>
            <label><span>新开始日期</span><input v-model="changeForm.new_start_date" type="date" /></label>
            <label><span>新结束日期</span><input v-model="changeForm.new_end_date" type="date" :required="changeForm.change_type === 'extension'" /></label>
            <label><span>新合同金额</span><input v-model="changeForm.new_amount" type="number" min="0" step="0.01" :required="changeForm.change_type === 'amount'" /></label>
          </template>
          <label class="wide"><span>变更说明</span><textarea v-model="changeForm.notes" required :placeholder="changeForm.change_type === 'supplement' ? '说明补充协议的具体约定' : '说明延期、调价、终止或补充约定的原因'"></textarea></label>
        </div>
        <p v-if="changeForm.change_type === 'supplement'" class="modal-guidance supplement-hint">将自动生成附属合同编号 {{ changeContract.contract_no }}-S…，名称沿用母合同，登记后可在列表中查看。</p>
        <button class="primary-button full">保存变更记录</button>
      </form>
    </div>

    <div v-if="historyContract" class="modal-backdrop" @click.self="historyContract = null">
      <section class="modal-panel contract-history-modal">
        <header class="modal-header"><div><p class="eyebrow">合同历史</p><h2>{{ historyContract.name }}</h2></div><button type="button" class="icon-button" @click="historyContract = null">×</button></header>
        <div v-if="historyLoading" class="history-loading">正在读取合同历史…</div>
        <div v-else-if="historyError" class="error-block history-error">{{ historyError }}</div>
        <div v-else class="history-workbench">
          <aside class="history-periods">
            <div class="history-periods-title"><strong>合同期次</strong><span>共 {{ historyRecords.length }} 期</span></div>
            <button v-for="(record, index) in historyRecords" :key="record.id" :class="{ active: historyIndex === index }" @click="historyIndex = index">
              <i>{{ String(index + 1).padStart(2, '0') }}</i>
              <span><strong>{{ record.contract_no }}</strong><small>{{ record.start_date || '未设置' }} 至 {{ record.end_date || '未设置' }}</small></span>
              <b v-if="index === historyRecords.length - 1">当前</b>
            </button>
          </aside>
          <section v-if="activeHistory" class="history-detail">
            <header class="history-contract-head"><div><span class="record-status" :data-status="activeHistory.status">{{ activeHistory.status_label }}</span><h3>{{ activeHistory.name }}</h3><p>{{ activeHistory.contract_no }}</p></div><strong>{{ money(activeHistory.total_amount) }}</strong></header>
            <dl class="history-facts">
              <div><dt>合同类型</dt><dd>{{ activeHistory.contract_type_name || '未分类' }}</dd></div>
              <div><dt>供应商</dt><dd>{{ activeHistory.supplier_name || '未设置' }}</dd></div>
              <div><dt>关联办事处</dt><dd>{{ activeHistory.office_name || '未关联' }}</dd></div>
              <div><dt>履约期间</dt><dd>{{ activeHistory.start_date || '—' }} 至 {{ activeHistory.end_date || '—' }}</dd></div>
              <div><dt>费用类别</dt><dd>{{ activeHistory.category_name || '未设置' }}</dd></div>
              <div><dt>负责人</dt><dd>{{ activeHistory.owner_name || '未设置' }}</dd></div>
              <div><dt>归属部门</dt><dd>{{ activeHistory.department_name || '未设置' }}</dd></div>
              <div><dt>金蝶编码</dt><dd>{{ activeHistory.kingdee_code || '未设置' }}</dd></div>
              <div><dt>到期处理</dt><dd>{{ activeHistory.auto_renew ? '合同约定自动续期' : '到期人工处理' }}</dd></div>
            </dl>
            <p v-if="activeHistory.amount_description || activeHistory.payment_method || activeHistory.payment_terms || activeHistory.service_content" class="history-notes"><strong>履约与结算</strong><span v-if="activeHistory.amount_description">费用：{{ activeHistory.amount_description }}</span><span v-if="activeHistory.payment_method">付款方式：{{ activeHistory.payment_method }}</span><span v-if="activeHistory.payment_terms">付款要求：{{ activeHistory.payment_terms }}</span><span v-if="activeHistory.service_content">服务内容：{{ activeHistory.service_content }}</span></p>
            <p v-if="activeHistory.notes" class="history-notes"><strong>合同备注</strong>{{ activeHistory.notes }}</p>
            <section class="history-section"><header><div><strong>变更记录</strong><span>延期、调价、补充协议与终止记录</span></div><b>{{ activeHistory.changes.length }}</b></header><div v-if="activeHistory.changes.length" class="history-change-list"><article v-for="change in activeHistory.changes" :key="change.id"><div><strong>{{ change.change_type_label }}</strong><time>{{ change.changed_on }}</time></div><p>{{ change.notes }}</p><small v-if="change.change_type === 'supplement'">补充金额：{{ money(change.new_amount || 0) }} · 补充期间：{{ change.new_start_date || '—' }} 至 {{ change.new_end_date || '—' }}</small><small v-else-if="change.new_end_date">结束日期：{{ change.old_end_date || '—' }} → {{ change.new_end_date }}</small><small v-else-if="change.new_amount">合同金额：{{ money(change.old_amount || 0) }} → {{ money(change.new_amount) }}</small></article></div><p v-else class="history-compact-empty">本期合同没有变更记录。</p></section>
            <section v-if="activeHistory.supplement_contracts.length" class="history-section"><header><div><strong>附属合同</strong><span>登记于本合同的补充协议</span></div><b>{{ activeHistory.supplement_contracts.length }}</b></header><div class="history-change-list"><article v-for="item in activeHistory.supplement_contracts" :key="item.id"><div><strong>{{ item.contract_no }}</strong><time>{{ item.start_date || '—' }} 至 {{ item.end_date || '—' }}</time></div><p>{{ item.name }}</p><small>补充金额：{{ money(item.amount) }} · {{ item.status_label }}</small></article></div></section>
            <section class="history-section"><header><div><strong>合同文件</strong><span>原件、扫描件与本期补充文件</span></div><b>{{ activeHistory.attachments.length }}</b></header><div v-if="activeHistory.attachments.length" class="history-file-list"><button v-for="file in activeHistory.attachments" :key="file.id" @click="downloadFile(file)"><span class="file-kind">{{ file.original_name.split('.').pop()?.slice(0, 4).toUpperCase() }}</span><span><strong>{{ file.original_name }}</strong><small>{{ file.change_label }} · {{ fileSize(file.size_bytes) }}</small></span><AppIcon name="download" :size="16" /></button></div><p v-else class="history-compact-empty">本期合同没有归档文件。</p></section>
          </section>
        </div>
      </section>
    </div>

    <div v-if="selectedContract" class="modal-backdrop" @click.self="selectedContract = null">
      <section class="modal-panel file-vault-modal">
        <header><div><p class="eyebrow">合同文件 · {{ selectedContract.contract_no }}</p><h2>{{ selectedContract.name }}</h2></div><button type="button" class="icon-button" @click="selectedContract = null">×</button></header>
        <div class="contract-upload-desk contract-upload-versioned">
          <label><span>归档位置</span><select v-model="fileChange"><option value="">初始合同</option><option v-for="change in [...selectedContract.changes].reverse()" :key="change.id" :value="change.id">{{ change.changed_on }} · {{ change.change_type_label }}</option></select></label>
          <label><span>文件类别</span><select v-model="documentType"><option value="signed">盖章扫描件</option><option value="invoice">发票</option><option value="other">其他</option></select></label>
          <label class="primary-button contract-file-picker"><AppIcon name="upload" :size="18" />{{ fileUploading ? '正在上传…' : '选择合同文件' }}<input type="file" multiple :disabled="fileUploading" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.webp,.zip,.rar,.7z,.ofd,.wps" @change="uploadFiles" /></label>
        </div>
        <p v-if="fileError" class="form-error file-vault-error">{{ fileError }}</p>
        <div v-if="selectedContract.attachments.length" class="contract-file-groups">
          <section v-for="group in attachmentGroups" :key="group.key"><header><strong>{{ group.label }}</strong><span>{{ group.files.length }} 个文件</span></header><div class="contract-file-list"><article v-for="file in group.files" :key="file.id"><span class="file-kind">{{ file.original_name.split('.').pop()?.slice(0, 4).toUpperCase() }}</span><div><strong>{{ file.original_name }}</strong><small>{{ file.document_type_label }} · {{ fileSize(file.size_bytes) }} · {{ file.uploaded_by_name }}</small></div><button class="secondary-button" @click="downloadFile(file)"><AppIcon name="download" :size="16" />下载</button><button class="text-button danger" @click="deleteFile(file)">删除</button></article></div></section>
        </div>
        <div v-else class="file-vault-empty"><strong>还没有合同文件</strong></div>
      </section>
    </div>
  </div>
</template>
