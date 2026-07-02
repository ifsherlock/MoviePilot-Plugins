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
    <VCard rounded="lg">
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
