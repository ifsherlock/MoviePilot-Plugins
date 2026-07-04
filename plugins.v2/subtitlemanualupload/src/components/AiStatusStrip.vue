<script setup>
import { computed, ref } from 'vue'
import { buildAiStatusDetail } from '../utils/aiStatus'

const props = defineProps({
  aiEnabled: { type: Boolean, default: false },
  aiAvailable: { type: Boolean, default: false },
  aiHasActiveTasks: { type: Boolean, default: false },
  aiTasksLoading: { type: Boolean, default: false },
  aiSummaryText: { type: String, default: '' },
  aiStatus: { type: Object, default: () => ({}) },
})

defineEmits(['open'])

const stripRef = ref(null)
const aiStatusDetail = computed(() => buildAiStatusDetail(props.aiStatus))

defineExpose({
  scrollIntoView(options) {
    stripRef.value?.scrollIntoView?.(options)
  },
  focus(options) {
    stripRef.value?.focus?.(options)
  },
})
</script>

<template>
  <button
    v-if="aiEnabled"
    ref="stripRef"
    class="ai-status-strip"
    :class="{ unavailable: !aiAvailable, active: aiHasActiveTasks }"
    type="button"
    @click="$emit('open')"
  >
    <span class="ai-status-orb">
      <VProgressCircular
        v-if="aiTasksLoading || aiHasActiveTasks"
        size="16"
        width="2"
        indeterminate
      />
      <VIcon v-else icon="mdi-robot-outline" size="18" />
    </span>
    <strong>{{ aiSummaryText }}</strong>
    <em>{{ aiAvailable ? '点击查看当前资源任务' : aiStatusDetail }}</em>
  </button>
</template>

<style scoped>
.ai-status-strip {
  display: flex;
  width: 100%;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 12px;
  border: 1px solid var(--smu-border-active);
  border-radius: 18px;
  background: var(--smu-accent-soft);
  color: var(--smu-text);
  text-align: left;
}

.ai-status-strip.active {
  border-color: var(--smu-border-active);
  box-shadow: inset 0 0 0 1px var(--smu-accent-soft);
}

.ai-status-strip.unavailable {
  background: var(--smu-card-bg-soft);
  color: var(--smu-text-muted);
}

.ai-status-orb {
  display: grid;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 999px;
  background: var(--smu-accent);
  color: var(--smu-accent-text);
}

.ai-status-strip strong {
  font-size: 13px;
  font-weight: 900;
}

.ai-status-strip em {
  min-width: 0;
  overflow: hidden;
  color: var(--smu-text-muted);
  font-size: 12px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
