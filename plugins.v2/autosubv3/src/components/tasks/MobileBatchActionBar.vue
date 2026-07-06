<script setup>
defineProps({
  selectedCount: {
    type: Number,
    default: 0,
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
})

const emit = defineEmits(['cancel-selected', 'restart-selected', 'delete-selected'])
</script>

<template>
  <aside v-if="selectedCount" class="autosub-mobile-batch-bar" aria-label="移动端批量操作">
    <div class="batch-count">
      <strong>{{ selectedCount }}</strong>
      <span>个已选</span>
    </div>
    <div class="batch-actions">
      <VBtn
        class="batch-primary-action mobile-touch-target"
        color="primary"
        variant="flat"
        :disabled="!restartableSelected.length || operating"
        :loading="operation === 'restart'"
        @click="emit('restart-selected')"
      >
        重跑
      </VBtn>
      <VBtn
        class="batch-secondary-action mobile-touch-target"
        color="warning"
        variant="tonal"
        :disabled="!cancellableSelected.length || operating"
        :loading="operation === 'cancel'"
        @click="emit('cancel-selected')"
      >
        取消
      </VBtn>
      <VBtn
        class="batch-danger-action mobile-touch-target"
        color="error"
        variant="text"
        :disabled="!deletableSelected.length || operating"
        :loading="operation === 'delete'"
        @click="emit('delete-selected')"
      >
        删除
      </VBtn>
    </div>
  </aside>
</template>

<style scoped>
.autosub-mobile-batch-bar {
  display: none;
}

@media (max-width: 760px) {
  .autosub-mobile-batch-bar {
    position: sticky;
    bottom: calc(72px + env(safe-area-inset-bottom));
    z-index: 11;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 10px;
    align-items: center;
    margin-top: 12px;
    border: 1px solid rgba(var(--v-border-color), 0.18);
    border-radius: 8px;
    background: rgb(var(--v-theme-surface));
    box-shadow: 0 8px 24px rgba(var(--v-theme-on-surface), 0.12);
    padding: 10px;
  }

  .batch-count {
    display: grid;
    gap: 2px;
    min-width: 58px;
    color: rgba(var(--v-theme-on-surface), 0.68);
    font-size: 12px;
    line-height: 1.2;
  }

  .batch-count strong {
    color: rgb(var(--v-theme-on-surface));
    font-size: 18px;
    line-height: 1;
  }

  .batch-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 72px 72px;
    gap: 8px;
    min-width: 0;
  }

  .batch-primary-action,
  .batch-secondary-action,
  .batch-danger-action {
    min-width: 44px;
    min-height: 46px;
    touch-action: manipulation;
  }
}

@media (max-width: 380px) {
  .autosub-mobile-batch-bar {
    grid-template-columns: 1fr;
  }

  .batch-count {
    grid-template-columns: auto 1fr;
    align-items: baseline;
  }
}
</style>
