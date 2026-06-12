<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { mediaLabel, targetLabel, unwrapResponse } from '../provider'

const props = defineProps({
  api: {
    type: Object,
    default: () => ({}),
  },
  pluginId: {
    type: String,
    default: 'SubtitleManualUpload',
  },
  navKey: {
    type: String,
    default: 'main',
  },
  hideTitle: {
    type: Boolean,
    default: false,
  },
})

const pluginBase = computed(() => `plugin/${props.pluginId || 'SubtitleManualUpload'}`)
const status = ref({
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
    rar_tool_path: '/usr/local/bin/7z',
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
})

const loading = ref(false)
const searching = ref(false)
const resolving = ref(false)
const refreshing = ref(false)
const preparing = ref(false)
const applying = ref(false)
const clearing = ref(false)
const aiSubmitting = ref(false)
const aiCancelling = ref(false)
const aiTasksLoading = ref(false)
const onlineSearching = ref(false)
const onlineDownloading = ref(false)
const onlinePreviewDownloading = ref(false)
const onlineAiDownloading = ref(false)
const dragging = ref(false)
const message = ref('')
const error = ref('')
const onlineError = ref('')
const searchKeyword = ref('')
const mediaType = ref('all')
const medias = ref([])
const mediaPage = ref(1)
const mediaPageSize = 24
const mediaTotal = ref(0)
const mediaHasMore = ref(false)
const mediaPrefetchPages = ref({})
const failedPosterImages = ref({})
let mediaSearchToken = 0
const rootTab = ref('match')
const matchHistoryLoading = ref(false)
const matchHistoryItems = ref([])
const matchHistoryPage = ref(1)
const matchHistoryPageSize = 20
const matchHistoryTotal = ref(0)
const matchHistoryHasMore = ref(false)
const expandedHistoryIds = ref([])
const expandedHistorySeasonKeys = ref([])
const expandedHistoryTargetIds = ref([])
const expandedDetailTargetIds = ref([])
const selectedHistoryTargetIds = ref({})
const timelineFixing = ref(false)
const autoTransferQueue = ref({
  summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, skipped: 0, failed: 0 },
  tasks: [],
  rate_limits: {},
  season_package_cache: [],
})
const autoQueueDialog = ref(false)
const selectedMedia = ref(null)
const detailTab = ref('match')
const seasons = ref([])
const selectedSeason = ref('all')
const targets = ref([])
const selectedTargetIds = ref([])
const lockedTargetIds = ref([])
const uploadDialog = ref(false)
const rarHelpDialog = ref(false)
const uploadTitle = ref('')
const uploadScopeTargets = ref([])
const files = ref([])
const preview = ref(null)
const fileInputRef = ref(null)
const fixTimeline = ref(false)
const batchLanguageSuffix = ref('')
const copyMessage = ref('')
const copyError = ref('')
const lastWritten = ref([])
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
const aiTaskDialog = ref(false)
const aiTaskDialogTarget = ref(null)
const aiTaskScopeTargets = ref([])
const aiRestartSourcePolicy = ref('reuse')
const aiStatusStripRef = ref(null)
const aiTaskData = ref({
  status: null,
  summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, ignored: 0, no_audio: 0, failed: 0, cancelled: 0 },
  tasks: [],
  task_by_target: {},
})
const timelineTaskData = ref({
  summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, skipped: 0, failed: 0 },
  tasks: [],
  task_by_target: {},
})
let aiTaskTimer = null
let timelineTaskTimer = null
let historyTimelineTimer = null
let autoQueueTimer = null
let onlineSearchSeq = 0
let onlineDownloadSeq = 0
const ONLINE_PROVIDER_TIMEOUT_MS = 25000
const ONLINE_DOWNLOAD_TIMEOUT_MS = 35000

const onlineProviderItems = [
  { title: 'SubHD', value: 'subhd' },
  { title: 'Zimuku', value: 'zimuku' },
  { title: '射手网(伪)', value: 'assrt' },
  { title: 'OpenSubtitles', value: 'opensubtitles' },
]
const aiRestartSourceOptions = [
  { title: '沿用原任务来源', value: 'reuse' },
  { title: '自动选择', value: 'auto' },
  { title: '本地外挂字幕', value: 'local_external' },
  { title: '视频内嵌字幕', value: 'embedded' },
  { title: '音轨 ASR', value: 'asr' },
]

const rarContainerInstallCommand = `docker exec -it moviepilot bash
apt-get update
apt-get install -y p7zip-full unrar-free`
const rarStaticInstallCommand = `curl -fsSLo /tmp/mp-7zz.sh \\
  https://raw.githubusercontent.com/ifsherlock/MoviePilot-Plugins/main/plugins.v2/subtitlemanualupload/scripts/install-static-7zz.sh
sudo bash /tmp/mp-7zz.sh

# 脚本默认优先使用清华/中科大 Gentoo distfiles 镜像下载 7zz。
# 如果自动检测不准，可直接指定 MoviePilot 宿主机映射目录：
sudo env MP_HOST_ROOT=/volume1/docker/moviepilot bash /tmp/mp-7zz.sh

# 如果需要指定下载源，可覆盖 DOWNLOAD_URL：
sudo env DOWNLOAD_URL=https://example.com/7zz.tar.xz bash /tmp/mp-7zz.sh

# 按脚本输出的实际路径添加到 MoviePilot volumes：
volumes:
  - /volume1/docker/moviepilot/tools/7zz:/usr/local/bin/7z:ro

# 重建或重启 MoviePilot 容器后验证：
docker exec moviepilot which 7z
docker exec moviepilot 7z i`
const rarHelpItems = [
  {
    badge: '方案一',
    title: '容器内临时安装',
    description: '适合临时测试，容器重建后可能失效。',
    button: '复制命令',
    copyLabel: '容器安装命令',
    command: rarContainerInstallCommand,
  },
  {
    badge: '方案二',
    title: '静态 7zz 下载并映射',
    description: '推荐长期使用。脚本默认优先使用清华/中科大镜像下载，会检测或提示输入 MoviePilot 宿主机目录，并设置 0755 执行权限。',
    button: '复制方案',
    copyLabel: '静态 7zz 安装映射方案',
    command: rarStaticInstallCommand,
  },
]

const visibleTargets = computed(() => targets.value || [])
const selectedTargets = computed(() => {
  const picked = new Set(selectedTargetIds.value || [])
  return visibleTargets.value.filter(item => picked.has(item.id))
})
const unlockedVisibleTargets = computed(() => visibleTargets.value.filter(item => !isLocked(item.id) && item.writable !== false))
const uploadTargets = computed(() => uploadScopeTargets.value.filter(item => !isLocked(item.id) && item.writable !== false))
const batchUploadTargets = computed(() => {
  const base = selectedTargets.value.length ? selectedTargets.value : visibleTargets.value
  return base.filter(item => !isLocked(item.id) && item.writable !== false)
})
const targetSelectItems = computed(() => uploadTargets.value.map(target => ({
  title: compactTargetName(target),
  value: target.id,
})))
const canPrepare = computed(() => uploadTargets.value.length > 0 && files.value.length > 0)
const canApply = computed(() => {
  const items = selectedPreviewItems.value
  return items.length > 0 && items.every(item => item.target_id)
})
const hasPreviewItems = computed(() => (preview.value?.items || []).length > 0)
const selectedPreviewItems = computed(() => (preview.value?.items || []).filter(item => item.selected !== false))
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
  const tasks = aiTaskData.value.tasks || []
  return targetId ? tasks.filter(item => item.target_id === targetId) : tasks
})
const aiDialogHasActiveTasks = computed(() => aiDialogTasks.value.some(task => isAiTaskActive(task)))
const timelineStatus = computed(() => status.value?.timeline_fixer || { available: false, modules: {} })
const timelineAvailable = computed(() => timelineStatus.value.available === true)
const timelineConfiguredMaxOffset = computed(() => {
  const value = Number(timelineStatus.value.configured_max_offset_seconds || timelineStatus.value.max_offset_seconds || 120)
  return Number.isFinite(value) && value > 0 ? value : 120
})
const timelineNeedsRiskyConfirm = computed(() => timelineConfiguredMaxOffset.value > 120)
const autoQueueSummary = computed(() => autoTransferQueue.value?.summary || status.value?.auto_transfer_queue || {})
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
const selectedPreviewTargets = computed(() => {
  const targetMap = new Map(uploadTargets.value.map(target => [target.id, target]))
  return selectedPreviewItems.value
    .map(item => targetMap.get(item.target_id))
    .filter(Boolean)
})
const allSelectedPreviewTargetsAreStream = computed(() => {
  const items = selectedPreviewTargets.value
  return items.length > 0 && items.every(isStreamTarget)
})
const hasSelectedPreviewStreamTargets = computed(() => selectedPreviewTargets.value.some(isStreamTarget))
const timelineEnabledForApply = computed(() => fixTimeline.value && timelineAvailable.value && !allSelectedPreviewTargetsAreStream.value)
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
const seasonCards = computed(() => {
  if (selectedMedia.value?.media_type !== 'tv') return []
  const total = seasons.value.reduce((sum, item) => sum + Number(item.local_count || 0), 0)
  return [
    { title: '全部季', subtitle: `${total} 集`, value: 'all', count: total },
    ...seasons.value
      .filter(item => item.available)
      .map(item => ({
        title: seasonLabel(item.season),
        subtitle: `${item.local_count || 0} 集`,
        value: item.season,
        count: item.local_count || 0,
      })),
  ]
})
const allVisibleSelected = computed(() => {
  if (!visibleTargets.value.length) return false
  const picked = new Set(selectedTargetIds.value || [])
  return visibleTargets.value.every(item => picked.has(item.id))
})
const matchHistoryRows = computed(() => visibleTargets.value.map(target => {
  const subtitles = target.subtitles || []
  const task = aiTaskForTarget(target)
  const timelineTask = timelineTaskForTarget(target)
  const written = (lastWritten.value || []).filter(item => (
    item.target_label === target.label
    || subtitles.some(subtitle => subtitle.path === item.output_path || subtitle.name === item.output_name)
  ))
  return {
    target,
    subtitles,
    task,
    timelineTask,
    written,
    hasTimelineRunning: applying.value && selectedPreviewTargets.value.some(item => item.id === target.id) && timelineEnabledForApply.value,
  }
}))
const selectedSubtitleTargets = computed(() => selectedTargets.value.filter(target => !isLocked(target.id) && (target.subtitles || []).length))
const selectedTimelineTargets = computed(() => selectedSubtitleTargets.value.filter(target => !isStreamTarget(target)))
const selectedRestorableTargets = computed(() => selectedSubtitleTargets.value.filter(target => (target.subtitles || []).some(subtitle => subtitle.backup_available)))
const matchHistorySummary = computed(() => {
  if (!matchHistoryTotal.value) return '暂无已匹配字幕记录'
  return `${matchHistoryTotal.value} 部资源有外挂字幕记录`
})
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

function formatMediaType(type) {
  return type === 'tv' ? '剧集' : '电影'
}

function rarDependencyModeLabel(mode) {
  if (mode === 'container_install') return '容器内自动安装'
  if (mode === 'mapped_binary') return '宿主机映射文件'
  return '仅检测'
}

function seasonLabel(season) {
  const value = Number(season || 0)
  return value === 0 ? '特别篇' : `第 ${value} 季`
}

function compactTargetName(target) {
  if (!target) return ''
  if (target.media_type !== 'tv') return target.basename || targetLabel(target)
  const season = Number(target.season || 0)
  const episode = Number(target.episode || 0)
  if (season && episode) {
    return `S${String(season).padStart(2, '0')}E${String(episode).padStart(2, '0')} · ${target.basename || targetLabel(target)}`
  }
  return target.basename || targetLabel(target)
}

function mediaStat(media) {
  const count = Number(media?.local_count || 0)
  if (media?.media_type === 'tv') {
    const seasonCount = Number(media?.season_count || 0)
    return `${seasonCount || '-'} 季 · ${count} 集本地资源`
  }
  return `${count || 1} 个本地资源`
}

function posterImageKey(item, url) {
  return `${item?.id || item?.media_id || item?.title || ''}\u0000${url || ''}`
}

function posterImageSrc(item) {
  const url = item?.poster_thumb_url || item?.poster_url || ''
  if (!url || failedPosterImages.value[posterImageKey(item, url)]) return ''
  return url
}

function markPosterFailed(item) {
  const url = item?.poster_thumb_url || item?.poster_url || ''
  if (!url) return
  failedPosterImages.value = {
    ...failedPosterImages.value,
    [posterImageKey(item, url)]: true,
  }
}

function posterLoading(index) {
  return index < 6 ? 'eager' : 'lazy'
}

function posterFetchPriority(index) {
  return index < 6 ? 'high' : 'low'
}

function historyMediaStat(item) {
  const subtitleCount = Number(item?.subtitle_count || 0)
  const targetCount = Number(item?.target_count || 0)
  if (item?.media_type === 'tv') return `${targetCount} 集 · ${subtitleCount} 个外挂字幕`
  return `${subtitleCount} 个外挂字幕`
}

function historyExpanded(item) {
  return expandedHistoryIds.value.includes(item?.id)
}

function toggleHistoryExpanded(item) {
  const id = item?.id
  if (!id) return
  if (expandedHistoryIds.value.includes(id)) {
    expandedHistoryIds.value = expandedHistoryIds.value.filter(value => value !== id)
    return
  }
  expandedHistoryIds.value = [...expandedHistoryIds.value, id]
}

function historySeasonKey(item, group) {
  return `${item?.id || 'history'}:${group?.key || group?.season || 'all'}`
}

function historySeasonExpanded(item, group) {
  return expandedHistorySeasonKeys.value.includes(historySeasonKey(item, group))
}

function toggleHistorySeasonExpanded(item, group) {
  const key = historySeasonKey(item, group)
  if (expandedHistorySeasonKeys.value.includes(key)) {
    expandedHistorySeasonKeys.value = expandedHistorySeasonKeys.value.filter(value => value !== key)
    return
  }
  expandedHistorySeasonKeys.value = [...expandedHistorySeasonKeys.value, key]
}

function historyTargetExpanded(target) {
  return expandedHistoryTargetIds.value.includes(target?.id)
}

function toggleHistoryTargetExpanded(target) {
  const id = target?.id
  if (!id) return
  if (expandedHistoryTargetIds.value.includes(id)) {
    expandedHistoryTargetIds.value = expandedHistoryTargetIds.value.filter(value => value !== id)
    return
  }
  expandedHistoryTargetIds.value = [...expandedHistoryTargetIds.value, id]
}

function historyDeletableTargets(item) {
  return (item?.targets || []).filter(target => target?.id && (target.subtitles || []).length)
}

function historySelectedIds(item) {
  const id = item?.id
  return id ? (selectedHistoryTargetIds.value[id] || []) : []
}

function historySelectedCount(item) {
  const selected = new Set(historySelectedIds(item))
  return historyDeletableTargets(item).filter(target => selected.has(target.id)).length
}

function allHistoryTargetsSelected(item) {
  const targets = historyDeletableTargets(item)
  return targets.length > 0 && historySelectedCount(item) === targets.length
}

function setHistorySelection(item, ids) {
  const itemId = item?.id
  if (!itemId) return
  selectedHistoryTargetIds.value = {
    ...selectedHistoryTargetIds.value,
    [itemId]: Array.from(new Set(ids)),
  }
}

