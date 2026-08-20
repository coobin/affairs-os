<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { api, ApiError } from "../api";
import AppIcon from "../components/AppIcon.vue";

defineProps<{ isSuperuser: boolean }>();

type OfficeContract = {
  id: number;
  contract_no?: string;
  name?: string;
  contract_type_name?: string;
  status?: string;
  status_label?: string;
  start_date?: string | null;
  end_date?: string | null;
  amount?: string | number | null;
  owner_name?: string;
};

type OfficeRecord = {
  id: number;
  code: string;
  name: string;
  status: string;
  status_label?: string;
  region: string;
  city: string;
  address: string;
  room_layout: string;
  area_sqm: string | number | null;
  responsible_name: string;
  responsible_phone: string;
  residents: string;
  resident_count: number | null;
  monthly_rent: string | number | null;
  rent_description: string;
  deposit: string | number | null;
  payment_frequency: string;
  payment_method: string;
  payment_terms: string;
  next_payment_date: string | null;
  latest_payment_amount: string | number | null;
  lease_start: string | null;
  lease_end: string | null;
  expected_move_out_date: string | null;
  renewal_status: string;
  sales_project: string;
  cost_attribution: string;
  feedback: string;
  notes: string;
  contracts: OfficeContract[];
};

type ListPayload<T> = T[] | { results: T[] };

const rows = ref<OfficeRecord[]>([]);
const loading = ref(false);
const error = ref("");
const formError = ref("");
const showForm = ref(false);
const editing = ref<OfficeRecord | null>(null);
const selectedOffice = ref<OfficeRecord | null>(null);
const detailLoading = ref(false);
const detailError = ref("");
const filters = reactive({ q: "", status: "", region: "", city: "", attention: "" });

const form = reactive({
  code: "",
  name: "",
  status: "active",
  region: "",
  city: "",
  address: "",
  room_layout: "",
  area_sqm: "",
  responsible_name: "",
  responsible_phone: "",
  residents: "",
  resident_count: "",
  monthly_rent: "",
  rent_description: "",
  deposit: "",
  payment_frequency: "",
  payment_method: "",
  payment_terms: "",
  next_payment_date: "",
  latest_payment_amount: "",
  lease_start: "",
  lease_end: "",
  expected_move_out_date: "",
  renewal_status: "",
  sales_project: "",
  cost_attribution: "",
  feedback: "",
  notes: "",
});

const statusNames: Record<string, string> = {
  active: "使用中",
  planned: "筹备中",
  inactive: "暂停使用",
  closed: "已关闭",
};

const regionOptions = computed(() => uniqueValues("region"));
const cityOptions = computed(() => uniqueValues("city", filters.region));
const filteredRows = computed(() => {
  const keyword = filters.q.trim().toLocaleLowerCase("zh-CN");
  return rows.value.filter((item) => {
    const searchable = [
      item.code, item.name, item.region, item.city, item.address, item.room_layout,
      item.responsible_name, item.responsible_phone, item.residents, item.sales_project,
      item.cost_attribution, item.renewal_status,
    ].filter(Boolean).join(" ").toLocaleLowerCase("zh-CN");
    if (keyword && !searchable.includes(keyword)) return false;
    if (filters.status && item.status !== filters.status) return false;
    if (filters.region && item.region !== filters.region) return false;
    if (filters.city && item.city !== filters.city) return false;
    if (filters.attention === "lease" && !isLeaseAttention(item)) return false;
    if (filters.attention === "payment" && !isPaymentAttention(item)) return false;
    if (filters.attention === "move_out" && !item.expected_move_out_date) return false;
    return true;
  });
});
const activeCount = computed(() => rows.value.filter((item) => item.status === "active").length);
const leaseAttentionCount = computed(() => rows.value.filter(isLeaseAttention).length);
const paymentAttentionCount = computed(() => rows.value.filter(isPaymentAttention).length);

function unwrap<T>(value: ListPayload<T>) {
  return Array.isArray(value) ? value : value.results;
}

function uniqueValues(key: "region" | "city", region = "") {
  const values = rows.value
    .filter((item) => !region || item.region === region)
    .map((item) => item[key]?.trim())
    .filter(Boolean) as string[];
  return [...new Set(values)].sort((a, b) => a.localeCompare(b, "zh-CN"));
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
    const payload = await api<ListPayload<OfficeRecord>>("/offices/");
    rows.value = unwrap(payload).map((item) => ({ ...item, contracts: item.contracts || [] }));
  } catch (err) {
    error.value = errorText(err, "办事处台账暂时无法加载。");
  } finally {
    loading.value = false;
  }
}

