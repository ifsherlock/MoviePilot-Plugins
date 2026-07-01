<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  autoQueueSummaryText: { type: String, default: '' },
  autoTransferQueue: { type: Object, default: () => ({}) },
  autoQueueTasks: { type: Array, default: () => [] },
})

defineEmits([
  'update:modelValue',
  'load-auto-transfer-queue',
])
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="760"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <VCard class="auto-queue-card" rounded="xl">
      <VCardTitle class="dialog-title">
        <div>
          <span>入库自动字幕队列</span>
          <p>{{ autoQueueSummaryText }}</p>
        </div>
        <div class="online-title-actions">
          <VBtn
            variant="tonal"
            prepend-icon="mdi-refresh"
            @click="$emit('load-auto-transfer-queue')"
          >
            刷新
          </VBtn>
          <VBtn icon="mdi-close" variant="text" @click="$emit('update:modelValue', false)" />
        </div>
      </VCardTitle>
      <VDivider />
      <VCardText>
        <div class="auto-queue-rates">
          <span
            v-for="(rate, provider) in autoTransferQueue.rate_limits || {}"
            :key="provider"
          >
            {{ provider }}：{{ rate.remaining }}/{{ rate.limit_per_minute }} 可用
          </span>
        </div>
        <div v-if="autoQueueTasks.length" class="auto-queue-list">
          <div
            v-for="task in autoQueueTasks.slice().reverse().slice(0, 12)"
            :key="task.id"
            class="auto-queue-row"
            :class="`auto-queue-${task.status}`"
          >
            <strong>{{ task.target_label || task.title || task.id }}</strong>
            <span>{{ task.message || task.status }}<template v-if="task.next_run_at"> · 下次 {{ task.next_run_at }}</template></span>
          </div>
        </div>
        <div v-else class="empty-state compact-empty">
          当前没有入库自动字幕任务。
        </div>
      </VCardText>
    </VCard>
  </VDialog>
</template>

<style scoped>
.auto-queue-card {
  margin-bottom: 14px;
  border: 1px solid rgba(192, 126, 42, 0.18);
  background: linear-gradient(135deg, rgba(255, 246, 226, 0.92), rgba(255, 255, 255, 0.78));
}

.dialog-title {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.dialog-title p {
  margin: 4px 0 0;
  color: #687873;
  font-size: 12px;
  font-weight: 400;
}

.online-title-actions,
.auto-queue-rates,
.auto-queue-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.online-title-actions {
  justify-content: flex-end;
}

.auto-queue-rates {
  justify-content: flex-start;
  flex-wrap: wrap;
  margin-top: 10px;
  color: rgba(35, 42, 39, 0.62);
  font-size: 0.82rem;
}

.auto-queue-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.auto-queue-row {
  border-radius: 14px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.74);
}

.auto-queue-row span {
  color: rgba(35, 42, 39, 0.62);
  font-size: 0.82rem;
}

.auto-queue-failed {
  border: 1px solid rgba(198, 58, 58, 0.24);
}

.auto-queue-in_progress,
.auto-queue-pending {
  border: 1px solid rgba(192, 126, 42, 0.24);
}

.empty-state {
  padding: 28px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.58);
  color: #687873;
  text-align: center;
}

.compact-empty {
  padding: 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.58);
}

@media (max-width: 720px) {
  .dialog-title {
    display: grid;
  }

  .online-title-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
