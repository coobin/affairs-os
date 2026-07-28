<script setup lang="ts">
defineProps<{ status: string; label: string }>();
</script>

<template>
  <span class="status-pill" :class="`status-${status}`">
    <i aria-hidden="true"></i>{{ label }}
  </span>
</template>
