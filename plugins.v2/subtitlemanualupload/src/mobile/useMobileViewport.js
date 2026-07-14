import { onBeforeUnmount, onMounted, ref } from 'vue'

const MOBILE_QUERY = '(max-width: 899px)'

export function useMobileViewport(query = MOBILE_QUERY) {
  const isMobileViewport = ref(false)
  let mediaQueryList = null

  function syncViewport(event) {
    isMobileViewport.value = Boolean(event?.matches)
  }

  onMounted(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    mediaQueryList = window.matchMedia(query)
    syncViewport(mediaQueryList)
    if (typeof mediaQueryList.addEventListener === 'function') {
      mediaQueryList.addEventListener('change', syncViewport)
      return
    }
    mediaQueryList.addListener(syncViewport)
  })

  onBeforeUnmount(() => {
    if (!mediaQueryList) return
    if (typeof mediaQueryList.removeEventListener === 'function') {
      mediaQueryList.removeEventListener('change', syncViewport)
      return
    }
    mediaQueryList.removeListener(syncViewport)
  })

  return isMobileViewport
}
