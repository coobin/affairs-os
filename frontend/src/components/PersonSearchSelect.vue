<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import type { User } from "../types";
import AppIcon from "./AppIcon.vue";

const props = withDefaults(defineProps<{
  modelValue: string | number | null;
  users: User[];
  placeholder?: string;
  emptyLabel?: string;
  required?: boolean;
}>(), {
  placeholder: "输入中文姓名搜索",
  emptyLabel: "未找到匹配人员",
  required: false,
});

const emit = defineEmits<{ "update:modelValue": [value: string] }>();
const root = ref<HTMLElement | null>(null);
const input = ref<HTMLInputElement | null>(null);
const open = ref(false);
const query = ref("");
const activeIndex = ref(0);

const selectedUser = computed(() =>
  props.users.find((user) => String(user.id) === String(props.modelValue || "")),
);
const selectedName = computed(() => selectedUser.value?.display_name.trim() || "");
const filteredUsers = computed(() => {
  const keyword = query.value.trim();
  return [...props.users]
    .filter((user) => !keyword || user.display_name.includes(keyword))
    .sort((left, right) => left.display_name.localeCompare(right.display_name, "zh-CN"));
});

watch(() => props.modelValue, () => {
  if (!open.value) query.value = selectedName.value;
}, { immediate: true });
watch(filteredUsers, () => { activeIndex.value = 0; });

function beginSearch() {
  open.value = true;
  query.value = "";
  activeIndex.value = 0;
}

function choose(user: User) {
  emit("update:modelValue", String(user.id));
  query.value = user.display_name;
  open.value = false;
}

function clearSelection() {
  emit("update:modelValue", "");
  query.value = "";
  open.value = true;
  input.value?.focus();
}

function onInput() {
  open.value = true;
  if (query.value !== selectedName.value) emit("update:modelValue", "");
}

function onInvalid() {
  open.value = true;
  input.value?.focus();
}

function onBlur() {
  window.setTimeout(() => {
    if (root.value && !root.value.contains(document.activeElement)) close();
  }, 0);
}

function close() {
  open.value = false;
  query.value = selectedName.value;
}

function onKeydown(event: KeyboardEvent) {
  if (!open.value && ["ArrowDown", "Enter", " "].includes(event.key)) {
    event.preventDefault();
    beginSearch();
    return;
  }
  if (!open.value) return;
  if (event.key === "ArrowDown") {
    event.preventDefault();
    activeIndex.value = Math.min(activeIndex.value + 1, filteredUsers.value.length - 1);
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    activeIndex.value = Math.max(activeIndex.value - 1, 0);
  } else if (event.key === "Enter" && filteredUsers.value[activeIndex.value]) {
    event.preventDefault();
    choose(filteredUsers.value[activeIndex.value]);
  } else if (event.key === "Escape") {
    event.preventDefault();
    close();
  }
}

function onOutsideClick(event: MouseEvent) {
  if (root.value && !root.value.contains(event.target as Node)) close();
}

onMounted(() => document.addEventListener("mousedown", onOutsideClick));
onBeforeUnmount(() => document.removeEventListener("mousedown", onOutsideClick));
</script>

<template>
  <div ref="root" class="person-search-select" :class="{ open }" @keydown="onKeydown">
    <AppIcon name="search" :size="17" />
    <input
      ref="input"
      v-model="query"
      :placeholder="placeholder"
      autocomplete="off"
      role="combobox"
      aria-autocomplete="list"
      :aria-expanded="open"
      @focus="beginSearch"
      @input="onInput"
      @blur="onBlur"
    />
    <select
      class="person-select-validator"
      :value="String(modelValue || '')"
      :required="required"
      tabindex="-1"
      aria-hidden="true"
      @invalid.prevent="onInvalid"
    >
      <option value=""></option>
      <option v-for="user in users" :key="user.id" :value="String(user.id)">{{ user.display_name }}</option>
    </select>
    <button v-if="modelValue" class="person-select-clear" type="button" title="清除选择" @click="clearSelection">
      <AppIcon name="close" :size="15" />
    </button>
    <div v-if="open" class="person-select-menu" role="listbox">
      <button
        v-for="(user, index) in filteredUsers"
        :key="user.id"
        type="button"
        role="option"
        :aria-selected="String(user.id) === String(modelValue)"
        :class="{ active: index === activeIndex, selected: String(user.id) === String(modelValue) }"
        @mouseenter="activeIndex = index"
        @mousedown.prevent="choose(user)"
      >
        <span class="person-select-avatar">{{ user.display_name.slice(0, 1) }}</span>
        <strong>{{ user.display_name }}</strong>
      </button>
      <p v-if="!filteredUsers.length">{{ emptyLabel }}</p>
    </div>
  </div>
</template>