function toggleHistoryTarget(item, targetId, checked) {
  if (!item?.id || !targetId) return
  const selected = new Set(historySelectedIds(item))
  if (checked) {
    selected.add(targetId)
  } else {
    selected.delete(targetId)
  }
  setHistorySelection(item, Array.from(selected))
}

function toggleHistoryItemTargets(item) {
  if (allHistoryTargetsSelected(item)) {
    setHistorySelection(item, [])
    return
  }
  setHistorySelection(item, historyDeletableTargets(item).map(target => target.id))
}

function historySeasonGroups(item) {
  const targets = historyDeletableTargets(item)
  if (!targets.length) return []
  if (item?.media_type !== 'tv') {
    return [
      {
        key: 'movie',
        direct: true,
        targets,
        subtitleCount: targets.reduce((sum, target) => sum + (target.subtitles || []).length, 0),
      },
    ]
  }
  const groups = new Map()
  targets.forEach(target => {
    const season = Number(target.season || 0)
    if (!groups.has(season)) {
      groups.set(season, {
        key: `season-${season}`,
        season,
        label: seasonLabel(season),
        targets: [],
        subtitleCount: 0,
      })
    }
    const group = groups.get(season)
    group.targets.push(target)
    group.subtitleCount += (target.subtitles || []).length
  })
  return Array.from(groups.values()).sort((a, b) => a.season - b.season)
}

function historySeasonSelectedCount(item, group) {
  const selected = new Set(historySelectedIds(item))
  return (group?.targets || []).filter(target => selected.has(target.id)).length
}

function allHistorySeasonTargetsSelected(item, group) {
  const targets = group?.targets || []
  if (!targets.length) return false
  return historySeasonSelectedCount(item, group) === targets.length
}

function historySeasonPartiallySelected(item, group) {
  const count = historySeasonSelectedCount(item, group)
  return count > 0 && count < (group?.targets || []).length
}

function toggleHistorySeasonTargets(item, group, checked) {
  if (!item?.id || !group?.targets?.length) return
  const selected = new Set(historySelectedIds(item))
  ;(group.targets || []).forEach(target => {
    if (!target?.id) return
    if (checked) {
      selected.add(target.id)
    } else {
      selected.delete(target.id)
    }
  })
  setHistorySelection(item, Array.from(selected))
}

async function clearHistoryTargets(item, targetsToClear, label) {
  const targetIds = (targetsToClear || []).map(target => target.id).filter(Boolean)
  if (!targetIds.length || clearing.value) return
  const subtitleCount = (targetsToClear || []).reduce((sum, target) => sum + (target.subtitles || []).length, 0)
  const confirmed = window.confirm(`确认删除${label}的 ${subtitleCount} 个外挂字幕？`)
  if (!confirmed) return
  clearing.value = true
  error.value = ''
  message.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/clear_subtitles`, {
      target_ids: targetIds,
      locked_target_ids: lockedTargetPayload(),
    })
    const data = unwrapResponse(response) || {}
    message.value = response?.message || `已删除 ${data.count || 0} 个外挂字幕`
    setHistorySelection(item, [])
    await loadMatchHistory()
  } catch (err) {
    error.value = errorMessage(err, '批量删除外挂字幕失败')
  } finally {
    clearing.value = false
  }
}

function clearHistorySelectedSubtitles(item) {
  const selected = new Set(historySelectedIds(item))
  const targetsToClear = historyDeletableTargets(item).filter(target => selected.has(target.id))
  clearHistoryTargets(item, targetsToClear, '选中集数')
}

function historyTimelineTargets(item) {
  return historyDeletableTargets(item).filter(target => !isStreamTarget(target) && (target.subtitles || []).length)
}

function historySelectedTimelineTargets(item) {
  const selected = new Set(historySelectedIds(item))
  return historyTimelineTargets(item).filter(target => selected.has(target.id))
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
    const response = await props.api.post(`${pluginBase.value}/timeline_fix_existing`, {
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

function fixHistorySelectedTimeline(item) {
  const targets = historySelectedTimelineTargets(item)
  fixExistingTimeline(targets.map(target => ({ target_id: target.id })), '选中集数')
}

function fixHistorySubtitleTimeline(target, subtitle) {
  if (!target || !subtitle) return
  fixExistingTimeline(
    [{ target_id: target.id, subtitle_path: subtitle.path }],
    subtitle.name || '单个字幕',
  )
}

function detailExpanded(target) {
  return expandedDetailTargetIds.value.includes(target?.id)
}

function toggleDetailExpanded(target) {
  const id = target?.id
  if (!id) return
  if (expandedDetailTargetIds.value.includes(id)) {
    expandedDetailTargetIds.value = expandedDetailTargetIds.value.filter(item => item !== id)
    return
  }
  expandedDetailTargetIds.value = [...expandedDetailTargetIds.value, id]
}

function detailRowForTarget(target) {
  return matchHistoryRows.value.find(row => row.target.id === target?.id) || {
    target,
    subtitles: target?.subtitles || [],
    task: aiTaskForTarget(target),
    timelineTask: timelineTaskForTarget(target),
    written: [],
  }
}

function fixSelectedDetailTimeline() {
  fixExistingTimeline(
    selectedTimelineTargets.value.map(target => ({ target_id: target.id })),
    '选中集数',
  )
}

async function restoreSubtitleBackup(target, subtitle) {
  if (!target || !subtitle) return
  clearing.value = true
  error.value = ''
  message.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/restore_subtitle_backup`, {
      target_id: target.id,
      subtitle_path: subtitle.path,
      subtitle_name: subtitle.name,
      locked_target_ids: lockedTargetPayload(),
    })
    message.value = response?.message || `已恢复调轴前字幕：${subtitle.name}`
    await loadTargets(selectedMedia.value, selectedSeason.value)
  } catch (err) {
    error.value = errorMessage(err, '恢复调轴前字幕失败')
  } finally {
    clearing.value = false
  }
}

async function restoreSelectedBackups() {
  const items = []
  selectedRestorableTargets.value.forEach(target => {
    ;(target.subtitles || []).forEach(subtitle => {
      if (subtitle.backup_available) items.push({ target, subtitle })
    })
  })
  if (!items.length || clearing.value) return
  const confirmed = window.confirm(`确认恢复选中集数的 ${items.length} 个调轴前备份？`)
  if (!confirmed) return
  clearing.value = true
  error.value = ''
  message.value = ''
  try {
    for (const item of items) {
      await props.api.post(`${pluginBase.value}/restore_subtitle_backup`, {
        target_id: item.target.id,
        subtitle_path: item.subtitle.path,
        subtitle_name: item.subtitle.name,
        locked_target_ids: lockedTargetPayload(),
      })
    }
    message.value = `已恢复 ${items.length} 个调轴前备份`
    await loadTargets(selectedMedia.value, selectedSeason.value)
  } catch (err) {
    error.value = errorMessage(err, '批量恢复调轴前字幕失败')
  } finally {
    clearing.value = false
  }
}

function formatBytes(value) {
  const size = Number(value || 0)
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  if (size >= 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${size} B`
}

function formatOffset(value) {
  const number = Number(value || 0)
  return `${number >= 0 ? '+' : ''}${number.toFixed(3)}s`
}

function timelineBaseText(base) {
  const value = String(base || '')
  if (value.startsWith('embedded:')) return '内嵌字幕基准'
  if (value === 'audio:rms' || value === 'audio:rms:cache') return 'RMS 音频检测（低精度）'
  if (value === 'audio:webrtc' || value === 'audio:webrtc:cache') return 'WebRTC 音频检测'
  if (value.startsWith('audio:')) return '音频基准'
  return value || '未知基准'
}

function timelineConfidenceText(value) {
  const known = {
    high: '高可信',
    medium: '中可信',
    low: '低可信',
    rejected: '已拒绝',
  }
  return known[value] || value || '未知可信度'
}

function timelineRiskText(value) {
  const known = {
    offset_over_120s: '偏移超过 120s',
    offset_over_configured_max: '超过配置最大偏移',
    low_score: '匹配分数过低',
    weak_score_margin: '最佳与次优差距过小',
    unstable_subtitle_activity: '字幕活动区间异常',
    unusual_scale_factor: '帧率比例异常',
  }
  return known[value] || value
}

function confirmRiskyTimelineOffset(actionLabel = '智能调轴') {
  if (!timelineNeedsRiskyConfirm.value) return false
  return window.confirm(
    `${actionLabel}当前允许最大偏移 ${timelineConfiguredMaxOffset.value}s。\n\n` +
    '超过 120s 的调轴结果通常意味着错集、错版本或整季包映射错误，不建议超过 120s。\n\n' +
    '确认后，本次请求才会允许 120-300s 的结果人工写入；自动入库不会放行高风险偏移。',
  )
}

function timelineResultText(item) {
  const timeline = item?.timeline || {}
  if (!timeline.enabled) return '未启用智能调轴'
  const base = timelineBaseText(timeline.base)
  if (timeline.applied) {
    return `已调轴 ${formatOffset(timeline.offset_seconds)} · ${base}`
  }
  return `未调整：偏移 ${formatOffset(timeline.offset_seconds)} 小于阈值 · ${base}`
}

function timelineMetaItems(item) {
  const timeline = item?.timeline || item || {}
  if (!timeline.enabled) return []
  const items = []
  if (timeline.confidence) items.push(`置信度：${timelineConfidenceText(timeline.confidence)}`)
  if (timeline.score_margin !== undefined) items.push(`差距：${Number(timeline.score_margin || 0).toFixed(3)}`)
  if (timeline.active_ratio !== undefined) items.push(`活动：${(Number(timeline.active_ratio || 0) * 100).toFixed(1)}%`)
  ;(timeline.risk_flags || []).forEach(flag => items.push(timelineRiskText(flag)))
  return items
}

function errorMessage(err, fallback) {
  return err?.response?.data?.detail
    || err?.response?.data?.message
    || err?.data?.detail
    || err?.data?.message
    || err?.message
    || fallback
}

function buildOutputName(target, item) {
  if (!target) return ''
  const basename = target.basename || 'subtitle'
  const suffix = item?.language_suffix || 'und'
  let ext = item?.ext || '.srt'
  if (!ext.startsWith('.')) ext = `.${ext}`
  return `${basename}.${suffix}${ext.toLowerCase()}`
}

function isLocked(targetId) {
  return lockedTargetIds.value.includes(targetId)
}

function lockedTargetPayload() {
  return [...lockedTargetIds.value]
}

function isStreamTarget(target) {
  if (!target) return false
  if (target.is_stream === true) return true
  const text = `${target.path || ''} ${target.relative_path || ''} ${target.basename || ''}`.toLowerCase()
  return /\.strm(?:$|[\s?#])/.test(text)
}

function isTargetActionDisabled(target) {
  return isLocked(target.id) || target.writable === false
}

function onlineResultKey(item) {
  return `${item?.provider || 'unknown'}:${item?.result_id || item?.page_url || item?.title || ''}`
}

function providerName(providerId) {
  const known = onlineProviderItems.find(item => item.value === providerId)
  return known?.title || providerId || '未知来源'
}

function providerPriority(providerId) {
  if (providerId === 'subhd') return 35
  if (providerId === 'assrt') return 30
  if (providerId === 'zimuku') return 25
  if (providerId === 'opensubtitles') return 20
  return 0
}

function onlineResultMeta(item) {
  const parts = []
  if (item.language) parts.push(item.language)
  if (item.format) parts.push(item.format)
  if (item.season || item.episode) {
    parts.push(`S${String(item.season || 0).padStart(2, '0')}E${String(item.episode || 0).padStart(2, '0')}`)
  }
  if (item.score) parts.push(`匹配 ${item.score}`)
  return parts.join(' · ') || '等待下载后自动匹配'
}

function isOnlineResultDownloadable(item) {
  return item?.downloadable !== false
}

function onlineResultLanguageCategory(item) {
  const category = String(item?.language_category || '').toLowerCase()
  if (['chinese', 'english', 'japanese', 'korean', 'other'].includes(category)) return category
  const text = `${item?.language || ''} ${item?.title || ''} ${item?.note || ''}`.toLowerCase()
  if (
    text.includes('中文')
    || text.includes('简体')
    || text.includes('繁体')
    || text.includes('双语')
    || text.includes('chinese')
    || /(^|[\s._()\[\]-])(zh|ze|chi|chs|cht|zho)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'chinese'
  if (
    text.includes('英文')
    || text.includes('english')
    || /(^|[\s._()\[\]-])(en|eng)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'english'
  if (
    text.includes('日文')
    || text.includes('日语')
    || text.includes('japanese')
    || /(^|[\s._()\[\]-])(ja|jpn)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'japanese'
  if (
    text.includes('korean')
    || /(^|[\s._()\[\]-])(ko|kor)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'korean'
  return 'other'
}

function onlineResultLanguageFilterCategory(item) {
  const category = onlineResultLanguageCategory(item)
  return category === 'korean' ? 'other' : category
}

function onlineResultLanguagePriority(item) {
  const category = onlineResultLanguageCategory(item)
  if (category === 'chinese') return 40
  if (category === 'english') return 30
  if (category === 'japanese' || category === 'korean') return 20
  return 10
}

function onlineResultIdentityPriority(item) {
  const status = String(item?.identity_status || '').toLowerCase()
  if (status === 'strong') return 30
  if (status === 'weak') return 10
  return 0
}

function isForeignOnlineResult(item) {
  return onlineResultLanguageCategory(item) !== 'chinese'
}

function providerProgressText(state) {
  if (state === 'searching') return '搜索中'
  if (state === 'done') return '已完成'
  if (state === 'timeout') return '超时'
  if (state === 'cancelled') return '已停止'
  if (state === 'error') return '失败'
  return '等待'
}

function providerProgressColor(state) {
  if (state === 'searching') return 'info'
  if (state === 'done') return 'success'
  if (state === 'timeout') return 'warning'
  if (state === 'cancelled') return 'default'
  if (state === 'error') return 'warning'
  return 'default'
}

function ensureConfiguredApiProvidersSelected() {
  const configured = [...(onlineStatus.value?.enabled_providers || [])]
    .filter(provider => onlineProviderItems.some(item => item.value === provider))
  if (onlineStatus.value?.assrt_api_configured) configured.push('assrt')
  if (onlineStatus.value?.opensubtitles_api_configured) configured.push('opensubtitles')
  if (!configured.length) return
  onlineSelectedProviders.value = Array.from(new Set(configured))
}

function stopAiPolling() {
  if (aiTaskTimer) {
    clearTimeout(aiTaskTimer)
    aiTaskTimer = null
  }
}

function stopTimelinePolling() {
  if (timelineTaskTimer) {
    clearTimeout(timelineTaskTimer)
    timelineTaskTimer = null
  }
}

function scheduleAiPolling() {
  stopAiPolling()
  if (!aiHasActiveTasks.value || !currentAiTaskTargets().length) return
  aiTaskTimer = setTimeout(() => {
    loadAiTasks({ silent: true })
  }, 5000)
}

function scheduleTimelinePolling() {
  stopTimelinePolling()
  if (!Number(timelineTaskData.value?.summary?.active || 0) || !visibleTargets.value.length) return
  timelineTaskTimer = setTimeout(() => {
    loadTimelineTasks({ silent: true })
  }, 4000)
}

function currentAiTaskTargets() {
  return aiTaskScopeTargets.value.length ? aiTaskScopeTargets.value : visibleTargets.value
}

async function loadAiTasks(options = {}) {
  const scopeTargets = Array.isArray(options.targets) && options.targets.length
    ? options.targets
    : currentAiTaskTargets()
  if (!scopeTargets.length) {
    aiTaskData.value = {
      ...aiTaskData.value,
      summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, ignored: 0, no_audio: 0, failed: 0, cancelled: 0 },
      tasks: [],
      task_by_target: {},
    }
    stopAiPolling()
    return
  }
  if (!options.silent) aiTasksLoading.value = true
  try {
    const response = await props.api.post(`${pluginBase.value}/ai_tasks`, {
      target_ids: scopeTargets.map(item => item.id),
    })
    aiTaskData.value = unwrapResponse(response) || aiTaskData.value
    if (aiTaskData.value.status) {
      status.value = { ...status.value, ai_subtitle: aiTaskData.value.status }
    }
  } catch (err) {
    if (!options.silent) {
      error.value = errorMessage(err, '读取 AI 字幕任务失败')
    }
  } finally {
    if (!options.silent) aiTasksLoading.value = false
    scheduleAiPolling()
  }
}

async function loadTimelineTasks(options = {}) {
  const scopeTargets = Array.isArray(options.targets) && options.targets.length
    ? options.targets
    : visibleTargets.value
  if (!scopeTargets.length) {
    timelineTaskData.value = {
      summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, skipped: 0, failed: 0 },
      tasks: [],
      task_by_target: {},
    }
    stopTimelinePolling()
    return
  }
  try {
    const response = await props.api.post(`${pluginBase.value}/timeline_tasks`, {
      target_ids: scopeTargets.map(item => item.id),
    })
    timelineTaskData.value = unwrapResponse(response) || timelineTaskData.value
  } catch (err) {
    if (!options.silent) {
      error.value = errorMessage(err, '读取智能调轴任务失败')
    }
  } finally {
    scheduleTimelinePolling()
  }
}

function aiTaskForTarget(target) {
  return (aiTaskData.value.task_by_target || {})[target?.id] || null
}

function timelineTaskForTarget(target) {
  if (!target) return null
  return (timelineTaskData.value.task_by_target || {})[target.id] || target.timeline_task || null
}

function isAiTaskActive(task) {
  return Boolean(task && (task.active || ['pending', 'in_progress'].includes(task.status)))
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

function aiStatusText(task) {
  if (!task) return '未提交'
  return task.message || task.status_label || task.status
}

function timelineTaskText(task) {
  if (!task) return '暂无调轴记录'
  if (task.status === 'completed' && task.timeline) {
    return timelineResultText({ timeline: task.timeline })
  }
  return task.message || task.status_label || task.status || '暂无调轴记录'
}

function openAiTaskDialog(target = null) {
  aiTaskDialogTarget.value = target
  aiTaskDialog.value = true
  const scopeTargets = target
    ? [target]
    : (aiTaskScopeTargets.value.length ? aiTaskScopeTargets.value : visibleTargets.value)
  aiTaskScopeTargets.value = scopeTargets
  loadAiTasks({ silent: true, targets: scopeTargets })
}

async function focusAiStatusStrip() {
  await nextTick()
  const el = aiStatusStripRef.value
  if (!el) return
  el.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  el.focus?.({ preventScroll: true })
}

async function submitAiForTargets(scopeTargets) {
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
    const response = await props.api.post(`${pluginBase.value}/ai_submit`, {
      target_ids: usableTargets.map(item => item.id),
      locked_target_ids: lockedTargetPayload(),
    })
    const data = unwrapResponse(response) || {}
    if (data.tasks) {
      aiTaskData.value = data.tasks
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
    const response = await props.api.post(`${pluginBase.value}/ai_cancel`, {
      target_ids: activeTargets.map(item => item.id),
      locked_target_ids: lockedTargetPayload(),
    })
    const data = unwrapResponse(response) || {}
    if (data.tasks) {
      aiTaskData.value = data.tasks
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
  const scopeTargets = aiTaskDialogTarget.value
    ? [aiTaskDialogTarget.value]
    : (aiTaskScopeTargets.value.length ? aiTaskScopeTargets.value : visibleTargets.value)
  const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false && !isStreamTarget(item))
  if (!usableTargets.length) {
    message.value = '没有可重新生成 AI 字幕的目标：选中的集数可能都已锁定或是 STRM'
    return
  }
  aiSubmitting.value = true
  error.value = ''
  message.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/ai_restart`, {
      target_ids: usableTargets.map(item => item.id),
      locked_target_ids: lockedTargetPayload(),
      source_policy: aiRestartSourcePolicy.value,
      overwrite_policy: aiRestartSourcePolicy.value === 'reuse' ? 'backup_replace' : 'new_variant',
    })
    const data = unwrapResponse(response) || {}
    if (data.tasks) {
      aiTaskData.value = data.tasks
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
  const task = aiTaskForTarget(target)
  if (task) {
    openAiTaskDialog(target)
    return
  }
  submitAiForTargets([target])
}

function clearTargetState() {
  seasons.value = []
  detailTab.value = 'match'
  selectedSeason.value = 'all'
  targets.value = []
  selectedTargetIds.value = []
  preview.value = null
  lastWritten.value = []
  aiTaskDialogTarget.value = null
  aiTaskScopeTargets.value = []
  aiTaskData.value = {
    ...aiTaskData.value,
    summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, ignored: 0, no_audio: 0, failed: 0, cancelled: 0 },
    tasks: [],
    task_by_target: {},
  }
  timelineTaskData.value = {
    summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, skipped: 0, failed: 0 },
    tasks: [],
    task_by_target: {},
  }
  stopAiPolling()
  stopTimelinePolling()
}

