<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { createSubtitleManualUploadApi } from '../api/subtitleManualUploadApi'
import { aiRestartSourceOptions, useAiTasks } from '../composables/useAiTasks'
import { useAutoTransferQueue } from '../composables/useAutoTransferQueue'
import { useMatchHistory } from '../composables/useMatchHistory'
import { useMediaSearch } from '../composables/useMediaSearch'
import { useOnlineSubtitles } from '../composables/useOnlineSubtitles'
import { usePluginStatus } from '../composables/usePluginStatus'
import { useTargets } from '../composables/useTargets'
import { useTimelineTasks } from '../composables/useTimelineTasks'
import { useUploadPreview } from '../composables/useUploadPreview'
import AiTaskDialog from './AiTaskDialog.vue'
import AutoTransferQueueDialog from './AutoTransferQueueDialog.vue'
import MediaGrid from './MediaGrid.vue'
import MatchHistoryPanel from './MatchHistoryPanel.vue'
import MediaSearchPanel from './MediaSearchPanel.vue'
import OnlineSubtitleDialog from './OnlineSubtitleDialog.vue'
import RarHelpDialog from './RarHelpDialog.vue'
import TargetDetailPanel from './TargetDetailPanel.vue'
import UploadDialog from './UploadDialog.vue'
import {
  buildOutputName,
  compactTargetName,
  errorMessage,
  formatBytes,
  formatMediaType,
  formatOffset,
  historyMediaStat,
  mediaLabel,
  mediaStat,
  rarDependencyModeLabel,
  seasonLabel,
  targetLabel,
  timelineMetaItems,
  timelineResultText,
  unwrapResponse,
} from '../utils/formatters'
import {
  isOnlineResultDownloadable,
  onlineProviderItems,
  onlineResultKey,
  onlineResultMeta,
  providerName,
  providerProgressColor,
  providerProgressText,
} from '../utils/onlineResult'
import { isStreamTarget } from '../utils/targetState'

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
const pluginApi = computed(() => createSubtitleManualUploadApi(props.api, pluginBase))
const clearing = ref(false)
const message = ref('')
const error = ref('')

const {
  resolving,
  selectedMedia,
  detailTab,
  seasons,
  selectedSeason,
  selectedTargetIds,
  lockedTargetIds,
  expandedDetailTargetIds,
  visibleTargets,
  selectedTargets,
  targetById,
  unlockedVisibleTargets,
  allVisibleSelected,
  isLocked,
  lockedTargetPayload,
  isTargetActionDisabled,
  detailExpanded,
  toggleDetailExpanded,
  clearTargetState,
  loadTargets,
  selectMedia,
  changeSeason,
  resetSelection,
  toggleSelectAll,
  toggleTarget,
  toggleLock,
} = useTargets({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  mediaLabel,
  clearRelatedState() {
    clearUploadPreviewState()
    resetAiTasks()
    resetTimelineTasks()
  },
  beforeLoadTargets() {
    preview.value = null
  },
  async afterTargetsLoaded(nextTargets) {
    aiTaskScopeTargets.value = nextTargets
    await loadAiTasks({ silent: true })
    await loadTimelineTasks({ silent: true })
  },
  runSearch: () => runSearch(),
})

const {
  searching,
  searchKeyword,
  mediaType,
  medias,
  mediaPage,
  mediaPageSize,
  mediaTotal,
  mediaHasMore,
  posterImageKey,
  posterImageSrc,
  markPosterFailed,
  posterLoading,
  posterFetchPriority,
  runSearch,
  loadMoreMedia,
} = useMediaSearch({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  selectedMedia,
  clearTargetState,
})

const {
  autoTransferQueue,
  autoQueueDialog,
  autoQueueSummary,
  autoQueueTasks,
  autoQueueSummaryText,
  applyAutoTransferSummary,
  stopAutoQueuePolling,
  loadAutoTransferQueue,
} = useAutoTransferQueue({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
})

