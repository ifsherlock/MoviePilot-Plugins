import { computed, ref } from 'vue'

const DEFAULT_STATUS = {
  enabled: false,
  source: 'MoviePilot 本地整理记录',
  index: {
    ready: false,
    updated_at: '',
    entry_count: 0,
    media_count: 0,
    expires_in: 0,
  },
  archive_support: {
    zip: true,
    rar: false,
    rar_tool: '',
    rar_tool_path: '/usr/bin/unar',
    rar_python: false,
    rar_python_package: 'rarfile',
    dependency_mode: 'none',
    dependency_status: {},
  },
  timeline_fixer: { available: false, modules: {} },
  ai_subtitle: {
    enabled: true,
    installed: false,
    available: false,
    running: false,
    queue_ready: false,
    plugin_name: 'AI字幕生成(联动版)',
    plugin_version: '',
    message: '请先安装并启用 AI字幕生成(联动版)',
    counts: {},
    updated_at: '',
  },
}

export function usePluginStatus({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  rootTab,
  selectedMedia,
  selectedSeason,
  applyAiStatus,
  applyAutoTransferSummary,
  loadAutoTransferQueue,
  loadTargets,
  loadMatchHistory,
  runSearch,
}) {
  const status = ref({ ...DEFAULT_STATUS })
  const loading = ref(false)
  const refreshing = ref(false)
  let indexRefreshTimer = null

  const indexStatus = computed(() => status.value?.index || {})
  const indexSummary = computed(() => {
    if (!indexStatus.value.ready) return '媒体库清单尚未缓存'
    const parts = [
      `${indexStatus.value.media_count || 0} 个媒体`,
      `${indexStatus.value.entry_count || 0} 个视频`,
    ]
    if (indexStatus.value.updated_at) parts.push(`更新于 ${indexStatus.value.updated_at}`)
    return parts.join(' · ')
  })
  const archiveStatus = computed(() => status.value?.archive_support || { zip: true, rar: false, rar_tool: '', rar_python: false })
  const rarAvailable = computed(() => archiveStatus.value.rar === true)
  const rarPythonAvailable = computed(() => archiveStatus.value.rar_python === true)
  const rarDependencyStatus = computed(() => archiveStatus.value.dependency_status || {})
  const timelineStatus = computed(() => status.value?.timeline_fixer || { available: false, modules: {} })
  const timelineAvailable = computed(() => timelineStatus.value.available === true)
  const timelineConfiguredMaxOffset = computed(() => {
    const value = Number(timelineStatus.value.configured_max_offset_seconds || timelineStatus.value.max_offset_seconds || 120)
    return Number.isFinite(value) && value > 0 ? value : 120
  })
  const timelineNeedsRiskyConfirm = computed(() => timelineConfiguredMaxOffset.value > 120)
  const timelineMissing = computed(() => {
    const missing = []
    if (timelineStatus.value.ffmpeg === false) missing.push('ffmpeg')
    if (timelineStatus.value.ffprobe === false) missing.push('ffprobe')
    const modules = timelineStatus.value.modules || {}
    Object.entries(modules).forEach(([name, ok]) => {
      if (name === 'webrtcvad') return
      if (!ok) missing.push(name)
    })
    return missing.join('、')
  })

  function applyStatus(nextStatus, options = {}) {
    status.value = nextStatus || status.value
    if (status.value.ai_subtitle) {
      applyAiStatus?.(status.value.ai_subtitle)
    }
    if (options.syncAutoTransfer && status.value.auto_transfer_queue) {
      applyAutoTransferSummary?.(status.value.auto_transfer_queue)
      if (Number(status.value.auto_transfer_queue.active || 0) > 0) {
        loadAutoTransferQueue?.()
      }
    }
  }

  async function loadStatus() {
    loading.value = true
    error.value = ''
    try {
      const response = await pluginApi.value.status()
      applyStatus(unwrapResponse(response) || status.value, { syncAutoTransfer: true })
    } catch (err) {
      error.value = errorMessage(err, '加载插件状态失败')
    } finally {
      loading.value = false
    }
  }

  function stopIndexRefreshPolling() {
    if (indexRefreshTimer) {
      clearTimeout(indexRefreshTimer)
      indexRefreshTimer = null
    }
  }

  function scheduleIndexRefreshPolling() {
    stopIndexRefreshPolling()
    if (!status.value?.index?.refreshing) {
      refreshing.value = false
      return
    }
    refreshing.value = true
    indexRefreshTimer = setTimeout(async () => {
      await pollIndexRefresh()
    }, 3000)
  }

  async function pollIndexRefresh() {
    try {
      const response = await pluginApi.value.status()
      const nextStatus = unwrapResponse(response) || status.value
      const wasRefreshing = Boolean(status.value?.index?.refreshing)
      applyStatus(nextStatus)
      if (nextStatus.index?.refresh_error) {
        error.value = nextStatus.index.refresh_error
        refreshing.value = false
        return
      }
      if (wasRefreshing && !nextStatus.index?.refreshing) {
        refreshing.value = false
        if (selectedMedia.value) {
          await loadTargets?.(selectedMedia.value, selectedSeason.value || 'all')
        } else if (rootTab.value === 'history') {
          await loadMatchHistory?.()
        } else {
          await runSearch?.()
        }
        message.value = '媒体库资源清单刷新完成'
        return
      }
      scheduleIndexRefreshPolling()
    } catch (err) {
      refreshing.value = false
      error.value = errorMessage(err, '刷新媒体库清单状态失败')
    }
  }

  async function refreshIndex() {
    refreshing.value = true
    error.value = ''
    try {
      const response = await pluginApi.value.refreshIndex({})
      const data = unwrapResponse(response) || {}
      if (data.index) {
        status.value = { ...status.value, index: data.index }
      }
      if (data.index?.refreshing) {
        scheduleIndexRefreshPolling()
      } else if (selectedMedia.value) {
        await loadTargets?.(selectedMedia.value, selectedSeason.value || 'all')
      } else if (rootTab.value === 'history') {
        await loadMatchHistory?.()
      } else {
        await runSearch?.()
      }
      message.value = response?.message || '已刷新媒体库资源清单'
    } catch (err) {
      error.value = errorMessage(err, '刷新媒体库清单失败')
      refreshing.value = false
    } finally {
      if (!status.value?.index?.refreshing) {
        refreshing.value = false
      }
    }
  }

  return {
    status,
    loading,
    refreshing,
    indexStatus,
    indexSummary,
    archiveStatus,
    rarAvailable,
    rarPythonAvailable,
    rarDependencyStatus,
    timelineStatus,
    timelineAvailable,
    timelineConfiguredMaxOffset,
    timelineNeedsRiskyConfirm,
    timelineMissing,
    loadStatus,
    refreshIndex,
    stopIndexRefreshPolling,
    scheduleIndexRefreshPolling,
  }
}