async function loadStatus() {
  loading.value = true
  error.value = ''
  try {
    const response = await props.api.get(`${pluginBase.value}/status`)
    status.value = unwrapResponse(response) || status.value
    if (status.value.ai_subtitle) {
      aiTaskData.value = { ...aiTaskData.value, status: status.value.ai_subtitle }
    }
    if (status.value.auto_transfer_queue) {
      autoTransferQueue.value = { ...autoTransferQueue.value, summary: status.value.auto_transfer_queue }
      if (Number(status.value.auto_transfer_queue.active || 0) > 0) {
        loadAutoTransferQueue()
      }
    }
  } catch (err) {
    error.value = errorMessage(err, '加载插件状态失败')
  } finally {
    loading.value = false
  }
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
    const response = await props.api.get(`${pluginBase.value}/auto_transfer_queue`)
    autoTransferQueue.value = unwrapResponse(response) || autoTransferQueue.value
    scheduleAutoQueuePolling()
  } catch (err) {
    error.value = errorMessage(err, '读取入库自动字幕队列失败')
  }
}

function stopHistoryTimelinePolling() {
  if (historyTimelineTimer) {
    clearTimeout(historyTimelineTimer)
    historyTimelineTimer = null
  }
}

function historyHasActiveTimelineTask() {
  return matchHistoryItems.value.some(item => (item.targets || []).some(target => {
    const task = target.timeline_task
    return task && (task.active || ['pending', 'in_progress'].includes(task.status))
  }))
}

function scheduleHistoryTimelinePolling() {
  stopHistoryTimelinePolling()
  if (!historyHasActiveTimelineTask()) return
  historyTimelineTimer = setTimeout(async () => {
    await loadMatchHistory()
    scheduleHistoryTimelinePolling()
  }, 3000)
}

async function loadOnlineStatus() {
  try {
    const response = await props.api.get(`${pluginBase.value}/online_status`)
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

async function refreshIndex() {
  refreshing.value = true
  error.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/refresh_index`, {})
    const data = unwrapResponse(response) || {}
    if (data.index) {
      status.value = { ...status.value, index: data.index }
    }
    if (selectedMedia.value) {
      await loadTargets(selectedMedia.value, selectedSeason.value || 'all')
    } else if (rootTab.value === 'history') {
      await loadMatchHistory()
    } else {
      await runSearch()
    }
    message.value = response?.message || '已刷新媒体库资源清单'
  } catch (err) {
    error.value = errorMessage(err, '刷新媒体库清单失败')
  } finally {
    refreshing.value = false
  }
}

function mediaRequestKey(keyword, type, page) {
  return `${type || 'all'}\u0000${keyword || ''}\u0000${page}`
}

function clearMediaPrefetch() {
  mediaPrefetchPages.value = {}
}

async function fetchMediaPage(keyword, type, page) {
  const params = new URLSearchParams()
  params.set('keyword', keyword)
  params.set('media_type', type)
  params.set('page', String(page))
  params.set('page_size', String(mediaPageSize))
  const response = await props.api.get(`${pluginBase.value}/search?${params.toString()}`)
  return unwrapResponse(response) || {}
}

function applyMediaPage(data, page, append) {
  mediaPage.value = Number(data.page || page)
  mediaTotal.value = Number(data.total || 0)
  mediaHasMore.value = Boolean(data.has_more)
  medias.value = append ? [...medias.value, ...(data.medias || [])] : (data.medias || [])
  if (!medias.value.length) {
    const keyword = searchKeyword.value.trim()
    message.value = keyword
      ? '本地资源库里没有匹配的视频目标，请换个关键词试试'
      : '本地整理记录里暂时没有可用的视频目标'
  }
}

async function prefetchMediaPage(page, token) {
  if (!mediaHasMore.value || page <= mediaPage.value) return
  const keyword = searchKeyword.value.trim()
  const type = mediaType.value
  const key = mediaRequestKey(keyword, type, page)
  if (mediaPrefetchPages.value[key]?.loading || mediaPrefetchPages.value[key]?.data) return
  mediaPrefetchPages.value = {
    ...mediaPrefetchPages.value,
    [key]: { loading: true },
  }
  try {
    const data = await fetchMediaPage(keyword, type, page)
    if (token !== mediaSearchToken) return
    mediaPrefetchPages.value = {
      ...mediaPrefetchPages.value,
      [key]: { data },
    }
  } catch (err) {
    if (token !== mediaSearchToken) return
    const nextCache = { ...mediaPrefetchPages.value }
    delete nextCache[key]
    mediaPrefetchPages.value = nextCache
  }
}

async function runSearch(options = {}) {
  const keyword = searchKeyword.value.trim()
  const append = Boolean(options.append)
  const page = append ? mediaPage.value + 1 : 1
  if (!append) {
    mediaSearchToken += 1
    clearMediaPrefetch()
  }
  const token = mediaSearchToken
  const cacheKey = mediaRequestKey(keyword, mediaType.value, page)
  const cachedPage = append ? mediaPrefetchPages.value[cacheKey]?.data : null
  if (cachedPage) {
    const nextCache = { ...mediaPrefetchPages.value }
    delete nextCache[cacheKey]
    mediaPrefetchPages.value = nextCache
    applyMediaPage(cachedPage, page, true)
    prefetchMediaPage(page + 1, token)
    return
  }
  searching.value = true
  error.value = ''
  message.value = ''
  if (!append) {
    selectedMedia.value = null
    clearTargetState()
  }
  try {
    const data = await fetchMediaPage(keyword, mediaType.value, page)
    if (token !== mediaSearchToken) return
    applyMediaPage(data, page, append)
    prefetchMediaPage(page + 1, token)
  } catch (err) {
    error.value = errorMessage(err, '搜索本地资源失败')
  } finally {
    if (token === mediaSearchToken) {
      searching.value = false
    }
  }
}

function submitRootSearch() {
  if (rootTab.value === 'history') {
    loadMatchHistory()
    return
  }
  runSearch()
}

function loadMoreMedia() {
  if (searching.value || !mediaHasMore.value) return
  runSearch({ append: true })
}

async function loadMatchHistory(options = {}) {
  const append = Boolean(options.append)
  const page = append ? matchHistoryPage.value + 1 : 1
  matchHistoryLoading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    params.set('keyword', searchKeyword.value.trim())
    params.set('media_type', mediaType.value)
    params.set('page', String(page))
    params.set('page_size', String(matchHistoryPageSize))
    const response = await props.api.get(`${pluginBase.value}/match_history?${params.toString()}`)
    const data = unwrapResponse(response) || {}
    matchHistoryPage.value = Number(data.page || page)
    matchHistoryTotal.value = Number(data.total || 0)
    matchHistoryHasMore.value = Boolean(data.has_more)
    matchHistoryItems.value = append ? [...matchHistoryItems.value, ...(data.items || [])] : (data.items || [])
    scheduleHistoryTimelinePolling()
  } catch (err) {
    error.value = errorMessage(err, '读取匹配历史失败')
  } finally {
    matchHistoryLoading.value = false
  }
}

function loadMoreMatchHistory() {
  if (matchHistoryLoading.value || !matchHistoryHasMore.value) return
  loadMatchHistory({ append: true })
}

function setRootTab(tab) {
  rootTab.value = tab
  selectedMedia.value = null
  clearTargetState()
  if (tab === 'history' && !matchHistoryItems.value.length) {
    loadMatchHistory()
  }
}

function buildMediaParams(media, season) {
  const params = new URLSearchParams()
  params.set('media_type', media.media_type || '')
  if (media.tmdb_id) params.set('tmdb_id', String(media.tmdb_id))
  if (media.douban_id) params.set('douban_id', String(media.douban_id))
  if (media.title) params.set('title', media.title)
  if (media.year) params.set('year', media.year)
  if (season !== null && season !== undefined && season !== '') {
    params.set('season', String(season))
  }
  return params
}

async function loadTargets(media = selectedMedia.value, season = selectedSeason.value) {
  if (!media) return
  resolving.value = true
  error.value = ''
  message.value = ''
  preview.value = null
  try {
    const params = buildMediaParams(media, season || 'all')
    const response = await props.api.get(`${pluginBase.value}/targets?${params.toString()}`)
    const data = unwrapResponse(response) || {}
    selectedMedia.value = data.media || media
    seasons.value = data.seasons || []
    selectedSeason.value = data.selected_season ?? 'all'
    targets.value = data.targets || []
    aiTaskScopeTargets.value = targets.value
    selectedTargetIds.value = []
    await loadAiTasks({ silent: true })
    await loadTimelineTasks({ silent: true })

    if (!targets.value.length) {
      message.value = `${mediaLabel(selectedMedia.value)} 没有找到本地可写入的视频文件`
    }
  } catch (err) {
    error.value = errorMessage(err, '读取本地视频目标失败')
  } finally {
    resolving.value = false
  }
}

async function selectMedia(media) {
  selectedMedia.value = media
  clearTargetState()
  await loadTargets(media, 'all')
}

async function changeSeason(season) {
  selectedSeason.value = season
  detailTab.value = 'match'
  selectedTargetIds.value = []
  await loadTargets(selectedMedia.value, season)
}

function resetSelection() {
  selectedMedia.value = null
  clearTargetState()
  runSearch()
}

function toggleSelectAll() {
  if (allVisibleSelected.value) {
    selectedTargetIds.value = []
    return
  }
  selectedTargetIds.value = visibleTargets.value.map(item => item.id)
}

function toggleTarget(targetId, checked) {
  const set = new Set(selectedTargetIds.value)
  if (checked) {
    set.add(targetId)
  } else {
    set.delete(targetId)
  }
  selectedTargetIds.value = Array.from(set)
}

function toggleLock(targetId) {
  if (isLocked(targetId)) {
    lockedTargetIds.value = lockedTargetIds.value.filter(item => item !== targetId)
    return
  }
  lockedTargetIds.value = [...lockedTargetIds.value, targetId]
}

function timelineResultForTarget(row) {
  if (row.timelineTask) return timelineTaskText(row.timelineTask)
  if (row.hasTimelineRunning) return '智能调轴处理中'
  const latest = [...(row.written || [])].reverse().find(item => item.timeline)
  if (latest) return timelineResultText(latest)
  if (isStreamTarget(row.target)) return 'STRM 资源不启用智能调轴'
  return '暂无调轴记录'
}

async function deleteSubtitle(target, subtitle) {
  if (!target || !subtitle) return
  clearing.value = true
  error.value = ''
  message.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/delete_subtitle`, {
      target_id: target.id,
      subtitle_path: subtitle.path,
      subtitle_name: subtitle.name,
      locked_target_ids: lockedTargetPayload(),
    })
    message.value = response?.message || `已删除外挂字幕：${subtitle.name}`
    if (selectedMedia.value) {
      await loadTargets(selectedMedia.value, selectedSeason.value)
    } else {
      await loadMatchHistory()
    }
  } catch (err) {
    error.value = errorMessage(err, '删除外挂字幕失败')
  } finally {
    clearing.value = false
  }
}