const {
  rootTab,
  matchHistoryLoading,
  matchHistoryItems,
  matchHistoryTotal,
  matchHistoryHasMore,
  historyExpanded,
  toggleHistoryExpanded,
  historySeasonKey,
  historySeasonExpanded,
  toggleHistorySeasonExpanded,
  historyTargetExpanded,
  toggleHistoryTargetExpanded,
  historyDeletableTargets,
  historySelectedIds,
  historySelectedCount,
  allHistoryTargetsSelected,
  toggleHistoryTarget,
  toggleHistoryItemTargets,
  historySeasonGroups,
  historySeasonSelectedCount,
  allHistorySeasonTargetsSelected,
  historySeasonPartiallySelected,
  toggleHistorySeasonTargets,
  clearHistorySelectedSubtitles,
  historySelectedTimelineTargets,
  fixHistorySelectedTimeline,
  fixHistorySubtitleTimeline,
  stopHistoryTimelinePolling,
  scheduleHistoryTimelinePolling,
  submitRootSearch,
  loadMatchHistory,
  loadMoreMatchHistory,
  setRootTab,
  matchHistorySummary,
} = useMatchHistory({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  clearing,
  searchKeyword,
  mediaType,
  selectedMedia,
  clearTargetState,
  lockedTargetPayload,
  isStreamTarget,
  seasonLabel,
  runSearch,
  fixExistingTimeline: (...args) => fixExistingTimeline(...args),
})

const {
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
} = usePluginStatus({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  rootTab,
  selectedMedia,
  selectedSeason,
  applyAiStatus(nextAiStatus) {
    aiTaskData.value = { ...aiTaskData.value, status: nextAiStatus }
  },
  applyAutoTransferSummary,
  loadAutoTransferQueue,
  loadTargets,
  loadMatchHistory,
  runSearch,
})

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

const {
  preparing,
  applying,
  dragging,
  uploadDialog,
  rarHelpDialog,
  uploadTitle,
  uploadScopeTargets,
  files,
  preview,
  fileInputRef,
  fixTimeline,
  batchLanguageSuffix,
  copyMessage,
  copyError,
  lastWritten,
  uploadTargets,
  batchUploadTargets,
  targetSelectItems,
  canApply,
  hasPreviewItems,
  selectedPreviewItems,
  selectedPreviewTargets,
  allSelectedPreviewTargetsAreStream,
  hasSelectedPreviewStreamTargets,
  timelineEnabledForApply,
  clearUploadPreviewState,
  prepareOnlineUploadState,
  openOnlinePreview,
  openBatchUpload,
  openSingleUpload,
  onPickFiles,
  removeFile,
  openFileDialog,
  handleDrop,
  handleDragOver,
  handleDragLeave,
  updatePreviewTarget,
  updateLanguageSuffix,
  togglePreviewItem,
  applyBatchLanguageSuffix,
  resetUploadPreview,
  openRarHelp,
  copyHelpText,
  applyUpload,
} = useUploadPreview({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  selectedTargets,
  visibleTargets,
  selectedMedia,
  selectedSeason,
  isLocked,
  lockedTargetPayload,
  loadTargets,
  timelineAvailable,
  timelineNeedsRiskyConfirm,
  confirmRiskyTimelineOffset,
  isStreamTarget,
  compactTargetName,
  seasonLabel,
  buildOutputName,
})

const selectedSubtitleTargets = computed(() => selectedTargets.value.filter(target => !isLocked(target.id) && (target.subtitles || []).length))

const {
  timelineFixing,
  timelineTaskData,
  selectedTimelineTargets,
  applyTimelineTaskData,
  resetTimelineTasks,
  stopTimelinePolling,
  loadTimelineTasks,
  timelineTaskForTarget,
  timelineTaskText,
  fixExistingTimeline,
  fixSelectedDetailTimeline,
} = useTimelineTasks({
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
})

const {
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
  aiHasActiveTasks,
  aiBatchCancelTargets,
  aiCapableBatchTargets,
  aiBatchLabel,
  aiSummaryText,
  aiDialogTasks,
  aiDialogHasExistingTasks,
  aiDialogHasActiveTasks,
  aiDialogSelectedAllowedTasks,
  aiDialogActionText,
  aiDialogSourceLabel,
  aiRestartSubtitleOptions,
  applyAiTaskData,
  resetAiTasks,
  stopAiPolling,
  loadAiTasks,
  aiTaskForTarget,
  isAiTaskActive,
  isAiTaskAllowed,
  aiTaskColor,
  aiTaskIcon,
  aiTaskTitle,
  aiTaskStatusClass,
  aiTaskIconForTask,
  aiStatusText,
  focusAiStatusStrip,
  openBatchAiGenerate,
  cancelBatchAiGenerate,
  cancelDialogAiTasks,
  regenerateDialogAiTasks,
  regenerateSingleAiTask,
  openSingleAiGenerate,
} = useAiTasks({
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
})

