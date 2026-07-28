<script setup lang="ts">
import { computed } from "vue";

import AppIcon from "../components/AppIcon.vue";

const props = defineProps<{ section: string }>();
const emit = defineEmits<{ navigate: [path: string] }>();

const content = computed(() => {
  const values: Record<string, { eyebrow: string; title: string; description: string; icon: string }> = {
    inventory: { eyebrow: "MVP 下一工作包", title: "数量库存", description: "配件、耗材和许可证库存将在下一工作包接入统一库存流水。", icon: "inventory" },
    stocktake: { eyebrow: "MVP 下一工作包", title: "扫码盘点", description: "盘点任务、应盘快照和连续扫码页面已经列入下一条核心业务链。", icon: "scan" },
    reports: { eyebrow: "MVP 下一工作包", title: "资产报表", description: "这里将提供部门分布、到期、闲置、维修和盘点差异明细。", icon: "chart" },
    settings: { eyebrow: "系统配置", title: "基础设置", description: "分类、地点和组织数据目前可通过 Django 管理后台维护，后续会补充易用页面。", icon: "settings" },
  };
  return values[props.section] || values.inventory;
});
</script>

<template>
  <div class="page placeholder-page">
    <div class="placeholder-icon"><AppIcon :name="content.icon" :size="36" /></div>
    <p class="eyebrow">{{ content.eyebrow }}</p>
    <h1>{{ content.title }}</h1>
    <p>{{ content.description }}</p>
    <button class="primary-button" @click="emit('navigate', '/assets')">
      先管理资产<AppIcon name="chevron-right" :size="18" />
    </button>
  </div>
</template>
