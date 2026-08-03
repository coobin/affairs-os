<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

import { api, ApiError, authenticatedBlob } from "../api";
import AppIcon from "../components/AppIcon.vue";
import AppModal from "../components/AppModal.vue";
import PersonSearchSelect from "../components/PersonSearchSelect.vue";
import StatusPill from "../components/StatusPill.vue";
import type { Asset, Lookups } from "../types";

const props = defineProps<{
  assetId: number;
  lookups: Lookups | null;
  canManage: boolean;
}>();
const emit = defineEmits<{ navigate: [path: string] }>();

const asset = ref<Asset | null>(null);
const loading = ref(true);
const error = ref("");
const modalOpen = ref(false);
const actionType = ref("");
const actionLoading = ref(false);
const actionError = ref("");
const resolvingIssues = ref(false);
const imageUploading = ref(false);
const imageError = ref("");
const imageUrls = ref<Record<number, string>>({});
const previewImageId = ref<number | null>(null);
const actionForm = reactive({
  target_user_id: "",
  target_location_id: "",
  expected_return_at: "",
  notes: "",
  requires_inspection: false,
});

const actionDefinitions: Record<string, { label: string; description: string }> = {
  assign: { label: "办理领用", description: "将资产长期分配给一名员工。" },
  loan: { label: "临时借用", description: "借出资产并设置预计归还日期。" },
  return: { label: "办理归还", description: "收回资产并恢复为在库状态。" },
  transfer: { label: "调拨地点", description: "改变资产当前存放地点并留下记录。" },
  dispose: { label: "标记报废", description: "将资产设为报废并保留历史记录。" },
};

const availableActions = computed(() => {
  if (!asset.value) return [];
  const rules: Record<string, string[]> = {
    available: ["assign", "loan", "transfer", "dispose"],
    assigned: ["return", "transfer", "dispose"],
    loaned: ["return", "transfer", "dispose"],
    disposed: [],
  };
  return rules[asset.value.status] || ["transfer", "dispose"];
});

const currentAction = computed(() => actionDefinitions[actionType.value]);

function formatDate(value: string | null, withTime = false) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", withTime
    ? { year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }
    : { year: "numeric", month: "numeric", day: "numeric" }
  ).format(new Date(value.length === 10 ? `${value}T00:00:00` : value));
}

function currency(value: string | null) {
  if (!value) return "—";
  return new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY" }).format(Number(value));
}

async function loadAsset() {
  loading.value = true;
  try {
    asset.value = await api<Asset>(`/assets/${props.assetId}/`);
    await loadImagePreviews();
  } catch {
    error.value = "没有找到这件资产，或当前账号无权查看。";
  } finally {
    loading.value = false;
  }
}

function clearImagePreviews() {
  Object.values(imageUrls.value).forEach((url) => URL.revokeObjectURL(url));
  imageUrls.value = {};
}

async function loadImagePreviews() {
  clearImagePreviews();
  if (!asset.value?.images.length) return;
  const entries = await Promise.all(
    asset.value.images.map(async (image) => {
      try {
        const blob = await authenticatedBlob(image.content_url);
        return [image.id, URL.createObjectURL(blob)] as const;
      } catch {
        return null;
      }
    }),
  );
  imageUrls.value = Object.fromEntries(entries.filter((entry) => entry !== null));
}

async function uploadImages(event: Event) {
  if (!asset.value) return;
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  if (!files.length) return;
  imageUploading.value = true;
  imageError.value = "";
  try {
    for (const file of files) {
      const body = new FormData();
      body.append("file", file);
      await api(`/assets/${asset.value.id}/images/`, { method: "POST", body });
    }
    await loadAsset();
  } catch (err) {
    imageError.value = err instanceof ApiError ? err.message : "图片上传失败，请重试。";
  } finally {
    imageUploading.value = false;
    input.value = "";
  }
}

async function setCover(imageId: number) {
  if (!asset.value) return;
  await api(`/assets/${asset.value.id}/images/${imageId}/`, {
    method: "PATCH",
    body: JSON.stringify({ is_cover: true }),
  });
  await loadAsset();
}

async function deleteImage(imageId: number) {
  if (!asset.value || !window.confirm("确认删除这张资产图片？")) return;
  try {
    await api(`/assets/${asset.value.id}/images/${imageId}/`, { method: "DELETE" });
    if (previewImageId.value === imageId) previewImageId.value = null;
    await loadAsset();
  } catch (err) {
    imageError.value = err instanceof ApiError ? err.message : "图片删除失败，请重试。";
  }
}

function openAction(action: string) {
  actionType.value = action;
  actionError.value = "";
  actionForm.target_user_id = "";
  actionForm.target_location_id = asset.value?.current_location ? String(asset.value.current_location) : "";
  actionForm.expected_return_at = "";
  actionForm.notes = "";
  actionForm.requires_inspection = false;
  modalOpen.value = true;
}

