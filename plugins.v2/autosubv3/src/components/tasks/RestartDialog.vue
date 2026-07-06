<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  restartTargets: {
    type: Array,
    default: () => [],
  },
  restartSourcePolicy: {
    type: String,
    default: 'reuse',
  },
  restartSourceOptions: {
    type: Array,
    default: () => [],
  },
  operation: {
    type: String,
    default: '',
  },
  operating: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'update:restartSourcePolicy', 'confirm'])

const dialog = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})

const sourcePolicy = computed({
  get: () => props.restartSourcePolicy,
  set: value => emit('update:restartSourcePolicy', value),
})
</script>

<template>
  <VDialog
    v-model="dialog"
    class="restart-dialog-overlay"
    content-class="restart-dialog-content"
    max-width="520"
  >
    <VCard class="restart-dialog-card" rounded="lg">
      <VCardTitle class="restart-dialog-title">
        <span>重新生成 AI 字幕</span>
        <span class="restart-dialog-count">{{ restartTargets.length }} 个任务</span>
      </VCardTitle>
      <VCardText class="restart-dialog-body">
        <VAlert
          class="mb-4"
          type="info"
          variant="tonal"
          density="compact"
          :text="`将重新提交 ${restartTargets.length} 个任务；默认沿用原任务来源，并使用当前最新模型配置。`"
        />
        <VSelect
          v-model="sourcePolicy"
          :items="restartSourceOptions"
          label="字幕来源"
          hint="改选来源会写入来源变体后缀，如 .aiasr.srt 或 .aiembedded.srt"
          persistent-hint
        />
      </VCardText>
      <VCardActions class="restart-dialog-actions">
        <VSpacer class="restart-actions-spacer" />
        <VBtn
          class="restart-cancel-action mobile-touch-target"
          variant="text"
          @click="dialog = false"
        >
          取消
        </VBtn>
        <VBtn
          class="restart-confirm-action mobile-touch-target"
          color="primary"
          variant="tonal"
          :loading="operation === 'restart'"
          :disabled="operating || !restartTargets.length"
          @click="emit('confirm')"
        >
          重新生成
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped>
.restart-dialog-card {
  display: flex;
  flex-direction: column;
  max-height: calc(100dvh - 24px);
}

.restart-dialog-title {
  display: flex;
  gap: 10px;
  align-items: baseline;
  justify-content: space-between;
  min-width: 0;
}

.restart-dialog-title span:first-child {
  min-width: 0;
  overflow-wrap: anywhere;
}

.restart-dialog-count {
  flex: 0 0 auto;
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 12px;
  font-weight: 500;
}

.restart-dialog-body {
  min-height: 0;
  overflow-y: auto;
}

@media (max-width: 520px) {
  .restart-dialog-card {
    width: min(100%, 390px);
    max-height: calc(100dvh - 24px);
    margin: 0 auto;
  }

  .restart-dialog-title {
    position: sticky;
    top: 0;
    z-index: 1;
    background: rgb(var(--v-theme-surface));
    padding: 16px 16px 10px;
    white-space: normal;
  }

  .restart-dialog-body {
    padding: 10px 16px;
  }

  .restart-dialog-actions {
    position: sticky;
    bottom: 0;
    z-index: 1;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    border-top: 1px solid rgba(var(--v-border-color), 0.16);
    background: rgb(var(--v-theme-surface));
    padding: 10px 16px calc(12px + env(safe-area-inset-bottom));
  }

  .restart-actions-spacer {
    display: none;
  }

  .restart-cancel-action,
  .restart-confirm-action {
    width: 100%;
  }
}
</style>

<style>
@media (max-width: 520px) {
  .restart-dialog-overlay {
    align-items: end;
    justify-content: center;
  }

  .restart-dialog-content {
    width: calc(100vw - 24px);
    max-height: calc(100dvh - 24px);
    margin: 0 12px 12px;
    z-index: 2;
    pointer-events: auto;
  }
}

@media (max-width: 900px) {
  .restart-dialog-card .mobile-touch-target {
    --v-btn-height: 46px;
    min-width: 44px;
    min-height: 46px;
  }
}

@media (max-width: 520px) {
  .restart-dialog-card .mobile-touch-target {
    width: 100%;
  }
}
</style>
