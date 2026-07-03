import {
  DEFAULT_CONFIG,
  SURFACE_SCAN_MS,
  VIEWPORT_PADDING,
} from './mascot/config'
import { loadMoviePilotPluginConfig } from './adapters/moviepilotAuth'
import { createMascotRuntime } from './mascot/runtime'
import { buildDomSurfaceLanes } from './mascot/surfaces'

const PLUGIN_ID = 'AgentMascot'
const ROOT_ID = 'agentmascot-global-root'
const STYLE_ID = 'agentmascot-global-style'
const HIDDEN_CLASS = 'agentmascot-native-hidden'
const CONFIG_POLL_MS = 15000
const DOM_SURFACE_SELECTORS = [
  'main',
  '.v-main',
  '.v-container',
  '.v-card',
  '.v-sheet',
  '.v-window',
  '.v-table',
  '[class*="dashboard"]',
  '[class*="layout"]',
].join(',')

let config = { ...DEFAULT_CONFIG }
let root = null
let img = null
let shadow = null
let nativeEntry = null
let nativeTrigger = null
let configTimer = 0
let restoreNativeTimer = 0
let nativeObserver = null
let surfaceLanes = []
let lastSurfaceScan = 0

const runtime = createMascotRuntime({
  bounds: viewportBounds,
  getConfig: () => config,
  getSurfaceLanes: collectSurfaceLanes,
  initialPet: {
    anchorX: 180,
    anchorY: 180,
    targetX: 360,
    targetY: 180,
    laneY: 180,
  },
  onUpdate: render,
  scheduler: {
    setInterval: (...args) => window.setInterval(...args),
    clearInterval: id => window.clearInterval(id),
    setTimeout: (...args) => window.setTimeout(...args),
    requestAnimationFrame: callback => window.requestAnimationFrame(callback),
    cancelAnimationFrame: id => window.cancelAnimationFrame(id),
  },
  viewportPadding: VIEWPORT_PADDING,
})
const pet = runtime.pet

async function loadConfig() {
  config = await loadMoviePilotPluginConfig(PLUGIN_ID)
  runtime.updateConfig(config)
  return config
}

function isEnabled() {
  return Boolean(config.enabled && config.replace_agent_entry)
}

function viewportBounds() {
  return {
    height: window.innerHeight,
    width: window.innerWidth,
  }
}

function collectSurfaceLanes(context, force = false) {
  const now = performance.now()
  if (!force && surfaceLanes.length && now - lastSurfaceScan < SURFACE_SCAN_MS) return surfaceLanes

  try {
    surfaceLanes = buildDomSurfaceLanes(context, document.querySelectorAll(DOM_SURFACE_SELECTORS), {
      getStyle: element => window.getComputedStyle(element),
      onError: error => console.debug('[AgentMascot] surface element skipped', error),
      shouldIgnoreElement: element => element === root || root?.contains(element) || nativeEntry?.contains(element),
      viewportPadding: VIEWPORT_PADDING,
    })
  } catch (error) {
    console.debug('[AgentMascot] surface scan skipped', error)
    surfaceLanes = buildDomSurfaceLanes(context, [])
  }

  lastSurfaceScan = now
  return surfaceLanes
}

function render() {
  if (!root || !img) return
  const state = runtime.renderState()
  root.style.width = `${state.size}px`
  root.style.height = `${state.size}px`
  root.style.transform = `translate3d(${state.left}px, ${state.top}px, 0) scaleX(${pet.lookRight ? -1 : 1})`
  img.src = state.frame
  shadow.style.display = config.shadow ? 'block' : 'none'
}

function hideNativeEntry() {
  nativeEntry = document.querySelector('.agent-assistant-fab')
  nativeTrigger = document.querySelector('.agent-assistant-fab__trigger')
  if (nativeEntry) nativeEntry.classList.add(HIDDEN_CLASS)
}

function openNativeAssistant() {
  hideNativeEntry()
  if (!nativeTrigger) return
  triggerNativeAssistant()
  window.setTimeout(() => {
    if (!isNativeAssistantOpen()) triggerNativeAssistant()
  }, 80)
  window.clearTimeout(restoreNativeTimer)
  restoreNativeTimer = window.setTimeout(hideNativeEntry, 300)
}

function triggerNativeAssistant() {
  if (!nativeTrigger) return
  if (typeof nativeTrigger.click === 'function') nativeTrigger.click()
  else nativeTrigger.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }))
}

