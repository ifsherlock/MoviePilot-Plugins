import { computed, nextTick, ref } from 'vue'

const EMPTY_AI_TASK_DATA = {
  status: null,
  summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, ignored: 0, no_audio: 0, failed: 0, cancelled: 0 },
  tasks: [],
  task_by_target: {},
  tasks_by_target: {},
}

export const aiRestartSourceOptions = [
  { title: '沿用原任务来源', value: 'reuse' },
  { title: '自动选择', value: 'auto' },
  { title: '选中外挂字幕', value: 'matched_external' },
  { title: '本地外挂字幕', value: 'local_external' },
  { title: '视频内嵌字幕', value: 'embedded' },
  { title: '音轨 ASR', value: 'asr' },
]

export function createEmptyAiTaskData(current = {}) {
  return {
    ...current,
    summary: { ...EMPTY_AI_TASK_DATA.summary },
    tasks: [],
    task_by_target: {},
    tasks_by_target: {},
  }
}

export function useAiTasks({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  status,
  visibleTargets,
  selectedMedia,
  selectedSeason,
  selectedTargets,
  batchUploadTargets,
  targetById,
  isLocked,
  lockedTargetPayload,
  isStreamTarget,
  formatBytes,
}) {
  const aiSubmitting = ref(false)
  const aiCancelling = ref(false)
  const aiTasksLoading = ref(false)
  const aiTaskDialog = ref(false)
  const aiTaskDialogTarget = ref(null)
  const aiTaskScopeTargets = ref([])
  const aiTaskLoadToken = ref(0)
  const aiRestartSourcePolicy = ref('reuse')
  const aiRestartSubtitlePath = ref('')
  const aiSelectedTaskIds = ref([])
  const aiStatusStripRef = ref(null)
  const aiTaskData = ref(createEmptyAiTaskData())
  let aiTaskTimer = null

  const aiStatus = computed(() => aiTaskData.value.status || status.value?.ai_subtitle || {})
  const aiEnabled = computed(() => aiStatus.value.enabled !== false)
  const aiAvailable = computed(() => aiEnabled.value && aiStatus.value.available === true)
  const aiSummary = computed(() => aiTaskData.value.summary || {})
  const aiHasActiveTasks = computed(() => Number(aiSummary.value.active || 0) > 0)
  const aiBatchCancelTargets = computed(() => batchUploadTargets.value.filter(target => isAiTaskActive(aiTaskForTarget(target))))
  const aiCapableBatchTargets = computed(() => batchUploadTargets.value.filter(target => !isStreamTarget(target)))
  const aiBatchLabel = computed(() => {
    if (selectedMedia.value?.media_type !== 'tv') return 'AI 生成字幕'
    if (selectedTargets.value.length) return `AI 生成选中 ${selectedTargets.value.length} 集`
    return selectedSeason.value === 'all' ? 'AI 生成全部季' : 'AI 生成本季'
  })
  const aiSummaryText = computed(() => {
    if (!aiEnabled.value) return 'AI 联动已关闭'
    if (!aiStatus.value.installed && !aiStatus.value.available) return aiStatus.value.message || '请先安装并启用 AI字幕生成(联动版)'
    const parts = []
    if (aiSummary.value.in_progress) parts.push(`${aiSummary.value.in_progress} 个生成中`)
    if (aiSummary.value.pending) parts.push(`${aiSummary.value.pending} 个排队`)
    if (aiSummary.value.failed) parts.push(`${aiSummary.value.failed} 个失败`)
    if (aiSummary.value.completed) parts.push(`${aiSummary.value.completed} 个完成`)
    if (aiSummary.value.ignored) parts.push(`${aiSummary.value.ignored} 个忽略`)
    if (aiSummary.value.no_audio) parts.push(`${aiSummary.value.no_audio} 个无音轨`)
    if (aiSummary.value.cancelled) parts.push(`${aiSummary.value.cancelled} 个取消`)
    return parts.length ? `AI：${parts.join(' / ')}` : (aiStatus.value.message || 'AI：暂无当前资源任务')
  })
  const aiDialogTasks = computed(() => {
    const targetId = aiTaskDialogTarget.value?.id
    if (targetId) {
      return (aiTaskData.value.tasks_by_target || {})[targetId] || []
    }
    return aiTaskData.value.tasks || []
  })
  const aiDialogHasExistingTasks = computed(() => Boolean(aiDialogTasks.value.length))
  const aiDialogActiveTasks = computed(() => aiDialogTasks.value.filter(task => isAiTaskActive(task)))
  const aiDialogHasActiveTasks = computed(() => aiDialogActiveTasks.value.length > 0)
  const aiDialogRestartableTasks = computed(() => aiDialogTasks.value.filter(task => isAiTaskRestartable(task)))
  const aiDialogSelectedRestartableTasks = computed(() => {
    const selected = new Set(aiSelectedTaskIds.value)
    return aiDialogRestartableTasks.value.filter(task => selected.has(task.task_id))
  })
  const aiDialogSelectedAllowedTasks = computed(() => aiDialogSelectedRestartableTasks.value.filter(isAiTaskAllowed))
  const aiDialogActionText = computed(() => (aiDialogHasExistingTasks.value ? '重新生成选中' : '生成'))
  const aiDialogSourceLabel = computed(() => (aiDialogHasExistingTasks.value ? '重新生成来源' : '生成来源'))
  const aiRestartSubtitleOptions = computed(() => {
    const target = aiTaskDialogTarget.value
    const subtitles = target?.subtitles || []
    return subtitles
      .filter(subtitle => String(subtitle.ext || '').toLowerCase() === '.srt')
      .map(subtitle => ({
        title: `${subtitle.name} · ${formatBytes(subtitle.size)}`,
        value: subtitle.path,
      }))
  })

  function applyAiTaskData(data) {
    aiTaskData.value = data || aiTaskData.value
    if (aiTaskData.value.status) {
      status.value = { ...status.value, ai_subtitle: aiTaskData.value.status }
    }
  }

  function resetAiTasks() {
    aiTaskDialogTarget.value = null
    aiTaskScopeTargets.value = []
    aiTaskData.value = createEmptyAiTaskData(aiTaskData.value)
    stopAiPolling()
  }

  function stopAiPolling() {
    if (aiTaskTimer) {
      clearTimeout(aiTaskTimer)
      aiTaskTimer = null
    }
  }

  function scheduleAiPolling() {
    stopAiPolling()
    if (!aiHasActiveTasks.value || !currentAiTaskTargets().length) return
    aiTaskTimer = setTimeout(() => {
      loadAiTasks({ silent: true })
    }, 5000)
  }

  function currentAiTaskTargets() {
    return aiTaskScopeTargets.value.length ? aiTaskScopeTargets.value : visibleTargets.value
  }

  async function loadAiTasks(options = {}) {
    const scopeTargets = Array.isArray(options.targets) && options.targets.length
      ? options.targets
      : currentAiTaskTargets()
    const requestToken = options.requestToken || 0
    const requestTargetIds = scopeTargets.map(item => item.id).join('|')
    if (!scopeTargets.length) {
      if (requestToken && requestToken !== aiTaskLoadToken.value) return
      aiTaskData.value = createEmptyAiTaskData(aiTaskData.value)
      stopAiPolling()
      return
    }
    if (!options.silent) aiTasksLoading.value = true
    try {
      const response = await pluginApi.value.aiTasks({
        target_ids: scopeTargets.map(item => item.id),
      })
      if (requestToken && requestToken !== aiTaskLoadToken.value) return
      if (requestToken) {
        const currentTargetIds = currentAiTaskTargets().map(item => item.id).join('|')
        if (currentTargetIds !== requestTargetIds) return
      }
      applyAiTaskData(unwrapResponse(response) || aiTaskData.value)
      aiSelectedTaskIds.value = aiSelectedTaskIds.value.filter(taskId => {
        const task = (aiTaskData.value.tasks || []).find(item => item.task_id === taskId)
        return task && isAiTaskAllowed(task)
      })
    } catch (err) {
      if (!options.silent) {
        error.value = errorMessage(err, '读取 AI 字幕任务失败')
      }
    } finally {
      if (!options.silent) aiTasksLoading.value = false
      scheduleAiPolling()
    }
  }

  function aiTaskForTarget(target) {
    return (aiTaskData.value.task_by_target || {})[target?.id] || null
  }

  function isAiTaskActive(task) {
    return Boolean(task && (task.active || ['pending', 'in_progress'].includes(task.status)))
  }

  function isAiTaskRestartable(task) {
    return Boolean(task && !isAiTaskActive(task) && ['completed', 'failed', 'cancelled', 'ignored', 'no_audio'].includes(task.status))
  }

  function targetForAiTask(task) {
    return targetById.value.get(task?.target_id) || null
  }

  function isAiTaskAllowed(task) {
    if (!isAiTaskRestartable(task)) return false
    const target = targetForAiTask(task)
    if (!target) return false
    return !isLocked(target.id) && target.writable !== false && !isStreamTarget(target)
  }

  function aiTaskColor(target) {
    const task = aiTaskForTarget(target)
    if (!aiAvailable.value) return undefined
    if (!task) return 'primary'
    if (task.status === 'pending') return 'info'
    if (task.status === 'in_progress') return 'warning'
    if (task.status === 'completed') return 'success'
    if (task.status === 'failed') return 'error'
    if (task.status === 'no_audio') return 'grey'
    if (task.status === 'cancelled') return 'grey'
    return 'secondary'
  }

  function aiTaskIcon(target) {
    const task = aiTaskForTarget(target)
    if (!task) return 'mdi-robot-outline'
    if (task.status === 'pending') return 'mdi-clock-outline'
    if (task.status === 'in_progress') return 'mdi-robot-happy-outline'
    if (task.status === 'completed') return 'mdi-check-decagram-outline'
    if (task.status === 'failed') return 'mdi-alert-circle-outline'
    if (task.status === 'no_audio') return 'mdi-volume-off'
    if (task.status === 'cancelled') return 'mdi-cancel'
    return 'mdi-robot-confused-outline'
  }

  function aiTaskTitle(target) {
    const task = aiTaskForTarget(target)
    if (isStreamTarget(target)) return 'STRM 资源暂不支持 AI 生成字幕'
    if (!aiEnabled.value) return 'AI 字幕联动已关闭'
    if (!aiAvailable.value) return aiStatus.value.message || '请先安装并启用 AI字幕生成(联动版)'
    if (!task) return '调用 AI 字幕生成'
    return task.message || task.status_label || '查看 AI 任务状态'
  }

  function aiTaskStatusClass(target) {
    const task = aiTaskForTarget(target)
    return task ? `ai-${task.status}` : 'ai-idle'
  }

  function aiTaskIconForTask(task) {
    if (!task) return 'mdi-robot-outline'
    if (task.status === 'completed') return 'mdi-robot-happy-outline'
    if (task.status === 'failed') return 'mdi-alert-circle-outline'
    if (task.status === 'cancelled') return 'mdi-cancel'
    if (task.status === 'no_audio') return 'mdi-volume-off'
    if (task.status === 'ignored') return 'mdi-debug-step-over'
    if (isAiTaskActive(task)) return 'mdi-progress-clock'
    return 'mdi-robot-outline'
  }

  function aiStatusText(task) {
    if (!task) return '未提交'
    return task.message || task.status_label || task.status
  }

  function openAiTaskDialog(target = null) {
    aiTaskDialogTarget.value = target
    aiRestartSubtitlePath.value = ''
    aiSelectedTaskIds.value = []
    aiTaskDialog.value = true
    const scopeTargets = target
      ? [target]
      : (aiTaskScopeTargets.value.length ? aiTaskScopeTargets.value : visibleTargets.value)
    aiTaskScopeTargets.value = scopeTargets
    const existingTasks = target
      ? (aiTaskForTarget(target) ? [aiTaskForTarget(target)] : [])
      : (aiTaskData.value.tasks || []).filter(task => scopeTargets.some(item => item.id === task.target_id))
    aiRestartSourcePolicy.value = existingTasks.length ? 'reuse' : 'auto'
    const requestToken = ++aiTaskLoadToken.value
    loadAiTasks({ silent: true, targets: scopeTargets, requestToken }).then(() => {
      if (aiTaskDialog.value && requestToken === aiTaskLoadToken.value) {
        aiRestartSourcePolicy.value = aiDialogHasExistingTasks.value ? 'reuse' : 'auto'
      }
    })
  }

  async function focusAiStatusStrip() {
    await nextTick()
    const el = aiStatusStripRef.value
    if (!el) return
    el.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
    el.focus?.({ preventScroll: true })
  }

  async function submitAiForTargets(scopeTargets) {
    return submitAiForTargetsWithOptions(scopeTargets)
  }

  async function submitAiForTargetsWithOptions(scopeTargets, options = {}) {
    const streamCount = scopeTargets.filter(isStreamTarget).length
    const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false)
    const capableTargets = usableTargets.filter(item => !isStreamTarget(item))
    if (!usableTargets.length || !capableTargets.length) {
      error.value = streamCount
        ? 'STRM 资源暂不支持 AI 生成字幕，请选择本地视频文件'
        : '没有可生成 AI 字幕的目标：选中的集数可能都已锁定'
      return
    }
    if (!aiAvailable.value) {
      error.value = aiStatus.value.message || '请先安装并启用 AI字幕生成(联动版)'
      return
    }
    aiSubmitting.value = true
    error.value = ''
    message.value = ''
    try {
      const payload = {
        target_ids: usableTargets.map(item => item.id),
        locked_target_ids: lockedTargetPayload(),
      }
      if (options.source_policy) payload.source_policy = options.source_policy
      if (options.source_subtitle_path) payload.source_subtitle_path = options.source_subtitle_path
      if (options.overwrite_policy) payload.overwrite_policy = options.overwrite_policy
      const response = await pluginApi.value.aiSubmit(payload)
      const data = unwrapResponse(response) || {}
      if (data.tasks) {
        applyAiTaskData(data.tasks)
      }
      aiTaskScopeTargets.value = usableTargets
      message.value = response?.message || '已提交 AI 字幕生成任务'
      await loadAiTasks({ silent: true, targets: usableTargets })
    } catch (err) {
      error.value = errorMessage(err, '提交 AI 字幕任务失败')
    } finally {
      aiSubmitting.value = false
    }
  }

  async function cancelAiForTargets(scopeTargets) {
    const activeTargets = scopeTargets.filter(target => isAiTaskActive(aiTaskForTarget(target)))
    if (!activeTargets.length) {
      message.value = '当前范围没有可取消的 AI 字幕任务'
      return
    }
    aiCancelling.value = true
    error.value = ''
    message.value = ''
    try {
      const response = await pluginApi.value.aiCancel({
        target_ids: activeTargets.map(item => item.id),
        locked_target_ids: lockedTargetPayload(),
      })
      const data = unwrapResponse(response) || {}
      if (data.tasks) {
        applyAiTaskData(data.tasks)
      }
      aiTaskScopeTargets.value = activeTargets
      message.value = response?.message || '已取消 AI 字幕任务'
      await loadAiTasks({ silent: true, targets: activeTargets })
    } catch (err) {
      error.value = errorMessage(err, '取消 AI 字幕任务失败')
    } finally {
      aiCancelling.value = false
    }
  }

  function openBatchAiGenerate() {
    submitAiForTargets(batchUploadTargets.value)
  }

  function cancelBatchAiGenerate() {
    cancelAiForTargets(batchUploadTargets.value)
  }

  function cancelDialogAiTasks() {
    const scopeTargets = aiTaskDialogTarget.value ? [aiTaskDialogTarget.value] : visibleTargets.value
    cancelAiForTargets(scopeTargets)
  }

  async function regenerateDialogAiTasks() {
    const selectedTaskIds = aiDialogSelectedAllowedTasks.value
      .map(task => task.task_id)
    return regenerateAiTasksByIds(selectedTaskIds)
  }

  async function regenerateSingleAiTask(task) {
    if (!isAiTaskAllowed(task)) return
    await regenerateAiTasksByIds([task.task_id])
  }

  async function regenerateAiTasksByIds(taskIds = []) {
    const scopeTargets = aiTaskDialogTarget.value
      ? [aiTaskDialogTarget.value]
      : (aiTaskScopeTargets.value.length ? aiTaskScopeTargets.value : visibleTargets.value)
    const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false && !isStreamTarget(item))
    if (!usableTargets.length) {
      message.value = '没有可重新生成 AI 字幕的目标：选中的集数可能都已锁定或是 STRM'
      return
    }
    if (aiRestartSourcePolicy.value === 'matched_external' && !aiRestartSubtitlePath.value) {
      message.value = '请先选择要用于重新生成的外挂 SRT 字幕'
      return
    }
    const hasExistingTasks = aiDialogHasExistingTasks.value
    if (hasExistingTasks && !taskIds.length) {
      message.value = '请先勾选可重新生成的 AI 历史任务；锁定、不可写、STRM 或正在处理的任务不能重跑'
      return
    }
    const sourcePolicy = !hasExistingTasks && aiRestartSourcePolicy.value === 'reuse'
      ? 'auto'
      : aiRestartSourcePolicy.value
    const overwritePolicy = hasExistingTasks
      ? (sourcePolicy === 'reuse' ? 'backup_replace' : 'new_variant')
      : (sourcePolicy === 'auto' ? 'skip' : 'new_variant')
    if (!hasExistingTasks) {
      await submitAiForTargetsWithOptions(usableTargets, {
        source_policy: sourcePolicy,
        source_subtitle_path: sourcePolicy === 'matched_external' ? aiRestartSubtitlePath.value : '',
        overwrite_policy: overwritePolicy,
      })
      return
    }
    aiSubmitting.value = true
    error.value = ''
    message.value = ''
    try {
      const response = await pluginApi.value.aiRestart({
        target_ids: usableTargets.map(item => item.id),
        task_ids: taskIds,
        locked_target_ids: lockedTargetPayload(),
        source_policy: sourcePolicy,
        source_subtitle_path: sourcePolicy === 'matched_external' ? aiRestartSubtitlePath.value : '',
        overwrite_policy: overwritePolicy,
      })
      const data = unwrapResponse(response) || {}
      if (data.tasks) {
        applyAiTaskData(data.tasks)
      }
      aiTaskScopeTargets.value = usableTargets
      message.value = response?.message || '已重新提交 AI 字幕生成任务'
      await loadAiTasks({ silent: true, targets: usableTargets })
    } catch (err) {
      error.value = errorMessage(err, '重新生成 AI 字幕任务失败')
    } finally {
      aiSubmitting.value = false
    }
  }

  function openSingleAiGenerate(target) {
    openAiTaskDialog(target)
  }

  return {
    aiSubmitting,
    aiCancelling,
    aiTasksLoading,
    aiTaskDialog,
    aiTaskDialogTarget,
    aiTaskScopeTargets,
    aiRestartSourcePolicy,
    aiRestartSubtitlePath,
    aiSelectedTaskIds,
    aiStatusStripRef,
    aiTaskData,
    aiStatus,
    aiEnabled,
    aiAvailable,
    aiSummary,
    aiHasActiveTasks,
    aiBatchCancelTargets,
    aiCapableBatchTargets,
    aiBatchLabel,
    aiSummaryText,
    aiDialogTasks,
    aiDialogHasExistingTasks,
    aiDialogActiveTasks,
    aiDialogHasActiveTasks,
    aiDialogRestartableTasks,
    aiDialogSelectedRestartableTasks,
    aiDialogSelectedAllowedTasks,
    aiDialogActionText,
    aiDialogSourceLabel,
    aiRestartSubtitleOptions,
    applyAiTaskData,
    resetAiTasks,
    stopAiPolling,
    scheduleAiPolling,
    currentAiTaskTargets,
    loadAiTasks,
    aiTaskForTarget,
    isAiTaskActive,
    isAiTaskRestartable,
    targetForAiTask,
    isAiTaskAllowed,
    aiTaskColor,
    aiTaskIcon,
    aiTaskTitle,
    aiTaskStatusClass,
    aiTaskIconForTask,
    aiStatusText,
    openAiTaskDialog,
    focusAiStatusStrip,
    submitAiForTargets,
    submitAiForTargetsWithOptions,
    cancelAiForTargets,
    openBatchAiGenerate,
    cancelBatchAiGenerate,
    cancelDialogAiTasks,
    regenerateDialogAiTasks,
    regenerateSingleAiTask,
    regenerateAiTasksByIds,
    openSingleAiGenerate,
  }
}
