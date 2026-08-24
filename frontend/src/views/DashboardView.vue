<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api } from "../api";
import AppIcon from "../components/AppIcon.vue";
import type { Dashboard } from "../types";

const props = defineProps<{ scopes: string[] }>();
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

const taskItems = computed(() => {
  if (!data.value) return [];
  const items: Array<{ label: string; hint: string; count: number; path: string; hot?: boolean }> = [];
  if (props.scopes.includes("assets")) {
    items.push({
      label: "借用已经超期",
      hint: "需要联系借用人归还",
      count: data.value.tasks.overdue_loans,
      path: "/assets?status=loaned&overdue=1",
      hot: true,
    });
  }
  if (props.scopes.includes("contracts")) {
    items.push({
      label: "合同即将到期",
      hint: "到期前45/30/15/7天、当天及逾期每日",
      count: data.value.admin_tasks.expiring_contracts,
      path: "/contracts?due=1",
    });
  }
  if (props.scopes.includes("vehicles")) {
    items.push({
      label: "车辆保险到期",
      hint: "未来 30 天或已到期",
      count: data.value.admin_tasks.vehicle_insurance_due,
      path: "/vehicles?tab=vehicles&insurance_due=1",
    });
  }
  return items;
});

const taskTotal = computed(() => taskItems.value.reduce((total, item) => total + item.count, 0));

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
      <section
        v-if="taskItems.length"
        class="workbench"
        :style="scopes.includes('assets') ? undefined : { gridTemplateColumns: '1fr' }"
      >
        <div v-if="scopes.includes('assets')" class="ledger-summary">
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
          </div>
        </div>

        <div class="task-board">
          <div class="section-title">
            <div>
              <p class="eyebrow">待办事项</p>
              <h2>需要你处理</h2>
            </div>
            <span>{{ taskTotal }} 项</span>
          </div>

          <button v-for="(item, index) in taskItems" :key="item.path" class="task-row" @click="emit('navigate', item.path)">
            <span class="task-index">{{ String(index + 1).padStart(2, '0') }}</span>
            <span class="task-copy"><strong>{{ item.label }}</strong><small>{{ item.hint }}</small></span>
            <strong class="task-count" :class="{ hot: item.hot }">{{ item.count }}</strong>
            <AppIcon name="chevron-right" :size="18" />
          </button>
        </div>
      </section>

      <section class="admin-todo-grid">
        <button v-if="scopes.includes('vehicles')" @click="emit('navigate','/vehicles')"><span>派车待审批</span><strong>{{ data.admin_tasks.pending_vehicle_dispatches }}</strong><small>查看用车申请</small></button>
        <button v-if="scopes.includes('procurement')" @click="emit('navigate','/procurement')"><span>采购待审批</span><strong>{{ data.admin_tasks.pending_purchase_requests }}</strong><small>查看采购申请</small></button>
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