function isNativeAssistantOpen() {
  const panel = document.querySelector('.agent-assistant-panel')
  if (!panel) return false
  const style = window.getComputedStyle(panel)
  const rect = panel.getBoundingClientRect()
  return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
}

function onPointerMove(event) {
  runtime.handlePointerMove({ x: event.clientX, y: event.clientY })
}

function startDrag(event) {
  if (event.button !== 0) return
  event.preventDefault()
  runtime.startDrag({ x: event.clientX, y: event.clientY })
  root?.setPointerCapture?.(event.pointerId)
}

function onDrag(event) {
  runtime.moveDrag({ x: event.clientX, y: event.clientY }, event.movementX)
}

function endDrag(event) {
  runtime.endDrag({ x: event.clientX, y: event.clientY }, event.movementX, event.movementY)
  root?.releasePointerCapture?.(event.pointerId)
}

function onClick(event) {
  if (runtime.shouldSuppressClick()) {
    event.preventDefault()
    return
  }
  event.preventDefault()
  openNativeAssistant()
}

function ensureStyle() {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
    .${HIDDEN_CLASS} {
      width: 0 !important;
      height: 0 !important;
      overflow: hidden !important;
    }
    .${HIDDEN_CLASS} > .agent-assistant-fab__trigger,
    .${HIDDEN_CLASS} > button,
    .${HIDDEN_CLASS} [role="button"] {
      opacity: 0 !important;
      pointer-events: none !important;
      transform: scale(0.01) !important;
    }
    #${ROOT_ID} {
      position: fixed;
      top: 0;
      left: 0;
      z-index: 2147483000;
      display: grid;
      place-items: center;
      cursor: grab;
      user-select: none;
      touch-action: none;
      will-change: transform;
    }
    #${ROOT_ID}:active {
      cursor: grabbing;
    }
    #${ROOT_ID} img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      pointer-events: none;
      -webkit-user-drag: none;
    }
    #${ROOT_ID} .agentmascot-global-shadow {
      position: absolute;
      left: 17%;
      right: 17%;
      bottom: 3px;
      height: 12px;
      border-radius: 999px;
      background: rgba(0, 0, 0, 0.26);
      filter: blur(5px);
      z-index: -1;
    }
  `
  document.head.appendChild(style)
}

function mount() {
  if (root) return
  ensureStyle()
  startNativeObserver()
  root = document.createElement('button')
  root.id = ROOT_ID
  root.type = 'button'
  root.setAttribute('aria-label', '打开智能体助手')
  img = document.createElement('img')
  img.alt = ''
  shadow = document.createElement('span')
  shadow.className = 'agentmascot-global-shadow'
  root.append(img, shadow)
  document.body.appendChild(root)
  document.addEventListener('pointermove', onPointerMove, { passive: true })
  root.addEventListener('pointerdown', startDrag)
  root.addEventListener('pointermove', onDrag)
  root.addEventListener('pointerup', endDrag)
  root.addEventListener('pointercancel', endDrag)
  root.addEventListener('click', onClick)
  hideNativeEntry()
  runtime.start()
}

function unmount() {
  runtime.stop()
  stopNativeObserver()
  document.removeEventListener('pointermove', onPointerMove)
  window.clearTimeout(restoreNativeTimer)
  nativeEntry?.classList.remove(HIDDEN_CLASS)
  root?.remove()
  root = null
  img = null
  shadow = null
}

function startNativeObserver() {
  hideNativeEntry()
  if (nativeObserver) return
  nativeObserver = new MutationObserver(() => {
    if (isEnabled()) hideNativeEntry()
  })
  nativeObserver.observe(document.body, { childList: true, subtree: true })
}

function stopNativeObserver() {
  nativeObserver?.disconnect()
  nativeObserver = null
}

async function syncFromConfig() {
  try {
    await loadConfig()
    if (isEnabled()) {
      mount()
      hideNativeEntry()
      render()
    } else {
      unmount()
    }
  } catch (error) {
    console.debug('[AgentMascot] 全局入口配置读取失败', error)
  }
}

function onResize() {
  runtime.clampToBounds()
}

function start() {
  if (window.__AgentMascotGlobalLoaderStarted) return
  window.__AgentMascotGlobalLoaderStarted = true
  syncFromConfig()
  configTimer = window.setInterval(syncFromConfig, CONFIG_POLL_MS)
  window.addEventListener('resize', onResize)
}

start()
