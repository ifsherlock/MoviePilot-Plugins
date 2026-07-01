import { ref } from 'vue'

export function useMediaSearch({
  pluginApi,
  unwrapResponse,
  errorMessage,
  error,
  message,
  selectedMedia,
  clearTargetState,
}) {
  const searching = ref(false)
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
    const response = await pluginApi.value.search(params)
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
      clearTargetState?.()
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

  function loadMoreMedia() {
    if (searching.value || !mediaHasMore.value) return
    runSearch({ append: true })
  }

  return {
    searching,
    searchKeyword,
    mediaType,
    medias,
    mediaPage,
    mediaPageSize,
    mediaTotal,
    mediaHasMore,
    mediaPrefetchPages,
    failedPosterImages,
    posterImageKey,
    posterImageSrc,
    markPosterFailed,
    posterLoading,
    posterFetchPriority,
    mediaRequestKey,
    clearMediaPrefetch,
    fetchMediaPage,
    applyMediaPage,
    prefetchMediaPage,
    runSearch,
    loadMoreMedia,
  }
}
