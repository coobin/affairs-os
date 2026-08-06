<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api, ApiError } from "../api";
import PersonSearchSelect from "../components/PersonSearchSelect.vue";
import type { Lookups, Supplier, Vehicle, VehicleDispatch, VehicleExpense } from "../types";

const props = defineProps<{ lookups: Lookups | null; canManage: boolean; isSuperuser: boolean }>();
type Tab = "dispatches" | "vehicles" | "expenses";
const tab = ref<Tab>("dispatches");
const dispatches = ref<VehicleDispatch[]>([]);
const vehicles = ref<Vehicle[]>([]);
const expenses = ref<VehicleExpense[]>([]);
const suppliers = ref<Supplier[]>([]);
const error = ref("");
const showDispatch = ref(false);
const showVehicle = ref(false);
const showExpense = ref(false);
const editingVehicle = ref<Vehicle | null>(null);
const editingExpense = ref<VehicleExpense | null>(null);
const processing = ref<VehicleDispatch | null>(null);
const dispatchForm = reactive({ purpose: "", destination: "", passenger_count: 1, planned_departure_at: "", planned_return_at: "" });
const vehicleForm = reactive({ plate_number: "", name: "", brand: "", model_name: "", energy_type: "gasoline", seats: 5, status: "available", department: "", custodian: "", current_mileage: 0, insurance_expires_at: "", inspection_expires_at: "", vin: "", engine_number: "", notes: "" });
const expenseForm = reactive({ vehicle: "", expense_type: "maintenance", occurred_on: new Date().toISOString().slice(0, 10), amount: "", supplier: "", odometer: "", next_due_on: "", next_due_mileage: "", notes: "" });
const processForm = reactive({ vehicle_id: "", driver_id: "", driver_name: "", mileage: "", notes: "" });
const availableVehicles = computed(() => vehicles.value.filter((item) => item.status === "available"));
const pendingCount = computed(() => dispatches.value.filter((item) => item.status === "pending").length);

