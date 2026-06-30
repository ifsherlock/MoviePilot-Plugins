import { computed, ref } from 'vue'

export function useTargets({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  mediaLabel,
  clearRelatedState,
  beforeLoadTargets,
  afterTargetsLoaded,
  runSearch,
}) {
  const resolving = ref(false)
  const selectedMedia = ref(null)
  const detailTab = ref('match')
  const seasons = ref([])
  const selectedSeason = ref('all')
  const targets = ref([])
  const selectedTargetIds = ref([])
  const lockedTargetIds = ref([])
  const expandedDetailTargetIds = ref([])

  const visibleTargets = computed(() => targets.value || [])
  const selectedTargets = computed(() => {
    const picked = new Set(selectedTargetIds.value || [])
    return visibleTargets.value.filter(item => picked.has(item.id))
  })
  const targetById = computed(() => new Map(visibleTargets.value.map(target => [target.id, target])))
  const unlockedVisibleTargets = computed(() => visibleTargets.value.filter(item => !isLocked(item.id) && item.writable !== false))
  const allVisibleSelected = computed(() => {
    if (!visibleTargets.value.length) return false
    const picked = new Set(selectedTargetIds.value || [])
    return visibleTargets.value.every(item => picked.has(item.id))
  })

  function isLocked(targetId) {
    return lockedTargetIds.value.includes(targetId)
  }

  function lockedTargetPayload() {
    return [...lockedTargetIds.value]
  }

  function isTargetActionDisabled(target) {
    return isLocked(target.id) || target.writable === false
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

  function clearTargetState() {
    seasons.value = []
    detailTab.value = 'match'
    selectedSeason.value = 'all'
    targets.value = []
    selectedTargetIds.value = []
    clearRelatedState?.()
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
    beforeLoadTargets?.()
    try {
      const params = buildMediaParams(media, season || 'all')
      const response = await pluginApi.value.targets(params)
      const data = unwrapResponse(response) || {}
      selectedMedia.value = data.media || media
      seasons.value = data.seasons || []
      selectedSeason.value = data.selected_season ?? 'all'
      targets.value = data.targets || []
      selectedTargetIds.value = []
      await afterTargetsLoaded?.(targets.value)

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
    runSearch?.()
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

  return {
    resolving,
    selectedMedia,
    detailTab,
    seasons,
    selectedSeason,
    targets,
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
    buildMediaParams,
    loadTargets,
    selectMedia,
    changeSeason,
    resetSelection,
    toggleSelectAll,
    toggleTarget,
    toggleLock,
  }
}