const {
  onlineSearching,
  onlineDownloading,
  onlinePreviewDownloading,
  onlineAiDownloading,
  onlineError,
  onlineDialog,
  onlineAiConfirmDialog,
  onlineTitle,
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
  openBatchOnlineSearch,
  openSingleOnlineSearch,
  runOnlineSearch,
  stopOnlineSearch,
  closeOnlineDialog,
  updateOnlineDialog,
  toggleOnlineResult,
  requestOnlineAiTranslate,
  confirmOnlineAiTranslate,
  downloadOnlinePreview,
  stopOnlineDownload,
} = useOnlineSubtitles({
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
  closeUploadDialog() {
    preview.value = null
    uploadDialog.value = false
  },
  applyAiTaskData,
  setAiTaskScopeTargets(targetsToSet) {
    aiTaskScopeTargets.value = targetsToSet
  },
  loadAiTasks,
  focusAiStatusStrip,
  applyTimelineTaskData,
  loadTimelineTasks,
})

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
const selectedRestorableTargets = computed(() => selectedSubtitleTargets.value.filter(target => (target.subtitles || []).some(subtitle => subtitle.backup_available)))

function detailRowForTarget(target) {
  return matchHistoryRows.value.find(row => row.target.id === target?.id) || {
    target,
    subtitles: target?.subtitles || [],
    task: aiTaskForTarget(target),
    timelineTask: timelineTaskForTarget(target),
    written: [],
  }
}

