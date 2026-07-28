<script setup lang="ts">
import AppIcon from "./AppIcon.vue";

defineProps<{ title: string; open: boolean; description?: string; wide?: boolean }>();
defineEmits<{ close: [] }>();
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-backdrop" @click.self="$emit('close')">
      <section class="modal-panel" :class="{ 'modal-panel-wide': wide }" role="dialog" aria-modal="true" :aria-label="title">
        <header class="modal-header">
          <div>
            <p class="eyebrow">资产业务</p>
            <h2>{{ title }}</h2>
            <p v-if="description">{{ description }}</p>
          </div>
          <button class="icon-button" aria-label="关闭" @click="$emit('close')">
            <AppIcon name="close" />
          </button>
        </header>
        <div class="modal-body"><slot /></div>
      </section>
    </div>
  </Teleport>
</template>
