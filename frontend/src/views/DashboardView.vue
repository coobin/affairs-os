<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api } from "../api";
import AppIcon from "../components/AppIcon.vue";
import type { Dashboard } from "../types";

defineProps<{ scopes: string[] }>();
const emit = defineEmits<{ navigate: [path: string] }>();
const data = ref<Dashboard | null>(null);
const loading = ref(true);
const error = ref("");

const dateLabel = computed(() =>
  new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date()),
);

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

onMounted(async () => {
  try {
    data.value = await api<Dashboard>("/dashboard/");
  } catch {
    error.value = "工作台数据暂时无法加载，请刷新重试。";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="page dashboard-page">
    <header class="page-intro dashboard-intro">
      <div>
        <p class="eyebrow">{{ dateLabel }}</p>
        <h1>今天的行政处理台</h1>
      </div>
      <div v-if="scopes.includes('assets')" class="intro-actions">
        <button class="secondary-button" @click="emit('navigate', '/assets')">
          <AppIcon name="search" :size="18" />查找资产
        </button>
        <button class="primary-button" @click="emit('navigate', '/assets/new')">
          <AppIcon name="plus" :size="18" />登记资产
        </button>
      </div>
    </header>

    <div v-if="loading" class="loading-block">正在整理资产事项…</div>
    <div v-else-if="error" class="error-block">{{ error }}</div>

    <template v-else-if="data">
      <section v-if="scopes.includes('assets')" class="workbench">
        <div class="ledger-summary">
          <div class="summary-heading">
            <p class="eyebrow">资产总览</p>
            <strong class="big-number">{{ data.summary.total }}</strong>
            <span>件资产在册</span>
          </div>
          <div class="summary-rows">
            <button @click="emit('navigate', '/assets?status=assigned')">
              <span><i class="signal assigned"></i>已分配责任人</span>
              <strong>{{ data.summary.assigned }}</strong>
            </button>
            <button @click="emit('navigate', '/assets?status=available')">
              <span><i class="signal available"></i>在库</span>
              <strong>{{ data.summary.available }}</strong>
            </button>
            <button @click="emit('navigate', '/assets')">
              <span><i class="signal attention"></i>需要关注</span>
              <strong>{{ data.summary.attention }}</strong>
            </button>
          </div>
        </div>

        <div class="task-board">
          <div class="section-title">
            <div>
              <p class="eyebrow">待办事项</p>
              <h2>需要你处理</h2>
            </div>
            <span>{{ data.tasks.warranty_due + data.tasks.overdue_loans + data.tasks.attention }} 项</span>
          </div>

          <button class="task-row" @click="emit('navigate', '/assets')">
            <span class="task-index">01</span>
            <span class="task-copy"><strong>保修即将到期</strong><small>未来 90 天内到期</small></span>
            <strong class="task-count">{{ data.tasks.warranty_due }}</strong>
            <AppIcon name="chevron-right" :size="18" />
          </button>
          <button class="task-row" @click="emit('navigate', '/assets?status=loaned')">
            <span class="task-index">02</span>
            <span class="task-copy"><strong>借用已经超期</strong><small>需要联系借用人归还</small></span>
            <strong class="task-count hot">{{ data.tasks.overdue_loans }}</strong>
            <AppIcon name="chevron-right" :size="18" />
          </button>
          <button class="task-row" @click="emit('navigate', '/assets')">
            <span class="task-index">03</span>
            <span class="task-copy"><strong>已报废资产</strong><small>保留历史记录，不再参与领用</small></span>
            <strong class="task-count">{{ data.tasks.attention }}</strong>
            <AppIcon name="chevron-right" :size="18" />
          </button>
        </div>
      </section>

      <section class="admin-todo-grid">
        <button v-if="scopes.includes('vehicles')" @click="emit('navigate','/vehicles')"><span>派车待审批</span><strong>{{ data.admin_tasks.pending_vehicle_dispatches }}</strong><small>查看用车申请</small></button>
        <button v-if="scopes.includes('vehicles')" @click="emit('navigate','/vehicles')"><span>车辆证照到期</span><strong>{{ data.admin_tasks.due_vehicle_documents }}</strong><small>未来 30 天或已到期</small></button>
        <button v-if="scopes.includes('procurement')" @click="emit('navigate','/procurement')"><span>采购待审批</span><strong>{{ data.admin_tasks.pending_purchase_requests }}</strong><small>查看采购申请</small></button>
        <button v-if="scopes.includes('contracts')" @click="emit('navigate','/contracts')"><span>合同即将到期</span><strong>{{ data.admin_tasks.expiring_contracts }}</strong><small>未来 30 天或已到期</small></button>
      </section>

      <section v-if="scopes.includes('assets')" class="dashboard-lower">
        <div class="activity-panel">
          <div class="section-title">
            <div>
              <p class="eyebrow">最近流转</p>
              <h2>流转记录</h2>
            </div>
            <button class="text-button" @click="emit('navigate', '/assets')">查看全部</button>
          </div>

          <div v-if="data.recent_events.length" class="activity-list">
            <article v-for="event in data.recent_events" :key="event.id">
              <span class="activity-mark"></span>
              <div>
                <strong>{{ event.action_label }}</strong>
                <p>{{ event.notes || "资产信息已更新" }}</p>
              </div>
              <span class="activity-meta">{{ event.actor_name }}<small>{{ formatDate(event.happened_at) }}</small></span>
            </article>
          </div>
          <div v-else class="empty-state">还没有资产流转。登记第一件资产后，记录会出现在这里。</div>
        </div>

        <aside class="quick-panel">
          <p class="eyebrow">快速办理</p>
          <h2>从一个动作开始</h2>
          <button @click="emit('navigate', '/assets')"><AppIcon name="asset" />领用或归还</button>
          <button @click="emit('navigate', '/assets/new')"><AppIcon name="plus" />登记新到资产</button>
        </aside>
      </section>
    </template>
  </div>
</template>
