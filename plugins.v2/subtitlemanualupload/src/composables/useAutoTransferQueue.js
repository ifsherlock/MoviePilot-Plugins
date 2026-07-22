import { computed, ref } from 'vue'

const EMPTY_AUTO_TRANSFER_QUEUE = {
  summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, skipped: 0, failed: 0 },
  tasks: [],
  rate_limits: {},
  season_package_cache: [],
}

export function createEmptyAutoTransferQueue() {
  return {
    summary: { ...EMPTY_AUTO_TRANSFER_QUEUE.summary },
    tasks: [],
    rate_limits: {},
    season_package_cache: [],
  }
}

export function useAutoTransferQueue({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
}) {
  const autoTransferQueue = ref(createEmptyAutoTransferQueue())
  const autoQueueDialog = ref(false)
  const autoQueueMutating = ref(false)
  const autoQueueActionTaskId = ref('')
  let autoQueueTimer = null

  const autoQueueSummary = computed(() => autoTransferQueue.value?.summary || {})
  const autoQueueTasks = computed(() => autoTransferQueue.value?.tasks || [])
  const autoQueueActive = computed(() => Number(autoQueueSummary.value.active || 0) > 0)
  const autoQueueSummaryText = computed(() => {
    const parts = []
    if (autoQueueSummary.value.in_progress) parts.push(`${autoQueueSummary.value.in_progress} 个处理中`)
    if (autoQueueSummary.value.pending) parts.push(`${autoQueueSummary.value.pending} 个排队`)
    if (autoQueueSummary.value.failed) parts.push(`${autoQueueSummary.value.failed} 个失败`)
    if (autoQueueSummary.value.completed) parts.push(`${autoQueueSummary.value.completed} 个完成`)
    if (autoQueueSummary.value.skipped) parts.push(`${autoQueueSummary.value.skipped} 个跳过`)
    return parts.length ? parts.join(' / ') : '暂无自动入库任务'
  })

  function applyAutoTransferSummary(summary) {
    autoTransferQueue.value = { ...autoTransferQueue.value, summary }
  }

  function stopAutoQueuePolling() {
    if (autoQueueTimer) {
      clearTimeout(autoQueueTimer)
      autoQueueTimer = null
    }
  }

  function scheduleAutoQueuePolling() {
    stopAutoQueuePolling()
    if (!autoQueueActive.value) return
    autoQueueTimer = setTimeout(() => {
      loadAutoTransferQueue()
    }, 3000)
  }

  async function loadAutoTransferQueue() {
    try {
      const response = await pluginApi.value.autoTransferQueue()
      autoTransferQueue.value = unwrapResponse(response) || autoTransferQueue.value
      scheduleAutoQueuePolling()
    } catch (err) {
      error.value = errorMessage(err, '读取自动入库队列失败')
    }
  }

  async function retryAutoTransferTask(task, options = {}) {
    if (!task?.id || autoQueueMutating.value) return
    const forceLowConfidence = Boolean(options.forceLowConfidence)
    if (forceLowConfidence && !window.confirm('确认无视智能调轴低可信结果，强制重新处理并直接入库？')) return
    autoQueueMutating.value = true
    autoQueueActionTaskId.value = task.id
    error.value = ''
    try {
      const response = await pluginApi.value.retryAutoTransferTask({
        task_id: task.id,
        force_low_confidence: forceLowConfidence,
      })
      autoTransferQueue.value = unwrapResponse(response) || autoTransferQueue.value
      message.value = response?.message || (forceLowConfidence ? '已强制重试自动入库任务' : '已重试自动入库任务')
      scheduleAutoQueuePolling()
    } catch (err) {
      error.value = errorMessage(err, '重试自动入库任务失败')
    } finally {
      autoQueueMutating.value = false
      autoQueueActionTaskId.value = ''
    }
  }

  async function clearAutoTransferHistory() {
    if (autoQueueMutating.value) return
    if (!window.confirm('确认清空已完成、已跳过和失败的自动入库历史任务？正在处理的任务会保留。')) return
    autoQueueMutating.value = true
    error.value = ''
    try {
      const response = await pluginApi.value.clearAutoTransferHistory()
      autoTransferQueue.value = unwrapResponse(response) || autoTransferQueue.value
      message.value = response?.message || '已清空自动入库历史任务'
    } catch (err) {
      error.value = errorMessage(err, '清空自动入库历史失败')
    } finally {
      autoQueueMutating.value = false
    }
  }

  return {
    autoTransferQueue,
    autoQueueDialog,
    autoQueueMutating,
    autoQueueActionTaskId,
    autoQueueSummary,
    autoQueueTasks,
    autoQueueActive,
    autoQueueSummaryText,
    applyAutoTransferSummary,
    stopAutoQueuePolling,
    scheduleAutoQueuePolling,
    loadAutoTransferQueue,
    retryAutoTransferTask,
    clearAutoTransferHistory,
  }
}
