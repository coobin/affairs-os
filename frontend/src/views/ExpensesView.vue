<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { api, ApiError, download } from "../api";
import type { AdministrativeExpense, Contract, ExpenseCategory, ExpenseSummary, Lookups, Paginated, Supplier } from "../types";

const props = defineProps<{ lookups: Lookups | null }>();
const year = ref(new Date().getFullYear());
const rows = ref<AdministrativeExpense[]>([]);
const summary = ref<ExpenseSummary | null>(null);
const categories = ref<ExpenseCategory[]>([]);
const suppliers = ref<Supplier[]>([]);
const contracts = ref<Contract[]>([]);
const showForm = ref(false);
const error = ref("");
const form = reactive({ occurred_on: new Date().toISOString().slice(0,10), category: "", department: "", supplier: "", contract: "", amount_type: "actual", amount: "", title: "", object_label: "", invoice_status: "pending", invoice_number: "", kingdee_code: "", external_id: "", notes: "" });
const years = computed(() => { const current=new Date().getFullYear(); return Array.from(new Set([...Array.from({length:6},(_,i)=>current-i), ...rows.value.map(x=>x.fiscal_year)])).sort((a,b)=>b-a); });
const maxCategory = computed(() => Math.max(...(summary.value?.by_category.map(x=>Number(x.total))||[1]), 1));
function unwrap<T>(value: T[] | Paginated<T>) { return Array.isArray(value) ? value : value.results; }
async function load() {
  try {
    const [expenseData, summaryData, categoryData, supplierData, contractData] = await Promise.all([
      api<Paginated<AdministrativeExpense>|AdministrativeExpense[]>(`/administrative-expenses/?year=${year.value}&page_size=200`),
      api<ExpenseSummary>(`/administrative-expenses/summary/?year=${year.value}`),
      api<ExpenseCategory[]>("/expense-categories/"), api<Supplier[]>("/suppliers/"), api<Contract[]>("/contracts/"),
    ]);
    rows.value=unwrap(expenseData); summary.value=summaryData; categories.value=categoryData; suppliers.value=supplierData; contracts.value=contractData;
  } catch(err) { error.value=err instanceof ApiError?err.message:"费用台账暂时无法加载。"; }
}
async function create() {
  try {
    await api("/administrative-expenses/", {method:"POST", body:JSON.stringify({...form, category:Number(form.category), department:form.department?Number(form.department):null, supplier:form.supplier?Number(form.supplier):null, contract:form.contract?Number(form.contract):null})});
    showForm.value=false; await load();
  } catch(err) { error.value=err instanceof ApiError?Object.values(err.errors).flat().join(" ")||err.message:"费用未保存。"; }
}
async function exportLedger(){ await download(`/administrative-expenses/export/?year=${year.value}`,{},`行政费用台账_${year.value}.xlsx`); }
function money(value:string|number|undefined){return `¥${Number(value||0).toLocaleString("zh-CN",{minimumFractionDigits:2,maximumFractionDigits:2})}`}
watch(year, load); onMounted(load);
</script>

