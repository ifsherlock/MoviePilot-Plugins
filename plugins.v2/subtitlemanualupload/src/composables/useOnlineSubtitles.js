import { computed, nextTick, ref } from 'vue'
import {
  isForeignOnlineResult,
  isOnlineResultDownloadable,
  onlineProviderItems,
  onlineResultIdentityPriority,
  onlineResultKey,
  onlineResultLanguageFilterCategory,
  onlineResultLanguagePriority,
  providerName,
  providerPriority,
} from '../utils/onlineResult'

const ONLINE_PROVIDER_TIMEOUT_MS = 25000
const ONLINE_DOWNLOAD_TIMEOUT_MS = 35000

export function useOnlineSubtitles({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  selectedMedia,
  selectedTargets,
  selectedSeason,
  batchUploadTargets,
  isLocked,
  lockedTargetPayload,
  compactTargetName,
  aiAvailable,
  timelineNeedsRiskyConfirm,
  confirmRiskyTimelineOffset,
  prepareOnlineUploadState,
  openOnlinePreview,
  closeUploadDialog,
  applyAiTaskData,
  setAiTaskScopeTargets,
  loadAiTasks,
  focusAiStatusStrip,
  applyTimelineTaskData,
  loadTimelineTasks,
}) {
  const onlineSearching = ref(false)
  const onlineDownloading = ref(false)
  const onlinePreviewDownloading = ref(false)
  const onlineAiDownloading = ref(false)
  const onlineError = ref('')
  const onlineDialog = ref(false)
  const onlineAiConfirmDialog = ref(false)
  const onlineTitle = ref('')
  const onlineScope = ref('auto')
  const onlineKeyword = ref('')
  const onlineTargets = ref([])
  const onlineStatus = ref({ providers: [], capabilities: {} })
  const onlineSelectedProviders = ref(['assrt', 'opensubtitles'])
  const onlineResults = ref([])
  const onlineLanguageFilter = ref('all')
  const onlineProviderFilter = ref('all')
  const onlineMessages = ref([])
  const onlineMessagesCollapsed = ref(false)
  const onlineManualLinks = ref([])
  const onlineProviderProgress = ref({})
  const selectedOnlineResultIds = ref([])
  let onlineSearchSeq = 0
  let onlineDownloadSeq = 0

  const hasOnlineResults = computed(() => onlineResults.value.length > 0)
  const filteredOnlineResults = computed(() => {
    return onlineResults.value.filter(item => {
      const languageMatched = onlineLanguageFilter.value === 'all' || onlineResultLanguageFilterCategory(item) === onlineLanguageFilter.value
      const providerMatched = onlineProviderFilter.value === 'all' || item.provider === onlineProviderFilter.value
      return languageMatched && providerMatched
    })
  })
  const onlineLanguageFilterItems = computed(() => {
    const languageItems = [
      { title: '中文', value: 'chinese' },
      { title: '英文', value: 'english' },
      { title: '日文', value: 'japanese' },
      { title: '其他', value: 'other' },
    ]
    const counts = onlineResults.value.reduce((acc, item) => {
      const category = onlineResultLanguageFilterCategory(item)
      acc[category] = (acc[category] || 0) + 1
      return acc
    }, {})
    return [
      { title: `全部 ${onlineResults.value.length}`, value: 'all' },
      ...languageItems.map(item => ({ title: `${item.title} ${counts[item.value] || 0}`, value: item.value })),
    ]
  })
  const onlineProviderFilterItems = computed(() => {
    const counts = onlineResults.value.reduce((acc, item) => {
      const provider = item.provider || 'unknown'
      acc[provider] = (acc[provider] || 0) + 1
      return acc
    }, {})
    return [
      { title: `全部 ${onlineResults.value.length}`, value: 'all' },
      ...onlineProviderItems.map(item => ({ title: `${item.title} ${counts[item.value] || 0}`, value: item.value })),
    ]
  })
  const selectedOnlineResults = computed(() => {
    const picked = new Set(selectedOnlineResultIds.value)
    return onlineResults.value.filter(item => picked.has(onlineResultKey(item)) && isOnlineResultDownloadable(item))
  })
  const canSubmitOnlineAiTranslate = computed(() => {
    return aiAvailable.value && selectedOnlineResults.value.length > 0 && selectedOnlineResults.value.every(isForeignOnlineResult)
  })
  const onlineMessageSummary = computed(() => {
    const messages = onlineMessages.value || []
    if (!messages.length) return ''
    const warnings = messages.filter(item => item.level !== 'info')
    const infos = messages.filter(item => item.level === 'info')
    const source = warnings.length ? warnings : infos
    const text = source
      .slice(0, 3)
      .map(item => item.provider ? `${providerName(item.provider)}：${item.message}` : item.message)
      .join('；')
    const extra = source.length > 3 ? `；另有 ${source.length - 3} 条提示` : ''
    return `${text}${extra}`
  })
  const onlineMessageType = computed(() => {
    return (onlineMessages.value || []).some(item => item.level !== 'info') ? 'warning' : 'info'
  })
  const onlineProviderProgressItems = computed(() => onlineSelectedProviders.value.map(provider => ({
    provider,
    state: onlineProviderProgress.value[provider] || 'idle',
  })))
  const onlineAiConfirmText = computed(() => {
    const count = selectedOnlineResults.value.length
    const targetCount = onlineTargets.value.length
    return `将把当前范围的 ${targetCount} 个目标提交给 AI字幕生成(联动版)；已选择 ${count} 个外语结果，提交后会关闭在线搜索并打开 AI 状态。`
  })
  const onlineBatchLabel = computed(() => {
    if (selectedMedia.value?.media_type !== 'tv') return '搜索在线字幕'
    if (selectedTargets.value.length) return `搜索选中 ${selectedTargets.value.length} 集`
    return selectedSeason.value === 'all' ? '搜索全部季字幕包' : '搜索本季字幕包'
  })

  function ensureConfiguredApiProvidersSelected() {
    const configured = [...(onlineStatus.value?.enabled_providers || [])]
      .filter(provider => onlineProviderItems.some(item => item.value === provider))
    if (onlineStatus.value?.assrt_api_configured) configured.push('assrt')
    if (onlineStatus.value?.opensubtitles_api_configured) configured.push('opensubtitles')
    if (!configured.length) return
    onlineSelectedProviders.value = Array.from(new Set(configured))
  }

  async function loadOnlineStatus() {
    try {
      const response = await pluginApi.value.onlineStatus()
      onlineStatus.value = unwrapResponse(response) || onlineStatus.value
      const enabled = onlineStatus.value.enabled_providers || []
      if (enabled.length) {
        onlineSelectedProviders.value = enabled
      }
      ensureConfiguredApiProvidersSelected()
    } catch (err) {
      onlineError.value = errorMessage(err, '加载在线字幕源状态失败')
    }
  }

  async function openOnlineDialog(scopeTargets, title, scope) {
    const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false)
    if (!usableTargets.length) {
      error.value = '没有可搜索的目标：选中的集数可能都已锁定'
      return
    }
    onlineTitle.value = title
    onlineScope.value = scope
    onlineTargets.value = usableTargets
    prepareOnlineUploadState(usableTargets, title)
    onlineKeyword.value = ''
    onlineResults.value = []
    onlineLanguageFilter.value = 'all'
    onlineProviderFilter.value = 'all'
    onlineMessages.value = []
    onlineMessagesCollapsed.value = false
    onlineManualLinks.value = []
    onlineProviderProgress.value = {}
    selectedOnlineResultIds.value = []
    onlineError.value = ''
    error.value = ''
    message.value = ''
    onlineDialog.value = true
    await loadOnlineStatus()
    await loadOnlineManualLinks()
    await runOnlineSearch()
  }

  function openBatchOnlineSearch() {
    const title = selectedMedia.value?.media_type === 'tv'
      ? onlineBatchLabel.value
      : '搜索在线字幕'
    const scope = selectedMedia.value?.media_type === 'tv'
      ? (selectedTargets.value.length ? 'batch' : 'season')
      : 'movie'
    openOnlineDialog(batchUploadTargets.value, title, scope)
  }

  function openSingleOnlineSearch(target) {
    openOnlineDialog([target], `搜索 ${compactTargetName(target)}`, 'episode')
  }

  function onlinePayload() {
    return {
      target_ids: onlineTargets.value.map(item => item.id),
      locked_target_ids: lockedTargetPayload(),
      media: selectedMedia.value,
      scope: onlineScope.value,
      keyword: onlineKeyword.value.trim(),
      providers: onlineSelectedProviders.value,
    }
  }

  async function loadOnlineManualLinks() {
    if (!onlineTargets.value.length) return
    try {
      const response = await pluginApi.value.onlineManualLinks(onlinePayload())
      const data = unwrapResponse(response) || {}
      onlineManualLinks.value = data.links || []
    } catch (err) {
      onlineError.value = errorMessage(err, '生成手动搜索链接失败')
    }
  }

  async function runOnlineSearch() {
    if (!onlineTargets.value.length || onlineSearching.value) return
    if (!onlineSelectedProviders.value.length) {
      onlineError.value = '请至少选择一个在线字幕源'
      return
    }
    const searchSeq = ++onlineSearchSeq
    const providers = [...onlineSelectedProviders.value]
    const payload = onlinePayload()
    onlineSearching.value = true
    onlineError.value = ''
    onlineResults.value = []
    onlineLanguageFilter.value = 'all'
    onlineProviderFilter.value = 'all'
    onlineMessages.value = []
    onlineMessagesCollapsed.value = false
    selectedOnlineResultIds.value = []
    onlineProviderProgress.value = Object.fromEntries(providers.map(provider => [provider, 'searching']))
    const finishSearch = () => {
      if (searchSeq !== onlineSearchSeq) return
      if (!onlineResults.value.length && !onlineMessages.value.length) {
        onlineMessages.value = [{ level: 'info', message: '没有搜索到可自动下载的字幕，可使用右侧手动搜索链接。' }]
      }
      onlineSearching.value = false
    }
    const searchProvider = async (provider) => {
      try {
        const response = await withTimeout(
          pluginApi.value.onlineSearchProvider({
            ...payload,
            provider,
            providers: [provider],
          }),
          ONLINE_PROVIDER_TIMEOUT_MS,
          `${providerName(provider)} 搜索超时，已保留其它字幕源结果。`,
        )
        if (searchSeq !== onlineSearchSeq) return
        const data = unwrapResponse(response) || {}
        mergeOnlineResults(data.results || [])
        appendOnlineMessages(data.messages || [])
        await nextTick()
        onlineProviderProgress.value = { ...onlineProviderProgress.value, [provider]: 'done' }
      } catch (err) {
        if (searchSeq !== onlineSearchSeq) return
        onlineProviderProgress.value = {
          ...onlineProviderProgress.value,
          [provider]: err?.name === 'TimeoutError' ? 'timeout' : 'error',
        }
        appendOnlineMessages([{
          provider,
          level: err?.name === 'TimeoutError' ? 'info' : 'warning',
          message: errorMessage(err, `${providerName(provider)} 在线字幕搜索失败`),
        }])
      }
    }
    Promise.allSettled(providers.map(provider => searchProvider(provider))).then(finishSearch)
  }

  function stopOnlineSearch() {
    if (!onlineSearching.value) return
    onlineSearchSeq += 1
    onlineSearching.value = false
    onlineProviderProgress.value = Object.fromEntries(
      Object.entries(onlineProviderProgress.value).map(([provider, state]) => [
        provider,
        state === 'searching' ? 'cancelled' : state,
      ]),
    )
    appendOnlineMessages([{ level: 'info', message: '已停止等待未返回的字幕源，已显示的结果会保留。' }])
  }

  function closeOnlineDialog() {
    if (onlineSearching.value) {
      stopOnlineSearch()
    }
    if (onlineDownloading.value) {
      stopOnlineDownload()
    }
    onlineDialog.value = false
  }

  function updateOnlineDialog(value) {
    if (value) {
      onlineDialog.value = true
      return
    }
    closeOnlineDialog()
  }

  function withTimeout(promise, timeoutMs, timeoutMessage) {
    let timer = null
    const timeout = new Promise((resolve, reject) => {
      timer = window.setTimeout(() => {
        const err = new Error(timeoutMessage)
        err.name = 'TimeoutError'
        reject(err)
      }, timeoutMs)
    })
    return Promise.race([promise, timeout]).finally(() => {
      if (timer) window.clearTimeout(timer)
    })
  }

  function mergeOnlineResults(items) {
    const merged = new Map(onlineResults.value.map(item => [onlineResultKey(item), item]))
    ;(items || []).forEach(item => {
      if (item) merged.set(onlineResultKey(item), item)
    })
    onlineResults.value = Array.from(merged.values()).sort((a, b) => {
      const provider = providerPriority(b.provider) - providerPriority(a.provider)
      if (provider) return provider
      const language = onlineResultLanguagePriority(b) - onlineResultLanguagePriority(a)
      if (language) return language
      const identity = onlineResultIdentityPriority(b) - onlineResultIdentityPriority(a)
      if (identity) return identity
      const score = Number(b.score || 0) - Number(a.score || 0)
      if (score) return score
      return providerName(a.provider).localeCompare(providerName(b.provider), 'zh-Hans-CN')
    })
  }

  function appendOnlineMessages(items) {
    const merged = new Map((onlineMessages.value || []).map(item => [`${item.provider || ''}:${item.level || ''}:${item.message || ''}`, item]))
    ;(items || []).forEach(item => {
      if (item?.message) {
        merged.set(`${item.provider || ''}:${item.level || ''}:${item.message || ''}`, item)
      }
    })
    onlineMessages.value = Array.from(merged.values())
  }

  function toggleOnlineResult(item, checked) {
    if (!isOnlineResultDownloadable(item)) return
    const key = onlineResultKey(item)
    const set = new Set(selectedOnlineResultIds.value)
    if (checked) {
      set.add(key)
    } else {
      set.delete(key)
    }
    selectedOnlineResultIds.value = Array.from(set)
  }

  function requestOnlineAiTranslate() {
    if (!selectedOnlineResults.value.length || onlineDownloading.value) return
    if (!canSubmitOnlineAiTranslate.value) {
      onlineError.value = aiAvailable.value
        ? '请只选择外语字幕结果后再提交 AI 翻译。'
        : 'AI 字幕生成联动当前不可用，无法提交翻译任务。'
      return
    }
    onlineError.value = ''
    onlineAiConfirmDialog.value = true
  }

  function confirmOnlineAiTranslate() {
    onlineAiConfirmDialog.value = false
    submitOnlineAiTranslate()
  }

  async function submitOnlineAiTranslate() {
    if (!selectedOnlineResults.value.length || onlineDownloading.value) return
    if (!canSubmitOnlineAiTranslate.value) {
      onlineError.value = aiAvailable.value
        ? '请只选择外语字幕结果后再提交 AI 翻译。'
        : 'AI 字幕生成联动当前不可用，无法提交翻译任务。'
      return
    }
    const allowRiskyOffset = timelineNeedsRiskyConfirm.value
    if (allowRiskyOffset && !confirmRiskyTimelineOffset('在线字幕提交 AI 前智能调轴')) return
    const downloadSeq = ++onlineDownloadSeq
    onlineDownloading.value = true
    onlineAiDownloading.value = true
    onlineError.value = ''
    const submittedTargets = [...onlineTargets.value]
    try {
      const response = await withTimeout(
        pluginApi.value.onlineAiSubmit({
          ...onlinePayload(),
          results: selectedOnlineResults.value,
          allow_risky_offset: allowRiskyOffset,
        }),
        ONLINE_DOWNLOAD_TIMEOUT_MS,
        'AI 字幕任务提交仍在等待响应，已停止等待；可稍后打开 AI 状态刷新查看。',
      )
      if (downloadSeq !== onlineDownloadSeq) return
      const data = unwrapResponse(response) || {}
      const aiResult = data.ai_translate || data
      if (data.tasks) {
        applyAiTaskData(data.tasks)
      } else if (aiResult.tasks) {
        applyAiTaskData(aiResult.tasks)
      }
      if (data.timeline_tasks) {
        applyTimelineTaskData(data.timeline_tasks)
      }
      closeUploadDialog()
      onlineDialog.value = false
      message.value = response?.message || '已提交 AI 字幕翻译任务，请查看 AI 字幕生成状态'
      setAiTaskScopeTargets(submittedTargets)
      await loadAiTasks({ silent: true, targets: submittedTargets })
      await loadTimelineTasks({ silent: true, targets: submittedTargets })
      await focusAiStatusStrip()
    } catch (err) {
      if (downloadSeq !== onlineDownloadSeq) return
      onlineError.value = errorMessage(err, '提交 AI 字幕翻译失败')
    } finally {
      if (downloadSeq === onlineDownloadSeq) {
        onlineDownloading.value = false
        onlineAiDownloading.value = false
      }
    }
  }

  async function downloadOnlinePreview() {
    if (!selectedOnlineResults.value.length || onlineDownloading.value) return
    const downloadSeq = ++onlineDownloadSeq
    onlineDownloading.value = true
    onlinePreviewDownloading.value = true
    onlineError.value = ''
    try {
      const response = await withTimeout(
        pluginApi.value.onlineDownloadPreview({
          ...onlinePayload(),
          results: selectedOnlineResults.value,
        }),
        ONLINE_DOWNLOAD_TIMEOUT_MS,
        '在线字幕下载仍在源站验证中，已停止等待；可换一个结果重试，或打开手动链接下载后上传。',
      )
      if (downloadSeq !== onlineDownloadSeq) return
      const data = unwrapResponse(response) || {}
      openOnlinePreview(data, response?.message || '已下载在线字幕并生成匹配预览')
      onlineDialog.value = false
    } catch (err) {
      if (downloadSeq !== onlineDownloadSeq) return
      onlineError.value = errorMessage(err, '在线字幕下载预览失败')
    } finally {
      if (downloadSeq === onlineDownloadSeq) {
        onlineDownloading.value = false
        onlinePreviewDownloading.value = false
        onlineAiDownloading.value = false
      }
    }
  }

  function stopOnlineDownload() {
    if (!onlineDownloading.value) return
    onlineDownloadSeq += 1
    onlineDownloading.value = false
    onlinePreviewDownloading.value = false
    onlineAiDownloading.value = false
    onlineError.value = '已停止等待在线字幕下载，当前搜索结果仍可继续选择。'
  }

  return {
    onlineSearching,
    onlineDownloading,
    onlinePreviewDownloading,
    onlineAiDownloading,
    onlineError,
    onlineDialog,
    onlineAiConfirmDialog,
    onlineTitle,
    onlineScope,
    onlineKeyword,
    onlineTargets,
    onlineStatus,
    onlineSelectedProviders,
    onlineResults,
    onlineLanguageFilter,
    onlineProviderFilter,
    onlineMessages,
    onlineMessagesCollapsed,
    onlineManualLinks,
    onlineProviderProgress,
    selectedOnlineResultIds,
    hasOnlineResults,
    filteredOnlineResults,
    onlineLanguageFilterItems,
    onlineProviderFilterItems,
    selectedOnlineResults,
    canSubmitOnlineAiTranslate,
    onlineMessageSummary,
    onlineMessageType,
    onlineProviderProgressItems,
    onlineAiConfirmText,
    onlineBatchLabel,
    ensureConfiguredApiProvidersSelected,
    loadOnlineStatus,
    openOnlineDialog,
    openBatchOnlineSearch,
    openSingleOnlineSearch,
    onlinePayload,
    loadOnlineManualLinks,
    runOnlineSearch,
    stopOnlineSearch,
    closeOnlineDialog,
    updateOnlineDialog,
    withTimeout,
    mergeOnlineResults,
    appendOnlineMessages,
    toggleOnlineResult,
    requestOnlineAiTranslate,
    confirmOnlineAiTranslate,
    submitOnlineAiTranslate,
    downloadOnlinePreview,
    stopOnlineDownload,
  }
}
