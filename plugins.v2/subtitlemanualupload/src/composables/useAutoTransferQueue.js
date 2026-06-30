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
}) {
  const autoTransferQueue = ref(createEmptyAutoTransferQueue())
  const autoQueueDialog = ref(false)
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
    return parts.length ? parts.join(' / ') : '暂无入库自动字幕任务'
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
      error.value = errorMessage(err, '读取入库自动字幕队列失败')
    }
  }

  return {
    autoTransferQueue,
    autoQueueDialog,
    autoQueueSummary,
    autoQueueTasks,
    autoQueueActive,
    autoQueueSummaryText,
    applyAutoTransferSummary,
    stopAutoQueuePolling,
    scheduleAutoQueuePolling,
    loadAutoTransferQueue,
  }
}
