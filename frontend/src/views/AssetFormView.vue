<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import { api, ApiError } from "../api";
import AppIcon from "../components/AppIcon.vue";
import PersonSearchSelect from "../components/PersonSearchSelect.vue";
import type { Asset, Lookups } from "../types";

const props = defineProps<{ lookups: Lookups | null; assetId?: number; isSuperuser: boolean }>();
const emit = defineEmits<{ navigate: [path: string] }>();
const isEditing = computed(() => Boolean(props.assetId));

const form = reactive({
  asset_tag: "",
  kingdee_code: "",
  custom_data: {} as Record<string, unknown>,
  class_type: "IT" as "IT" | "ADMIN",
  category: "",
  brand: "",
  model_name: "",
  serial_number: "",
  specification: "",
  cpu: "",
  memory: "",
  storage: "",
  wired_mac: "",
  wireless_mac: "",
  status: "available",
  is_requestable: true,
  assigned_to: "",
  current_location: "",
  custodian_department: "",
  purchase_date: "",
  purchase_cost: "",
  warranty_expires_at: "",
  notes: "",
});
const selectedCategoryName = computed(
  () => props.lookups?.categories.find((item) => String(item.id) === form.category)?.name || "",
);
const filteredCategories = computed(
  () => (props.lookups?.categories || []).filter((item) => item.class_type === form.class_type),
);
const displayName = computed(() => {
  const brand = form.brand.trim();
  const modelName = form.model_name.trim();
  if (brand && modelName) {
    return modelName.toLowerCase().startsWith(brand.toLowerCase()) ? modelName : `${brand} ${modelName}`;
  }
  return brand || modelName || selectedCategoryName.value || "选择分类后自动生成";
});
const loading = ref(false);
const loadingAsset = ref(false);
const deleting = ref(false);
const error = ref("");
const fieldErrors = ref<Record<string, unknown>>({});

async function loadAsset() {
  if (!props.assetId) return;
  loadingAsset.value = true;
  error.value = "";
  try {
    const asset = await api<Asset>(`/assets/${props.assetId}/`);
    Object.assign(form, {
      asset_tag: asset.asset_tag,
      kingdee_code: asset.kingdee_code,
      custom_data: asset.custom_data,
      class_type: asset.category_class_type,
      category: String(asset.category),
      brand: asset.brand,
      model_name: asset.model_name,
      serial_number: asset.serial_number,
      specification: asset.specification,
      cpu: asset.cpu,
      memory: asset.memory,
      storage: asset.storage,
      wired_mac: asset.wired_mac,
      wireless_mac: asset.wireless_mac,
      status: asset.status,
      is_requestable: asset.is_requestable,
      assigned_to: asset.assigned_to ? String(asset.assigned_to) : "",
      current_location: asset.current_location ? String(asset.current_location) : "",
      custodian_department: asset.custodian_department ? String(asset.custodian_department) : "",
      purchase_date: asset.purchase_date || "",
      purchase_cost: asset.purchase_cost || "",
      warranty_expires_at: asset.warranty_expires_at || "",
      notes: asset.notes,
    });
  } catch {
    error.value = "没有找到这件资产，或当前账号无权编辑。";
  } finally {
    loadingAsset.value = false;
  }
}

