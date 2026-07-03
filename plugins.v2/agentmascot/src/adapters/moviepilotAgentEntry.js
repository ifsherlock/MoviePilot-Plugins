const ENTRY_SELECTOR = '.agent-assistant-fab'
const TRIGGER_SELECTOR = '.agent-assistant-fab__trigger'
const PANEL_SELECTOR = '.agent-assistant-panel'

export function nativeAgentEntryStyle(hiddenClass) {
  return `
    .${hiddenClass} {
      width: 0 !important;
      height: 0 !important;
      overflow: hidden !important;
    }
    .${hiddenClass} > ${TRIGGER_SELECTOR},
    .${hiddenClass} > button,
    .${hiddenClass} [role="button"] {
      opacity: 0 !important;
      pointer-events: none !important;
      transform: scale(0.01) !important;
    }
  `
}

export function createMoviePilotAgentEntry(options = {}) {
  const env = options.env || globalThis
  const hiddenClass = options.hiddenClass || 'agentmascot-native-hidden'
  const isEnabled = options.isEnabled || (() => true)
  let nativeEntry = null
  let nativeTrigger = null
  let nativeObserver = null
  let restoreNativeTimer = 0

  function refresh() {
    nativeEntry = env.document?.querySelector(ENTRY_SELECTOR) || null
    nativeTrigger = env.document?.querySelector(TRIGGER_SELECTOR) || null
    if (nativeEntry) nativeEntry.classList.add(hiddenClass)
  }

  function trigger() {
    if (!nativeTrigger) return
    if (typeof nativeTrigger.click === 'function') nativeTrigger.click()
    else nativeTrigger.dispatchEvent(new env.MouseEvent('click', { bubbles: true, cancelable: true, view: env }))
  }

  function isPanelOpen() {
    const panel = env.document?.querySelector(PANEL_SELECTOR)
    if (!panel) return false
    const style = env.getComputedStyle(panel)
    const rect = panel.getBoundingClientRect()
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
  }

  function open() {
    refresh()
    if (!nativeTrigger) return
    trigger()
    env.setTimeout(() => {
      if (!isPanelOpen()) trigger()
    }, 80)
    env.clearTimeout(restoreNativeTimer)
    restoreNativeTimer = env.setTimeout(refresh, 300)
  }

  function contains(element) {
    return Boolean(element && nativeEntry?.contains(element))
  }

  function startObserver() {
    refresh()
    if (nativeObserver) return
    nativeObserver = new env.MutationObserver(() => {
      if (isEnabled()) refresh()
    })
    nativeObserver.observe(env.document.body, { childList: true, subtree: true })
  }

  function stopObserver() {
    nativeObserver?.disconnect()
    nativeObserver = null
  }

  function destroy() {
    stopObserver()
    env.clearTimeout(restoreNativeTimer)
    nativeEntry?.classList.remove(hiddenClass)
    nativeEntry = null
    nativeTrigger = null
  }

  return {
    contains,
    destroy,
    hide: refresh,
    open,
    startObserver,
    stopObserver,
  }
}
