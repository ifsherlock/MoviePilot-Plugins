import { computed, ref } from 'vue'

function resolveValue(source) {
  if (typeof source === 'function') return source()
  return source?.value ?? source
}

function unwrapResponse(response) {
  return response?.data?.data || response?.data || response || {}
}

function errorMessage(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback
}

export function canCancelTask(task) {
  return Boolean(task?.active || ['pending', 'in_progress'].includes(task?.status))
}

export function canRestartTask(task) {
  return Boolean(task?.video_file && ['completed', 'cancelled', 'failed', 'ignored', 'no_audio'].includes(task?.status))
}

export function canDeleteTask(task) {
  return Boolean(task?.task_id && !['in_progress'].includes(task?.status))
}

export function useAutoSubTasks({ api, pluginBase, confirmDelete = window.confirm } = {}) {
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
  const restartDialog = ref(false)
  const restartTargets = ref([])
  const restartSourcePolicy = ref('reuse')
  const restartSourceOptions = [
    { title: '沿用原任务来源', value: 'reuse' },
    { title: '自动选择', value: 'auto' },
    { title: '本地外挂字幕', value: 'local_external' },
    { title: '视频内嵌字幕', value: 'embedded' },
    { title: '音轨 ASR', value: 'asr' },
  ]

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

  function apiClient() {
    return resolveValue(api) || {}
  }

  function basePath() {
    return resolveValue(pluginBase)
  }

  async function loadTasks() {
    loading.value = true
    error.value = ''
    try {
      const response = await apiClient().get(`${basePath()}/tasks?limit=1000`)
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
      const response = await apiClient().post(`${basePath()}/cancel`, {
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
    restartTargets.value = picked
    restartSourcePolicy.value = 'reuse'
    restartDialog.value = true
  }

  async function confirmRestartTasks() {
    const picked = (restartTargets.value || []).filter(canRestartTask)
    if (!picked.length || operating.value) return
    operating.value = true
    operation.value = 'restart'
    error.value = ''
    message.value = ''
    try {
      const response = await apiClient().post(`${basePath()}/restart`, {
        task_ids: picked.map(task => task.task_id),
        source_policy: restartSourcePolicy.value,
        overwrite_policy: restartSourcePolicy.value === 'reuse' ? 'backup_replace' : 'new_variant',
      })
      message.value = response?.message || `已重新提交 ${picked.length} 个任务`
      restartDialog.value = false
      await loadTasks()
    } catch (err) {
      error.value = errorMessage(err, '重新生成 AI 字幕任务失败')
    } finally {
      operation.value = ''
      operating.value = false
    }
  }

  async function deleteTasks(inputTasks) {
    const picked = (inputTasks || []).filter(canDeleteTask)
    if (!picked.length || operating.value) return
    const confirmed = confirmDelete(`确定删除 ${picked.length} 个 AI 字幕任务记录吗？`)
    if (!confirmed) return
    operating.value = true
    operation.value = 'delete'
    error.value = ''
    message.value = ''
    try {
      const response = await apiClient().post(`${basePath()}/delete`, {
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

  function setStatusFilter(value) {
    statusFilter.value = value
    const visibleIds = new Set(visibleTasks.value.map(task => task.task_id))
    selectedTaskIds.value = selectedTaskIds.value.filter(id => visibleIds.has(id))
  }

  return {
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
    sortedTasks,
    visibleTasks,
    allVisibleSelected,
    selectedTasks,
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
  }
}
