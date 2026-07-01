import { computed, ref } from 'vue'

const EMPTY_TIMELINE_TASK_DATA = {
  summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, skipped: 0, failed: 0 },
  tasks: [],
  task_by_target: {},
}

export function createEmptyTimelineTaskData() {
  return {
    summary: { ...EMPTY_TIMELINE_TASK_DATA.summary },
    tasks: [],
    task_by_target: {},
  }
}

export function useTimelineTasks({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  visibleTargets,
  selectedSubtitleTargets,
  lockedTargetPayload,
  timelineAvailable,
  timelineNeedsRiskyConfirm,
  timelineMissing,
  confirmRiskyTimelineOffset,
  isStreamTarget,
  timelineResultText,
  loadMatchHistory,
  scheduleHistoryTimelinePolling,
}) {
  const timelineFixing = ref(false)
  const timelineTaskData = ref(createEmptyTimelineTaskData())
  let timelineTaskTimer = null

  const selectedTimelineTargets = computed(() => selectedSubtitleTargets.value.filter(target => !isStreamTarget(target)))

  function applyTimelineTaskData(data) {
    timelineTaskData.value = data || timelineTaskData.value
  }

  function resetTimelineTasks() {
    timelineTaskData.value = createEmptyTimelineTaskData()
    stopTimelinePolling()
  }

  function stopTimelinePolling() {
    if (timelineTaskTimer) {
      clearTimeout(timelineTaskTimer)
      timelineTaskTimer = null
    }
  }

  function scheduleTimelinePolling() {
    stopTimelinePolling()
    if (!Number(timelineTaskData.value?.summary?.active || 0) || !visibleTargets.value.length) return
    timelineTaskTimer = setTimeout(() => {
      loadTimelineTasks({ silent: true })
    }, 4000)
  }

  async function loadTimelineTasks(options = {}) {
    const scopeTargets = Array.isArray(options.targets) && options.targets.length
      ? options.targets
      : visibleTargets.value
    if (!scopeTargets.length) {
      timelineTaskData.value = createEmptyTimelineTaskData()
      stopTimelinePolling()
      return
    }
    try {
      const response = await pluginApi.value.timelineTasks({
        target_ids: scopeTargets.map(item => item.id),
      })
      applyTimelineTaskData(unwrapResponse(response) || timelineTaskData.value)
    } catch (err) {
      if (!options.silent) {
        error.value = errorMessage(err, '读取智能调轴任务失败')
      }
    } finally {
      scheduleTimelinePolling()
    }
  }

  function timelineTaskForTarget(target) {
    if (!target) return null
    return (timelineTaskData.value.task_by_target || {})[target.id] || target.timeline_task || null
  }

  function timelineTaskText(task) {
    if (!task) return '暂无调轴记录'
    if (task.status === 'completed' && task.timeline) {
      return timelineResultText({ timeline: task.timeline })
    }
    return task.message || task.status_label || task.status || '暂无调轴记录'
  }

  async function fixExistingTimeline(items, label = '选中字幕') {
    if (!timelineAvailable.value) {
      error.value = `智能调轴不可用：缺少 ${timelineMissing.value || '依赖'}`
      return
    }
    if (!items.length) {
      error.value = '没有可调轴的历史字幕'
      return
    }
    const confirmed = window.confirm(`确认对${label}提交 ${items.length} 个智能调轴任务？`)
    if (!confirmed) return
    const allowRiskyOffset = timelineNeedsRiskyConfirm.value
    if (allowRiskyOffset && !confirmRiskyTimelineOffset(`${label}智能调轴`)) return
    timelineFixing.value = true
    error.value = ''
    message.value = ''
    try {
      const response = await pluginApi.value.timelineFixExisting({
        items,
        locked_target_ids: lockedTargetPayload(),
        allow_risky_offset: allowRiskyOffset,
      })
      const data = unwrapResponse(response) || {}
      message.value = response?.message || `已提交 ${data.accepted || 0} 个智能调轴任务`
      await loadMatchHistory()
      scheduleHistoryTimelinePolling()
    } catch (err) {
      error.value = errorMessage(err, '提交历史字幕智能调轴失败')
    } finally {
      timelineFixing.value = false
    }
  }

  function fixSelectedDetailTimeline() {
    fixExistingTimeline(
      selectedTimelineTargets.value.map(target => ({ target_id: target.id })),
      '选中集数',
    )
  }

  return {
    timelineFixing,
    timelineTaskData,
    selectedTimelineTargets,
    applyTimelineTaskData,
    resetTimelineTasks,
    stopTimelinePolling,
    scheduleTimelinePolling,
    loadTimelineTasks,
    timelineTaskForTarget,
    timelineTaskText,
    fixExistingTimeline,
    fixSelectedDetailTimeline,
  }
}