async function load() {
  error.value = "";
  try {
    dispatches.value = await api<VehicleDispatch[]>("/vehicle-dispatches/");
    if (props.canManage) {
      [vehicles.value, expenses.value, suppliers.value] = await Promise.all([
        api<Vehicle[]>("/vehicles/"), api<VehicleExpense[]>("/vehicle-expenses/"), api<Supplier[]>("/suppliers/"),
      ]);
    }
  } catch (err) { error.value = err instanceof ApiError ? err.message : "车辆信息暂时无法加载。"; }
}
async function createDispatch() {
  try {
    await api("/vehicle-dispatches/", { method: "POST", body: JSON.stringify(dispatchForm) });
    Object.assign(dispatchForm, { purpose: "", destination: "", passenger_count: 1, planned_departure_at: "", planned_return_at: "" });
    showDispatch.value = false; await load();
  } catch (err) { error.value = formatError(err, "用车申请未提交。"); }
}
async function saveVehicle() {
  try {
    const payload = { ...vehicleForm, department: vehicleForm.department ? Number(vehicleForm.department) : null, custodian: vehicleForm.custodian ? Number(vehicleForm.custodian) : null, insurance_expires_at: vehicleForm.insurance_expires_at || null, inspection_expires_at: vehicleForm.inspection_expires_at || null };
    if (editingVehicle.value) {
      await api(`/vehicles/${editingVehicle.value.id}/`, { method: "PATCH", body: JSON.stringify(payload) });
    } else {
      await api("/vehicles/", { method: "POST", body: JSON.stringify(payload) });
    }
    showVehicle.value = false; editingVehicle.value = null; await load();
  } catch (err) { error.value = formatError(err, "车辆未保存。"); }
}
function openVehicleNew() {
  editingVehicle.value = null;
  Object.assign(vehicleForm, { plate_number: "", name: "", brand: "", model_name: "", energy_type: "gasoline", seats: 5, status: "available", department: "", custodian: "", current_mileage: 0, insurance_expires_at: "", inspection_expires_at: "", vin: "", engine_number: "", notes: "" });
  showVehicle.value = true;
}
function openVehicleEdit(item: Vehicle) {
  editingVehicle.value = item;
  Object.assign(vehicleForm, {
    plate_number: item.plate_number, name: item.name, brand: item.brand, model_name: item.model_name,
    energy_type: item.energy_type, seats: item.seats, status: item.status, department: item.department || "",
    custodian: item.custodian || "", current_mileage: item.current_mileage,
    insurance_expires_at: item.insurance_expires_at || "", inspection_expires_at: item.inspection_expires_at || "",
    vin: item.vin || "", engine_number: item.engine_number || "", notes: item.notes || "",
  });
  showVehicle.value = true;
}
async function deleteVehicle(item: Vehicle) {
  if (!window.confirm(`确认删除车辆“${item.plate_number} · ${item.name}”？删除后无法恢复。`)) return;
  try {
    await api(`/vehicles/${item.id}/`, { method: "DELETE" });
    await load();
  } catch (err) { error.value = formatError(err, "车辆删除失败。"); }
}
async function saveExpense() {
  try {
    const payload = { ...expenseForm, vehicle: Number(expenseForm.vehicle), supplier: expenseForm.supplier ? Number(expenseForm.supplier) : null, odometer: expenseForm.odometer ? Number(expenseForm.odometer) : null, next_due_on: expenseForm.next_due_on || null, next_due_mileage: expenseForm.next_due_mileage ? Number(expenseForm.next_due_mileage) : null };
    if (editingExpense.value) {
      await api(`/vehicle-expenses/${editingExpense.value.id}/`, { method: "PATCH", body: JSON.stringify(payload) });
    } else {
      await api("/vehicle-expenses/", { method: "POST", body: JSON.stringify(payload) });
    }
    showExpense.value = false; editingExpense.value = null; await load();
  } catch (err) { error.value = formatError(err, "车辆事项未保存。"); }
}
function openExpenseNew() {
  editingExpense.value = null;
  Object.assign(expenseForm, { vehicle: "", expense_type: "maintenance", occurred_on: new Date().toISOString().slice(0, 10), amount: "", supplier: "", odometer: "", next_due_on: "", next_due_mileage: "", notes: "" });
  showExpense.value = true;
}
function openExpenseEdit(item: VehicleExpense) {
  editingExpense.value = item;
  Object.assign(expenseForm, {
    vehicle: String(item.vehicle), expense_type: item.expense_type, occurred_on: item.occurred_on, amount: item.amount,
    supplier: item.supplier || "", odometer: item.odometer || "", next_due_on: item.next_due_on || "",
    next_due_mileage: item.next_due_mileage || "", notes: item.notes || "",
  });
  showExpense.value = true;
}
async function deleteExpense(item: VehicleExpense) {
  if (!window.confirm(`确认删除车辆事项“${item.vehicle_label} · ${item.expense_type_label}（${item.occurred_on}）”？对应的费用台账记录也会一并删除。`)) return;
  try {
    await api(`/vehicle-expenses/${item.id}/`, { method: "DELETE" });
    await load();
  } catch (err) { error.value = formatError(err, "车辆事项删除失败。"); }
}
function openProcess(item: VehicleDispatch) { processing.value = item; Object.assign(processForm, { vehicle_id: item.vehicle || "", driver_id: item.driver || "", driver_name: item.driver_name || "", mileage: item.end_mileage || item.start_mileage || "", notes: item.notes || "" }); }
async function process(action: "approve" | "dispatch" | "depart" | "complete" | "reject") {
  if (!processing.value) return;
  try {
    await api(`/vehicle-dispatches/${processing.value.id}/${action}/`, { method: "POST", body: JSON.stringify(processForm) });
    processing.value = null; await load();
  } catch (err) { error.value = formatError(err, "派车状态未更新。"); }
}
async function cancel(item: VehicleDispatch) { await api(`/vehicle-dispatches/${item.id}/cancel/`, { method: "POST" }); await load(); }
async function updateVehicleStatus(item: Vehicle, event: Event) { const value=(event.target as HTMLSelectElement).value; try { await api(`/vehicles/${item.id}/`,{method:"PATCH",body:JSON.stringify({status:value})}); await load(); } catch(err){ error.value=formatError(err,"车辆状态未更新。"); } }
function formatError(err: unknown, fallback: string) { return err instanceof ApiError ? Object.values(err.errors).flat().join(" ") || err.message : fallback; }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "—"; }
function money(value: string | number) { return `¥${Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`; }
onMounted(load);
</script>