<template>
  <div class="page module-page admin-module-page">
    <header class="page-intro"><div><p class="eyebrow">行政费用 · 统一口径</p><h1>{{ year }} 年费用台账</h1><p>预计、承诺、实际与冲销分开记录，为后续预算系统接入保留标准字段。</p></div><div class="page-actions"><select v-model="year" class="year-select"><option v-for="x in years" :key="x" :value="x">{{x}} 年</option></select><button class="secondary-button" @click="exportLedger">导出台账</button><button class="primary-button" @click="showForm=true">登记费用</button></div></header>
    <section class="expense-summary-grid"><article><span>本年实际发生</span><strong>{{money(summary?.totals.net_actual)}}</strong><small>已扣除冲销金额</small></article><article><span>已承诺金额</span><strong>{{money(summary?.totals.committed)}}</strong><small>已签约或已下单</small></article><article><span>已批准金额</span><strong>{{money(summary?.totals.approved)}}</strong><small>审批通过待执行</small></article><article><span>预计金额</span><strong>{{money(summary?.totals.estimated)}}</strong><small>申请与计划口径</small></article></section>
    <section class="expense-layout"><div class="ledger-panel"><header class="panel-title"><div><p class="eyebrow">费用明细</p><h2>全年发生记录</h2></div><span>{{rows.length}} 条</span></header><table class="admin-table"><thead><tr><th>日期</th><th>事项 / 对象</th><th>类别 / 部门</th><th>供应商 / 合同</th><th>金额类型</th><th>金额</th><th>对接状态</th></tr></thead><tbody><tr v-for="item in rows" :key="item.id"><td>{{item.occurred_on}}</td><td><strong>{{item.title}}</strong><small>{{item.object_label||item.source_no||'手工登记'}}</small></td><td>{{item.category_name}}<small>{{item.department_name||'未设置部门'}}</small></td><td>{{item.supplier_name||'—'}}<small>{{item.contract_name}}</small></td><td><span class="record-status" :data-status="item.amount_type">{{item.amount_type_label}}</span></td><td><strong>{{money(item.amount)}}</strong></td><td><small>{{item.kingdee_code||'待补金蝶编码'}} · {{item.sync_status==='pending'?'待同步':item.sync_status}}</small></td></tr></tbody></table><div v-if="!rows.length" class="empty-state large">本年度还没有费用记录。</div></div><aside class="expense-rank"><p class="eyebrow">费用构成</p><h2>按类别归集</h2><div v-for="item in summary?.by_category||[]" :key="item.category__name" class="rank-row"><div><span>{{item.category__name}}</span><strong>{{money(item.total)}}</strong></div><i><b :style="{width:`${Number(item.total)/maxCategory*100}%`}"></b></i></div><div v-if="!summary?.by_category.length" class="empty-state">暂无构成数据。</div></aside></section>
    <div v-if="error" class="error-block">{{error}}</div>
    <div v-if="showForm" class="modal-backdrop" @click.self="showForm=false"><form class="modal-panel admin-form-modal" @submit.prevent="create"><header><div><p class="eyebrow">费用台账</p><h2>登记行政费用</h2></div><button type="button" class="icon-button" @click="showForm=false">×</button></header><div class="form-grid"><label><span>发生日期</span><input v-model="form.occurred_on" type="date" required /></label><label><span>费用类别</span><select v-model="form.category" required><option value="">请选择</option><option v-for="x in categories.filter(x=>x.is_active)" :key="x.id" :value="x.id">{{x.name}}</option></select></label><label><span>金额类型</span><select v-model="form.amount_type"><option value="estimated">预计</option><option value="approved">已批准</option><option value="committed">已承诺</option><option value="actual">实际发生</option><option value="reversal">冲销</option></select></label><label><span>金额</span><input v-model="form.amount" type="number" min="0" step="0.01" required /></label><label class="wide"><span>费用事项</span><input v-model="form.title" required /></label><label><span>归属部门</span><select v-model="form.department"><option value="">未设置</option><option v-for="x in lookups?.departments||[]" :key="x.id" :value="x.id">{{x.name}}</option></select></label><label><span>供应商</span><select v-model="form.supplier"><option value="">未设置</option><option v-for="x in suppliers" :key="x.id" :value="x.id">{{x.name}}</option></select></label><label><span>关联合同</span><select v-model="form.contract"><option value="">未设置</option><option v-for="x in contracts" :key="x.id" :value="x.id">{{x.contract_no}} · {{x.name}}</option></select></label><label><span>费用对象</span><input v-model="form.object_label" placeholder="车辆、场地或项目" /></label><label><span>发票状态</span><select v-model="form.invoice_status"><option value="none">无需发票</option><option value="pending">待收票</option><option value="received">已收票</option><option value="verified">已核验</option></select></label><label><span>发票号码</span><input v-model="form.invoice_number" /></label><label><span>金蝶编码</span><input v-model="form.kingdee_code" /></label><label><span>预算系统标识</span><input v-model="form.external_id" placeholder="以后对接时使用" /></label><label class="wide"><span>备注</span><textarea v-model="form.notes"></textarea></label></div><button class="primary-button full">保存费用记录</button></form></div>
  </div>
</template>
