<script setup>
import { computed, onMounted } from 'vue'
import { useAutoSubTasks } from '../composables/useAutoSubTasks'

const props = defineProps({
  api: {
    type: Object,
    default: () => ({}),
  },
  pluginId: {
    type: String,
    default: 'AutoSubv3',
  },
})

const emit = defineEmits(['close'])
const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoSubv3'}`)

const {
  loading,
  operating,
  operation,
  sortOrder,
  statusFilter,
  selectedTaskIds,
  error,
  message,
  status,
  tasks,
  restartDialog,
  restartTargets,
  restartSourcePolicy,
  restartSourceOptions,
  visibleTasks,
  allVisibleSelected,
  cancellableSelected,
  restartableSelected,
  deletableSelected,
  statusChips,
  loadTasks,
  cancelTasks,
  restartTasks,
  confirmRestartTasks,
  deleteTasks,
  toggleTask,
  toggleAll,
  canCancelTask,
  canRestartTask,
  canDeleteTask,
  setStatusFilter,
} = useAutoSubTasks({
  api: () => props.api,
  pluginBase,
})

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

onMounted(loadTasks)
</script>

<template>
  <div class="autosub-page">
    <VToolbar density="comfortable" color="transparent" class="autosub-toolbar">
      <div>
        <div class="text-h6 ms-3">AI字幕生成(联动版)</div>
        <div class="toolbar-subtitle ms-3">{{ status.message || '查看任务数据' }}</div>
      </div>
      <VSpacer />
      <VBtn
        variant="tonal"
        :prepend-icon="sortOrder === 'desc' ? 'mdi-sort-clock-descending' : 'mdi-sort-clock-ascending'"
        @click="sortOrder = sortOrder === 'desc' ? 'asc' : 'desc'"
      >
        {{ sortOrder === 'desc' ? '最新在前' : '最早在前' }}
      </VBtn>
      <VBtn
        variant="tonal"
        prepend-icon="mdi-checkbox-multiple-marked-outline"
        :disabled="!visibleTasks.length"
        @click="toggleAll"
      >
        {{ allVisibleSelected ? '取消全选' : '全选' }}
      </VBtn>
      <VBtn
        color="warning"
        variant="tonal"
        prepend-icon="mdi-cancel"
        :disabled="!cancellableSelected.length || operating"
        :loading="operation === 'cancel'"
        @click="cancelTasks(cancellableSelected)"
      >
        批量取消
      </VBtn>
      <VBtn
        color="primary"
        variant="tonal"
        prepend-icon="mdi-restart"
        :disabled="!restartableSelected.length || operating"
        :loading="operation === 'restart'"
        @click="restartTasks(restartableSelected)"
      >
        批量重新生成
      </VBtn>
      <VBtn
        color="error"
        variant="tonal"
        prepend-icon="mdi-delete-outline"
        :disabled="!deletableSelected.length || operating"
        :loading="operation === 'delete'"
        @click="deleteTasks(deletableSelected)"
      >
        批量删除
      </VBtn>
      <VBtn icon="mdi-refresh" variant="text" :loading="loading" @click="loadTasks" />
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <main class="autosub-content">
      <VAlert v-if="error" class="mb-4" type="error" variant="tonal" :text="error" />
      <VAlert v-if="message" class="mb-4" type="success" variant="tonal" :text="message" />

      <div class="summary-strip">
        <VChip
          v-for="chip in statusChips"
          :key="chip.value"
          size="small"
          class="filter-chip"
          :variant="statusFilter === chip.value ? 'flat' : 'tonal'"
          :color="chip.color || (statusFilter === chip.value ? 'primary' : undefined)"
          @click="setStatusFilter(chip.value)"
        >
          {{ chip.label }} {{ chip.count }}
        </VChip>
      </div>

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
            @update:model-value="value => toggleTask(task, value)"
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
              @click="cancelTasks([task])"
            >
              取消
            </VBtn>
            <VBtn
              size="small"
              color="primary"
              variant="tonal"
              :disabled="!canRestartTask(task) || operating"
              @click="restartTasks([task])"
            >
              重新生成
            </VBtn>
            <VBtn
              size="small"
              color="error"
              variant="tonal"
              :disabled="!canDeleteTask(task) || operating"
              @click="deleteTasks([task])"
            >
              删除
            </VBtn>
          </div>
        </div>
      </div>
    </main>

    <VDialog v-model="restartDialog" max-width="520">
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
            v-model="restartSourcePolicy"
            :items="restartSourceOptions"
            label="字幕来源"
            hint="改选来源会写入来源变体后缀，如 .aiasr.srt 或 .aiembedded.srt"
            persistent-hint
          />
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" @click="restartDialog = false">取消</VBtn>
          <VBtn
            color="primary"
            variant="tonal"
            :loading="operation === 'restart'"
            :disabled="operating || !restartTargets.length"
            @click="confirmRestartTasks"
          >
            重新生成
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>

<style scoped>
.autosub-page {
  min-height: 100%;
  background: rgb(var(--v-theme-background));
}

.autosub-toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgb(var(--v-theme-surface));
}

.toolbar-subtitle {
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
  line-height: 1.3;
}

.autosub-content {
  padding: 18px;
}

.summary-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.filter-chip {
  cursor: pointer;
  user-select: none;
}

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
