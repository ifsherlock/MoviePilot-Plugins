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
import MediaGrid from './MediaGrid.vue'
import MediaSearchPanel from './MediaSearchPanel.vue'
import TargetDetailPanel from './TargetDetailPanel.vue'
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
              v-if="aiAvailable && (aiTaskDialogTarget || aiDialogTasks.length)"
              variant="tonal"
              color="warning"
              prepend-icon="mdi-robot-happy-outline"
              :disabled="aiDialogHasExistingTasks && !aiDialogSelectedAllowedTasks.length"
              :loading="aiSubmitting"
              @click="regenerateDialogAiTasks"
            >
              {{ aiDialogActionText }}
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
          <div v-if="aiAvailable && (aiTaskDialogTarget || aiDialogTasks.length)" class="ai-restart-options">
            <VSelect
              v-model="aiRestartSourcePolicy"
              :items="aiRestartSourceOptions"
              :label="aiDialogSourceLabel"
              density="comfortable"
              hint="改选来源会写入来源变体后缀，如 .aiasr.srt 或 .aiembedded.srt"
              persistent-hint
            />
            <VSelect
              v-if="aiRestartSourcePolicy === 'matched_external'"
              v-model="aiRestartSubtitlePath"
              class="mt-3"
              :items="aiRestartSubtitleOptions"
              label="外挂字幕"
              density="comfortable"
              :hint="aiRestartSubtitleOptions.length ? '使用这条外挂 SRT 作为 AI 翻译来源' : '当前集没有可用于 AI 翻译的 SRT 外挂字幕'"
              persistent-hint
              :disabled="!aiRestartSubtitleOptions.length"
            />
          </div>
          <div v-if="aiDialogTasks.length" class="ai-task-list">
            <div
              v-for="task in aiDialogTasks"
              :key="task.task_id"
              class="ai-task-row"
              :class="`ai-${task.status}`"
            >
              <VCheckbox
                v-model="aiSelectedTaskIds"
                :value="task.task_id"
                density="compact"
                hide-details
                :disabled="!isAiTaskAllowed(task)"
              />
              <div class="ai-task-badge">
                <VIcon :icon="aiTaskIconForTask(task)" />
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
                <VBtn
                  size="small"
                  variant="tonal"
                  color="warning"
                  :disabled="!isAiTaskAllowed(task)"
                  :loading="aiSubmitting"
                  @click="regenerateSingleAiTask(task)"
                >
                  重新生成
                </VBtn>
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
            <div class="dropzone-icon">SRT / ASS / ZIP / RAR / 7Z</div>
            <div class="dropzone-title">把字幕或压缩包拖到这里</div>
            <div class="dropzone-text">
              支持字幕文件、ZIP、RAR、7Z；RAR/7Z 需容器内解压器支持。
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
              accept=".srt,.ass,.ssa,.sbv,.sub,.vtt,.webvtt,.zip,.rar,.7z"
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
  grid-template-columns: auto 42px minmax(0, 1fr) auto;
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

@media (max-width: 720px) {
  .ai-task-row {
    grid-template-columns: auto 42px minmax(0, 1fr);
  }

  .ai-task-time {
    grid-column: 1 / -1;
    justify-items: start;
  }
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
