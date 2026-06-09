<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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
const dragging = ref(false)
const message = ref('')
const error = ref('')
const onlineError = ref('')
const searchKeyword = ref('')
const mediaType = ref('all')
const medias = ref([])
const selectedMedia = ref(null)
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
const onlineProviderFilter = ref('all')
const onlineMessages = ref([])
const onlineMessagesCollapsed = ref(false)
const onlineManualLinks = ref([])
const onlineProviderProgress = ref({})
const selectedOnlineResultIds = ref([])
const aiTaskDialog = ref(false)
const aiTaskDialogTarget = ref(null)
const aiTaskData = ref({
  status: null,
  summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, ignored: 0, no_audio: 0, failed: 0, cancelled: 0 },
  tasks: [],
  task_by_target: {},
})
let aiTaskTimer = null
let onlineSearchSeq = 0
let onlineDownloadSeq = 0
const ONLINE_PROVIDER_TIMEOUT_MS = 25000
const ONLINE_DOWNLOAD_TIMEOUT_MS = 35000

const onlineProviderItems = [
  { title: '射手网(伪)', value: 'assrt' },
  { title: 'OpenSubtitles', value: 'opensubtitles' },
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
  const items = preview.value?.items || []
  return items.length > 0 && items.every(item => item.target_id)
})
const hasPreviewItems = computed(() => (preview.value?.items || []).length > 0)
const hasOnlineResults = computed(() => onlineResults.value.length > 0)
const filteredOnlineResults = computed(() => {
  if (onlineProviderFilter.value === 'all') return onlineResults.value
  return onlineResults.value.filter(item => onlineResultLanguageCategory(item) === onlineProviderFilter.value)
})
const onlineProviderFilterItems = computed(() => {
  const languageItems = [
    { title: '中文', value: 'chinese' },
    { title: '英文', value: 'english' },
    { title: '日文', value: 'japanese' },
    { title: '其他', value: 'other' },
  ]
  const counts = onlineResults.value.reduce((acc, item) => {
    const category = onlineResultLanguageCategory(item)
    acc[category] = (acc[category] || 0) + 1
    return acc
  }, {})
  return [
    { title: `全部 ${onlineResults.value.length}`, value: 'all' },
    ...languageItems.map(item => ({ title: `${item.title} ${counts[item.value] || 0}`, value: item.value })),
  ]
})
const selectedOnlineResults = computed(() => {
  const picked = new Set(selectedOnlineResultIds.value)
  return onlineResults.value.filter(item => picked.has(onlineResultKey(item)) && isOnlineResultDownloadable(item))
})
const canSubmitOnlineAiTranslate = computed(() => {
  return aiAvailable.value && selectedOnlineResults.value.length > 0 && selectedOnlineResults.value.every(isEnglishOnlineResult)
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
const onlineApiStatusText = computed(() => {
  const parts = []
  parts.push(`射手网(伪) ${onlineStatus.value?.assrt_api_configured ? '已配置' : '未配置'}`)
  parts.push(`OpenSubtitles 搜索 ${onlineStatus.value?.opensubtitles_api_configured ? '已配置' : '未配置'}`)
  parts.push(`OpenSubtitles 下载认证 ${onlineStatus.value?.opensubtitles_download_configured ? '已配置' : '未配置'}`)
  return `${parts.join(' · ')}。右侧有 SubHD/Zimuku 手动跳转入口。`
})
const onlineAiConfirmText = computed(() => {
  const count = selectedOnlineResults.value.length
  const targetCount = onlineTargets.value.length
  return `将下载 ${count} 个英文字幕结果，并提交给 AI字幕生成(联动版) 翻译；当前范围包含 ${targetCount} 个目标。`
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
const timelineMissing = computed(() => {
  const missing = []
  if (timelineStatus.value.ffmpeg === false) missing.push('ffmpeg')
  if (timelineStatus.value.ffprobe === false) missing.push('ffprobe')
  const modules = timelineStatus.value.modules || {}
  Object.entries(modules).forEach(([name, ok]) => {
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

function timelineResultText(item) {
  const timeline = item?.timeline || {}
  if (!timeline.enabled) return '未启用智能调轴'
  const base = timeline.base === 'audio' ? '音频基准' : '内置字幕基准'
  if (timeline.applied) {
    return `已调轴 ${formatOffset(timeline.offset_seconds)} · ${base}`
  }
  return `未调整：偏移 ${formatOffset(timeline.offset_seconds)} 小于阈值 · ${base}`
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

function onlineResultKey(item) {
  return `${item?.provider || 'unknown'}:${item?.result_id || item?.page_url || item?.title || ''}`
}

function providerName(providerId) {
  const known = onlineProviderItems.find(item => item.value === providerId)
  return known?.title || providerId || '未知来源'
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
  if (['chinese', 'english', 'japanese', 'other'].includes(category)) return category
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
  return 'other'
}

function isEnglishOnlineResult(item) {
  return onlineResultLanguageCategory(item) === 'english'
}

function providerStatus(providerId) {
  const providers = [
    ...(onlineStatus.value.providers || []),
    ...(onlineStatus.value.manual_providers || []),
  ]
  const item = providers.find(provider => provider.id === providerId)
  const host = item?.host ? `${item.host} · ` : ''
  return `${host}${item?.message || ''}`
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
  const configured = []
  if (onlineStatus.value?.assrt_api_configured) configured.push('assrt')
  if (onlineStatus.value?.opensubtitles_api_configured) configured.push('opensubtitles')
  if (!configured.length) return
  onlineSelectedProviders.value = configured
}

function stopAiPolling() {
  if (aiTaskTimer) {
    clearTimeout(aiTaskTimer)
    aiTaskTimer = null
  }
}

function scheduleAiPolling() {
  stopAiPolling()
  if (!aiHasActiveTasks.value || !visibleTargets.value.length) return
  aiTaskTimer = setTimeout(() => {
    loadAiTasks({ silent: true })
  }, 5000)
}

async function loadAiTasks(options = {}) {
  if (!visibleTargets.value.length) {
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
      target_ids: visibleTargets.value.map(item => item.id),
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

function aiTaskForTarget(target) {
  return (aiTaskData.value.task_by_target || {})[target?.id] || null
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

function openAiTaskDialog(target = null) {
  aiTaskDialogTarget.value = target
  aiTaskDialog.value = true
  loadAiTasks({ silent: true })
}

async function submitAiForTargets(scopeTargets) {
  const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false)
  if (!usableTargets.length) {
    error.value = '没有可生成 AI 字幕的目标：选中的集数可能都已锁定'
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
    })
    const data = unwrapResponse(response) || {}
    if (data.tasks) {
      aiTaskData.value = data.tasks
    }
    message.value = response?.message || '已提交 AI 字幕生成任务'
    await loadAiTasks({ silent: true })
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
    })
    const data = unwrapResponse(response) || {}
    if (data.tasks) {
      aiTaskData.value = data.tasks
    }
    message.value = response?.message || '已取消 AI 字幕任务'
    await loadAiTasks({ silent: true })
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
  selectedSeason.value = 'all'
  targets.value = []
  selectedTargetIds.value = []
  preview.value = null
  lastWritten.value = []
  aiTaskDialogTarget.value = null
  aiTaskData.value = {
    ...aiTaskData.value,
    summary: { total: 0, active: 0, pending: 0, in_progress: 0, completed: 0, ignored: 0, no_audio: 0, failed: 0, cancelled: 0 },
    tasks: [],
    task_by_target: {},
  }
  stopAiPolling()
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
  } catch (err) {
    error.value = errorMessage(err, '加载插件状态失败')
  } finally {
    loading.value = false
  }
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

async function runSearch() {
  const keyword = searchKeyword.value.trim()
  searching.value = true
  error.value = ''
  message.value = ''
  selectedMedia.value = null
  clearTargetState()
  try {
    const params = new URLSearchParams()
    params.set('keyword', keyword)
    params.set('media_type', mediaType.value)
    params.set('limit', '48')
    const response = await props.api.get(`${pluginBase.value}/search?${params.toString()}`)
    const data = unwrapResponse(response) || {}
    medias.value = data.medias || []
    if (!medias.value.length) {
      message.value = keyword
        ? '本地资源库里没有匹配的视频目标，请换个关键词试试'
        : '本地整理记录里暂时没有可用的视频目标'
    }
  } catch (err) {
    error.value = errorMessage(err, '搜索本地资源失败')
  } finally {
    searching.value = false
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
    selectedTargetIds.value = []
    await loadAiTasks({ silent: true })

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

function openUploadDialog(scopeTargets, title) {
  const usableTargets = scopeTargets.filter(item => !isLocked(item.id) && item.writable !== false)
  if (!usableTargets.length) {
    error.value = '没有可上传的目标：选中的集数可能都已锁定'
    return
  }
  uploadScopeTargets.value = usableTargets
  uploadTitle.value = title
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
  onlineProviderFilter.value = 'all'
  onlineMessages.value = []
  onlineMessagesCollapsed.value = false
  selectedOnlineResultIds.value = []
  onlineProviderProgress.value = Object.fromEntries(providers.map(provider => [provider, 'searching']))
  let settledCount = 0
  const finishProvider = () => {
    settledCount += 1
    if (settledCount < providers.length || searchSeq !== onlineSearchSeq) return
    if (!onlineResults.value.length && !onlineMessages.value.length) {
      onlineMessages.value = [{ level: 'info', message: '没有搜索到可自动下载的字幕，可使用右侧手动搜索链接。' }]
    }
    onlineSearching.value = false
  }
  providers.forEach(async provider => {
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
    } finally {
      finishProvider()
    }
  })
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
      ? '请只选择英文字幕结果后再提交 AI 翻译。'
      : 'AI 字幕生成联动当前不可用，无法提交翻译任务。'
    return
  }
  onlineError.value = ''
  onlineAiConfirmDialog.value = true
}

function confirmOnlineAiTranslate() {
  onlineAiConfirmDialog.value = false
  downloadOnlinePreview(true)
}

async function downloadOnlinePreview(submitAiTranslate = false) {
  if (!selectedOnlineResults.value.length || onlineDownloading.value) return
  if (submitAiTranslate && !canSubmitOnlineAiTranslate.value) {
    onlineError.value = aiAvailable.value
      ? '请只选择英文字幕结果后再提交 AI 翻译。'
      : 'AI 字幕生成联动当前不可用，无法提交翻译任务。'
    return
  }
  const downloadSeq = ++onlineDownloadSeq
  onlineDownloading.value = true
  onlineError.value = ''
  try {
    const response = await withTimeout(
      props.api.post(`${pluginBase.value}/online_download_preview`, {
        ...onlinePayload(),
        results: selectedOnlineResults.value,
        submit_ai_translate: submitAiTranslate,
      }),
      ONLINE_DOWNLOAD_TIMEOUT_MS,
      '在线字幕下载仍在源站验证中，已停止等待；可换一个结果重试，或打开手动链接下载后上传。',
    )
    if (downloadSeq !== onlineDownloadSeq) return
    preview.value = unwrapResponse(response)
    batchLanguageSuffix.value = ''
    if (preview.value?.items) {
      preview.value.items.forEach(item => {
        const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id)
        item.output_name = item.output_name || buildOutputName(target, item)
      })
    }
    onlineDialog.value = false
    uploadDialog.value = true
    message.value = response?.message || (submitAiTranslate ? '已下载英文字幕并提交 AI 翻译' : '已下载在线字幕并生成匹配预览')
  } catch (err) {
    if (downloadSeq !== onlineDownloadSeq) return
    onlineError.value = errorMessage(err, '在线字幕下载预览失败')
  } finally {
    if (downloadSeq === onlineDownloadSeq) {
      onlineDownloading.value = false
    }
  }
}

function stopOnlineDownload() {
  if (!onlineDownloading.value) return
  onlineDownloadSeq += 1
  onlineDownloading.value = false
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
      preview.value.items.forEach(item => {
        const target = uploadTargets.value.find(targetItem => targetItem.id === item.target_id)
        item.output_name = item.output_name || buildOutputName(target, item)
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

function applyBatchLanguageSuffix() {
  const suffix = batchLanguageSuffix.value.trim()
  if (!suffix || !preview.value?.items?.length) return
  preview.value.items.forEach(item => {
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
  applying.value = true
  error.value = ''
  try {
    const payload = {
      session_id: preview.value.session_id,
      fix_timeline: fixTimeline.value,
      items: preview.value.items.map(item => ({
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
  if (!selectedTargetIds.value.length) return
  clearing.value = true
  error.value = ''
  try {
    const response = await props.api.post(`${pluginBase.value}/clear_subtitles`, {
      target_ids: selectedTargetIds.value,
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

onMounted(async () => {
  await loadStatus()
  await runSearch()
})

onBeforeUnmount(() => {
  stopAiPolling()
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
              <div class="section-kicker">资源选择</div>
              <h2>选择本地已有资源</h2>
              <p>仅展示 MoviePilot 已整理到本地库的视频资源。{{ indexSummary }}</p>
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
              @keyup.enter="runSearch"
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
            <VBtn color="primary" :loading="searching" @click="runSearch">搜索</VBtn>
          </div>
        </VCardText>
      </VCard>

      <div v-if="medias.length" class="media-list">
        <button
          v-for="media in medias"
          :key="media.id"
          class="media-card"
          @click="selectMedia(media)"
        >
          <div class="poster-frame">
            <img
              v-if="media.poster_url"
              :src="media.poster_url"
              :alt="mediaLabel(media)"
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
      <div v-else class="empty-state">
        {{ searching ? '正在读取本地资源...' : '输入关键词搜索；留空搜索会显示最近整理的视频。' }}
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
                  v-if="selectedMedia.poster_url"
                  :src="selectedMedia.poster_url"
                  :alt="mediaLabel(selectedMedia)"
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
              :disabled="!batchUploadTargets.length || !aiAvailable"
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
            <div class="toolbar-hint">
              锁定项不参与批量上传；清空仅删除选中项外挂字幕。
            </div>
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
                :disabled="isLocked(target.id) || (!aiAvailable && !aiTaskForTarget(target))"
                @click="openSingleAiGenerate(target)"
              />
              <VBtn
                variant="text"
                icon="mdi-magnify"
                title="搜索此集在线字幕"
                :disabled="isLocked(target.id)"
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
                :disabled="isLocked(target.id)"
                @click="openSingleUpload(target)"
              >
                单集上传
              </VBtn>
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
            </div>
          </div>
        </VCardText>
      </VCard>
    </section>

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
                <span>{{ task.video_name }}</span>
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

    <VDialog v-model="onlineDialog" max-width="1080">
      <VCard class="online-dialog" rounded="xl">
        <VCardTitle class="dialog-title">
          <div>
            <span>{{ onlineTitle || '在线字幕搜索' }}</span>
            <p>{{ onlineTargets.length }} 个目标 · 下载后进入匹配预览，不会直接写入</p>
          </div>
          <div class="online-title-actions">
            <VBtn
              color="success"
              :disabled="!selectedOnlineResults.length"
              :loading="onlineDownloading"
              @click="downloadOnlinePreview"
            >
              下载并生成预览
            </VBtn>
            <VBtn
              color="primary"
              variant="tonal"
              :disabled="!canSubmitOnlineAiTranslate"
              :loading="onlineDownloading"
              @click="requestOnlineAiTranslate"
            >
              下载并提交 AI 翻译
            </VBtn>
            <VBtn
              v-if="onlineDownloading"
              color="warning"
              variant="tonal"
              @click="stopOnlineDownload"
            >
              停止等待
            </VBtn>
            <VBtn icon="mdi-close" variant="text" @click="onlineDialog = false" />
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
            class="mb-4"
            type="info"
            variant="tonal"
            density="compact"
            :text="onlineApiStatusText"
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
                  <span>{{ providerStatus(provider.provider) }}</span>
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
            text="确认后会下载所选英文字幕并提交 AI 翻译任务；误触后可在 AI 状态里取消。"
          />
        </VCardText>
        <VCardActions class="justify-end">
          <VBtn variant="text" @click="onlineAiConfirmDialog = false">取消</VBtn>
          <VBtn
            color="primary"
            variant="flat"
            :loading="onlineDownloading"
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
            text="写入前会分析视频/字幕时间轴，可能占用 CPU 并造成短暂卡顿。"
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
                  :disabled="!timelineAvailable"
                  label="智能调轴"
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
            >
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
                @update:model-value="value => updatePreviewTarget(item.upload_id, value)"
              />
              <VTextField
                :model-value="item.language_suffix"
                label="语言后缀"
                variant="outlined"
                density="comfortable"
                hide-details
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

.poster-frame img,
.mini-poster img {
  width: 100%;
  height: 100%;
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

.episode-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.episode-row {
  display: grid;
  grid-template-columns: auto 58px minmax(0, 1fr) repeat(5, auto);
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

.result-row span,
.result-row em {
  color: #687873;
  font-size: 12px;
  font-style: normal;
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
  grid-template-columns: minmax(160px, 1fr) minmax(210px, 1fr) 116px minmax(180px, 1fr);
  gap: 10px;
  align-items: center;
  padding: 12px;
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
    grid-template-columns: auto 48px minmax(0, 1fr);
  }

  .episode-row > .cc-btn,
  .episode-row > .v-btn {
    justify-self: start;
  }
}
</style>