async function submitAction() {
  if (!asset.value) return;
  actionLoading.value = true;
  actionError.value = "";
  const payload = {
    action: actionType.value,
    target_user_id: actionForm.target_user_id ? Number(actionForm.target_user_id) : null,
    target_location_id: actionForm.target_location_id ? Number(actionForm.target_location_id) : null,
    expected_return_at: actionForm.expected_return_at || null,
    notes: actionForm.notes,
    requires_inspection: actionForm.requires_inspection,
  };
  try {
    const result = await api<{ asset: Asset }>(`/assets/${asset.value.id}/actions/`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    asset.value = result.asset;
    modalOpen.value = false;
  } catch (err) {
    actionError.value = err instanceof ApiError ? err.message : "操作未完成，请稍后重试。";
    if (err instanceof ApiError && Object.keys(err.errors).length) {
      actionError.value = Object.values(err.errors).flat().join(" ");
    }
  } finally {
    actionLoading.value = false;
  }
}

async function resolveImportIssues() {
  if (!asset.value) return;
  resolvingIssues.value = true;
  try {
    asset.value = await api<Asset>(`/assets/${asset.value.id}/import-issues-resolved/`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  } finally {
    resolvingIssues.value = false;
  }
}

watch(() => props.assetId, loadAsset);
onMounted(loadAsset);
onBeforeUnmount(clearImagePreviews);
</script>

<template>
  <div class="page detail-page">
    <button class="back-button" @click="emit('navigate', '/assets')">
      <AppIcon name="arrow-left" :size="18" />返回资产列表
    </button>

    <div v-if="loading" class="loading-block">正在读取资产台账…</div>
    <div v-else-if="error" class="error-block">{{ error }}</div>

    <template v-else-if="asset">
      <section
        v-if="Array.isArray(asset.custom_data.import_warnings) && asset.custom_data.import_warnings.length"
        class="import-issue-banner"
      >
        <div>
          <p class="eyebrow">导入待完善</p>
          <strong>这件资产已先入库，以下资料需要补充</strong>
          <ul>
            <li v-for="message in asset.custom_data.import_warnings" :key="String(message)">
              {{ message }}
            </li>
          </ul>
        </div>
        <div v-if="canManage" class="issue-actions">
          <button class="secondary-button" @click="emit('navigate', `/assets/${asset.id}/edit`)">
            完善资料
          </button>
          <button class="text-button" :disabled="resolvingIssues" @click="resolveImportIssues">
            {{ resolvingIssues ? "处理中…" : "标记为已完善" }}
          </button>
        </div>
      </section>

      <header class="asset-identity">
        <div class="asset-tag-rail">
          <span>ASSET</span>
          <strong>{{ asset.asset_tag }}</strong>
          <i></i><i></i><i></i>
        </div>
        <div class="asset-title">
          <div class="title-row">
            <p class="eyebrow">{{ asset.category_class_type_label }} · {{ asset.category_name }} · {{ asset.category_code }}</p>
            <StatusPill :status="asset.status" :label="asset.status_label" />
            <span v-if="!asset.is_requestable" class="request-closed-badge">不可申请</span>
          </div>
          <h1>{{ asset.name }}</h1>
          <p>资产类型：{{ asset.category_name }}</p>
        </div>
        <div v-if="canManage" class="action-cluster">
          <button class="secondary-button" @click="emit('navigate', `/assets/${asset.id}/edit`)">
            编辑资料
          </button>
          <button
            v-for="action in availableActions"
            :key="action"
            :class="action === 'dispose' ? 'danger-button' : action === availableActions[0] ? 'primary-button' : 'secondary-button'"
            @click="openAction(action)"
          >
            {{ actionDefinitions[action].label }}
          </button>
        </div>
      </header>

      <section class="detail-grid">
        <div class="detail-main">
          <section class="detail-card asset-image-card">
            <div class="section-title">
              <div><h2>资产影像</h2></div>
              <label v-if="canManage && (asset.images?.length || 0) < 10" class="secondary-button compact-upload">
                <AppIcon name="upload" :size="17" />
                {{ imageUploading ? "正在上传…" : "上传图片" }}
                <input type="file" accept="image/jpeg,image/png,image/webp" multiple :disabled="imageUploading" @change="uploadImages" />
              </label>
            </div>
            <p v-if="imageError" class="form-error">{{ imageError }}</p>
            <div v-if="asset.images?.length" class="asset-image-strip">
              <article v-for="image in asset.images" :key="image.id" :class="{ cover: image.is_cover }">
                <button class="asset-image-thumb" :disabled="!imageUrls[image.id]" @click="previewImageId = image.id">
                  <img v-if="imageUrls[image.id]" :src="imageUrls[image.id]" :alt="image.original_name" />
                  <span v-else>图片暂时无法读取</span>
                </button>
                <div class="asset-image-meta">
                  <span>{{ image.is_cover ? "封面" : image.original_name }}</span>
                  <div v-if="canManage">
                    <button v-if="!image.is_cover" class="text-button" @click="setCover(image.id)">设为封面</button>
                    <button class="text-button danger" @click="deleteImage(image.id)">删除</button>
                  </div>
                </div>
              </article>
            </div>
            <div v-else class="image-empty-state">
              <span>还没有资产影像</span>
            </div>
          </section>

          <section class="detail-card">
            <div class="section-title"><div><h2>当前信息</h2></div></div>
            <div class="fact-grid">
              <div><AppIcon name="user" /><span>责任人<small>{{ asset.assignee_name || "暂无责任人" }}</small></span></div>
              <div><AppIcon name="asset" /><span>归属部门<small>{{ asset.department_name || "未设置" }}</small></span></div>
              <div><AppIcon name="map" /><span>当前地点<small>{{ asset.location_name || "未设置" }}</small></span></div>
              <div><AppIcon name="calendar" /><span>预计归还<small>{{ formatDate(asset.expected_return_at) }}</small></span></div>
            </div>
          </section>

          <section class="detail-card">
            <div class="section-title"><div><h2>流转记录</h2></div><span>{{ asset.events.length }} 条</span></div>
            <div v-if="asset.events.length" class="event-timeline">
              <article v-for="event in asset.events" :key="event.id">
                <div class="event-track"><i></i></div>
                <div class="event-copy">
                  <div><strong>{{ event.action_label }}</strong><time>{{ formatDate(event.happened_at, true) }}</time></div>
                  <p>{{ event.notes || "未填写说明" }}</p>
                  <small>
                    {{ event.actor_name || "系统" }}
                    <template v-if="event.to_user_name"> · 交给 {{ event.to_user_name }}</template>
                    <template v-if="event.to_location_name"> · {{ event.to_location_name }}</template>
                  </small>
                </div>
              </article>
            </div>
            <div v-else class="empty-state">还没有流转记录。</div>
          </section>
        </div>

        <aside class="detail-side">
          <section class="detail-card compact-card">
            <p class="eyebrow">设备配置</p>
            <dl>
              <div><dt>主要配置</dt><dd>{{ asset.specification || "—" }}</dd></div>
              <div><dt>CPU</dt><dd>{{ asset.cpu || "—" }}</dd></div>
              <div><dt>内存</dt><dd>{{ asset.memory || "—" }}</dd></div>
              <div><dt>硬盘</dt><dd>{{ asset.storage || "—" }}</dd></div>
              <div><dt>有线 MAC</dt><dd>{{ asset.wired_mac || "—" }}</dd></div>
              <div><dt>无线 MAC</dt><dd>{{ asset.wireless_mac || "—" }}</dd></div>
            </dl>
          </section>
          <section class="detail-card compact-card">
            <p class="eyebrow">设备信息</p>
            <dl>
              <div><dt>资产标签</dt><dd>{{ asset.asset_tag }}</dd></div>
              <div><dt>序列号</dt><dd>{{ asset.serial_number || "—" }}</dd></div>
              <div><dt>金蝶编码</dt><dd>{{ asset.kingdee_code || "—" }}</dd></div>
              <div><dt>采购日期</dt><dd>{{ formatDate(asset.purchase_date) }}</dd></div>
              <div><dt>采购金额</dt><dd>{{ currency(asset.purchase_cost) }}</dd></div>
            </dl>
          </section>
          <section v-if="asset.notes" class="detail-card compact-card note-card">
            <p class="eyebrow">备注</p>
            <p>{{ asset.notes }}</p>
          </section>
        </aside>
      </section>

      <AppModal
        :open="modalOpen"
        :title="currentAction?.label || '办理资产业务'"
        :description="currentAction?.description"
        @close="modalOpen = false"
      >
        <form class="action-form" @submit.prevent="submitAction">
          <label v-if="['assign', 'loan'].includes(actionType)">
            <span>责任人 <b>*</b></span>
            <PersonSearchSelect v-model="actionForm.target_user_id" :users="lookups?.users || []" required />
          </label>
          <label v-if="['accept', 'return', 'transfer', 'repair_complete'].includes(actionType)">
            <span>目标地点 <b v-if="actionType === 'transfer'">*</b></span>
            <select v-model="actionForm.target_location_id" :required="actionType === 'transfer'">
              <option value="">保持或暂不设置</option>
              <option v-for="item in lookups?.locations || []" :key="item.id" :value="item.id">
                {{ item.name }} · {{ item.kind_label }}
              </option>
            </select>
          </label>
          <label v-if="actionType === 'loan'">
            <span>预计归还日期 <b>*</b></span>
            <input v-model="actionForm.expected_return_at" type="date" required />
          </label>
          <label>
            <span>办理说明</span>
            <textarea v-model="actionForm.notes" rows="4" placeholder="填写交接情况、故障或处置依据"></textarea>
          </label>
          <p v-if="actionError" class="form-error">{{ actionError }}</p>
          <div class="modal-actions">
            <button type="button" class="text-button" @click="modalOpen = false">取消</button>
            <button class="primary-button" :disabled="actionLoading">
              {{ actionLoading ? "正在办理…" : `确认${currentAction?.label || "操作"}` }}
            </button>
          </div>
        </form>
      </AppModal>
      <AppModal
        :open="previewImageId !== null"
        title="资产图片"
        @close="previewImageId = null"
      >
        <img
          v-if="previewImageId !== null && imageUrls[previewImageId]"
          class="asset-image-preview"
          :src="imageUrls[previewImageId]"
          alt="资产影像"
        />
      </AppModal>
    </template>
  </div>
</template>
