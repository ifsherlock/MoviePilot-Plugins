<script setup>
import { computed, onMounted, ref } from 'vue'

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
const loading = ref(false)
const operating = ref(false)
const operation = ref('')
const sortOrder = ref('desc')
const statusFilter = ref('all')
const selectedTaskIds = ref([])
const error = ref('')
const message = ref('')
const status = ref({})
const tasks = ref([])

const sortedTasks = computed(() => {
  const items = [...tasks.value]
  items.sort((a, b) => {
    const left = new Date(a.add_time || 0).getTime()
    const right = new Date(b.add_time || 0).getTime()
    return sortOrder.value === 'desc' ? right - left : left - right
  })
  return items
})
const visibleTasks = computed(() => {
  if (statusFilter.value === 'all') return sortedTasks.value
  return sortedTasks.value.filter(task => task.status === statusFilter.value)
})
const visibleTaskIds = computed(() => new Set(visibleTasks.value.map(task => task.task_id)))
const allVisibleSelected = computed(() => (
  Boolean(visibleTasks.value.length)
  && visibleTasks.value.every(task => selectedTaskIds.value.includes(task.task_id))
))
const selectedTasks = computed(() => {
  const picked = new Set(selectedTaskIds.value)
  return visibleTasks.value.filter(task => picked.has(task.task_id))
})
const cancellableSelected = computed(() => selectedTasks.value.filter(canCancelTask))
const restartableSelected = computed(() => selectedTasks.value.filter(canRestartTask))
const deletableSelected = computed(() => selectedTasks.value.filter(canDeleteTask))
const statusChips = computed(() => [
  { value: 'all', label: '总数', count: tasks.value.length },
  { value: 'pending', label: '等待', count: status.value.counts?.pending || 0, color: 'info' },
  { value: 'in_progress', label: '处理中', count: status.value.counts?.in_progress || 0, color: 'warning' },
  { value: 'completed', label: '完成', count: status.value.counts?.completed || 0, color: 'success' },
  { value: 'failed', label: '失败', count: status.value.counts?.failed || 0, color: 'error' },
  { value: 'cancelled', label: '已取消', count: status.value.counts?.cancelled || 0 },
])

function unwrapResponse(response) {
  return response?.data?.data || response?.data || response || {}
}

function errorMessage(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback
}

async function loadTasks() {
  loading.value = true
  error.value = ''
  try {
    const response = await props.api.get(`${pluginBase.value}/tasks?limit=1000`)
    const data = unwrapResponse(response)
    status.value = data.status || {}
    tasks.value = data.tasks || []
    selectedTaskIds.value = selectedTaskIds.value.filter(id => tasks.value.some(task => task.task_id === id))
  } catch (err) {
    error.value = errorMessage(err, '读取 AI 字幕任务失败')
  } finally {
    loading.value = false
  }
}

async function cancelTasks(inputTasks) {
  const picked = (inputTasks || []).filter(canCancelTask)
  if (!picked.length || operating.value) return
  operating.value = true
  operation.value = 'cancel'
  error.value = ''
  message.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/cancel`, {
      task_ids: picked.map(task => task.task_id),
    })
    message.value = response?.message || `已取消 ${picked.length} 个任务`
    await loadTasks()
  } catch (err) {
    error.value = errorMessage(err, '取消 AI 字幕任务失败')
  } finally {
    operation.value = ''
    operating.value = false
  }
}

async function restartTasks(inputTasks) {
  const picked = (inputTasks || []).filter(canRestartTask)
  if (!picked.length || operating.value) return
  operating.value = true
  operation.value = 'restart'
  error.value = ''
  message.value = ''
  try {
    const groups = picked.reduce((acc, task) => {
      const source = task.source || 'manual'
      acc[source] = acc[source] || []
      acc[source].push(task.video_file)
      return acc
    }, {})
    const responses = []
    for (const [source, paths] of Object.entries(groups)) {
      responses.push(await props.api.post(`${pluginBase.value}/submit`, { source, paths }))
    }
    message.value = responses.length === 1
      ? responses[0]?.message || `已重新提交 ${picked.length} 个任务`
      : `已按来源重新提交 ${picked.length} 个任务`
    await loadTasks()
  } catch (err) {
    error.value = errorMessage(err, '重启 AI 字幕任务失败')
  } finally {
    operation.value = ''
    operating.value = false
  }
}

async function deleteTasks(inputTasks) {
  const picked = (inputTasks || []).filter(canDeleteTask)
  if (!picked.length || operating.value) return
  const confirmed = window.confirm(`确定删除 ${picked.length} 个 AI 字幕任务记录吗？`)
  if (!confirmed) return
  operating.value = true
  operation.value = 'delete'
  error.value = ''
  message.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/delete`, {
      task_ids: picked.map(task => task.task_id),
    })
    message.value = response?.message || `已删除 ${picked.length} 个任务记录`
    await loadTasks()
  } catch (err) {
    error.value = errorMessage(err, '删除 AI 字幕任务失败')
  } finally {
    operation.value = ''
    operating.value = false
  }
}

function toggleTask(task, checked) {
  const set = new Set(selectedTaskIds.value)
  if (checked) {
    set.add(task.task_id)
  } else {
    set.delete(task.task_id)
  }
  selectedTaskIds.value = Array.from(set)
}

function toggleAll() {
  if (allVisibleSelected.value) {
    selectedTaskIds.value = selectedTaskIds.value.filter(id => !visibleTaskIds.value.has(id))
    return
  }
  selectedTaskIds.value = Array.from(new Set([
    ...selectedTaskIds.value,
    ...visibleTasks.value.map(task => task.task_id),
  ]))
}

function canCancelTask(task) {
  return Boolean(task?.active || ['pending', 'in_progress'].includes(task?.status))
}

function canRestartTask(task) {
  return Boolean(task?.video_file && ['cancelled', 'failed', 'ignored', 'no_audio'].includes(task?.status))
}

function canDeleteTask(task) {
  return Boolean(task?.task_id && !['in_progress'].includes(task?.status))
}

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

function setStatusFilter(value) {
  statusFilter.value = value
  const visibleIds = new Set(visibleTasks.value.map(task => task.task_id))
  selectedTaskIds.value = selectedTaskIds.value.filter(id => visibleIds.has(id))
}

function pathParts(path) {
  const text = String(path || '')
  const match = text.match(/^(.*?[\\/])((?:Season|S\d{1,2})[^\\/]*(?:[\\/].*)?)$/i)
  if (match) return [match[1], match[2]]
  if (text.length > 72) return [text.slice(0, 72), text.slice(72)]
  return [text]
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
        批量重启
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
              重启
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
