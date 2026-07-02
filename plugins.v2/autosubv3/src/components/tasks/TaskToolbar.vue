<script setup>
const props = defineProps({
  status: {
    type: Object,
    default: () => ({}),
  },
  sortOrder: {
    type: String,
    default: 'desc',
  },
  visibleTasks: {
    type: Array,
    default: () => [],
  },
  allVisibleSelected: {
    type: Boolean,
    default: false,
  },
  cancellableSelected: {
    type: Array,
    default: () => [],
  },
  restartableSelected: {
    type: Array,
    default: () => [],
  },
  deletableSelected: {
    type: Array,
    default: () => [],
  },
  operating: {
    type: Boolean,
    default: false,
  },
  operation: {
    type: String,
    default: '',
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:sortOrder',
  'toggle-all',
  'cancel-selected',
  'restart-selected',
  'delete-selected',
  'refresh',
  'close',
])

function toggleSortOrder() {
  emit('update:sortOrder', props.sortOrder === 'desc' ? 'asc' : 'desc')
}
</script>

<template>
  <VToolbar density="comfortable" color="transparent" class="autosub-toolbar">
    <div>
      <div class="text-h6 ms-3">AI字幕生成(联动版)</div>
      <div class="toolbar-subtitle ms-3">{{ status.message || '查看任务数据' }}</div>
    </div>
    <VSpacer />
    <VBtn
      variant="tonal"
      :prepend-icon="sortOrder === 'desc' ? 'mdi-sort-clock-descending' : 'mdi-sort-clock-ascending'"
      @click="toggleSortOrder"
    >
      {{ sortOrder === 'desc' ? '最新在前' : '最早在前' }}
    </VBtn>
    <VBtn
      variant="tonal"
      prepend-icon="mdi-checkbox-multiple-marked-outline"
      :disabled="!visibleTasks.length"
      @click="emit('toggle-all')"
    >
      {{ allVisibleSelected ? '取消全选' : '全选' }}
    </VBtn>
    <VBtn
      color="warning"
      variant="tonal"
      prepend-icon="mdi-cancel"
      :disabled="!cancellableSelected.length || operating"
      :loading="operation === 'cancel'"
      @click="emit('cancel-selected')"
    >
      批量取消
    </VBtn>
    <VBtn
      color="primary"
      variant="tonal"
      prepend-icon="mdi-restart"
      :disabled="!restartableSelected.length || operating"
      :loading="operation === 'restart'"
      @click="emit('restart-selected')"
    >
      批量重新生成
    </VBtn>
    <VBtn
      color="error"
      variant="tonal"
      prepend-icon="mdi-delete-outline"
      :disabled="!deletableSelected.length || operating"
      :loading="operation === 'delete'"
      @click="emit('delete-selected')"
    >
      批量删除
    </VBtn>
    <VBtn icon="mdi-refresh" variant="text" :loading="loading" @click="emit('refresh')" />
    <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
  </VToolbar>
</template>

<style scoped>
.autosub-toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgb(var(--v-theme-surface));
}

.toolbar-subtitle {
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
  line-height: 1.3;
}
</style>
