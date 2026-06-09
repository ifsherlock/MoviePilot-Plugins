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
const sortOrder = ref('desc')
const selectedTaskIds = ref([])
const error = ref('')
const message = ref('')
const status = ref({})
const tasks = ref([])

const selectedTasks = computed(() => {
  const picked = new Set(selectedTaskIds.value)
  return sortedTasks.value.filter(task => picked.has(task.task_id))
})
const sortedTasks = computed(() => {
  const items = [...tasks.value]
  items.sort((a, b) => {
    const left = new Date(a.add_time || 0).getTime()
    const right = new Date(b.add_time || 0).getTime()
    return sortOrder.value === 'desc' ? right - left : left - right
  })
  return items
})
const cancellableSelected = computed(() => selectedTasks.value.filter(canCancelTask))
const restartableSelected = computed(() => selectedTasks.value.filter(canRestartTask))

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
    operating.value = false
  }
}

async function restartTasks(inputTasks) {
  const picked = (inputTasks || []).filter(canRestartTask)
  if (!picked.length || operating.value) return
  operating.value = true
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
  selectedTaskIds.value = selectedTaskIds.value.length === sortedTasks.value.length
    ? []
    : sortedTasks.value.map(task => task.task_id)
}

function canCancelTask(task) {
  return Boolean(task?.active || ['pending', 'in_progress'].includes(task?.status))
}

function canRestartTask(task) {
  return Boolean(task?.video_file && ['cancelled', 'failed', 'ignored', 'no_audio'].includes(task?.status))
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
        :disabled="!sortedTasks.length"
        @click="toggleAll"
      >
        {{ selectedTaskIds.length === sortedTasks.length ? '取消全选' : '全选' }}
      </VBtn>
      <VBtn
        color="warning"
        variant="tonal"
        prepend-icon="mdi-cancel"
        :disabled="!cancellableSelected.length || operating"
        :loading="operating && Boolean(cancellableSelected.length)"
        @click="cancelTasks(cancellableSelected)"
      >
        批量取消
      </VBtn>
      <VBtn
        color="primary"
        variant="tonal"
        prepend-icon="mdi-restart"
        :disabled="!restartableSelected.length || operating"
        :loading="operating && Boolean(restartableSelected.length)"
        @click="restartTasks(restartableSelected)"
      >
        批量重启
      </VBtn>
      <VBtn icon="mdi-refresh" variant="text" :loading="loading" @click="loadTasks" />
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <main class="autosub-content">
      <VAlert v-if="error" class="mb-4" type="error" variant="tonal" :text="error" />
      <VAlert v-if="message" class="mb-4" type="success" variant="tonal" :text="message" />

      <div class="summary-strip">
        <VChip size="small" variant="tonal">总数 {{ tasks.length }}</VChip>
        <VChip size="small" variant="tonal" color="info">等待 {{ status.counts?.pending || 0 }}</VChip>
        <VChip size="small" variant="tonal" color="warning">处理中 {{ status.counts?.in_progress || 0 }}</VChip>
        <VChip size="small" variant="tonal" color="success">完成 {{ status.counts?.completed || 0 }}</VChip>
        <VChip size="small" variant="tonal" color="error">失败 {{ status.counts?.failed || 0 }}</VChip>
        <VChip size="small" variant="tonal">已取消 {{ status.counts?.cancelled || 0 }}</VChip>
      </div>

      <div v-if="loading && !tasks.length" class="empty-state">正在读取任务...</div>
      <div v-else-if="!tasks.length" class="empty-state">暂无 AI 字幕任务</div>
      <div v-else class="task-list">
        <div
          v-for="task in sortedTasks"
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