function clearFilters() {
  Object.assign(filters, { q: "", status: "", region: "", city: "", attention: "" });
}

function openNew() {
  editing.value = null;
  Object.assign(form, {
    code: "", name: "", status: "active", region: "", city: "", address: "",
    room_layout: "", area_sqm: "", responsible_name: "", responsible_phone: "",
    residents: "", resident_count: "", monthly_rent: "", rent_description: "",
    deposit: "", payment_frequency: "", payment_method: "", payment_terms: "",
    next_payment_date: "", latest_payment_amount: "", lease_start: "", lease_end: "",
    expected_move_out_date: "", renewal_status: "", sales_project: "",
    cost_attribution: "", feedback: "", notes: "",
  });
  formError.value = "";
  showForm.value = true;
}

function openEdit(item: OfficeRecord) {
  editing.value = item;
  Object.assign(form, {
    code: item.code || "", name: item.name || "", status: item.status || "active",
    region: item.region || "", city: item.city || "", address: item.address || "",
    room_layout: item.room_layout || "", area_sqm: valueText(item.area_sqm),
    responsible_name: item.responsible_name || "", responsible_phone: item.responsible_phone || "",
    residents: item.residents || "", resident_count: valueText(item.resident_count),
    monthly_rent: valueText(item.monthly_rent), rent_description: item.rent_description || "",
    deposit: valueText(item.deposit), payment_frequency: item.payment_frequency || "",
    payment_method: item.payment_method || "", payment_terms: item.payment_terms || "",
    next_payment_date: item.next_payment_date || "", latest_payment_amount: valueText(item.latest_payment_amount),
    lease_start: item.lease_start || "", lease_end: item.lease_end || "",
    expected_move_out_date: item.expected_move_out_date || "", renewal_status: item.renewal_status || "",
    sales_project: item.sales_project || "", cost_attribution: item.cost_attribution || "",
    feedback: item.feedback || "", notes: item.notes || "",
  });
  formError.value = "";
  showForm.value = true;
}

function nullableNumber(value: string) {
  return value === "" ? null : Number(value);
}

function officePayload() {
  return {
    ...form,
    code: form.code.trim(),
    name: form.name.trim(),
    region: form.region.trim(),
    city: form.city.trim(),
    address: form.address.trim(),
    area_sqm: nullableNumber(form.area_sqm),
    resident_count: nullableNumber(form.resident_count),
    monthly_rent: nullableNumber(form.monthly_rent),
    deposit: nullableNumber(form.deposit),
    latest_payment_amount: nullableNumber(form.latest_payment_amount),
    next_payment_date: form.next_payment_date || null,
    lease_start: form.lease_start || null,
    lease_end: form.lease_end || null,
    expected_move_out_date: form.expected_move_out_date || null,
  };
}

async function saveOffice() {
  formError.value = "";
  try {
    if (editing.value) {
      await api(`/offices/${editing.value.id}/`, { method: "PATCH", body: JSON.stringify(officePayload()) });
    } else {
      await api("/offices/", { method: "POST", body: JSON.stringify(officePayload()) });
    }
    showForm.value = false;
    await load();
  } catch (err) {
    formError.value = errorText(err, "办事处资料未保存。");
  }
}

async function deleteOffice(item: OfficeRecord) {
  if (!window.confirm(`确认删除“${item.name}”？关联合同不会因此删除。`)) return;
  try {
    await api(`/offices/${item.id}/`, { method: "DELETE" });
    await load();
  } catch (err) {
    error.value = errorText(err, "办事处删除失败。");
  }
}

async function openDetail(item: OfficeRecord) {
  selectedOffice.value = item;
  detailLoading.value = true;
  detailError.value = "";
  try {
    const detail = await api<OfficeRecord>(`/offices/${item.id}/`);
    selectedOffice.value = { ...detail, contracts: detail.contracts || [] };
  } catch (err) {
    detailError.value = errorText(err, "办事处详情暂时无法加载。");
  } finally {
    detailLoading.value = false;
  }
}

function daysUntil(value: string | null) {
  if (!value) return null;
  const target = new Date(`${value}T00:00:00`).getTime();
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target - today.getTime()) / 86_400_000);
}

function isLeaseAttention(item: OfficeRecord) {
  const days = daysUntil(item.expected_move_out_date || item.lease_end);
  return item.status === "active" && days !== null && days <= 90;
}

function isPaymentAttention(item: OfficeRecord) {
  const days = daysUntil(item.next_payment_date);
  return item.status === "active" && days !== null && days <= 30;
}

