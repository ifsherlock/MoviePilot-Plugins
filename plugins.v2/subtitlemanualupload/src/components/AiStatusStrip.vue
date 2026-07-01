<script setup>
import { ref } from 'vue'

defineProps({
  aiEnabled: { type: Boolean, default: false },
  aiAvailable: { type: Boolean, default: false },
  aiHasActiveTasks: { type: Boolean, default: false },
  aiTasksLoading: { type: Boolean, default: false },
  aiSummaryText: { type: String, default: '' },
  aiStatus: { type: Object, default: () => ({}) },
})

defineEmits(['open'])

const stripRef = ref(null)

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
    <em>{{ aiAvailable ? '点击查看当前资源任务' : aiStatus.message }}</em>
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
  border: 1px solid rgba(165, 118, 46, 0.2);
  border-radius: 18px;
  background: linear-gradient(90deg, rgba(255, 244, 218, 0.9), rgba(235, 242, 236, 0.72));
  color: #31463f;
  text-align: left;
}

.ai-status-strip.active {
  border-color: rgba(190, 135, 48, 0.46);
  box-shadow: inset 0 0 0 1px rgba(190, 135, 48, 0.12);
}

.ai-status-strip.unavailable {
  background: rgba(245, 241, 232, 0.78);
  color: #7a6d61;
}

.ai-status-orb {
  display: grid;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 999px;
  background: #31463f;
  color: #fff8e8;
}

.ai-status-strip strong {
  font-size: 13px;
  font-weight: 900;
}

.ai-status-strip em {
  min-width: 0;
  overflow: hidden;
  color: #687873;
  font-size: 12px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
