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
  <VDialog v-model="dialog" max-width="520">
    <VCard class="restart-dialog-card" rounded="lg">
      <VCardTitle>重新生成 AI 字幕</VCardTitle>
      <VCardText>
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
      <VCardActions>
        <VSpacer />
        <VBtn variant="text" @click="dialog = false">取消</VBtn>
        <VBtn
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
  max-height: calc(100dvh - 24px);
}

@media (max-width: 520px) {
  .restart-dialog-card :deep(.v-card-title) {
    white-space: normal;
    overflow-wrap: anywhere;
  }

  .restart-dialog-card :deep(.v-card-text) {
    overflow-y: auto;
  }

  .restart-dialog-card :deep(.v-card-actions) {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .restart-dialog-card :deep(.v-card-actions .v-spacer) {
    display: none;
  }

  .restart-dialog-card :deep(.v-card-actions .v-btn) {
    width: 100%;
  }
}
</style>