function leaseText(item: OfficeRecord) {
  const end = item.expected_move_out_date || item.lease_end;
  const days = daysUntil(end);
  if (!end || days === null) return "未设置到期日";
  if (days < 0) return `${item.expected_move_out_date ? "预计退租" : "合同"}已过 ${-days} 天`;
  if (days === 0) return `${item.expected_move_out_date ? "预计退租" : "合同"}今天到期`;
  return `距${item.expected_move_out_date ? "预计退租" : "合同到期"} ${days} 天`;
}

function statusText(item: OfficeRecord) {
  return item.status_label || statusNames[item.status] || item.status || "未设置";
}

function money(value: string | number | null) {
  if (value === null || value === "") return "未设置";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return String(value);
  return `¥${amount.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function valueText(value: string | number | null) {
  return value === null || value === undefined ? "" : String(value);
}

function dateSpan(start?: string | null, end?: string | null) {
  if (!start && !end) return "未设置履约期间";
  return `${start || "—"} 至 ${end || "—"}`;
}

onMounted(load);
</script>

<template>
  <div class="page module-page admin-module-page office-register-page">
    <header class="page-intro office-intro">
      <div>
        <p class="eyebrow">办事处 · 场地与租约</p>
        <h1>地点独立管理，合同保留关联</h1>
        <p>一个地点可以持续使用并关联历次租赁合同，现场信息不随续签被覆盖。</p>
      </div>
      <button class="primary-button" @click="openNew"><AppIcon name="plus" :size="18" />登记办事处</button>
    </header>

    <section class="admin-kpi-strip office-kpis" aria-label="办事处概览">
      <div><span>登记地点</span><strong>{{ rows.length }}</strong></div>
      <div><span>使用中</span><strong>{{ activeCount }}</strong></div>
      <div><span>90 天内到期或退租</span><strong>{{ leaseAttentionCount }}</strong></div>
      <div><span>30 天内付款</span><strong>{{ paymentAttentionCount }}</strong></div>
    </section>

    <section class="office-filter-bar" aria-label="筛选办事处">
      <label class="office-search">
        <AppIcon name="search" :size="18" />
        <span class="sr-only">搜索办事处</span>
        <input v-model="filters.q" placeholder="搜索名称、城市、地址、负责人或项目" />
      </label>
      <select v-model="filters.status" aria-label="状态"><option value="">全部状态</option><option value="active">使用中</option><option value="planned">筹备中</option><option value="inactive">暂停使用</option><option value="closed">已关闭</option></select>
      <select v-model="filters.region" aria-label="区域" @change="filters.city = ''"><option value="">全部区域</option><option v-for="item in regionOptions" :key="item" :value="item">{{ item }}</option></select>
      <select v-model="filters.city" aria-label="城市"><option value="">全部城市</option><option v-for="item in cityOptions" :key="item" :value="item">{{ item }}</option></select>
      <select v-model="filters.attention" aria-label="待关注事项"><option value="">全部事项</option><option value="lease">租约到期 / 退租</option><option value="payment">近期付款</option><option value="move_out">已有退租计划</option></select>
      <button v-if="Object.values(filters).some(Boolean)" class="text-button" @click="clearFilters">清除条件</button>
      <span class="office-result-count">{{ filteredRows.length }} 个地点</span>
    </section>

    <div v-if="error" class="error-block">{{ error }}</div>
    <div v-else-if="loading" class="loading-block">正在读取办事处和租约信息…</div>
    <section v-else-if="filteredRows.length" class="office-site-grid">
      <article v-for="item in filteredRows" :key="item.id" class="office-site-card" :class="{ attention: isLeaseAttention(item), muted: ['inactive', 'closed'].includes(item.status) }">
        <header>
          <span class="office-code">{{ item.code }}</span>
          <span class="office-status" :data-status="item.status">{{ statusText(item) }}</span>
        </header>
        <div class="office-location-head">
          <span>{{ item.region || "未设置区域" }} · {{ item.city || "未设置城市" }}</span>
          <h2>{{ item.name }}</h2>
          <p><AppIcon name="map" :size="15" />{{ item.address || "未设置详细地址" }}</p>
        </div>
        <dl class="office-facts">
          <div><dt>房型 / 面积</dt><dd>{{ item.room_layout || "—" }}<small>{{ item.area_sqm ? `${item.area_sqm} ㎡` : "面积未设置" }}</small></dd></div>
          <div><dt>现场负责人</dt><dd>{{ item.responsible_name || "未设置" }}<small>{{ item.responsible_phone || "未设置电话" }}</small></dd></div>
          <div><dt>居住人员</dt><dd>{{ item.resident_count === null ? "人数待核对" : `${item.resident_count} 人` }}<small>{{ item.residents || "未登记名单" }}</small></dd></div>
          <div><dt>当前月租</dt><dd>{{ money(item.monthly_rent) }}<small>{{ item.payment_frequency || "未设置付款频率" }}</small></dd></div>
        </dl>
        <div class="lease-ribbon" :class="{ due: isLeaseAttention(item) }">
          <div><span>{{ item.lease_start || "未设置开始日" }}</span><i></i><span>{{ item.lease_end || "未设置到期日" }}</span></div>
          <strong>{{ leaseText(item) }}</strong>
          <small v-if="item.expected_move_out_date">预计退租 {{ item.expected_move_out_date }}</small>
        </div>
        <footer>
          <button class="office-detail-button" @click="openDetail(item)"><span>地点档案与关联合同</span><AppIcon name="chevron-right" :size="16" /></button>
          <div><button class="text-button" @click="openEdit(item)">编辑</button><button v-if="isSuperuser" class="text-button danger" @click="deleteOffice(item)">删除</button></div>
        </footer>
      </article>
    </section>
    <div v-else class="empty-state large"><strong>没有符合条件的办事处</strong><p>可以清除筛选条件，或登记新的办公与住宿地点。</p><button class="primary-button" @click="openNew">登记办事处</button></div>

    <div v-if="showForm" class="modal-backdrop" @click.self="showForm = false">
      <form class="modal-panel admin-form-modal office-form-modal" @submit.prevent="saveOffice">
        <header>
          <div><p class="eyebrow">办事处档案</p><h2>{{ editing ? "编辑地点与租赁信息" : "登记办事处" }}</h2></div>
          <button type="button" class="icon-button" aria-label="关闭" @click="showForm = false"><AppIcon name="close" /></button>
        </header>
        <div class="office-form-body">
          <p v-if="formError" class="form-error office-form-error">{{ formError }}</p>
          <section class="office-form-section">
            <header><strong>地点资料</strong><span>用于识别长期使用的办公或住宿地点</span></header>
            <div class="office-form-grid">
              <label><span>办事处编码</span><input v-model="form.code" required placeholder="例如 OFFICE-HZ-01" /></label>
              <label><span>办事处名称</span><input v-model="form.name" required /></label>
              <label><span>状态</span><select v-model="form.status"><option value="active">使用中</option><option value="planned">筹备中</option><option value="inactive">暂停使用</option><option value="closed">已关闭</option></select></label>
              <label><span>所属区域</span><input v-model="form.region" list="office-region-options" /></label>
              <label><span>城市</span><input v-model="form.city" required list="office-city-options" /></label>
              <label><span>房型</span><input v-model="form.room_layout" placeholder="例如 三室二厅" /></label>
              <label><span>面积（㎡）</span><input v-model="form.area_sqm" type="number" min="0" step="0.01" /></label>
              <label class="wide"><span>详细地址</span><input v-model="form.address" required /></label>
            </div>
          </section>
          <section class="office-form-section">
            <header><strong>现场负责与居住人员</strong><span>现场联系人独立于系统合同管理员</span></header>
            <div class="office-form-grid">
              <label><span>现场负责人</span><input v-model="form.responsible_name" /></label>
              <label><span>负责人电话</span><input v-model="form.responsible_phone" inputmode="tel" /></label>
              <label><span>居住人数</span><input v-model="form.resident_count" type="number" min="0" step="1" /></label>
              <label class="wide"><span>居住人员</span><textarea v-model="form.residents" placeholder="多人可用顿号分隔；流动人员可直接文字说明"></textarea></label>
            </div>
          </section>
          <section class="office-form-section">
            <header><strong>租赁与付款</strong><span>合同约定到期日与预计退租日期分别维护</span></header>
            <div class="office-form-grid">
              <label><span>本期开始日期</span><input v-model="form.lease_start" type="date" /></label>
              <label><span>合同约定到期日</span><input v-model="form.lease_end" type="date" /></label>
              <label><span>预计退租日期</span><input v-model="form.expected_move_out_date" type="date" /></label>
              <label><span>月租金</span><input v-model="form.monthly_rent" type="number" min="0" step="0.01" /></label>
              <label><span>押金</span><input v-model="form.deposit" type="number" min="0" step="0.01" /></label>
              <label><span>付款频率</span><input v-model="form.payment_frequency" placeholder="例如 季付、半年付" /></label>
              <label><span>付款方式</span><input v-model="form.payment_method" placeholder="例如 押一付三" /></label>
              <label><span>下次付款日期</span><input v-model="form.next_payment_date" type="date" /></label>
              <label><span>最近付款金额</span><input v-model="form.latest_payment_amount" type="number" min="0" step="0.01" /></label>
              <label class="wide"><span>租金说明</span><textarea v-model="form.rent_description" placeholder="分阶段调价、服务费或物业费等无法放入单一金额的约定"></textarea></label>
              <label class="wide"><span>付款要求</span><textarea v-model="form.payment_terms"></textarea></label>
              <label class="wide"><span>续租情况</span><textarea v-model="form.renewal_status"></textarea></label>
            </div>
          </section>
          <section class="office-form-section">
            <header><strong>项目归属与说明</strong><span>保留费用分摊和现场反馈口径</span></header>
            <div class="office-form-grid">
              <label class="wide"><span>销售项目归属</span><input v-model="form.sales_project" /></label>
              <label class="wide"><span>费用归属明细</span><textarea v-model="form.cost_attribution"></textarea></label>
              <label class="wide"><span>负责人反馈</span><textarea v-model="form.feedback"></textarea></label>
              <label class="wide"><span>备注</span><textarea v-model="form.notes"></textarea></label>
            </div>
          </section>
          <datalist id="office-region-options"><option v-for="item in regionOptions" :key="item" :value="item" /></datalist>
          <datalist id="office-city-options"><option v-for="item in cityOptions" :key="item" :value="item" /></datalist>
        </div>
        <footer class="office-form-footer"><button type="button" class="secondary-button" @click="showForm = false">取消</button><button class="primary-button">{{ editing ? "保存修改" : "保存办事处" }}</button></footer>
      </form>
    </div>

    <div v-if="selectedOffice" class="modal-backdrop" @click.self="selectedOffice = null">
      <section class="modal-panel office-detail-modal">
        <header class="modal-header office-detail-header">
          <div><p class="eyebrow">{{ selectedOffice.code }}</p><h2>{{ selectedOffice.name }}</h2><p>{{ selectedOffice.region }} · {{ selectedOffice.city }} · {{ statusText(selectedOffice) }}</p></div>
          <button type="button" class="icon-button" aria-label="关闭" @click="selectedOffice = null"><AppIcon name="close" /></button>
        </header>
        <div v-if="detailLoading" class="office-detail-loading">正在读取地点档案和可查看的合同…</div>
        <div v-else-if="detailError" class="error-block office-detail-error">{{ detailError }}</div>
        <div v-else class="office-detail-body">
          <aside class="office-address-plaque">
            <AppIcon name="map" :size="24" />
            <span>{{ selectedOffice.city || "未设置城市" }}</span>
            <strong>{{ selectedOffice.address || "未设置详细地址" }}</strong>
            <small>{{ selectedOffice.room_layout || "未设置房型" }}<template v-if="selectedOffice.area_sqm"> · {{ selectedOffice.area_sqm }} ㎡</template></small>
          </aside>
          <div class="office-detail-main">
            <section class="office-detail-section">
              <header><div><strong>现场信息</strong><span>负责人和当前居住情况</span></div></header>
              <dl>
                <div><dt>现场负责人</dt><dd>{{ selectedOffice.responsible_name || "未设置" }}</dd></div>
                <div><dt>联系电话</dt><dd>{{ selectedOffice.responsible_phone || "未设置" }}</dd></div>
                <div><dt>居住人数</dt><dd>{{ selectedOffice.resident_count === null ? "待核对" : `${selectedOffice.resident_count} 人` }}</dd></div>
                <div class="wide"><dt>居住人员</dt><dd>{{ selectedOffice.residents || "未登记" }}</dd></div>
              </dl>
            </section>
            <section class="office-detail-section">
              <header><div><strong>租赁与付款</strong><span>{{ leaseText(selectedOffice) }}</span></div></header>
              <dl>
                <div><dt>本期租赁</dt><dd>{{ dateSpan(selectedOffice.lease_start, selectedOffice.lease_end) }}</dd></div>
                <div><dt>预计退租</dt><dd>{{ selectedOffice.expected_move_out_date || "未设置" }}</dd></div>
                <div><dt>当前月租</dt><dd>{{ money(selectedOffice.monthly_rent) }}</dd></div>
                <div><dt>押金</dt><dd>{{ money(selectedOffice.deposit) }}</dd></div>
                <div><dt>付款安排</dt><dd>{{ [selectedOffice.payment_frequency, selectedOffice.payment_method].filter(Boolean).join(" · ") || "未设置" }}</dd></div>
                <div><dt>下次付款</dt><dd>{{ selectedOffice.next_payment_date || "未设置" }}<small v-if="selectedOffice.latest_payment_amount">最近付款 {{ money(selectedOffice.latest_payment_amount) }}</small></dd></div>
                <div v-if="selectedOffice.rent_description" class="wide"><dt>租金说明</dt><dd>{{ selectedOffice.rent_description }}</dd></div>
                <div v-if="selectedOffice.payment_terms" class="wide"><dt>付款要求</dt><dd>{{ selectedOffice.payment_terms }}</dd></div>
              </dl>
            </section>
            <section class="office-detail-section">
              <header><div><strong>项目与后续安排</strong><span>费用归属和现场反馈</span></div></header>
              <dl>
                <div><dt>销售项目</dt><dd>{{ selectedOffice.sales_project || "未设置" }}</dd></div>
                <div><dt>费用归属</dt><dd>{{ selectedOffice.cost_attribution || "未设置" }}</dd></div>
                <div class="wide"><dt>续租情况</dt><dd>{{ selectedOffice.renewal_status || "未记录" }}</dd></div>
                <div v-if="selectedOffice.feedback" class="wide"><dt>负责人反馈</dt><dd>{{ selectedOffice.feedback }}</dd></div>
                <div v-if="selectedOffice.notes" class="wide"><dt>备注</dt><dd>{{ selectedOffice.notes }}</dd></div>
              </dl>
            </section>
            <section class="office-contract-section">
              <header><div><strong>关联合同</strong><span>仅显示当前账号有权查看的接口结果</span></div><b>{{ selectedOffice.contracts.length }}</b></header>
              <div v-if="selectedOffice.contracts.length" class="office-contract-list">
                <article v-for="contract in selectedOffice.contracts" :key="contract.id">
                  <span class="contract-status" :data-status="contract.status">{{ contract.status_label || contract.status || "未设置状态" }}</span>
                  <div><strong>{{ contract.name || "未命名合同" }}</strong><small>{{ contract.contract_no || "未设置合同编号" }} · {{ contract.contract_type_name || "未分类" }}</small></div>
                  <div class="contract-period"><strong>{{ dateSpan(contract.start_date, contract.end_date) }}</strong><small>{{ contract.owner_name ? `负责人：${contract.owner_name}` : "负责人未设置" }}</small></div>
                </article>
              </div>
              <p v-else class="office-contract-empty">当前接口未返回可查看的关联合同。</p>
            </section>
          </div>
        </div>
        <footer class="office-detail-footer"><button class="secondary-button" @click="selectedOffice = null">关闭</button><button class="primary-button" @click="openEdit(selectedOffice); selectedOffice = null">编辑地点资料</button></footer>
      </section>
    </div>
  </div>
</template>

<style scoped>
.office-intro > div { max-width: 800px; }
.office-kpis { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.office-filter-bar {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 18px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.9);
}
.office-filter-bar select { min-height: 42px; padding: 0 32px 0 11px; border: 1px solid var(--line-dark); border-radius: 9px; color: var(--ink); background: #fff; }
.office-search { display: flex; min-width: 260px; flex: 1; align-items: center; gap: 9px; min-height: 42px; padding: 0 12px; color: var(--ink-soft); border: 1px solid var(--line-dark); border-radius: 9px; background: #fff; }
.office-search:focus-within { border-color: var(--blue); box-shadow: 0 0 0 3px rgba(25, 95, 164, 0.12); }
.office-search input { width: 100%; border: 0; background: transparent; color: var(--ink); }
.office-result-count { margin-left: auto; padding-right: 5px; color: var(--ink-soft); font-size: 12px; white-space: nowrap; }
.office-site-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.office-site-card { position: relative; display: flex; min-width: 0; flex-direction: column; overflow: hidden; border: 1px solid var(--line); border-radius: 17px; background: #fff; box-shadow: 0 8px 28px rgba(28, 49, 65, 0.045); transition: transform 150ms ease, border-color 150ms ease, box-shadow 150ms ease; }
.office-site-card::before { position: absolute; top: 0; bottom: 0; left: 0; width: 5px; background: var(--admin-teal); content: ""; }
.office-site-card.attention::before { background: var(--orange); }
.office-site-card:hover { border-color: #a9c5cb; transform: translateY(-2px); box-shadow: 0 16px 34px rgba(28, 49, 65, 0.08); }
.office-site-card.muted { background: #f8fafb; opacity: 0.84; }
.office-site-card > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 20px 0 24px; }
.office-code { color: var(--ink-soft); font: 700 12px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 0.05em; }
.office-status { padding: 5px 9px; border-radius: 999px; color: #176d7c; background: #e9f3f4; font-size: 11px; font-weight: 800; }
.office-status[data-status="planned"] { color: #8c5a00; background: #fff1d8; }
.office-status[data-status="inactive"], .office-status[data-status="closed"] { color: #6b7378; background: #edf0f2; }
.office-location-head { min-height: 145px; padding: 22px 20px 18px 24px; border-bottom: 1px solid var(--line); }
.office-location-head > span { color: var(--admin-teal); font-size: 12px; font-weight: 800; }
.office-location-head h2 { margin: 8px 0 8px; font-size: 21px; line-height: 1.32; }
.office-location-head p { display: flex; align-items: flex-start; gap: 6px; margin: 0; color: var(--ink-soft); font-size: 12px; line-height: 1.55; }
.office-location-head p svg { flex: 0 0 auto; margin-top: 2px; }
.office-facts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 0; padding: 18px 20px 18px 24px; }
.office-facts div { min-width: 0; }
.office-facts dt { color: var(--ink-soft); font-size: 11px; }
.office-facts dd { margin: 5px 0 0; overflow: hidden; color: #263d47; font-size: 13px; font-weight: 800; }
.office-facts dd small { display: block; margin-top: 4px; overflow: hidden; text-overflow: ellipsis; color: var(--ink-soft); font-size: 11px; font-weight: 400; white-space: nowrap; }
.lease-ribbon { margin: 0 20px 0 24px; padding: 13px 14px; border-radius: 11px; color: #2b5963; background: #edf6f7; }
.lease-ribbon.due { color: #86551d; background: #fff3e5; }
.lease-ribbon > div { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 9px; font: 700 10px ui-monospace, SFMono-Regular, Menlo, monospace; }
.lease-ribbon i { height: 1px; background: currentColor; opacity: 0.35; }
.lease-ribbon strong, .lease-ribbon small { display: block; }
.lease-ribbon strong { margin-top: 9px; font-size: 12px; }
.lease-ribbon small { margin-top: 3px; opacity: 0.75; font-size: 11px; }
.office-site-card > footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: auto; padding: 17px 20px 18px 24px; }
.office-site-card > footer > div { display: flex; gap: 10px; }
.office-detail-button { display: inline-flex; min-width: 0; align-items: center; gap: 5px; padding: 0; color: var(--blue); background: transparent; font-size: 12px; font-weight: 800; text-align: left; }
.office-site-card .text-button { font-size: 12px; }
.text-button.danger { color: var(--red); }
.office-form-modal { width: min(980px, 96vw); }
.office-form-body { display: grid; gap: 14px; padding: 20px 24px 10px; background: #f5f8f9; }
.office-form-error { margin: 0; padding: 11px 13px; border-radius: 9px; background: #fff1f0; }
.office-form-section { overflow: hidden; border: 1px solid var(--line); border-radius: 13px; background: #fff; }
.office-form-section > header { display: flex; align-items: baseline; gap: 10px; padding: 15px 18px; border-bottom: 1px solid var(--line); }
.office-form-section > header strong { color: var(--admin-ink); }
.office-form-section > header span { color: var(--ink-soft); font-size: 11px; }
.office-form-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; padding: 18px; }
.office-form-grid label { display: flex; flex-direction: column; gap: 7px; }
.office-form-grid label > span { color: #405964; font-size: 12px; font-weight: 800; }
.office-form-grid input, .office-form-grid select, .office-form-grid textarea { width: 100%; min-height: 43px; padding: 10px 12px; color: #18313c; border: 1px solid #cbd7dc; border-radius: 10px; background: #fff; }
.office-form-grid textarea { min-height: 78px; resize: vertical; }
.office-form-grid .wide { grid-column: 1 / -1; }
.office-form-footer { position: sticky; z-index: 2; bottom: 0; display: flex; justify-content: flex-end; gap: 10px; padding: 16px 24px; border-top: 1px solid var(--line); background: rgba(255, 255, 255, 0.96); backdrop-filter: blur(10px); }
.office-detail-modal { width: min(1040px, 96vw); }
.office-detail-loading { display: grid; min-height: 340px; place-items: center; color: var(--ink-soft); }
.office-detail-error { margin: 24px; }
.office-detail-body { display: grid; grid-template-columns: 250px minmax(0, 1fr); align-items: start; gap: 18px; padding: 22px 24px 12px; background: #f5f8f9; }
.office-address-plaque { position: sticky; top: 0; display: flex; min-height: 260px; flex-direction: column; padding: 23px; color: #fff; border-radius: 14px; background: var(--admin-ink); box-shadow: 0 14px 34px rgba(18, 59, 74, 0.18); }
.office-address-plaque::after { position: absolute; right: 18px; bottom: 18px; width: 44px; height: 44px; border: 1px solid rgba(255, 255, 255, 0.17); border-radius: 50%; content: ""; }
.office-address-plaque > span { margin-top: 35px; color: #9bd2dc; font: 800 12px ui-monospace, monospace; letter-spacing: 0.12em; }
.office-address-plaque > strong { margin-top: 12px; font-size: 18px; line-height: 1.55; }
.office-address-plaque > small { margin-top: auto; color: #bfd0d6; line-height: 1.5; }
.office-detail-main { display: grid; gap: 14px; }
.office-detail-section, .office-contract-section { overflow: hidden; border: 1px solid var(--line); border-radius: 13px; background: #fff; }
.office-detail-section > header, .office-contract-section > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 15px 17px; border-bottom: 1px solid var(--line); }
.office-detail-section > header div, .office-contract-section > header div { display: grid; gap: 3px; }
.office-detail-section > header span, .office-contract-section > header span { color: var(--ink-soft); font-size: 11px; }
.office-contract-section > header b { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 9px; color: var(--admin-teal); background: var(--admin-wash); }
.office-detail-section dl { display: grid; grid-template-columns: 1fr 1fr; gap: 0; margin: 0; }
.office-detail-section dl div { min-width: 0; padding: 14px 17px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.office-detail-section dl div:nth-child(even), .office-detail-section dl .wide { border-right: 0; }
.office-detail-section dl div:last-child { border-bottom: 0; }
.office-detail-section dl .wide { grid-column: 1 / -1; }
.office-detail-section dt { color: var(--ink-soft); font-size: 11px; }
.office-detail-section dd { margin: 5px 0 0; overflow-wrap: anywhere; color: #253b45; font-size: 13px; font-weight: 700; line-height: 1.55; }
.office-detail-section dd small { display: block; margin-top: 3px; color: var(--ink-soft); font-size: 11px; font-weight: 400; }
.office-contract-list { display: grid; gap: 8px; padding: 12px; }
.office-contract-list article { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 13px; border: 1px solid var(--line); border-radius: 10px; }
.office-contract-list article > div { min-width: 0; }
.office-contract-list article strong, .office-contract-list article small { display: block; }
.office-contract-list article small { margin-top: 4px; color: var(--ink-soft); font-size: 11px; }
.contract-status { padding: 5px 8px; border-radius: 999px; color: #176d7c; background: #e9f3f4; font-size: 10px; font-weight: 800; }
.contract-status[data-status="expired"], .contract-status[data-status="terminated"] { color: #a43832; background: #fce8e6; }
.contract-period { text-align: right; }
.contract-period strong { font-size: 11px; }
.office-contract-empty { margin: 0; padding: 28px; color: var(--ink-soft); text-align: center; }
.office-detail-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 24px; border-top: 1px solid var(--line); background: #fff; }
@media (max-width: 1120px) {
  .office-site-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .office-filter-bar { flex-wrap: wrap; }
  .office-search { min-width: min(100%, 420px); }
  .office-form-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 760px) {
  .office-intro { align-items: stretch; }
  .office-intro .primary-button { width: 100%; }
  .office-kpis, .office-site-grid { grid-template-columns: 1fr; }
  .office-filter-bar { align-items: stretch; }
  .office-filter-bar select, .office-search { width: 100%; min-width: 0; }
  .office-result-count { width: 100%; margin-left: 0; }
  .office-form-grid { grid-template-columns: 1fr; }
  .office-form-grid .wide { grid-column: auto; }
  .office-form-section > header { align-items: flex-start; flex-direction: column; }
  .office-detail-body { grid-template-columns: 1fr; }
  .office-address-plaque { position: relative; min-height: 210px; }
  .office-detail-section dl { grid-template-columns: 1fr; }
  .office-detail-section dl div, .office-detail-section dl div:nth-child(even) { border-right: 0; }
  .office-detail-section dl .wide { grid-column: auto; }
  .office-contract-list article { grid-template-columns: 1fr; }
  .contract-status { width: fit-content; }
  .contract-period { text-align: left; }
}
</style>