<template>
  <div class="page module-page admin-module-page">
    <header class="page-intro"><div><p class="eyebrow">行政资源 · 车辆</p><h1>从申请用车到费用归集</h1></div><div class="page-actions"><button class="primary-button" @click="showDispatch = true">申请用车</button><button v-if="canManage" class="secondary-button" @click="openVehicleNew">登记车辆</button></div></header>
    <section class="admin-kpi-strip"><div><span>待处理派车</span><strong>{{ pendingCount }}</strong></div><div v-if="canManage"><span>可用车辆</span><strong>{{ availableVehicles.length }}</strong></div><div v-if="canManage"><span>本年车辆费用</span><strong>{{ money(expenses.filter(x => x.occurred_on.startsWith(String(new Date().getFullYear()))).reduce((s,x) => s + Number(x.amount), 0)) }}</strong></div></section>
    <nav class="ledger-tabs"><button :class="{active:tab==='dispatches'}" @click="tab='dispatches'">派车申请</button><button v-if="canManage" :class="{active:tab==='vehicles'}" @click="tab='vehicles'">车辆台账</button><button v-if="canManage" :class="{active:tab==='expenses'}" @click="tab='expenses'">车辆事项与费用</button></nav>
    <div v-if="error" class="error-block">{{ error }}</div>
    <section v-if="tab === 'dispatches'" class="ledger-panel"><table class="admin-table"><thead><tr><th>单号 / 申请人</th><th>行程</th><th>计划时间</th><th>车辆 / 驾驶员</th><th>状态</th><th></th></tr></thead><tbody><tr v-for="item in dispatches" :key="item.id"><td><strong>{{ item.request_no }}</strong><small>{{ item.requester_name }} · {{ item.department_name || '未设置部门' }}</small></td><td><strong>{{ item.destination }}</strong><small>{{ item.purpose }} · {{ item.passenger_count }} 人</small></td><td>{{ formatDate(item.planned_departure_at) }}<small>至 {{ formatDate(item.planned_return_at) }}</small></td><td>{{ item.vehicle_label || '待分配' }}<small>{{ item.driver_display || '待安排驾驶员' }}</small></td><td><span class="record-status" :data-status="item.status">{{ item.status_label }}</span></td><td><button v-if="canManage && ['pending','approved','dispatched','in_progress'].includes(item.status)" class="text-button" @click="openProcess(item)">处理</button><button v-else-if="['pending','approved'].includes(item.status)" class="text-button" @click="cancel(item)">取消</button></td></tr></tbody></table><div v-if="!dispatches.length" class="empty-state large">还没有用车申请。</div></section>
    <section v-else-if="tab === 'vehicles'" class="vehicle-cards"><article v-for="item in vehicles" :key="item.id"><header><span class="vehicle-plate">{{ item.plate_number }}</span><span class="record-status" :data-status="item.status">{{ item.status_label }}</span></header><h2>{{ item.name }}</h2><p>{{ [item.brand,item.model_name].filter(Boolean).join(' ') || '未设置品牌型号' }}</p><dl><div><dt>里程</dt><dd>{{ item.current_mileage.toLocaleString() }} km</dd></div><div><dt>座位</dt><dd>{{ item.seats }} 座</dd></div><div><dt>保险到期</dt><dd>{{ item.insurance_expires_at || '未设置' }}</dd></div><div><dt>年检到期</dt><dd>{{ item.inspection_expires_at || '未设置' }}</dd></div></dl><label class="card-status-control"><span>调整车辆状态</span><select :value="item.status" @change="updateVehicleStatus(item,$event)"><option value="available">可用</option><option value="maintenance">维修保养</option><option value="suspended">停用</option><option value="retired">已处置</option></select></label><div class="vehicle-card-actions"><button v-if="canManage" class="secondary-button" @click="openVehicleEdit(item)">编辑</button><button v-if="isSuperuser" class="text-button danger" @click="deleteVehicle(item)">删除</button></div></article><div v-if="!vehicles.length" class="empty-state large">还没有登记车辆。</div></section>
    <section v-else class="ledger-panel"><div class="panel-actions"><button class="primary-button" @click="openExpenseNew">登记车辆事项</button></div><table class="admin-table"><thead><tr><th>日期</th><th>车辆</th><th>事项</th><th>服务商</th><th>里程 / 下次到期</th><th>金额</th><th></th></tr></thead><tbody><tr v-for="item in expenses" :key="item.id"><td>{{ item.occurred_on }}</td><td><strong>{{ item.vehicle_label }}</strong></td><td>{{ item.expense_type_label }}<small>{{ item.notes }}</small></td><td>{{ item.supplier_name || '未设置' }}</td><td>{{ item.odometer ? `${item.odometer.toLocaleString()} km` : '—' }}<small>{{ item.next_due_on || (item.next_due_mileage ? `${item.next_due_mileage} km` : '无下次提醒') }}</small></td><td><strong>{{ money(item.amount) }}</strong></td><td><button v-if="canManage" class="text-button" @click="openExpenseEdit(item)">编辑</button><button v-if="isSuperuser" class="text-button danger" @click="deleteExpense(item)">删除</button></td></tr></tbody></table></section>

    <div v-if="showDispatch" class="modal-backdrop" @click.self="showDispatch=false"><form class="modal-panel admin-form-modal" @submit.prevent="createDispatch"><header><div><p class="eyebrow">用车申请</p><h2>填写本次行程</h2></div><button type="button" class="icon-button" @click="showDispatch=false">×</button></header><div class="form-grid"><label><span>目的地</span><input v-model="dispatchForm.destination" required /></label><label><span>乘车人数</span><input v-model.number="dispatchForm.passenger_count" type="number" min="1" required /></label><label><span>计划出发</span><input v-model="dispatchForm.planned_departure_at" type="datetime-local" required /></label><label><span>计划返回</span><input v-model="dispatchForm.planned_return_at" type="datetime-local" required /></label><label class="wide"><span>用车事由</span><textarea v-model="dispatchForm.purpose" required></textarea></label></div><button class="primary-button full">提交用车申请</button></form></div>
    <div v-if="showVehicle" class="modal-backdrop" @click.self="showVehicle=false"><form class="modal-panel admin-form-modal" @submit.prevent="saveVehicle"><header><div><p class="eyebrow">车辆台账</p><h2>{{ editingVehicle ? '编辑车辆' : '登记车辆' }}</h2></div><button type="button" class="icon-button" @click="showVehicle=false">×</button></header><div class="form-grid"><label><span>车牌号</span><input v-model="vehicleForm.plate_number" required /></label><label><span>车辆名称</span><input v-model="vehicleForm.name" required placeholder="例如：商务车 1 号" /></label><label><span>品牌</span><input v-model="vehicleForm.brand" /></label><label><span>型号</span><input v-model="vehicleForm.model_name" /></label><label><span>能源类型</span><select v-model="vehicleForm.energy_type"><option value="gasoline">汽油</option><option value="diesel">柴油</option><option value="electric">纯电</option><option value="hybrid">混动</option><option value="other">其他</option></select></label><label><span>座位数</span><input v-model.number="vehicleForm.seats" type="number" min="1" /></label><label><span>管理部门</span><select v-model="vehicleForm.department"><option value="">未设置</option><option v-for="x in lookups?.departments||[]" :key="x.id" :value="x.id">{{ x.name }}</option></select></label><label><span>负责人</span><PersonSearchSelect v-model="vehicleForm.custodian" :users="lookups?.users || []" /></label><label><span>当前里程</span><input v-model.number="vehicleForm.current_mileage" type="number" min="0" /></label><label><span>保险到期</span><input v-model="vehicleForm.insurance_expires_at" type="date" /></label><label><span>年检到期</span><input v-model="vehicleForm.inspection_expires_at" type="date" /></label><label><span>车架号</span><input v-model="vehicleForm.vin" /></label><label class="wide"><span>备注</span><textarea v-model="vehicleForm.notes"></textarea></label></div><button class="primary-button full">{{ editingVehicle ? '保存修改' : '保存车辆' }}</button></form></div>
    <div v-if="showExpense" class="modal-backdrop" @click.self="showExpense=false"><form class="modal-panel admin-form-modal" @submit.prevent="saveExpense"><header><div><p class="eyebrow">车辆事项</p><h2>{{ editingExpense ? '编辑费用与提醒' : '登记费用与下次提醒' }}</h2></div><button type="button" class="icon-button" @click="showExpense=false">×</button></header><div class="form-grid"><label><span>车辆</span><select v-model="expenseForm.vehicle" required><option value="">请选择</option><option v-for="x in vehicles" :key="x.id" :value="x.id">{{ x.plate_number }} · {{ x.name }}</option></select></label><label><span>事项类型</span><select v-model="expenseForm.expense_type"><option value="maintenance">保养</option><option value="repair">维修</option><option value="insurance">保险</option><option value="inspection">年检</option><option value="fuel">加油</option><option value="charge">充电</option><option value="violation">违章</option><option value="accident">事故</option><option value="parking">停车通行</option><option value="other">其他</option></select></label><label><span>发生日期</span><input v-model="expenseForm.occurred_on" type="date" required /></label><label><span>金额</span><input v-model="expenseForm.amount" type="number" min="0" step="0.01" required /></label><label><span>服务商</span><select v-model="expenseForm.supplier"><option value="">未设置</option><option v-for="x in suppliers" :key="x.id" :value="x.id">{{ x.name }}</option></select></label><label><span>发生时里程</span><input v-model="expenseForm.odometer" type="number" min="0" /></label><label><span>下次到期</span><input v-model="expenseForm.next_due_on" type="date" /></label><label><span>下次保养里程</span><input v-model="expenseForm.next_due_mileage" type="number" min="0" /></label><label class="wide"><span>事项说明</span><textarea v-model="expenseForm.notes"></textarea></label></div><button class="primary-button full">{{ editingExpense ? '保存修改' : '保存并归集费用' }}</button></form></div>
    <div v-if="processing" class="modal-backdrop" @click.self="processing=null"><section class="modal-panel admin-form-modal"><header><div><p class="eyebrow">{{ processing.request_no }}</p><h2>{{ processing.status_label }} · {{ processing.destination }}</h2></div><button class="icon-button" @click="processing=null">×</button></header><div class="form-grid"><template v-if="['pending','approved'].includes(processing.status)"><label><span>分配车辆</span><select v-model="processForm.vehicle_id"><option value="">请选择</option><option v-for="x in availableVehicles" :key="x.id" :value="x.id">{{ x.plate_number }} · {{ x.name }}</option></select></label><label><span>内部驾驶员</span><PersonSearchSelect v-model="processForm.driver_id" :users="lookups?.users || []" placeholder="输入中文姓名搜索（可不选择）" /></label><label><span>外部驾驶员</span><input v-model="processForm.driver_name" placeholder="与内部驾驶员任选其一" /></label></template><label v-if="['dispatched','in_progress'].includes(processing.status)"><span>{{ processing.status==='dispatched'?'出车里程':'返回里程' }}</span><input v-model="processForm.mileage" type="number" min="0" /></label><label class="wide"><span>处理说明</span><textarea v-model="processForm.notes"></textarea></label></div><div class="modal-actions"><button v-if="processing.status==='pending'" class="secondary-button" @click="process('approve')">仅批准</button><button v-if="['pending','approved'].includes(processing.status)" class="primary-button" @click="process('dispatch')">确认派车</button><button v-if="processing.status==='dispatched'" class="primary-button" @click="process('depart')">确认出车</button><button v-if="processing.status==='in_progress'" class="primary-button" @click="process('complete')">办理返回</button><button v-if="processing.status==='pending'" class="danger-button" @click="process('reject')">驳回</button></div></section></div>
  </div>
</template>
