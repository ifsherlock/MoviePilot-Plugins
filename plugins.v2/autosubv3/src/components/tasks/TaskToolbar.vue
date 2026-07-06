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
  <header class="autosub-toolbar">
    <div class="toolbar-copy">
      <div class="toolbar-title">AI字幕生成(联动版)</div>
      <div class="toolbar-subtitle">{{ status.message || '查看任务数据' }}</div>
    </div>
    <div class="toolbar-actions">
      <VBtn
        class="mobile-touch-target"
        variant="tonal"
        :prepend-icon="sortOrder === 'desc' ? 'mdi-sort-clock-descending' : 'mdi-sort-clock-ascending'"
        @click="toggleSortOrder"
      >
        {{ sortOrder === 'desc' ? '最新在前' : '最早在前' }}
      </VBtn>
      <VBtn
        class="mobile-touch-target"
        variant="tonal"
        prepend-icon="mdi-checkbox-multiple-marked-outline"
        :disabled="!visibleTasks.length"
        @click="emit('toggle-all')"
      >
        {{ allVisibleSelected ? '取消全选' : '全选' }}
      </VBtn>
      <VBtn
        class="mobile-touch-target"
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
        class="mobile-touch-target"
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
        class="mobile-touch-target"
        color="error"
        variant="tonal"
        prepend-icon="mdi-delete-outline"
        :disabled="!deletableSelected.length || operating"
        :loading="operation === 'delete'"
        @click="emit('delete-selected')"
      >
        批量删除
      </VBtn>
      <VBtn class="mobile-touch-target" aria-label="刷新任务" icon="mdi-refresh" variant="text" :loading="loading" @click="emit('refresh')" />
      <VBtn class="mobile-touch-target" aria-label="关闭 AI字幕生成" icon="mdi-close" variant="text" @click="emit('close')" />
    </div>
  </header>
</template>

<style scoped>
.autosub-toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
  min-height: 64px;
  padding: 8px 12px;
  background: rgb(var(--v-theme-surface));
}

.toolbar-copy {
  flex: 1 1 auto;
  min-width: 0;
}

.toolbar-title,
.toolbar-subtitle {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toolbar-title {
  font-size: 1.25rem;
  font-weight: 500;
  line-height: 1.6;
}

.toolbar-subtitle {
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
  line-height: 1.3;
}

.toolbar-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
  align-items: center;
}

@media (max-width: 760px) {
  .autosub-toolbar {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    align-items: start;
    padding: 8px;
  }

  .toolbar-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    width: 100%;
  }

  .toolbar-actions .v-btn:nth-child(3),
  .toolbar-actions .v-btn:nth-child(4),
  .toolbar-actions .v-btn:nth-child(5) {
    flex-basis: 100%;
  }

  .toolbar-actions .v-btn--icon {
    flex: 0 0 auto;
  }
}
</style>

<style>
@media (max-width: 900px) {
  .autosub-page .toolbar-actions .mobile-touch-target {
    --v-btn-height: 46px;
    min-width: 44px;
    min-height: 46px;
  }

  .autosub-page .toolbar-actions .mobile-touch-target:not(.v-btn--icon) {
    flex: 1 1 calc(50% - 8px);
    min-width: 0;
  }

  .autosub-page .toolbar-actions .mobile-touch-target.v-btn--icon {
    width: 46px;
    height: 46px;
  }
}
</style>