async function restoreSubtitleBackup(target, subtitle) {
  if (!target || !subtitle) return
  clearing.value = true
  error.value = ''
  message.value = ''
  try {
    const response = await pluginApi.value.restoreSubtitleBackup({
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
      await pluginApi.value.restoreSubtitleBackup({
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

function confirmRiskyTimelineOffset(actionLabel = '智能调轴') {
  if (!timelineNeedsRiskyConfirm.value) return false
  return window.confirm(
    `${actionLabel}当前允许最大偏移 ${timelineConfiguredMaxOffset.value}s。\n\n` +
    '超过 120s 的调轴结果通常意味着错集、错版本或整季包映射错误，不建议超过 120s。\n\n' +
    '确认后，本次请求才会允许 120-300s 的结果人工写入；自动入库不会放行高风险偏移。',
  )
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
    const response = await pluginApi.value.deleteSubtitle({
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

async function clearSelectedSubtitles() {
  const targetIds = selectedSubtitleTargets.value.map(target => target.id)
  if (!targetIds.length) return
  clearing.value = true
  error.value = ''
  try {
    const response = await pluginApi.value.clearSubtitles({
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
  stopIndexRefreshPolling()
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
      <MediaSearchPanel
        v-model:search-keyword="searchKeyword"
        v-model:media-type="mediaType"
        :root-tab="rootTab"
        :match-history-summary="matchHistorySummary"
        :index-summary="indexSummary"
        :refreshing="refreshing"
        :match-history-loading="matchHistoryLoading"
        :searching="searching"
        @refresh-index="refreshIndex"
        @submit="submitRootSearch"
      />

      <MediaGrid
        :root-tab="rootTab"
        :medias="medias"
        :media-total="mediaTotal"
        :media-has-more="mediaHasMore"
        :searching="searching"
        :format-media-type="formatMediaType"
        :media-label="mediaLabel"
        :media-stat="mediaStat"
        :poster-image-src="posterImageSrc"
        :poster-loading="posterLoading"
        :poster-fetch-priority="posterFetchPriority"
        @select-media="selectMedia"
        @mark-poster-failed="markPosterFailed"
        @load-more="loadMoreMedia"
      />

      <MatchHistoryPanel
        :root-tab="rootTab"
        :auto-queue-tasks="autoQueueTasks"
        :auto-queue-summary="autoQueueSummary"
        :auto-queue-summary-text="autoQueueSummaryText"
        :match-history-items="matchHistoryItems"
        :match-history-total="matchHistoryTotal"
        :match-history-has-more="matchHistoryHasMore"
        :match-history-loading="matchHistoryLoading"
        :clearing="clearing"
        :timeline-fixing="timelineFixing"
        :timeline-available="timelineAvailable"
        :poster-image-src="posterImageSrc"
        :media-label="mediaLabel"
        :poster-loading="posterLoading"
        :poster-fetch-priority="posterFetchPriority"
        :mark-poster-failed="markPosterFailed"
        :format-media-type="formatMediaType"
        :history-media-stat="historyMediaStat"
        :history-expanded="historyExpanded"
        :toggle-history-expanded="toggleHistoryExpanded"
        :history-selected-count="historySelectedCount"
        :history-deletable-targets="historyDeletableTargets"
        :toggle-history-item-targets="toggleHistoryItemTargets"
        :all-history-targets-selected="allHistoryTargetsSelected"
        :clear-history-selected-subtitles="clearHistorySelectedSubtitles"
        :history-selected-timeline-targets="historySelectedTimelineTargets"
        :fix-history-selected-timeline="fixHistorySelectedTimeline"
        :history-season-groups="historySeasonGroups"
        :history-season-key="historySeasonKey"
        :all-history-season-targets-selected="allHistorySeasonTargetsSelected"
        :history-season-partially-selected="historySeasonPartiallySelected"
        :toggle-history-season-targets="toggleHistorySeasonTargets"
        :history-season-expanded="historySeasonExpanded"
        :toggle-history-season-expanded="toggleHistorySeasonExpanded"
        :history-season-selected-count="historySeasonSelectedCount"
        :history-selected-ids="historySelectedIds"
        :toggle-history-target="toggleHistoryTarget"
        :history-target-expanded="historyTargetExpanded"
        :toggle-history-target-expanded="toggleHistoryTargetExpanded"
        :compact-target-name="compactTargetName"
        :is-target-action-disabled="isTargetActionDisabled"
        :open-single-online-search="openSingleOnlineSearch"
        :timeline-task-text="timelineTaskText"
        :timeline-meta-items="timelineMetaItems"
        :format-bytes="formatBytes"
        :fix-history-subtitle-timeline="fixHistorySubtitleTimeline"
        :is-stream-target="isStreamTarget"
        :delete-subtitle="deleteSubtitle"
        @open-auto-queue="autoQueueDialog = true"
        @load-more-match-history="loadMoreMatchHistory"
      />
    </section>

    <section v-else class="episode-stage">
      <TargetDetailPanel
        ref="aiStatusStripRef"
        :selected-media="selectedMedia"
        :selected-season="selectedSeason"
        :selected-targets="selectedTargets"
        :selected-target-ids="selectedTargetIds"
        :locked-target-ids="lockedTargetIds"
        :visible-targets="visibleTargets"
        :season-cards="seasonCards"
        :resolving="resolving"
        :ai-enabled="aiEnabled"
        :ai-available="aiAvailable"
        :ai-has-active-tasks="aiHasActiveTasks"
        :ai-tasks-loading="aiTasksLoading"
        :ai-summary-text="aiSummaryText"
        :ai-status="aiStatus"
        :all-visible-selected="allVisibleSelected"
        :unlocked-visible-targets="unlockedVisibleTargets"
        :ai-capable-batch-targets="aiCapableBatchTargets"
        :ai-submitting="aiSubmitting"
        :ai-batch-label="aiBatchLabel"
        :ai-batch-cancel-targets="aiBatchCancelTargets"
        :ai-cancelling="aiCancelling"
        :online-searching="onlineSearching"
        :online-batch-label="onlineBatchLabel"
        :batch-upload-targets="batchUploadTargets"
        :clearing="clearing"
        :selected-timeline-targets="selectedTimelineTargets"
        :timeline-fixing="timelineFixing"
        :timeline-available="timelineAvailable"
        :selected-restorable-targets="selectedRestorableTargets"
        :last-written="lastWritten"
        :poster-image-src="posterImageSrc"
        :media-label="mediaLabel"
        :format-media-type="formatMediaType"
        :compact-target-name="compactTargetName"
        :format-bytes="formatBytes"
        :is-locked="isLocked"
        :is-target-action-disabled="isTargetActionDisabled"
        :is-stream-target="isStreamTarget"
        :detail-expanded="detailExpanded"
        :detail-row-for-target="detailRowForTarget"
        :ai-task-for-target="aiTaskForTarget"
        :ai-task-status-class="aiTaskStatusClass"
        :ai-task-icon="aiTaskIcon"
        :ai-task-color="aiTaskColor"
        :ai-task-title="aiTaskTitle"
        :ai-status-text="aiStatusText"
        :timeline-result-for-target="timelineResultForTarget"
        :timeline-meta-items="timelineMetaItems"
        :timeline-task-for-target="timelineTaskForTarget"
        :timeline-result-text="timelineResultText"
        @reset-selection="resetSelection"
        @mark-poster-failed="markPosterFailed"
        @load-targets="loadTargets"
        @change-season="changeSeason"
        @open-ai-task-dialog="openAiTaskDialog"
        @toggle-select-all="toggleSelectAll"
        @open-batch-upload="openBatchUpload"
        @open-batch-ai-generate="openBatchAiGenerate"
        @cancel-batch-ai-generate="cancelBatchAiGenerate"
        @open-batch-online-search="openBatchOnlineSearch"
        @clear-selected-subtitles="clearSelectedSubtitles"
        @fix-selected-detail-timeline="fixSelectedDetailTimeline"
        @restore-selected-backups="restoreSelectedBackups"
        @toggle-target="toggleTarget"
        @toggle-detail-expanded="toggleDetailExpanded"
        @open-single-ai-generate="openSingleAiGenerate"
        @open-single-online-search="openSingleOnlineSearch"
        @toggle-lock="toggleLock"
        @open-single-upload="openSingleUpload"
        @fix-history-subtitle-timeline="fixHistorySubtitleTimeline"
        @restore-subtitle-backup="restoreSubtitleBackup"
        @delete-subtitle="deleteSubtitle"
      />
    </section>

    <AutoTransferQueueDialog
      v-model="autoQueueDialog"
      :auto-queue-summary-text="autoQueueSummaryText"
      :auto-transfer-queue="autoTransferQueue"
      :auto-queue-tasks="autoQueueTasks"
      @load-auto-transfer-queue="loadAutoTransferQueue"
    />

    <AiTaskDialog
      v-model="aiTaskDialog"
      v-model:ai-restart-source-policy="aiRestartSourcePolicy"
      v-model:ai-restart-subtitle-path="aiRestartSubtitlePath"
      v-model:ai-selected-task-ids="aiSelectedTaskIds"
      :ai-task-dialog-target="aiTaskDialogTarget"
      :compact-target-name="compactTargetName"
      :ai-summary-text="aiSummaryText"
      :ai-dialog-has-active-tasks="aiDialogHasActiveTasks"
      :ai-cancelling="aiCancelling"
      :ai-available="aiAvailable"
      :ai-dialog-tasks="aiDialogTasks"
      :ai-dialog-has-existing-tasks="aiDialogHasExistingTasks"
      :ai-dialog-selected-allowed-tasks="aiDialogSelectedAllowedTasks"
      :ai-submitting="aiSubmitting"
      :ai-dialog-action-text="aiDialogActionText"
      :ai-tasks-loading="aiTasksLoading"
      :ai-status="aiStatus"
      :ai-restart-source-options="aiRestartSourceOptions"
      :ai-dialog-source-label="aiDialogSourceLabel"
      :ai-restart-subtitle-options="aiRestartSubtitleOptions"
      :is-ai-task-allowed="isAiTaskAllowed"
      :ai-task-icon-for-task="aiTaskIconForTask"
      :ai-status-text="aiStatusText"
      @cancel-dialog-ai-tasks="cancelDialogAiTasks"
      @regenerate-dialog-ai-tasks="regenerateDialogAiTasks"
      @load-ai-tasks="loadAiTasks"
      @regenerate-single-ai-task="regenerateSingleAiTask"
    />

    <OnlineSubtitleDialog
      v-model="onlineDialog"
      v-model:online-keyword="onlineKeyword"
      v-model:online-selected-providers="onlineSelectedProviders"
      v-model:online-messages-collapsed="onlineMessagesCollapsed"
      v-model:online-language-filter="onlineLanguageFilter"
      v-model:online-provider-filter="onlineProviderFilter"
      v-model:online-ai-confirm-dialog="onlineAiConfirmDialog"
      :online-title="onlineTitle"
      :online-targets="onlineTargets"
      :selected-online-results="selectedOnlineResults"
      :online-ai-downloading="onlineAiDownloading"
      :online-preview-downloading="onlinePreviewDownloading"
      :can-submit-online-ai-translate="canSubmitOnlineAiTranslate"
      :online-downloading="onlineDownloading"
      :online-provider-items="onlineProviderItems"
      :online-searching="onlineSearching"
      :online-error="onlineError"
      :online-messages="onlineMessages"
      :online-message-type="onlineMessageType"
      :online-message-summary="onlineMessageSummary"
      :has-online-results="hasOnlineResults"
      :filtered-online-results="filteredOnlineResults"
      :online-results="onlineResults"
      :online-language-filter-items="onlineLanguageFilterItems"
      :online-provider-filter-items="onlineProviderFilterItems"
      :online-provider-progress-items="onlineProviderProgressItems"
      :selected-online-result-ids="selectedOnlineResultIds"
      :online-manual-links="onlineManualLinks"
      :online-ai-confirm-text="onlineAiConfirmText"
      :provider-progress-color="providerProgressColor"
      :provider-progress-text="providerProgressText"
      :provider-name="providerName"
      :online-result-key="onlineResultKey"
      :online-result-meta="onlineResultMeta"
      :is-online-result-downloadable="isOnlineResultDownloadable"
      @update:model-value="updateOnlineDialog"
      @download-online-preview="downloadOnlinePreview"
      @request-online-ai-translate="requestOnlineAiTranslate"
      @stop-online-download="stopOnlineDownload"
      @close-online-dialog="closeOnlineDialog"
      @run-online-search="runOnlineSearch"
      @stop-online-search="stopOnlineSearch"
      @toggle-online-result="toggleOnlineResult"
      @confirm-online-ai-translate="confirmOnlineAiTranslate"
    />
    <UploadDialog
      v-model="uploadDialog"
      v-model:fix-timeline="fixTimeline"
      v-model:batch-language-suffix="batchLanguageSuffix"
      :upload-title="uploadTitle"
      :has-preview-items="hasPreviewItems"
      :all-selected-preview-targets-are-stream="allSelectedPreviewTargetsAreStream"
      :has-selected-preview-stream-targets="hasSelectedPreviewStreamTargets"
      :timeline-available="timelineAvailable"
      :applying="applying"
      :can-apply="canApply"
      :dragging="dragging"
      :preparing="preparing"
      :rar-python-available="rarPythonAvailable"
      :rar-available="rarAvailable"
      :archive-status="archiveStatus"
      :rar-dependency-status="rarDependencyStatus"
      :timeline-missing="timelineMissing"
      :files="files"
      :preview="preview"
      :target-select-items="targetSelectItems"
      :upload-targets="uploadTargets"
      :format-bytes="formatBytes"
      :rar-dependency-mode-label="rarDependencyModeLabel"
      :build-output-name="buildOutputName"
      @reset-upload-preview="resetUploadPreview"
      @apply-upload="applyUpload"
      @pick-files="onPickFiles"
      @drop="handleDrop"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @remove-file="removeFile"
      @open-rar-help="openRarHelp"
      @apply-batch-language-suffix="applyBatchLanguageSuffix"
      @toggle-preview-item="togglePreviewItem"
      @update-preview-target="updatePreviewTarget"
      @update-language-suffix="updateLanguageSuffix"
    />
    <RarHelpDialog
      v-model="rarHelpDialog"
      :rar-help-items="rarHelpItems"
      :copy-message="copyMessage"
      :copy-error="copyError"
      :rar-dependency-status="rarDependencyStatus"
      @copy-help-text="copyHelpText"
    />
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

.hero-card {
  padding: 26px;
  margin-bottom: 18px;
  border: 1px solid rgba(83, 103, 94, 0.16);
  border-radius: 28px;
  background: rgba(255, 252, 245, 0.88);
  box-shadow: 0 24px 70px rgba(43, 62, 58, 0.1);
  backdrop-filter: blur(14px);
}

.hero-card h1 {
  margin: 0;
}

.hero-card p {
  margin: 8px 0 0;
  color: #64746f;
  line-height: 1.7;
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

@media (max-width: 900px) {
  .subtitle-upload-page {
    padding: 14px;
  }
}
</style>
