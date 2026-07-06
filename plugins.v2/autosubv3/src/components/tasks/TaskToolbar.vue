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
      <VBtn class="mobile-refresh-action mobile-touch-target" aria-label="刷新任务" icon="mdi-refresh" variant="text" :loading="loading" @click="emit('refresh')" />
      <VBtn
        class="sort-action mobile-touch-target"
        variant="tonal"
        :prepend-icon="sortOrder === 'desc' ? 'mdi-sort-clock-descending' : 'mdi-sort-clock-ascending'"
        @click="toggleSortOrder"
      >
        {{ sortOrder === 'desc' ? '最新在前' : '最早在前' }}
      </VBtn>
      <VBtn
        class="select-action mobile-touch-target"
        variant="tonal"
        prepend-icon="mdi-checkbox-multiple-marked-outline"
        :disabled="!visibleTasks.length"
        @click="emit('toggle-all')"
      >
        {{ allVisibleSelected ? '取消全选' : '全选' }}
      </VBtn>
      <VBtn
        class="desktop-batch-action mobile-touch-target"
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
        class="desktop-batch-action mobile-touch-target"
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
        class="desktop-batch-action mobile-touch-target"
        color="error"
        variant="tonal"
        prepend-icon="mdi-delete-outline"
        :disabled="!deletableSelected.length || operating"
        :loading="operation === 'delete'"
        @click="emit('delete-selected')"
      >
        批量删除
      </VBtn>
      <VBtn class="desktop-refresh-action mobile-touch-target" aria-label="刷新任务" icon="mdi-refresh" variant="text" :loading="loading" @click="emit('refresh')" />
      <VBtn class="close-action mobile-touch-target" aria-label="关闭 AI字幕生成" icon="mdi-close" variant="text" @click="emit('close')" />
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

.mobile-refresh-action {
  display: none;
}

@media (max-width: 760px) {
  .autosub-toolbar {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 8px;
    align-items: start;
    padding: 8px;
  }

  .toolbar-title {
    font-size: 1.05rem;
    line-height: 1.35;
  }

  .toolbar-actions {
    display: grid;
    grid-template-columns: 46px minmax(0, 1fr) minmax(0, 1fr) 46px;
    gap: 8px;
    width: 100%;
  }

  .desktop-batch-action,
  .desktop-refresh-action {
    display: none;
  }

  .mobile-refresh-action {
    display: inline-grid;
  }

  .sort-action,
  .select-action {
    min-width: 0;
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
    min-width: 0;
  }

  .autosub-page .toolbar-actions .mobile-touch-target.v-btn--icon {
    width: 46px;
    height: 46px;
  }
}
</style>
