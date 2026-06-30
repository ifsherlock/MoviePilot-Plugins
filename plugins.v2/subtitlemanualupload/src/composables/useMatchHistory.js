import { computed, ref } from 'vue'

const MATCH_HISTORY_PAGE_SIZE = 20

export function useMatchHistory({
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
  fixExistingTimeline,
}) {
  const rootTab = ref('match')
  const matchHistoryLoading = ref(false)
  const matchHistoryItems = ref([])
  const matchHistoryPage = ref(1)
  const matchHistoryPageSize = MATCH_HISTORY_PAGE_SIZE
  const matchHistoryTotal = ref(0)
  const matchHistoryHasMore = ref(false)
  const expandedHistoryIds = ref([])
  const expandedHistorySeasonKeys = ref([])
  const expandedHistoryTargetIds = ref([])
  const selectedHistoryTargetIds = ref({})
  let historyTimelineTimer = null

  const matchHistorySummary = computed(() => {
    if (!matchHistoryTotal.value) return '暂无已匹配字幕记录'
    return `${matchHistoryTotal.value} 部资源有外挂字幕记录`
  })

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
      const response = await pluginApi.value.clearSubtitles({
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

  function submitRootSearch() {
    if (rootTab.value === 'history') {
      loadMatchHistory()
      return
    }
    runSearch()
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
      const response = await pluginApi.value.matchHistory(params)
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

  return {
    rootTab,
    matchHistoryLoading,
    matchHistoryItems,
    matchHistoryPage,
    matchHistoryPageSize,
    matchHistoryTotal,
    matchHistoryHasMore,
    expandedHistoryIds,
    expandedHistorySeasonKeys,
    expandedHistoryTargetIds,
    selectedHistoryTargetIds,
    matchHistorySummary,
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
    setHistorySelection,
    toggleHistoryTarget,
    toggleHistoryItemTargets,
    historySeasonGroups,
    historySeasonSelectedCount,
    allHistorySeasonTargetsSelected,
    historySeasonPartiallySelected,
    toggleHistorySeasonTargets,
    clearHistoryTargets,
    clearHistorySelectedSubtitles,
    historyTimelineTargets,
    historySelectedTimelineTargets,
    fixHistorySelectedTimeline,
    fixHistorySubtitleTimeline,
    stopHistoryTimelinePolling,
    historyHasActiveTimelineTask,
    scheduleHistoryTimelinePolling,
    submitRootSearch,
    loadMatchHistory,
    loadMoreMatchHistory,
    setRootTab,
  }
}
