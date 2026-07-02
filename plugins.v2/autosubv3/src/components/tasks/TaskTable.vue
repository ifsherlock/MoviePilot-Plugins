<script setup>
defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  tasks: {
    type: Array,
    default: () => [],
  },
  visibleTasks: {
    type: Array,
    default: () => [],
  },
  selectedTaskIds: {
    type: Array,
    default: () => [],
  },
  operating: {
    type: Boolean,
    default: false,
  },
  canCancelTask: {
    type: Function,
    default: () => false,
  },
  canRestartTask: {
    type: Function,
    default: () => false,
  },
  canDeleteTask: {
    type: Function,
    default: () => false,
  },
})

const emit = defineEmits(['toggle-task', 'cancel', 'restart', 'delete'])

function statusColor(task) {
  return {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    failed: 'error',
    cancelled: 'default',
    ignored: 'default',
    no_audio: 'default',
  }[task?.status] || 'default'
}

function pathParts(path) {
  const text = String(path || '')
  const match = text.match(/^(.*?[\\/])((?:Season|S\d{1,2})[^\\/]*(?:[\\/].*)?)$/i)
  if (match) return [match[1], match[2]]
  if (text.length > 72) return [text.slice(0, 72), text.slice(72)]
  return [text]
}

function sourceText(task) {
  const source = task?.resolved_source_label || task?.source_policy_label || task?.source_label || task?.source || ''
  const asset = task?.source_asset_name || task?.source_subtitle_name || ''
  return asset ? `${source} · ${asset}` : source
}
</script>

<template>
  <div v-if="loading && !tasks.length" class="empty-state">正在读取任务...</div>
  <div v-else-if="!tasks.length" class="empty-state">暂无 AI 字幕任务</div>
  <div v-else-if="!visibleTasks.length" class="empty-state">当前筛选暂无任务</div>
  <div v-else class="task-list">
    <div
      v-for="task in visibleTasks"
      :key="task.task_id"
      class="task-row"
      :class="{ selected: selectedTaskIds.includes(task.task_id) }"
    >
      <VCheckbox
        :model-value="selectedTaskIds.includes(task.task_id)"
        density="compact"
        hide-details
        @update:model-value="value => emit('toggle-task', task, value)"
      />
      <div class="task-main">
        <div class="task-title">
          <strong>{{ task.video_name || '未知视频' }}</strong>
          <VChip size="x-small" variant="tonal" :color="statusColor(task)">
            {{ task.status_label || task.status }}
          </VChip>
        </div>
        <div class="task-path">
          <template v-for="(part, index) in pathParts(task.video_file)" :key="`${task.task_id}-${index}`">
            <span>{{ part }}</span>
            <br v-if="index === 0 && pathParts(task.video_file).length > 1">
          </template>
        </div>
        <div class="task-meta">
          <span>{{ task.source_label || task.source }}</span>
          <span v-if="sourceText(task)">{{ sourceText(task) }}</span>
          <span v-if="task.output_name">输出：{{ task.output_name }}</span>
          <span>{{ task.add_time || '-' }}</span>
          <span>{{ task.complete_time || '-' }}</span>
          <span v-if="task.message">{{ task.message }}</span>
        </div>
      </div>
      <div class="task-actions">
        <VBtn
          size="small"
          color="warning"
          variant="tonal"
          :disabled="!canCancelTask(task) || operating"
          @click="emit('cancel', task)"
        >
          取消
        </VBtn>
        <VBtn
          size="small"
          color="primary"
          variant="tonal"
          :disabled="!canRestartTask(task) || operating"
          @click="emit('restart', task)"
        >
          重新生成
        </VBtn>
        <VBtn
          size="small"
          color="error"
          variant="tonal"
          :disabled="!canDeleteTask(task) || operating"
          @click="emit('delete', task)"
        >
          删除
        </VBtn>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-list {
  display: grid;
  gap: 10px;
}

.task-row {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  border: 1px solid rgba(var(--v-border-color), 0.16);
  border-radius: 8px;
  background: rgb(var(--v-theme-surface));
  padding: 12px;
}

.task-row.selected {
  border-color: rgba(var(--v-theme-primary), 0.45);
}

.task-title {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
}

.task-path {
  color: rgba(var(--v-theme-on-surface), 0.74);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 6px;
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 12px;
}

.task-actions {
  display: flex;
  gap: 8px;
}

.empty-state {
  border: 1px dashed rgba(var(--v-border-color), 0.28);
  border-radius: 8px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  padding: 28px;
  text-align: center;
}

@media (max-width: 760px) {
  .task-row {
    grid-template-columns: 36px minmax(0, 1fr);
  }

  .task-actions {
    grid-column: 2;
  }
}
</style>