function openUploadDialog(scopeTargets, title) {
  const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false)
  if (!usableTargets.length) {
    error.value = '没有可上传的目标：选中的集数可能都已锁定'
    return
  }
  uploadScopeTargets.value = usableTargets
  uploadTitle.value = title
  if (usableTargets.every(isStreamTarget)) {
    fixTimeline.value = false
  }
  files.value = []
  preview.value = null
  batchLanguageSuffix.value = ''
  lastWritten.value = []
  error.value = ''
  message.value = ''
  uploadDialog.value = true
}

function openBatchUpload() {
  const title = selectedTargets.value.length
    ? `批量上传选中 ${batchUploadTargets.value.length} 集`
    : `批量上传 ${selectedSeason.value === 'all' ? '全部季' : seasonLabel(selectedSeason.value)}`
  openUploadDialog(batchUploadTargets.value, title)
}

function openSingleUpload(target) {
  openUploadDialog([target], `上传 ${compactTargetName(target)}`)
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
  uploadScopeTargets.value = usableTargets
  uploadTitle.value = `${title} · 在线字幕`
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
  lastWritten.value = []
  preview.value = null
  files.value = []
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
    const response = await props.api.post(`${pluginBase.value}/online_manual_links`, onlinePayload())
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
        props.api.post(`${pluginBase.value}/online_search_provider`, {
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

function withTimeout(promise, timeoutMs, message) {
  let timer = null
  const timeout = new Promise((resolve, reject) => {
    timer = window.setTimeout(() => {
      const err = new Error(message)
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
      props.api.post(`${pluginBase.value}/online_ai_submit`, {
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
      aiTaskData.value = data.tasks
    } else if (aiResult.tasks) {
      aiTaskData.value = aiResult.tasks
    }
    if (data.timeline_tasks) {
      timelineTaskData.value = data.timeline_tasks
    }
    preview.value = null
    uploadDialog.value = false
    onlineDialog.value = false
    message.value = response?.message || '已提交 AI 字幕翻译任务，请查看 AI 字幕生成状态'
    aiTaskScopeTargets.value = submittedTargets
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
      props.api.post(`${pluginBase.value}/online_download_preview`, {
        ...onlinePayload(),
        results: selectedOnlineResults.value,
      }),
      ONLINE_DOWNLOAD_TIMEOUT_MS,
      '在线字幕下载仍在源站验证中，已停止等待；可换一个结果重试，或打开手动链接下载后上传。',
    )
    if (downloadSeq !== onlineDownloadSeq) return
    const data = unwrapResponse(response) || {}
    preview.value = data
    batchLanguageSuffix.value = ''
    if (preview.value?.items) {
      const preferSingleCandidate = preview.value.source === 'online' && preview.value.items.length > 1
      preview.value.items.forEach((item, index) => {
        const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id)
        item.output_name = item.output_name || buildOutputName(target, item)
        item.selected = item.selected !== false && (!preferSingleCandidate || index === 0)
      })
    }
    onlineDialog.value = false
    uploadDialog.value = true
    message.value = response?.message || '已下载在线字幕并生成匹配预览'
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

async function onPickFiles(event) {
  const pickedFiles = Array.from(event?.target?.files || [])
  mergeFiles(pickedFiles)
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
  await prepareUploadAfterFiles(pickedFiles)
}

function mergeFiles(inputFiles) {
  const existing = new Map(files.value.map(item => [`${item.name}-${item.size}`, item]))
  for (const file of inputFiles) {
    const key = `${file.name}-${file.size}`
    if (!existing.has(key)) {
      existing.set(key, file)
    }
  }
  files.value = Array.from(existing.values())
  lastWritten.value = []
}

function removeFile(file) {
  files.value = files.value.filter(item => !(item.name === file.name && item.size === file.size))
}

function openFileDialog() {
  fileInputRef.value?.click()
}

async function handleDrop(event) {
  event.preventDefault()
  dragging.value = false
  const dropped = Array.from(event.dataTransfer?.files || [])
  mergeFiles(dropped)
  await prepareUploadAfterFiles(dropped)
}

function handleDragOver(event) {
  event.preventDefault()
  dragging.value = true
}

function handleDragLeave(event) {
  event.preventDefault()
  dragging.value = false
}

async function prepareUpload() {
  if (!canPrepare.value || preparing.value) return
  preparing.value = true
  error.value = ''
  try {
    const targetIds = uploadTargets.value.map(item => item.id)
    const formData = new FormData()
    formData.append('target_ids', JSON.stringify(targetIds))
    files.value.forEach(file => {
      formData.append('files', file)
    })
    const response = await props.api.post(`${pluginBase.value}/prepare_upload`, formData)
    preview.value = unwrapResponse(response)
    batchLanguageSuffix.value = ''
    if (preview.value?.items) {
      const preferSingleCandidate = preview.value.source === 'online' && preview.value.items.length > 1
      preview.value.items.forEach((item, index) => {
        const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id)
        item.output_name = item.output_name || buildOutputName(target, item)
        item.selected = item.selected !== false && (!preferSingleCandidate || index === 0)
      })
    }
    message.value = response?.message || '已生成匹配预览'
  } catch (err) {
    error.value = errorMessage(err, '上传预解析失败')
  } finally {
    preparing.value = false
  }
}

async function prepareUploadAfterFiles(inputFiles) {
  if (!inputFiles.length || hasPreviewItems.value || !canPrepare.value) return
  await prepareUpload()
}

function updatePreviewTarget(uploadId, targetId) {
  const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId)
  if (!item) return
  const target = uploadTargets.value.find(targetItem => targetItem.id === targetId)
  item.target_id = targetId
  item.output_name = buildOutputName(target, item)
}

function updateLanguageSuffix(uploadId, value) {
  const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId)
  if (!item) return
  item.language_suffix = String(value || '').trim() || 'und'
  const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id)
  item.output_name = buildOutputName(target, item)
}

function togglePreviewItem(uploadId, checked) {
  const item = (preview.value?.items || []).find(previewItem => previewItem.upload_id === uploadId)
  if (!item) return
  item.selected = Boolean(checked)
}

function applyBatchLanguageSuffix() {
  const suffix = batchLanguageSuffix.value.trim()
  if (!suffix || !preview.value?.items?.length) return
  selectedPreviewItems.value.forEach(item => {
    item.language_suffix = suffix
    const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id)
    item.output_name = buildOutputName(target, item)
  })
}

function resetUploadPreview() {
  files.value = []
  preview.value = null
  batchLanguageSuffix.value = ''
  lastWritten.value = []
  error.value = ''
  message.value = ''
}

function openRarHelp() {
  copyMessage.value = ''
  copyError.value = ''
  rarHelpDialog.value = true
}

async function copyHelpText(text, label) {
  copyMessage.value = ''
  copyError.value = ''
  try {
    await navigator.clipboard.writeText(text)
    copyMessage.value = `${label} 已复制`
  } catch (err) {
    copyError.value = '复制失败，请手动选择命令文本复制'
  }
}

async function applyUpload() {
  if (!canApply.value || !preview.value) return
  const allowRiskyOffset = timelineEnabledForApply.value && timelineNeedsRiskyConfirm.value
  if (allowRiskyOffset && !confirmRiskyTimelineOffset('写入字幕智能调轴')) return
  applying.value = true
  error.value = ''
  try {
    const payload = {
      session_id: preview.value.session_id,
      fix_timeline: timelineEnabledForApply.value,
      allow_risky_offset: allowRiskyOffset,
      locked_target_ids: lockedTargetPayload(),
      items: selectedPreviewItems.value.map(item => ({
        upload_id: item.upload_id,
        target_id: item.target_id,
        ext: item.ext,
        language_suffix: item.language_suffix,
      })),
    }
    const response = await props.api.post(`${pluginBase.value}/apply_upload`, payload)
    const data = unwrapResponse(response) || {}
    const written = data.written || []
    const successMessage = response?.message || `已写入 ${data.count || 0} 个字幕文件`
    files.value = []
    preview.value = null
    uploadDialog.value = false
    await loadTargets(selectedMedia.value, selectedSeason.value)
    message.value = successMessage
    lastWritten.value = written
  } catch (err) {
    error.value = errorMessage(err, '写入字幕失败')
  } finally {
    applying.value = false
  }
}

async function clearSelectedSubtitles() {
  const targetIds = selectedSubtitleTargets.value.map(target => target.id)
  if (!targetIds.length) return
  clearing.value = true
  error.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/clear_subtitles`, {
      target_ids: targetIds,
      locked_target_ids: lockedTargetPayload(),
    })
    const data = unwrapResponse(response) || {}
    const successMessage = response?.message || `已删除 ${data.count || 0} 个外挂字幕`
    await loadTargets(selectedMedia.value, selectedSeason.value)
    message.value = successMessage
  } catch (err) {
    error.value = errorMessage(err, '清空外挂字幕失败')
  } finally {
    clearing.value = false
  }
}

onMounted(() => {
  loadStatus()
  loadAutoTransferQueue()
  runSearch()
})

onBeforeUnmount(() => {
  stopAiPolling()
  stopTimelinePolling()
  stopHistoryTimelinePolling()
  stopAutoQueuePolling()
})

defineExpose({
  loadStatus,
  refreshIndex,
  runSearch,
  loading,
  searching,
  resolving,
  refreshing,
  preparing,
  applying,
  clearing,
  aiSubmitting,
  aiCancelling,
  aiTasksLoading,
  onlineSearching,
  onlineDownloading,
})
</script>

<template>
  <div class="subtitle-upload-page">
    <div v-if="!selectedMedia" class="root-tabs">
      <button
        type="button"
        :class="{ active: rootTab === 'match' }"
        @click="setRootTab('match')"
      >
        字幕匹配
      </button>
      <button
        type="button"
        :class="{ active: rootTab === 'history' }"
        @click="setRootTab('history')"
      >
        匹配历史
      </button>
    </div>

    <div v-if="!hideTitle" class="hero-card">
      <div>
        <h1>字幕匹配</h1>
        <p>从 MoviePilot 本地库选择资源，上传字幕后确认匹配与改名结果。</p>
      </div>
    </div>

    <VAlert
      v-if="error"
      class="mb-4"
      type="error"
      variant="tonal"
      :text="error"
    />
    <VAlert
      v-else-if="message"
      class="mb-4"
      type="success"
      variant="tonal"
      :text="message"
    />

    <section v-if="!selectedMedia" class="media-stage">
      <VCard class="glass-card search-card" rounded="xl" elevation="0">
        <VCardText>
          <div class="search-head">
            <div>
              <div class="section-kicker">{{ rootTab === 'history' ? '历史记录' : '资源选择' }}</div>
              <h2>{{ rootTab === 'history' ? '查看已匹配字幕' : '选择本地已有资源' }}</h2>
              <p>{{ rootTab === 'history' ? matchHistorySummary : `仅展示 MoviePilot 已整理到本地库的视频资源。${indexSummary}` }}</p>
            </div>
            <VBtn
              variant="tonal"
              color="primary"
              prepend-icon="mdi-refresh"
              :loading="refreshing"
              @click="refreshIndex"
            >
              刷新媒体库清单
            </VBtn>
          </div>
          <div class="search-bar">
            <VTextField
              v-model="searchKeyword"
              label="片名、剧名或文件关键词"
              variant="outlined"
              density="comfortable"
              hide-details
              clearable
              @keyup.enter="submitRootSearch"
            />
            <VSelect
              v-model="mediaType"
              :items="[
                { title: '全部', value: 'all' },
                { title: '电影', value: 'movie' },
                { title: '剧集', value: 'tv' },
              ]"
              label="类型"
              variant="outlined"
              density="comfortable"
              hide-details
            />
            <VBtn
              color="primary"
              :loading="rootTab === 'history' ? matchHistoryLoading : searching"
              @click="submitRootSearch"
            >
              搜索
            </VBtn>
          </div>
        </VCardText>
      </VCard>

      <div v-if="rootTab === 'match' && medias.length" class="media-list">
        <button
          v-for="(media, index) in medias"
          :key="media.id"
          class="media-card"
          @click="selectMedia(media)"
        >
          <div class="poster-frame">
            <img
              v-if="posterImageSrc(media)"
              :src="posterImageSrc(media)"
              :alt="mediaLabel(media)"
              :loading="posterLoading(index)"
              :fetchpriority="posterFetchPriority(index)"
              decoding="async"
              draggable="false"
              @error="markPosterFailed(media)"
            >
            <span v-else>{{ formatMediaType(media.media_type) }}</span>
          </div>
          <div class="media-copy">
            <div class="media-type">{{ formatMediaType(media.media_type) }}</div>
            <h3>{{ mediaLabel(media) }}</h3>
            <p>{{ mediaStat(media) }}</p>
          </div>
          <VIcon icon="mdi-chevron-right" />
        </button>
      </div>
      <div v-if="rootTab === 'match' && medias.length" class="pager-row">
        <span>{{ medias.length }}/{{ mediaTotal || medias.length }} 个资源</span>
        <VBtn
          v-if="mediaHasMore"
          variant="tonal"
          :loading="searching"
          @click="loadMoreMedia"
        >
          加载下一页
        </VBtn>
      </div>
      <div v-else-if="rootTab === 'match'" class="empty-state">
        {{ searching ? '正在读取本地资源...' : '输入关键词搜索；留空搜索会显示最近整理的视频。' }}
      </div>

      <div
        v-if="rootTab === 'history' && (autoQueueTasks.length || autoQueueSummary.active)"
        class="auto-queue-entry"
      >
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="mdi-tray-full"
          @click="autoQueueDialog = true"
        >
          入库自动字幕队列 · {{ autoQueueSummaryText }}
        </VBtn>
      </div>

      <div v-if="rootTab === 'history' && matchHistoryItems.length" class="global-history-list">
        <div
          v-for="(item, index) in matchHistoryItems"
          :key="item.id"
          class="global-history-card"
        >
          <button
            type="button"
            class="global-history-head"
            @click="toggleHistoryExpanded(item)"
          >
            <div class="poster-frame compact">
              <img
                v-if="posterImageSrc(item)"
                :src="posterImageSrc(item)"
                :alt="mediaLabel(item)"
                :loading="posterLoading(index)"
                :fetchpriority="posterFetchPriority(index)"
                decoding="async"
                draggable="false"
                @error="markPosterFailed(item)"
              >
              <span v-else>{{ formatMediaType(item.media_type) }}</span>
            </div>
            <div class="media-copy">
              <div class="media-type">{{ formatMediaType(item.media_type) }}</div>
              <h3>{{ mediaLabel(item) }}</h3>
              <p>{{ historyMediaStat(item) }} · {{ item.latest_at || '未知时间' }}</p>
            </div>
            <VIcon :icon="historyExpanded(item) ? 'mdi-chevron-up' : 'mdi-chevron-down'" />
          </button>
          <div v-if="historyExpanded(item)" class="global-history-targets">
            <div class="history-bulk-toolbar">
              <div class="history-bulk-copy">
                <strong>已选 {{ historySelectedCount(item) }}/{{ historyDeletableTargets(item).length }} 集</strong>
                <span>{{ item.subtitle_count }} 个外挂字幕</span>
              </div>
              <div class="history-bulk-actions">
                <VBtn
                  size="small"
                  variant="tonal"
                  prepend-icon="mdi-checkbox-multiple-marked-outline"
                  :disabled="!historyDeletableTargets(item).length || clearing"
                  @click.stop="toggleHistoryItemTargets(item)"
                >
                  {{ allHistoryTargetsSelected(item) ? '取消全选' : '全选' }}
                </VBtn>
                <VBtn
                  size="small"
                  color="error"
                  variant="tonal"
                  prepend-icon="mdi-delete-sweep"
                  :disabled="!historySelectedCount(item) || clearing"
                  :loading="clearing"
                  @click.stop="clearHistorySelectedSubtitles(item)"
                >
                  删除选中
                </VBtn>
                <VBtn
                  size="small"
                  color="warning"
                  variant="tonal"
                  prepend-icon="mdi-timeline-clock-outline"
                  :disabled="!historySelectedTimelineTargets(item).length || timelineFixing || !timelineAvailable"
                  :loading="timelineFixing"
                  @click.stop="fixHistorySelectedTimeline(item)"
                >
                  调轴选中
                </VBtn>
              </div>
            </div>
            <div class="history-season-tree">
              <div
                v-for="season in historySeasonGroups(item)"
                :key="historySeasonKey(item, season)"
                class="history-season-node"
              >
                <div v-if="!season.direct" class="history-season-row">
                  <VCheckbox
                    :model-value="allHistorySeasonTargetsSelected(item, season)"
                    :indeterminate="historySeasonPartiallySelected(item, season)"
                    density="compact"
                    hide-details
                    :disabled="!season.targets.length || clearing"
                    @click.stop
                    @update:model-value="value => toggleHistorySeasonTargets(item, season, value)"
                  />
                  <button
                    type="button"
                    class="history-season-toggle"
                    @click.stop="toggleHistorySeasonExpanded(item, season)"
                  >
                    <VIcon :icon="historySeasonExpanded(item, season) ? 'mdi-chevron-down' : 'mdi-chevron-right'" />
                    <strong>{{ season.label }}</strong>
                    <span>{{ season.targets.length }} 集 · {{ season.subtitleCount }} 个外挂字幕</span>
                    <em v-if="historySeasonSelectedCount(item, season)">已选 {{ historySeasonSelectedCount(item, season) }}</em>
                  </button>
                </div>
                <div
                  v-if="season.direct || historySeasonExpanded(item, season)"
                  class="history-episode-list"
                  :class="{ 'direct-targets': season.direct }"
                >
                  <div
                    v-for="target in season.targets"
                    :key="`${historySeasonKey(item, season)}-${target.id}`"
                    class="history-episode-node"
                  >
                    <div class="history-episode-row">
                      <VCheckbox
                        :model-value="historySelectedIds(item).includes(target.id)"
                        density="compact"
                        hide-details
                        :disabled="!(target.subtitles || []).length || clearing"
                        @click.stop
                        @update:model-value="value => toggleHistoryTarget(item, target.id, value)"
                      />
                      <button
                        type="button"
                        class="history-episode-toggle"
                        @click.stop="toggleHistoryTargetExpanded(target)"
                      >
                        <VIcon :icon="historyTargetExpanded(target) ? 'mdi-chevron-down' : 'mdi-chevron-right'" />
                        <span class="episode-title">{{ compactTargetName(target) }}</span>
                        <small>{{ (target.subtitles || []).length }} 个外挂字幕</small>
                      </button>
                      <VBtn
                        size="small"
                        variant="tonal"
                        prepend-icon="mdi-magnify"
                        :disabled="isTargetActionDisabled(target)"
                        @click.stop="openSingleOnlineSearch(target)"
                      >
                        重新搜索
                      </VBtn>
                    </div>
                    <div v-if="historyTargetExpanded(target)" class="history-subtitle-children">
                      <div class="episode-path">{{ target.relative_path }}</div>
                      <div v-if="target.timeline_task" class="history-status compact-status">
                        <span>调轴：{{ timelineTaskText(target.timeline_task) }}</span>
                        <span
                          v-for="meta in timelineMetaItems(target.timeline_task.timeline)"
                          :key="`${target.id}-${meta}`"
                          class="timeline-meta"
                        >
                          {{ meta }}
                        </span>
                      </div>
                      <div class="subtitle-history-list compact-subtitles">
                        <div
                          v-for="subtitle in target.subtitles"
                          :key="subtitle.path"
                          class="subtitle-history-item"
                        >
                          <div class="subtitle-history-copy">
                            <strong>{{ subtitle.name }}</strong>
                            <span>{{ formatBytes(subtitle.size) }} · {{ subtitle.modified_at || '未知时间' }}</span>
                          </div>
                          <div class="subtitle-history-actions">
                            <VBtn
                              size="small"
                              variant="tonal"
                              color="warning"
                              :loading="timelineFixing"
                              :disabled="timelineFixing || !timelineAvailable || isStreamTarget(target)"
                              @click.stop="fixHistorySubtitleTimeline(target, subtitle)"
                            >
                              调轴
                            </VBtn>
                            <VBtn
                              size="small"
                              variant="tonal"
                              color="error"
                              :loading="clearing"
                              @click.stop="deleteSubtitle(target, subtitle)"
                            >
                              删除
                            </VBtn>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="!historySeasonGroups(item).length" class="empty-state compact-empty">
              暂无可管理的外挂字幕
            </div>
          </div>
        </div>
      </div>
      <div v-if="rootTab === 'history' && matchHistoryItems.length" class="pager-row">
        <span>{{ matchHistoryItems.length }}/{{ matchHistoryTotal || matchHistoryItems.length }} 部资源</span>
        <VBtn
          v-if="matchHistoryHasMore"
          variant="tonal"
          :loading="matchHistoryLoading"
          @click="loadMoreMatchHistory"
        >
          加载下一页
        </VBtn>
      </div>
      <div v-else-if="rootTab === 'history'" class="empty-state">
        {{ matchHistoryLoading ? '正在读取匹配历史...' : '还没有找到已匹配字幕记录。' }}
      </div>
    </section>

    <section v-else class="episode-stage">
      <VCard class="glass-card detail-card" rounded="xl" elevation="0">
        <VCardText>
          <div class="detail-head">
            <div class="selected-media">
              <button class="back-btn" @click="resetSelection">
                <VIcon icon="mdi-arrow-left" />
              </button>
              <div class="mini-poster">
                <img
                  v-if="posterImageSrc(selectedMedia)"
                  :src="posterImageSrc(selectedMedia)"
                  :alt="mediaLabel(selectedMedia)"
                  loading="eager"
                  fetchpriority="high"
                  decoding="async"
                  draggable="false"
                  @error="markPosterFailed(selectedMedia)"
                >
                <span v-else>{{ formatMediaType(selectedMedia.media_type) }}</span>
              </div>
              <div>
                <div class="section-kicker">{{ formatMediaType(selectedMedia.media_type) }}</div>
                <h2>{{ mediaLabel(selectedMedia) }}</h2>
                <p>{{ visibleTargets.length }} 个本地目标 · {{ selectedTargets.length }} 个已选 · {{ lockedTargetIds.length }} 个锁定</p>
              </div>
            </div>
            <VBtn variant="tonal" :loading="resolving" @click="loadTargets(selectedMedia, selectedSeason)">
              刷新列表
            </VBtn>
          </div>

          <div v-if="selectedMedia.media_type === 'tv'" class="season-strip">
            <button
              v-for="season in seasonCards"
              :key="season.value"
              class="season-card"
              :class="{ active: selectedSeason === season.value }"
              @click="changeSeason(season.value)"
            >
              <span>{{ season.title }}</span>
              <strong>{{ season.subtitle }}</strong>
            </button>
          </div>

          <button
            v-if="aiEnabled"
            ref="aiStatusStripRef"
            class="ai-status-strip"
            :class="{ unavailable: !aiAvailable, active: aiHasActiveTasks }"
            type="button"
            @click="openAiTaskDialog()"
          >
            <span class="ai-status-orb">
              <VProgressCircular
                v-if="aiTasksLoading || aiHasActiveTasks"
                size="16"
                width="2"
                indeterminate
              />
              <VIcon v-else icon="mdi-robot-outline" size="18" />
            </span>
            <strong>{{ aiSummaryText }}</strong>
            <em>{{ aiAvailable ? '点击查看当前资源任务' : aiStatus.message }}</em>
          </button>

          <div class="match-panel">
          <div class="toolbar-row">
            <VBtn variant="tonal" @click="toggleSelectAll">
              {{ allVisibleSelected ? '取消全选' : '全选当前列表' }}
            </VBtn>
            <VBtn
              color="primary"
              :disabled="!unlockedVisibleTargets.length"
              @click="openBatchUpload"
            >
              {{ selectedTargets.length ? '上传选中字幕' : '批量上传整季字幕' }}
            </VBtn>
            <VBtn
              v-if="aiEnabled"
              color="warning"
              variant="tonal"
              prepend-icon="mdi-robot-outline"
              :disabled="!aiCapableBatchTargets.length || !aiAvailable"
              :loading="aiSubmitting"
              @click="openBatchAiGenerate"
            >
              {{ aiBatchLabel }}
            </VBtn>
            <VBtn
              v-if="aiEnabled && aiBatchCancelTargets.length"
              color="error"
              variant="tonal"
              prepend-icon="mdi-cancel"
              :loading="aiCancelling"
              @click="cancelBatchAiGenerate"
            >
              取消 AI
            </VBtn>
            <VBtn
              class="online-batch-btn"
              color="success"
              variant="flat"
              prepend-icon="mdi-cloud-search-outline"
              :disabled="!batchUploadTargets.length"
              :loading="onlineSearching"
              @click="openBatchOnlineSearch"
            >
              {{ onlineBatchLabel }}
            </VBtn>
            <VBtn
              color="error"
              variant="tonal"
              :disabled="!selectedTargetIds.length"
              :loading="clearing"
              @click="clearSelectedSubtitles"
            >
              清空选中外挂字幕
            </VBtn>
            <VBtn
              color="warning"
              variant="tonal"
              prepend-icon="mdi-timeline-clock"
              :disabled="!selectedTimelineTargets.length || timelineFixing || !timelineAvailable"
              :loading="timelineFixing"
              @click="fixSelectedDetailTimeline"
            >
              批量调轴
            </VBtn>
            <VBtn
              color="secondary"
              variant="tonal"
              prepend-icon="mdi-restore"
              :disabled="!selectedRestorableTargets.length || clearing"
              :loading="clearing"
              @click="restoreSelectedBackups"
            >
              批量恢复
            </VBtn>
          </div>

          <div v-if="visibleTargets.length" class="episode-list">
            <div
              v-for="target in visibleTargets"
              :key="target.id"
              class="episode-row"
              :class="{ locked: isLocked(target.id) }"
            >
              <VCheckbox
                :model-value="selectedTargetIds.includes(target.id)"
                density="compact"
                hide-details
                @update:model-value="value => toggleTarget(target.id, value)"
              />
              <VBtn
                class="episode-expand-btn"
                variant="tonal"
                density="comfortable"
                :icon="detailExpanded(target) ? 'mdi-chevron-down' : 'mdi-chevron-right'"
                :title="detailExpanded(target) ? '收起外挂字幕' : '展开外挂字幕'"
                @click="toggleDetailExpanded(target)"
              />
              <div class="episode-index">
                {{ target.media_type === 'tv' ? `E${String(target.episode || 0).padStart(2, '0')}` : 'MOV' }}
              </div>
              <div class="episode-copy">
                <div class="episode-title">{{ compactTargetName(target) }}</div>
                <div class="episode-path">{{ target.relative_path }}</div>
              </div>
              <VMenu v-if="target.has_subtitle" location="bottom end">
                <template #activator="{ props: menuProps }">
                  <VBtn
                    v-bind="menuProps"
                    class="cc-btn has-sub"
                    variant="text"
                    icon="mdi-closed-caption"
                    :title="`已有 ${target.subtitle_count} 个外挂字幕`"
                  />
                </template>
                <VCard min-width="280" rounded="lg">
                  <VList density="compact">
                    <VListSubheader>已有外挂字幕</VListSubheader>
                    <VListItem
                      v-for="subtitle in target.subtitles"
                      :key="subtitle.path"
                      :title="subtitle.name"
                      :subtitle="formatBytes(subtitle.size)"
                    />
                  </VList>
                </VCard>
              </VMenu>
              <VBtn
                v-else
                class="cc-btn"
                variant="text"
                icon="mdi-closed-caption-outline"
                title="暂无外挂字幕"
              />
              <VBtn
                v-if="aiEnabled"
                class="ai-row-btn"
                :class="aiTaskStatusClass(target)"
                variant="text"
                :icon="aiTaskIcon(target)"
                :color="aiTaskColor(target)"
                :title="aiTaskTitle(target)"
                :disabled="isTargetActionDisabled(target) || isStreamTarget(target) || (!aiAvailable && !aiTaskForTarget(target))"
                @click="openSingleAiGenerate(target)"
              />
              <VBtn
                variant="text"
                icon="mdi-magnify"
                title="搜索此集在线字幕"
                :disabled="isTargetActionDisabled(target)"
                @click="openSingleOnlineSearch(target)"
              />
              <VBtn
                variant="text"
                :icon="isLocked(target.id) ? 'mdi-lock' : 'mdi-lock-open-variant'"
                :color="isLocked(target.id) ? 'warning' : undefined"
                :title="isLocked(target.id) ? '解锁此集' : '锁定此集，批量上传跳过'"
                @click="toggleLock(target.id)"
              />
              <VBtn
                color="primary"
                variant="tonal"
                size="small"
                :disabled="isTargetActionDisabled(target)"
                @click="openSingleUpload(target)"
              >
                单集上传
              </VBtn>
              <div v-if="detailExpanded(target)" class="episode-expanded">
                <div class="history-status compact-status">
                  <span>{{ (target.subtitles || []).length ? `${target.subtitles.length} 个外挂字幕` : '暂无外挂字幕' }}</span>
                  <span v-if="detailRowForTarget(target).task">AI：{{ aiStatusText(detailRowForTarget(target).task) }}</span>
                  <span>{{ timelineResultForTarget(detailRowForTarget(target)) }}</span>
                  <span
                    v-for="meta in timelineMetaItems(timelineTaskForTarget(target)?.timeline)"
                    :key="`${target.id}-detail-${meta}`"
                    class="timeline-meta"
                  >
                    {{ meta }}
                  </span>
                  <span v-if="isStreamTarget(target)">STRM 资源不启用 AI 生成和智能调轴</span>
                </div>
                <div v-if="(target.subtitles || []).length" class="subtitle-history-list compact-subtitles">
                  <div
                    v-for="subtitle in target.subtitles"
                    :key="subtitle.path"
                    class="subtitle-history-item"
                  >
                    <div class="subtitle-history-copy">
                      <strong>{{ subtitle.name }}</strong>
                      <span>{{ formatBytes(subtitle.size) }} · {{ subtitle.modified_at || '未知时间' }}</span>
                    </div>
                    <div class="subtitle-history-actions">
                      <VBtn
                        size="small"
                        variant="tonal"
                        color="warning"
                        :loading="timelineFixing"
                        :disabled="timelineFixing || !timelineAvailable || isTargetActionDisabled(target) || isStreamTarget(target)"
                        @click.stop="fixHistorySubtitleTimeline(target, subtitle)"
                      >
                        调轴
                      </VBtn>
                      <VBtn
                        size="small"
                        variant="tonal"
                        color="secondary"
                        :loading="clearing"
                        :disabled="!subtitle.backup_available || isTargetActionDisabled(target)"
                        @click.stop="restoreSubtitleBackup(target, subtitle)"
                      >
                        恢复
                      </VBtn>
                      <VBtn
                        size="small"
                        variant="tonal"
                        color="error"
                        :loading="clearing"
                        :disabled="isTargetActionDisabled(target)"
                        @click.stop="deleteSubtitle(target, subtitle)"
                      >
                        删除
                      </VBtn>
                    </div>
                  </div>
                </div>
                <div v-else class="empty-state compact-empty">
                  当前集暂无外挂字幕。
                </div>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            {{ resolving ? '正在读取本地视频目标...' : '这个资源没有本地视频文件。' }}
          </div>

          <div v-if="lastWritten.length" class="result-panel">
            <div class="section-kicker">写入结果</div>
            <div v-for="item in lastWritten" :key="item.output_path" class="result-row">
              <div>
                <strong>{{ item.output_name }}</strong>
                <span>{{ item.target_label }}</span>
              </div>
              <em>{{ timelineResultText(item) }}</em>
              <div v-if="timelineMetaItems(item).length" class="timeline-meta-list">
                <span
                  v-for="meta in timelineMetaItems(item)"
                  :key="`${item.output_path}-${meta}`"
                  class="timeline-meta"
                >
                  {{ meta }}
                </span>
              </div>
            </div>
          </div>
          </div>
        </VCardText>
      </VCard>
    </section>

    <VDialog v-model="autoQueueDialog" max-width="760">
      <VCard class="auto-queue-card" rounded="xl">
        <VCardTitle class="dialog-title">
          <div>
            <span>入库自动字幕队列</span>
            <p>{{ autoQueueSummaryText }}</p>
          </div>
          <div class="online-title-actions">
            <VBtn
              variant="tonal"
              prepend-icon="mdi-refresh"
              @click="loadAutoTransferQueue"
            >
              刷新
            </VBtn>
            <VBtn icon="mdi-close" variant="text" @click="autoQueueDialog = false" />
          </div>
        </VCardTitle>
        <VDivider />
        <VCardText>
          <div class="auto-queue-rates">
            <span
              v-for="(rate, provider) in autoTransferQueue.rate_limits || {}"
              :key="provider"
            >
              {{ provider }}：{{ rate.remaining }}/{{ rate.limit_per_minute }} 可用
            </span>
          </div>
          <div v-if="autoQueueTasks.length" class="auto-queue-list">
            <div
              v-for="task in autoQueueTasks.slice().reverse().slice(0, 12)"
              :key="task.id"
              class="auto-queue-row"
              :class="`auto-queue-${task.status}`"
            >
              <strong>{{ task.target_label || task.title || task.id }}</strong>
              <span>{{ task.message || task.status }}<template v-if="task.next_run_at"> · 下次 {{ task.next_run_at }}</template></span>
            </div>
          </div>
          <div v-else class="empty-state compact-empty">
            当前没有入库自动字幕任务。
          </div>
        </VCardText>
      </VCard>
    </VDialog>

    <VDialog v-model="aiTaskDialog" max-width="860">
      <VCard class="ai-task-dialog" rounded="xl">
        <VCardTitle class="dialog-title">
          <div>
            <span>{{ aiTaskDialogTarget ? `AI 状态 · ${compactTargetName(aiTaskDialogTarget)}` : 'AI 字幕生成状态' }}</span>
            <p>{{ aiSummaryText }} · 状态来自 AI字幕生成(联动版) 队列</p>
          </div>
          <div class="online-title-actions">
            <VBtn
              v-if="aiDialogHasActiveTasks"
              variant="tonal"
              color="error"
              prepend-icon="mdi-cancel"
              :loading="aiCancelling"
              @click="cancelDialogAiTasks"
            >
              取消任务
            </VBtn>
            <VBtn
              v-else-if="aiAvailable && (aiTaskDialogTarget || aiDialogTasks.length)"
              variant="tonal"
              color="warning"
              prepend-icon="mdi-robot-happy-outline"
              :loading="aiSubmitting"
              @click="regenerateDialogAiTasks"
            >
              重新生成
            </VBtn>
            <VBtn
              variant="tonal"
              color="primary"
              prepend-icon="mdi-refresh"
              :loading="aiTasksLoading"
              @click="loadAiTasks"
            >
              刷新
            </VBtn>
            <VBtn icon="mdi-close" variant="text" @click="aiTaskDialog = false" />
          </div>
        </VCardTitle>
        <VDivider />
        <VCardText>
          <VAlert
            v-if="!aiAvailable"
            class="mb-4"
            type="warning"
            variant="tonal"
            :text="aiStatus.message || '请先安装并启用 AI字幕生成(联动版)'"
          />
          <div v-if="aiAvailable && !aiDialogHasActiveTasks && (aiTaskDialogTarget || aiDialogTasks.length)" class="ai-restart-options">
            <VSelect
              v-model="aiRestartSourcePolicy"
              :items="aiRestartSourceOptions"
              label="重新生成来源"
              density="comfortable"
              hint="改选来源会写入来源变体后缀，如 .aiasr.srt 或 .aiembedded.srt"
              persistent-hint
            />
          </div>
          <div v-if="aiDialogTasks.length" class="ai-task-list">
            <div
              v-for="task in aiDialogTasks"
              :key="task.task_id"
              class="ai-task-row"
              :class="`ai-${task.status}`"
            >
              <div class="ai-task-badge">
                <VIcon :icon="aiTaskIcon({ id: task.target_id })" />
              </div>
              <div class="ai-task-main">
                <strong>{{ task.target_label || task.video_name }}</strong>
                <span>{{ task.source_asset_name || task.source_subtitle_name ? `字幕源：${task.source_asset_name || task.source_subtitle_name}` : (task.resolved_source_label || task.source_policy_label || task.video_name) }}</span>
                <span v-if="task.output_name">输出：{{ task.output_name }}</span>
                <p>{{ aiStatusText(task) }}</p>
              </div>
              <div class="ai-task-time">
                <VChip size="small" variant="tonal">{{ task.status_label }}</VChip>
                <span>{{ task.complete_time || task.add_time || '-' }}</span>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            当前资源还没有 AI 字幕生成任务。可以点击单集 AI 图标，或使用上方“AI 生成”批量提交。
          </div>
        </VCardText>
      </VCard>
    </VDialog>

    <VDialog :model-value="onlineDialog" max-width="1080" @update:model-value="updateOnlineDialog">
      <VCard class="online-dialog" rounded="xl">
        <VCardTitle class="dialog-title">
          <div>
            <span>{{ onlineTitle || '在线字幕搜索' }}</span>
            <p>{{ onlineTargets.length }} 个目标 · 下载会进入匹配预览，提交 AI 翻译会直接进入 AI 状态</p>
          </div>
          <div class="online-title-actions">
            <VBtn
              color="success"
              :disabled="!selectedOnlineResults.length || onlineAiDownloading"
              :loading="onlinePreviewDownloading"
              @click="downloadOnlinePreview"
            >
              下载并生成预览
            </VBtn>
            <VBtn
              color="primary"
              variant="tonal"
              :disabled="!canSubmitOnlineAiTranslate || onlinePreviewDownloading"
              :loading="onlineAiDownloading"
              @click="requestOnlineAiTranslate"
            >
              提交 AI 翻译
            </VBtn>
            <VBtn
              v-if="onlineDownloading"
              color="warning"
              variant="tonal"
              @click="stopOnlineDownload"
            >
              停止等待
            </VBtn>
            <VBtn icon="mdi-close" variant="text" @click="closeOnlineDialog" />
          </div>
        </VCardTitle>
        <VDivider />
        <VCardActions class="online-search-actions">
          <VTextField
            v-model="onlineKeyword"
            label="手动关键词（可选）"
            placeholder="留空按资源名、季集号自动生成"
            variant="outlined"
            density="comfortable"
            hide-details
            clearable
            @keyup.enter="runOnlineSearch"
          />
          <VSelect
            v-model="onlineSelectedProviders"
            :items="onlineProviderItems"
            label="字幕源"
            variant="outlined"
            density="comfortable"
            hide-details
            multiple
            chips
          />
          <VBtn
            color="primary"
            :disabled="!onlineSelectedProviders.length"
            :loading="onlineSearching"
            @click="runOnlineSearch"
          >
            搜索
          </VBtn>
          <VBtn
            v-if="onlineSearching"
            color="warning"
            variant="tonal"
            @click="stopOnlineSearch"
          >
            停止等待
          </VBtn>
        </VCardActions>
        <VDivider />
        <VCardText>
          <VAlert
            v-if="onlineError"
            class="mb-4"
            type="error"
            variant="tonal"
            :text="onlineError"
          />
          <VAlert
            v-if="onlineMessages.length && !onlineMessagesCollapsed"
            class="online-message-summary"
            :type="onlineMessageType"
            variant="tonal"
            density="compact"
          >
            <div class="online-message-summary-content">
              <span>{{ onlineMessageSummary }}</span>
              <VBtn
                size="x-small"
                variant="text"
                @click="onlineMessagesCollapsed = true"
              >
                收起
              </VBtn>
            </div>
          </VAlert>

          <div class="online-layout">
            <section class="online-results-panel">
              <div class="online-panel-head">
                <div>
                  <div class="section-kicker">自动搜索</div>
                  <h3>选择要下载的字幕</h3>
                </div>
                <span>{{ hasOnlineResults ? `${filteredOnlineResults.length}/${onlineResults.length} 条结果` : '暂无结果' }}</span>
              </div>
              <VChipGroup
                v-if="hasOnlineResults"
                v-model="onlineLanguageFilter"
                class="online-provider-filter"
                mandatory
                selected-class="online-provider-filter-active"
              >
                <VChip
                  v-for="item in onlineLanguageFilterItems"
                  :key="item.value"
                  :value="item.value"
                  size="small"
                  variant="tonal"
                >
                  {{ item.title }}
                </VChip>
              </VChipGroup>
              <VChipGroup
                v-if="hasOnlineResults"
                v-model="onlineProviderFilter"
                class="online-provider-filter"
                mandatory
                selected-class="online-provider-filter-active"
              >
                <VChip
                  v-for="item in onlineProviderFilterItems"
                  :key="item.value"
                  :value="item.value"
                  size="small"
                  variant="tonal"
                >
                  {{ item.title }}
                </VChip>
              </VChipGroup>
              <div v-if="onlineProviderProgressItems.length" class="online-provider-progress">
                <VChip
                  v-for="item in onlineProviderProgressItems"
                  :key="item.provider"
                  size="small"
                  variant="tonal"
                  :color="providerProgressColor(item.state)"
                >
                  {{ providerName(item.provider) }} · {{ providerProgressText(item.state) }}
                </VChip>
              </div>

              <div v-if="onlineSearching && !filteredOnlineResults.length" class="online-loading">
                正在从 API 搜索字幕，先返回的结果会先显示...
              </div>
              <div v-if="filteredOnlineResults.length" class="online-result-list">
                <div
                  v-for="item in filteredOnlineResults"
                  :key="onlineResultKey(item)"
                  class="online-result-card"
                  :class="{
                    active: selectedOnlineResultIds.includes(onlineResultKey(item)),
                    disabled: !isOnlineResultDownloadable(item),
                  }"
                >
                  <VCheckbox
                    :model-value="selectedOnlineResultIds.includes(onlineResultKey(item))"
                    density="compact"
                    hide-details
                    :disabled="!isOnlineResultDownloadable(item)"
                    @update:model-value="value => toggleOnlineResult(item, value)"
                  />
                  <div class="online-result-main">
                    <div class="online-result-title">{{ item.title }}</div>
                    <div class="online-result-meta">
                      <span>{{ providerName(item.provider) }}</span>
                      <span>{{ onlineResultMeta(item) }}</span>
                      <span v-if="!isOnlineResultDownloadable(item)" class="online-manual-badge">
                        需手动下载
                      </span>
                    </div>
                    <p v-if="item.note">{{ item.note }}</p>
                    <p v-if="item.match_detail" class="online-match-detail">{{ item.match_detail }}</p>
                  </div>
                  <a
                    v-if="item.page_url"
                    class="online-open-link"
                    :href="item.page_url"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    查看
                  </a>
                </div>
              </div>
              <div v-else-if="!onlineSearching" class="empty-state">
                {{ hasOnlineResults ? '当前平台筛选下没有结果。' : '没有可自动下载的字幕结果。可以换关键词重试，或使用右侧手动搜索。' }}
              </div>
            </section>

            <aside class="manual-links-panel">
              <div class="section-kicker">手动搜索</div>
              <h3>跳转字幕站</h3>
              <p>自动搜索失败或源站需要验证时，可打开链接下载字幕包后回到本页上传。</p>
              <div
                v-for="provider in onlineManualLinks"
                :key="provider.provider"
                class="manual-provider"
              >
                <div class="manual-provider-head">
                  <strong>{{ provider.name }}</strong>
                </div>
                <div class="manual-keywords">
                  <a
                    v-for="link in provider.links"
                    :key="`${provider.provider}-${link.keyword}`"
                    :href="link.url"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {{ link.keyword }}
                  </a>
                </div>
              </div>
            </aside>
          </div>
        </VCardText>
      </VCard>
    </VDialog>

    <VDialog v-model="onlineAiConfirmDialog" max-width="520">
      <VCard rounded="lg">
        <VCardTitle class="dialog-title compact">
          <div>
            <span>确认提交 AI 翻译</span>
            <p>{{ onlineAiConfirmText }}</p>
          </div>
        </VCardTitle>
        <VDivider />
        <VCardText>
          <VAlert
            type="warning"
            variant="tonal"
            text="确认后会在后台下载所选外语字幕，智能调轴后提交到 AI 字幕生成队列；不会打开匹配预览，误触后可在 AI 状态里取消。"
          />
        </VCardText>
        <VCardActions class="justify-end">
          <VBtn variant="text" @click="onlineAiConfirmDialog = false">取消</VBtn>
          <VBtn
            color="primary"
            variant="flat"
            :loading="onlineAiDownloading"
            @click="confirmOnlineAiTranslate"
          >
            确认提交
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="uploadDialog" max-width="980">
      <VCard class="upload-dialog" rounded="xl">
        <VCardTitle class="dialog-title">
          <span>{{ uploadTitle || '上传字幕' }}</span>
          <VBtn icon="mdi-close" variant="text" @click="uploadDialog = false" />
        </VCardTitle>
        <VDivider />
        <VCardActions class="dialog-actions dialog-actions-top">
          <VBtn variant="text" @click="uploadDialog = false">关闭</VBtn>
          <VSpacer />
          <VBtn
            v-if="hasPreviewItems"
            variant="tonal"
            @click="resetUploadPreview"
          >
            重新选择文件
          </VBtn>
          <VTooltip
            v-if="hasPreviewItems"
            location="top"
            :text="allSelectedPreviewTargetsAreStream ? 'STRM 资源暂不支持智能调轴。' : (hasSelectedPreviewStreamTargets ? 'STRM 目标会跳过调轴，其余本地视频正常处理。' : '写入前会分析视频/字幕时间轴，可能占用 CPU 并造成短暂卡顿。')"
          >
            <template #activator="{ props: tooltipProps }">
              <div
                v-bind="tooltipProps"
                class="timeline-action"
              >
                <VSwitch
                  v-model="fixTimeline"
                  color="primary"
                  density="comfortable"
                  hide-details
                  :disabled="!timelineAvailable || allSelectedPreviewTargetsAreStream"
                  :label="hasSelectedPreviewStreamTargets ? '智能调轴（STRM跳过）' : '智能调轴'"
                />
              </div>
            </template>
          </VTooltip>
          <VBtn
            v-if="hasPreviewItems"
            color="success"
            :disabled="!canApply"
            :loading="applying"
            @click="applyUpload"
          >
            写入字幕
          </VBtn>
        </VCardActions>
        <VDivider />
        <VCardText>
          <div
            v-if="!hasPreviewItems"
            class="dropzone"
            :class="{ dragging }"
            @drop="handleDrop"
            @dragover="handleDragOver"
            @dragleave="handleDragLeave"
          >
            <div class="dropzone-icon">SRT / ASS / ZIP / RAR</div>
            <div class="dropzone-title">把字幕或压缩包拖到这里</div>
            <div class="dropzone-text">
              支持字幕文件、ZIP、RAR；RAR 需容器内解压器支持。
            </div>
            <VBtn
              color="primary"
              variant="flat"
              :disabled="preparing"
              :loading="preparing"
              @click="openFileDialog"
            >
              选择文件
            </VBtn>
            <input
              ref="fileInputRef"
              class="hidden-input"
              type="file"
              multiple
              accept=".srt,.ass,.ssa,.sbv,.sub,.vtt,.webvtt,.zip,.rar"
              @change="onPickFiles"
            >
          </div>

          <div v-if="!hasPreviewItems" class="support-row">
            <span :class="{ ok: rarPythonAvailable }">rarfile：{{ rarPythonAvailable ? '已安装' : '将由 requirements.txt 安装' }}</span>
            <span :class="{ ok: rarAvailable }">RAR 解压器：{{ rarAvailable ? archiveStatus.rar_tool || '可用' : '未检测到' }}</span>
            <span :class="{ ok: rarDependencyStatus.state === 'ready' }">
              处理方式：{{ rarDependencyModeLabel(archiveStatus.dependency_mode) }}
            </span>
            <button class="support-help" type="button" @click="openRarHelp">
              RAR 不能解压？查看处理方式
            </button>
            <span :class="{ ok: timelineAvailable }">
              智能调轴：{{ timelineAvailable ? '可用' : `缺少 ${timelineMissing || '依赖'}` }}
            </span>
          </div>

          <div v-if="!hasPreviewItems && files.length" class="file-list">
            <div v-for="file in files" :key="`${file.name}-${file.size}`" class="file-row">
              <div>
                <strong>{{ file.name }}</strong>
                <span>{{ formatBytes(file.size) }}</span>
              </div>
              <VBtn size="small" variant="text" color="error" @click="removeFile(file)">移除</VBtn>
            </div>
          </div>

          <div v-if="hasPreviewItems" class="preview-list">
            <div class="preview-head">
              <div>
                <div class="section-kicker">字幕匹配</div>
                <h3>确认集数与输出文件名</h3>
              </div>
              <div class="batch-language">
                <VTextField
                  v-model="batchLanguageSuffix"
                  label="批量语言后缀"
                  placeholder="chi / eng / jpn"
                  variant="outlined"
                  density="comfortable"
                  hide-details
                  @keyup.enter="applyBatchLanguageSuffix"
                />
                <VBtn
                  variant="tonal"
                  color="primary"
                  :disabled="!batchLanguageSuffix.trim()"
                  @click="applyBatchLanguageSuffix"
                >
                  应用到全部
                </VBtn>
              </div>
            </div>
            <div
              v-for="item in preview.items"
              :key="item.upload_id"
              class="preview-row"
              :class="{ disabled: item.selected === false }"
            >
              <VCheckbox
                :model-value="item.selected !== false"
                density="compact"
                hide-details
                @update:model-value="value => togglePreviewItem(item.upload_id, value)"
              />
              <div class="subtitle-source">
                <strong>{{ item.source_name }}</strong>
                <span>
                  {{ item.archive_name ? `来自 ${item.archive_name} · ` : '' }}{{ item.detected_label || '未知语言' }}
                </span>
              </div>
              <VSelect
                :model-value="item.target_id"
                :items="targetSelectItems"
                label="对应集数"
                variant="outlined"
                density="comfortable"
                hide-details
                :disabled="item.selected === false"
                @update:model-value="value => updatePreviewTarget(item.upload_id, value)"
              />
              <VTextField
                :model-value="item.language_suffix"
                label="语言后缀"
                variant="outlined"
                density="comfortable"
                hide-details
                :disabled="item.selected === false"
                @update:model-value="value => updateLanguageSuffix(item.upload_id, value)"
              />
              <div class="output-name">
                <span>改名为</span>
                <strong>{{ item.output_name || buildOutputName(uploadTargets.find(target => target.id === item.target_id), item) || '待选择目标' }}</strong>
              </div>
            </div>
          </div>
        </VCardText>
      </VCard>
    </VDialog>

    <VDialog v-model="rarHelpDialog" max-width="820">
      <VCard class="rar-help-dialog" rounded="xl">
        <VCardTitle class="dialog-title">
          <span>RAR 解压器说明</span>
          <VBtn icon="mdi-close" variant="text" @click="rarHelpDialog = false" />
        </VCardTitle>
        <VDivider />
        <VCardText>
          <div class="rar-help-summary">
            <p><strong>说明：</strong><code>rarfile</code> 只是 Python 调用封装，不是独立解压器。</p>
            <p><strong>要求：</strong>MoviePilot 容器内需要能执行 <code>unrar</code>、<code>7z</code>、<code>7za</code>、<code>7zz</code> 或 <code>bsdtar</code>。</p>
            <p><strong>方案：</strong>临时测试可在容器内安装；长期使用推荐通过国内镜像下载宿主机静态 <code>7zz</code>，设置执行权限后映射到容器内 <code>/usr/local/bin/7z</code>。</p>
          </div>

          <div class="rar-help-list">
            <section
              v-for="item in rarHelpItems"
              :key="item.title"
              class="rar-help-row"
            >
              <div class="rar-help-row-head">
                <div class="rar-help-row-title">
                  <span class="rar-help-step">{{ item.badge }}</span>
                  <strong>{{ item.title }}</strong>
                </div>
                <button
                  type="button"
                  class="rar-help-copy"
                  @click="copyHelpText(item.command, item.copyLabel)"
                >
                  {{ item.button }}
                </button>
              </div>
              <p>{{ item.description }}</p>
              <div class="command-block">
                <pre>{{ item.command }}</pre>
              </div>
            </section>
          </div>

          <VAlert
            v-if="copyMessage"
            class="mt-4"
            type="success"
            variant="tonal"
            :text="copyMessage"
          />
          <VAlert
            v-else-if="copyError"
            class="mt-4"
            type="warning"
            variant="tonal"
            :text="copyError"
          />

          <VAlert
            v-if="rarDependencyStatus.message"
            class="mt-4"
            :type="rarDependencyStatus.state === 'ready' ? 'success' : 'warning'"
            variant="tonal"
            :text="rarDependencyStatus.message"
          />

          <VAlert
            class="mt-4"
            type="info"
            variant="tonal"
            text="插件不会主动重启 Docker 容器。映射文件后需要按你的部署方式重建或重启 MoviePilot 容器；安装或映射完成后，刷新插件状态即可重新检测。"
          />
        </VCardText>
      </VCard>
    </VDialog>
  </div>
</template>

<style scoped>
.subtitle-upload-page {
  min-height: 100%;
  padding: 24px;
  background:
    radial-gradient(circle at 12% 12%, rgba(210, 154, 79, 0.18), transparent 28%),
    radial-gradient(circle at 88% 0%, rgba(48, 90, 82, 0.16), transparent 32%),
    linear-gradient(180deg, #f5f0e7 0%, #edf1ec 100%);
  color: #263238;
  font-family: "LXGW WenKai Screen", "Noto Serif SC", "PingFang SC", sans-serif;
}

.hero-card,
.glass-card {
  border: 1px solid rgba(83, 103, 94, 0.16);
  background: rgba(255, 252, 245, 0.88);
  box-shadow: 0 24px 70px rgba(43, 62, 58, 0.1);
  backdrop-filter: blur(14px);
}

.hero-card {
  padding: 26px;
  margin-bottom: 18px;
  border-radius: 28px;
}

.hero-card h1,
.search-head h2,
.detail-head h2,
.preview-head h3 {
  margin: 0;
  letter-spacing: -0.04em;
}

.hero-card p,
.search-head p,
.detail-head p {
  margin: 8px 0 0;
  color: #64746f;
  line-height: 1.7;
}

.section-kicker,
.media-type {
  color: #8a6b3f;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.root-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.root-tabs button {
  padding: 9px 16px;
  border: 1px solid rgba(91, 109, 100, 0.16);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.74);
  color: #53655f;
  font-weight: 900;
}

.root-tabs button.active {
  border-color: rgba(150, 99, 40, 0.58);
  background: #fff4da;
  color: #30443f;
  box-shadow: inset 0 -3px 0 #b47a35;
}

.media-stage,
.episode-stage {
  display: grid;
  gap: 16px;
}

.search-card {
  border-radius: 28px;
}

.search-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.search-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px auto;
  gap: 12px;
  align-items: center;
}

.media-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}

.media-card {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  width: 100%;
  min-height: 112px;
  padding: 12px;
  border: 1px solid rgba(83, 103, 94, 0.16);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.76);
  color: inherit;
  text-align: left;
  content-visibility: auto;
  contain-intrinsic-size: 112px;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.media-card:hover {
  transform: translateY(-2px);
  border-color: rgba(159, 107, 45, 0.45);
  background: #fff8ea;
}

.poster-frame,
.mini-poster {
  display: grid;
  place-items: center;
  overflow: hidden;
  background: #30463f;
  color: #fffaf0;
}

.poster-frame {
  width: 72px;
  height: 96px;
  border-radius: 16px;
}

.poster-frame.compact {
  width: 56px;
  height: 74px;
  border-radius: 14px;
  font-size: 12px;
}

.poster-frame img,
.mini-poster img {
  display: block;
  width: 100%;
  height: 100%;
  background: #30463f;
  object-fit: cover;
}

.media-copy {
  min-width: 0;
}

.media-copy h3 {
  margin: 4px 0 6px;
  font-size: 17px;
  word-break: break-word;
}

.media-copy p {
  margin: 0;
  color: #687873;
  font-size: 13px;
}

.pager-row {
  display: flex;
  justify-content: center;
  gap: 12px;
  align-items: center;
  padding: 4px 0 8px;
  color: #687873;
  font-size: 13px;
}

.global-history-list {
  display: grid;
  gap: 12px;
}

.auto-queue-card {
  margin-bottom: 14px;
  border: 1px solid rgba(192, 126, 42, 0.18);
  background: linear-gradient(135deg, rgba(255, 246, 226, 0.92), rgba(255, 255, 255, 0.78));
}

.auto-queue-head,
.auto-queue-rates,
.auto-queue-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.auto-queue-rates {
  justify-content: flex-start;
  flex-wrap: wrap;
  margin-top: 10px;
  color: rgba(35, 42, 39, 0.62);
  font-size: 0.82rem;
}

.auto-queue-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.auto-queue-row {
  border-radius: 14px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.74);
}

.auto-queue-row span {
  color: rgba(35, 42, 39, 0.62);
  font-size: 0.82rem;
}

.auto-queue-failed {
  border: 1px solid rgba(198, 58, 58, 0.24);
}

.auto-queue-in_progress,
.auto-queue-pending {
  border: 1px solid rgba(192, 126, 42, 0.24);
}

.global-history-card {
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 22px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.76);
}

.global-history-head {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  width: 100%;
  padding: 12px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
}

.global-history-targets {
  display: grid;
  gap: 10px;
  padding: 0 12px 12px;
}

.history-bulk-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border: 1px solid rgba(91, 109, 100, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.58);
}

.history-bulk-copy {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: #53655f;
  font-size: 12px;
}

.history-bulk-copy strong {
  color: #263a33;
  font-size: 13px;
}

.history-bulk-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.history-season-tree {
  display: grid;
  gap: 8px;
}

.history-season-node {
  overflow: hidden;
  border: 1px solid rgba(91, 109, 100, 0.13);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.62);
}

.history-season-row,
.history-episode-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-height: 46px;
  padding: 6px 10px;
}

.history-season-toggle,
.history-episode-toggle {
  display: flex;
  min-width: 0;
  gap: 8px;
  align-items: center;
  border: 0;
  background: transparent;
  color: #30443f;
  text-align: left;
}

.history-season-toggle strong,
.history-episode-toggle .episode-title {
  min-width: 0;
  overflow: hidden;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-season-toggle span,
.history-episode-toggle small {
  flex: 0 0 auto;
  color: #6f7f79;
  font-size: 12px;
}

.history-season-toggle em {
  flex: 0 0 auto;
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(255, 244, 218, 0.9);
  color: #8a5f23;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.history-episode-list {
  display: grid;
  gap: 6px;
  padding: 0 10px 10px 42px;
}

.history-episode-list.direct-targets {
  padding: 8px 10px 10px;
}

.history-episode-node {
  border-radius: 12px;
  background: rgba(245, 241, 232, 0.52);
}

.history-subtitle-children {
  display: grid;
  gap: 8px;
  padding: 0 10px 10px 42px;
}

.history-row.compact-row {
  border-radius: 16px;
  background: rgba(245, 241, 232, 0.58);
}

.history-row.selectable {
  grid-template-columns: auto minmax(0, 1fr) auto;
}

.compact-subtitles {
  margin-top: 8px;
}

.detail-card {
  border-radius: 28px;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.selected-media {
  display: grid;
  grid-template-columns: auto 58px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.back-btn {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border: 0;
  border-radius: 999px;
  background: #e8ded0;
  color: #30443f;
}

.mini-poster {
  width: 58px;
  height: 78px;
  border-radius: 14px;
  font-size: 12px;
}

.season-strip {
  display: flex;
  gap: 10px;
  max-width: 100%;
  padding-bottom: 12px;
  margin-bottom: 14px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  -webkit-overflow-scrolling: touch;
}

.season-card {
  display: inline-flex;
  flex: 0 0 auto;
  gap: 8px;
  align-items: center;
  min-width: max-content;
  padding: 10px 16px;
  border: 1px solid rgba(91, 109, 100, 0.16);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.74);
  color: inherit;
  text-align: left;
  white-space: nowrap;
}

.season-card.active {
  border-color: rgba(150, 99, 40, 0.58);
  background: #fff4da;
  box-shadow: inset 0 -3px 0 #b47a35;
}

.season-card span {
  font-weight: 800;
}

.season-card strong {
  color: #6d7b76;
  font-size: 13px;
}

.toolbar-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding: 12px;
  border-radius: 20px;
  background: rgba(238, 232, 219, 0.58);
}

.toolbar-hint {
  flex: 1 1 260px;
  color: #687873;
  font-size: 12px;
}

.ai-status-strip {
  display: flex;
  width: 100%;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 12px;
  border: 1px solid rgba(165, 118, 46, 0.2);
  border-radius: 18px;
  background: linear-gradient(90deg, rgba(255, 244, 218, 0.9), rgba(235, 242, 236, 0.72));
  color: #31463f;
  text-align: left;
}

.ai-status-strip.active {
  border-color: rgba(190, 135, 48, 0.46);
  box-shadow: inset 0 0 0 1px rgba(190, 135, 48, 0.12);
}

.ai-status-strip.unavailable {
  background: rgba(245, 241, 232, 0.78);
  color: #7a6d61;
}

.ai-status-orb {
  display: grid;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 999px;
  background: #31463f;
  color: #fff8e8;
}

.ai-status-strip strong {
  font-size: 13px;
  font-weight: 900;
}

.ai-status-strip em {
  min-width: 0;
  overflow: hidden;
  color: #687873;
  font-size: 12px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-tabs {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 12px;
}

.detail-tabs button {
  padding: 8px 14px;
  border: 1px solid rgba(91, 109, 100, 0.16);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.74);
  color: #53655f;
  font-weight: 900;
}

.detail-tabs button.active {
  border-color: rgba(150, 99, 40, 0.58);
  background: #fff4da;
  color: #30443f;
  box-shadow: inset 0 -3px 0 #b47a35;
}

.match-panel,
.history-panel {
  min-width: 0;
}

.episode-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.episode-row {
  display: grid;
  grid-template-columns: auto auto 58px minmax(0, 1fr) repeat(5, auto);
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.76);
}

.episode-row.locked {
  background: rgba(238, 228, 207, 0.68);
}

.episode-expand-btn {
  min-width: 34px;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(91, 109, 100, 0.16);
  background: rgba(232, 237, 240, 0.82);
  color: #53655f;
}

.episode-expanded {
  display: grid;
  grid-column: 1 / -1;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(248, 250, 247, 0.72);
}

.compact-status {
  margin-top: 0;
}

.timeline-meta-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
  min-width: 160px;
}

.timeline-meta {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid rgba(var(--v-theme-outline), 0.24);
  background: rgba(var(--v-theme-surface), 0.78);
  color: rgba(var(--v-theme-on-surface), 0.74);
  font-size: 12px;
  line-height: 1.35;
}

.compact-subtitles {
  grid-column: 1 / -1;
}

.compact-empty {
  padding: 12px;
  border-radius: 14px;
}

.episode-index {
  display: grid;
  min-width: 48px;
  min-height: 34px;
  place-items: center;
  border-radius: 999px;
  background: #e8edf0;
  color: #53655f;
  font-size: 12px;
  font-weight: 900;
}

.episode-title {
  font-weight: 900;
  word-break: break-word;
}

.episode-path {
  margin-top: 4px;
  color: #6f7f79;
  font-size: 12px;
  word-break: break-all;
}

.cc-btn {
  color: #97a09c;
}

.cc-btn.has-sub {
  color: #2f7d62;
}

.ai-row-btn {
  border-radius: 999px;
}

.ai-row-btn.ai-pending,
.ai-row-btn.ai-in_progress {
  background: rgba(255, 230, 177, 0.72);
}

.ai-row-btn.ai-completed {
  background: rgba(219, 243, 226, 0.82);
}

.ai-row-btn.ai-failed {
  background: rgba(255, 226, 224, 0.82);
}

.ai-row-btn.ai-cancelled {
  background: rgba(229, 232, 231, 0.82);
}

.empty-state {
  padding: 28px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.58);
  color: #687873;
  text-align: center;
}

.result-panel {
  display: grid;
  gap: 10px;
  padding-top: 18px;
  margin-top: 18px;
  border-top: 1px solid rgba(91, 109, 100, 0.14);
}

.result-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.7);
}

.result-row div {
  display: grid;
  gap: 3px;
}

.result-row .timeline-meta-list {
  display: flex;
  gap: 6px;
}

.result-row span,
.result-row em {
  color: #687873;
  font-size: 12px;
  font-style: normal;
}

.history-list {
  display: grid;
  gap: 12px;
}

.history-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 12px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.76);
}

.history-main {
  min-width: 0;
}

.history-status {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.history-status span {
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(232, 237, 240, 0.72);
  color: #53655f;
  font-size: 12px;
}

.history-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.subtitle-history-list {
  display: grid;
  grid-column: 1 / -1;
  gap: 8px;
}

.subtitle-history-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(245, 241, 232, 0.68);
}

.subtitle-history-copy {
  min-width: 0;
  flex: 1 1 auto;
}

.subtitle-history-item strong,
.subtitle-history-item span {
  display: block;
  overflow-wrap: anywhere;
}

.subtitle-history-item span {
  color: #687873;
  font-size: 12px;
}

.subtitle-history-actions {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  padding: 4px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.78);
}

.subtitle-history-actions .v-btn {
  min-width: 52px;
}

.upload-dialog {
  background:
    radial-gradient(circle at 10% 0%, rgba(215, 167, 98, 0.2), transparent 28%),
    #fffaf2;
}

.online-dialog {
  background:
    radial-gradient(circle at 12% 0%, rgba(80, 126, 107, 0.14), transparent 30%),
    radial-gradient(circle at 88% 18%, rgba(214, 160, 82, 0.16), transparent 30%),
    #fffaf2;
}

.online-batch-btn {
  box-shadow: 0 12px 28px rgba(47, 111, 82, 0.22);
  font-weight: 900;
}

.ai-task-dialog {
  background:
    radial-gradient(circle at 8% 0%, rgba(219, 164, 71, 0.18), transparent 28%),
    radial-gradient(circle at 90% 20%, rgba(65, 116, 95, 0.14), transparent 32%),
    #fffaf2;
}

.ai-task-list {
  display: grid;
  gap: 10px;
}

.ai-restart-options {
  margin-bottom: 14px;
}

.ai-task-row {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
}

.ai-task-row.ai-in_progress,
.ai-task-row.ai-pending {
  border-color: rgba(180, 122, 53, 0.3);
  background: #fff4da;
}

.ai-task-row.ai-completed {
  border-color: rgba(77, 143, 100, 0.26);
  background: rgba(230, 247, 235, 0.78);
}

.ai-task-row.ai-failed {
  border-color: rgba(185, 78, 70, 0.3);
  background: rgba(255, 234, 232, 0.8);
}

.ai-task-row.ai-cancelled {
  border-color: rgba(109, 123, 117, 0.24);
  background: rgba(239, 242, 240, 0.84);
}

.ai-task-badge {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 999px;
  background: #31463f;
  color: #fff8e8;
}

.ai-task-main {
  min-width: 0;
}

.ai-task-main strong,
.ai-task-main span,
.ai-task-main p {
  display: block;
}

.ai-task-main strong {
  font-weight: 900;
  word-break: break-word;
}

.ai-task-main span,
.ai-task-main p,
.ai-task-time span {
  color: #687873;
  font-size: 12px;
}

.ai-task-main p {
  margin: 4px 0 0;
}

.ai-task-time {
  display: grid;
  justify-items: end;
  gap: 6px;
}

.online-search-actions {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(220px, 0.7fr) auto;
  gap: 12px;
  padding: 14px 18px;
  background: rgba(255, 250, 242, 0.96);
}

.online-message-summary {
  margin-bottom: 14px;
}

.online-message-summary-content {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.online-message-summary-content span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.online-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 16px;
}

.online-results-panel,
.manual-links-panel {
  min-width: 0;
  padding: 14px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.7);
}

.online-panel-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.online-panel-head h3,
.manual-links-panel h3 {
  margin: 4px 0 0;
}

.online-panel-head span,
.manual-links-panel p,
.manual-provider-head span,
.online-result-meta,
.online-result-main p {
  color: #687873;
  font-size: 12px;
}

.online-provider-filter {
  margin: -4px 0 12px;
}

.online-provider-progress {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.online-provider-filter-active {
  background: #2f604f !important;
  color: #fff !important;
}

.online-loading {
  padding: 24px;
  border-radius: 18px;
  background: #f3eadb;
  color: #53655f;
  text-align: center;
}

.online-result-list {
  display: grid;
  gap: 10px;
  max-height: 520px;
  overflow-y: auto;
  padding-right: 4px;
}

.online-result-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 12px;
  border: 1px solid rgba(91, 109, 100, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.76);
}

.online-result-card.active {
  border-color: rgba(150, 99, 40, 0.5);
  background: #fff4da;
}

.online-result-card.disabled {
  opacity: 0.72;
  background: rgba(245, 241, 232, 0.72);
}

.online-result-main {
  min-width: 0;
}

.online-result-title {
  font-weight: 900;
  word-break: break-word;
}

.online-result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.online-manual-badge {
  padding: 1px 8px;
  border: 1px solid rgba(150, 99, 40, 0.24);
  border-radius: 999px;
  background: rgba(150, 99, 40, 0.1);
  color: #7c4d18;
  font-weight: 800;
}

.online-result-main p {
  margin: 6px 0 0;
}

.online-match-detail {
  color: #8a6b3f !important;
}

.online-open-link,
.manual-keywords a {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #e7eee8;
  color: #2f604f;
  font-size: 12px;
  font-weight: 900;
  text-decoration: none;
}

.manual-links-panel {
  align-self: start;
}

.manual-links-panel p {
  margin: 8px 0 14px;
  line-height: 1.6;
}

.manual-provider {
  display: grid;
  gap: 8px;
  padding: 10px 0;
  border-top: 1px solid rgba(91, 109, 100, 0.12);
}

.manual-provider-head {
  display: grid;
  gap: 2px;
}

.manual-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.dialog-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dialog-title p {
  margin: 4px 0 0;
  color: #687873;
  font-size: 12px;
  font-weight: 400;
}

.online-title-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}

.dropzone {
  position: relative;
  display: grid;
  gap: 10px;
  justify-items: center;
  padding: 30px 18px;
  border: 1px dashed rgba(151, 101, 42, 0.48);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 250, 239, 0.95), rgba(241, 236, 225, 0.9));
  text-align: center;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.dropzone.dragging {
  transform: translateY(-1px);
  border-color: rgba(169, 105, 26, 0.9);
  background: #fff1d3;
}

.dropzone-icon {
  padding: 6px 10px;
  border-radius: 999px;
  background: #314840;
  color: #fff9ed;
  font-size: 12px;
  font-weight: 900;
}

.dropzone-title {
  font-size: 18px;
  font-weight: 900;
}

.dropzone-text,
.support-row,
.file-row span,
.subtitle-source span,
.output-name span {
  color: #687873;
  font-size: 12px;
}

.hidden-input {
  display: none;
}

.support-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.support-row span {
  padding: 5px 9px;
  border-radius: 999px;
  background: #ece8df;
}

.support-row span.ok {
  background: #e2f1e9;
  color: #2f7d62;
}

.support-help {
  padding: 5px 10px;
  border: 0;
  border-radius: 999px;
  background: #fff0d6;
  color: #9a611d;
  font-size: 12px;
  font-weight: 800;
}

.rar-help-dialog {
  background: #fffaf2;
}

.rar-help-summary {
  color: #52635d;
  line-height: 1.7;
}

.rar-help-summary code {
  padding: 1px 5px;
  border-radius: 6px;
  background: #efe6d8;
}

.rar-help-summary {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid rgba(91, 109, 100, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.64);
}

.rar-help-summary p {
  margin: 0;
}

.rar-help-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.rar-help-row {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
}

.rar-help-row-head {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}

.rar-help-row-title {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.rar-help-step {
  padding: 3px 8px;
  border-radius: 999px;
  background: #efe6d8;
  color: #8a6b3f;
  font-size: 12px;
  font-weight: 900;
}

.rar-help-copy {
  flex: 0 0 auto;
  padding: 8px 14px;
  border: 0;
  border-radius: 999px;
  background: #2f443d;
  color: #fff6e8;
  cursor: pointer;
  font-size: 12px;
  font-weight: 900;
  box-shadow: 0 8px 18px rgba(47, 68, 61, 0.18);
}

.rar-help-copy:hover {
  background: #243730;
}

.rar-help-row-title strong {
  color: #2f443d;
}

.rar-help-row p {
  margin: 0;
  color: #687873;
  font-size: 12px;
  line-height: 1.6;
}

.command-block {
  min-width: 0;
}

.command-block pre {
  padding: 10px;
  margin: 0;
  overflow-x: auto;
  border-radius: 12px;
  background: #2f443d;
  color: #fff6e8;
  font-size: 12px;
  line-height: 1.5;
}

.file-list,
.preview-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.file-row,
.preview-row {
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
}

.file-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
}

.file-row div,
.subtitle-source,
.output-name {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.preview-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.batch-language {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-width: min(100%, 360px);
}

.preview-row {
  display: grid;
  grid-template-columns: auto minmax(160px, 1fr) minmax(210px, 1fr) 116px minmax(180px, 1fr);
  gap: 10px;
  align-items: center;
  padding: 12px;
}

.preview-row.disabled {
  opacity: 0.58;
}

.subtitle-source strong,
.output-name strong {
  word-break: break-word;
}

.dialog-actions {
  padding: 12px 18px;
}

.dialog-actions-top {
  flex-wrap: wrap;
  gap: 8px;
  background: rgba(255, 250, 242, 0.96);
}

.timeline-action {
  display: flex;
  align-items: center;
}

@media (max-width: 900px) {
  .subtitle-upload-page {
    padding: 14px;
  }

  .hero-card,
  .search-bar,
  .online-search-actions,
  .online-layout,
  .detail-head,
  .preview-row {
    grid-template-columns: 1fr;
  }

  .rar-help-row-head {
    align-items: stretch;
    flex-direction: column;
  }

  .rar-help-copy {
    width: 100%;
  }

  .detail-head,
  .search-head,
  .preview-head {
    display: grid;
  }

  .detail-tabs {
    justify-content: stretch;
  }

  .detail-tabs button {
    flex: 1 1 0;
  }

  .history-row,
  .subtitle-history-item {
    grid-template-columns: 1fr;
  }

  .history-row.selectable {
    grid-template-columns: 1fr;
  }

  .history-season-row,
  .history-episode-row {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .history-episode-row > .v-btn {
    grid-column: 2;
    justify-self: start;
  }

  .history-episode-list,
  .history-subtitle-children {
    padding-left: 16px;
  }

  .history-season-toggle,
  .history-episode-toggle {
    flex-wrap: wrap;
  }

  .subtitle-history-item {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-actions {
    justify-content: flex-start;
  }

  .subtitle-history-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .online-title-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .batch-language {
    grid-template-columns: 1fr;
  }

  .dialog-actions-top {
    align-items: stretch;
  }

  .dialog-actions-top .v-btn {
    flex: 1 1 auto;
  }

  .episode-row {
    grid-template-columns: auto auto 48px minmax(0, 1fr);
  }

  .episode-row > .cc-btn,
  .episode-row > .v-btn:not(.episode-expand-btn) {
    justify-self: start;
  }
}
</style>