async function save() {
  loading.value = true;
  error.value = "";
  fieldErrors.value = {};
  const { asset_tag, class_type, custom_data, ...assetFields } = form;
  const cleanedCustomData = { ...custom_data };
  delete cleanedCustomData.responsible_person;
  const payload = {
    ...assetFields,
    category: Number(form.category),
    assigned_to: form.assigned_to ? Number(form.assigned_to) : null,
    current_location: form.current_location ? Number(form.current_location) : null,
    custodian_department: form.custodian_department ? Number(form.custodian_department) : null,
    purchase_date: form.purchase_date || null,
    purchase_cost: form.purchase_cost || null,
    warranty_expires_at: form.warranty_expires_at || null,
    custom_data: {
      ...cleanedCustomData,
    },
  };
  try {
    const asset = await api<Asset>(isEditing.value ? `/assets/${props.assetId}/` : "/assets/", {
      method: isEditing.value ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    emit("navigate", `/assets/${asset.id}`);
  } catch (err) {
    if (err instanceof ApiError) {
      error.value = err.message;
      fieldErrors.value = err.errors;
    } else {
      error.value = "资产未保存，请稍后重试。";
    }
  } finally {
    loading.value = false;
  }
}

async function deleteAsset() {
  if (!props.assetId) return;
  if (!window.confirm(`确认删除资产“${form.asset_tag} · ${displayName.value}”？删除后无法恢复。`)) return;
  deleting.value = true;
  error.value = "";
  try {
    await api(`/assets/${props.assetId}/`, { method: "DELETE" });
    emit("navigate", "/assets");
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "资产删除失败。";
  } finally {
    deleting.value = false;
  }
}

function fieldError(name: string) {
  const value = fieldErrors.value[name];
  return Array.isArray(value) ? String(value[0]) : value ? String(value) : "";
}

watch(() => form.assigned_to, (value) => {
  if (value && form.status === "available") form.status = "assigned";
  if (!value && ["assigned", "loaned"].includes(form.status)) form.status = "available";
  if (value && !loadingAsset.value) {
    const person = props.lookups?.users.find((item) => String(item.id) === String(value));
    if (person?.department) form.custodian_department = String(person.department);
  }
}, { flush: "sync" });
watch(() => form.status, (value) => {
  if (["available", "disposed"].includes(value)) form.assigned_to = "";
});
watch(() => form.class_type, () => {
  if (form.category && !filteredCategories.value.some((item) => String(item.id) === form.category)) {
    form.category = "";
  }
});

onMounted(loadAsset);
</script>

<template>
  <div class="page form-page">
    <button class="back-button" @click="emit('navigate', isEditing ? `/assets/${props.assetId}` : '/assets')">
      <AppIcon name="arrow-left" :size="18" />{{ isEditing ? "返回资产详情" : "返回资产列表" }}
    </button>

    <header class="page-intro compact">
      <div>
        <p class="eyebrow">{{ isEditing ? "编辑台账" : "新增台账" }}</p>
        <h1>{{ isEditing ? "修改资产资料" : "登记一件新资产" }}</h1>
      </div>
    </header>

    <div v-if="loadingAsset" class="loading-block">正在读取资产资料…</div>
    <form v-else class="asset-form-layout" @submit.prevent="save">
      <div class="form-main">
        <section class="form-section">
          <div class="form-section-title"><span>01</span><div><h2>识别信息</h2></div></div>
          <div class="form-grid">
            <label>
              <span>资产编号</span>
              <input :value="form.asset_tag || '保存后自动生成'" readonly />
            </label>
            <label>
              <span>显示名称</span>
              <input :value="displayName" readonly />
            </label>
            <label>
              <span>资产分类 <b>*</b></span>
              <select v-model="form.class_type" required>
                <option value="IT">IT资产</option>
                <option value="ADMIN">行政资产</option>
              </select>
            </label>
            <label>
              <span>资产类型 <b>*</b></span>
              <select v-model="form.category" required>
                <option value="" disabled>请选择类型</option>
                <option v-for="item in filteredCategories" :key="item.id" :value="item.id">
                  {{ item.name }} · {{ item.code }}
                </option>
              </select>
              <small v-if="fieldError('category')" class="field-error">{{ fieldError("category") }}</small>
            </label>
            <label>
              <span>金蝶编码</span>
              <input v-model="form.kingdee_code" placeholder="金蝶系统中的资产编码" />
            </label>
            <label>
              <span>序列号</span>
              <input v-model="form.serial_number" placeholder="设备 SN 或序列号" />
              <small v-if="fieldError('serial_number')" class="field-error">{{ fieldError("serial_number") }}</small>
            </label>
            <label>
              <span>品牌</span>
              <input v-model="form.brand" placeholder="例如 Apple" />
            </label>
            <label>
              <span>型号</span>
              <input v-model="form.model_name" placeholder="例如 MacBook Pro M4" />
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="form-section-title"><span>02</span><div><h2>设备配置</h2></div></div>
          <div class="form-grid">
            <label class="full-span">
              <span>主要配置</span>
              <input v-model="form.specification" placeholder="例如 RTX 5070Ti、27 英寸 4K、双电源等" />
            </label>
            <label><span>CPU</span><input v-model="form.cpu" placeholder="例如 i5-13500H" /></label>
            <label><span>内存</span><input v-model="form.memory" placeholder="例如 16G" /></label>
            <label><span>硬盘</span><input v-model="form.storage" placeholder="例如 1T SSD" /></label>
            <label><span>有线 MAC 地址</span><input v-model="form.wired_mac" placeholder="例如 F4A8-0DE1-67F1" /></label>
            <label><span>无线 MAC 地址</span><input v-model="form.wireless_mac" placeholder="例如 C815-4ED5-2235" /></label>
          </div>
        </section>

        <section class="form-section">
          <div class="form-section-title"><span>03</span><div><h2>位置与归属</h2></div></div>
          <div class="form-grid">
            <label>
              <span>资产状态</span>
              <select v-model="form.status" required>
                <option v-for="item in props.lookups?.statuses || []" :key="item.value" :value="item.value">
                  {{ item.label }}
                </option>
              </select>
              <small v-if="fieldError('status')" class="field-error">{{ fieldError("status") }}</small>
            </label>
            <label class="checkbox-field">
              <input v-model="form.is_requestable" type="checkbox" />
              <span>允许员工申请</span>
            </label>
            <label>
              <span>责任人</span>
              <PersonSearchSelect v-model="form.assigned_to" :users="props.lookups?.users || []" placeholder="输入中文姓名搜索" />
              <small v-if="fieldError('assigned_to')" class="field-error">{{ fieldError("assigned_to") }}</small>
            </label>
            <label>
              <span>当前地点</span>
              <select v-model="form.current_location">
                <option value="">暂不设置</option>
                <option v-for="item in props.lookups?.locations || []" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </label>
            <label>
              <span>归属部门</span>
              <select v-model="form.custodian_department">
                <option value="">暂不设置</option>
                <option v-for="item in props.lookups?.departments || []" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="form-section-title"><span>04</span><div><h2>采购与保修</h2></div></div>
          <div class="form-grid">
            <label><span>采购日期</span><input v-model="form.purchase_date" type="date" /></label>
            <label><span>采购金额</span><input v-model="form.purchase_cost" type="number" min="0" step="0.01" placeholder="0.00" /></label>
            <label>
              <span>保修到期</span>
              <input v-model="form.warranty_expires_at" type="date" />
              <small v-if="fieldError('warranty_expires_at')" class="field-error">{{ fieldError("warranty_expires_at") }}</small>
            </label>
            <label class="full-span"><span>备注</span><textarea v-model="form.notes" rows="4" placeholder="可记录采购批次、设备状况或其他说明"></textarea></label>
          </div>
        </section>
      </div>

      <aside class="form-side">
        <div class="asset-tag-preview">
          <p>ASSET LABEL</p>
          <strong>{{ form.asset_tag || "等待资产编号" }}</strong>
          <span>{{ displayName }}</span>
          <div class="mini-barcode"><i v-for="n in 13" :key="n"></i></div>
          <small>{{ props.lookups?.categories.find((item) => item.id === Number(form.category))?.code || "—" }}</small>
        </div>
        <div class="save-panel">
          <p v-if="error" class="form-error">{{ error }}</p>
          <button class="primary-button full" :disabled="loading">
            {{ loading ? "正在保存…" : isEditing ? "保存修改" : "保存资产" }}
            <AppIcon name="chevron-right" :size="18" />
          </button>
          <button v-if="isEditing && isSuperuser" type="button" class="danger-button full" :disabled="deleting" @click="deleteAsset">
            {{ deleting ? "正在删除…" : "删除资产" }}
          </button>
          <button type="button" class="text-button full" @click="emit('navigate', isEditing ? `/assets/${props.assetId}` : '/assets')">取消</button>
        </div>
      </aside>
    </form>
  </div>
</template>
