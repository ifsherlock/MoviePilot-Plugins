import {
  SURFACE_SCAN_MS,
  VIEWPORT_PADDING,
} from '../mascot/config'
import { buildDomSurfaceLanes } from '../mascot/surfaces'

const ROOT_ID = 'agentmascot-global-root'
const STYLE_ID = 'agentmascot-global-style'
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

export function createGlobalDomAdapter(options = {}) {
  const env = options.env || globalThis
  const agentEntry = options.agentEntry
  const getRuntime = options.getRuntime
  let root = null
  let img = null
  let shadow = null
  let surfaceLanes = []
  let lastSurfaceScan = 0

  function runtime() {
    return getRuntime()
  }

  function bounds() {
    return {
      height: env.innerHeight,
      width: env.innerWidth,
    }
  }

  function collectSurfaceLanes(context, force = false) {
    const now = env.performance?.now?.() || Date.now()
    if (!force && surfaceLanes.length && now - lastSurfaceScan < SURFACE_SCAN_MS) return surfaceLanes

    try {
      surfaceLanes = buildDomSurfaceLanes(context, env.document.querySelectorAll(DOM_SURFACE_SELECTORS), {
        getStyle: element => env.getComputedStyle(element),
        onError: error => console.debug('[AgentMascot] surface element skipped', error),
        shouldIgnoreElement: element => element === root || root?.contains(element) || agentEntry.contains(element),
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
    const state = runtime().renderState()
    const pet = runtime().pet
    root.style.width = `${state.size}px`
    root.style.height = `${state.size}px`
    root.style.transform = `translate3d(${state.left}px, ${state.top}px, 0) scaleX(${pet.lookRight ? -1 : 1})`
    img.src = state.frame
    shadow.style.display = runtime().config().shadow ? 'block' : 'none'
  }

  function onPointerMove(event) {
    runtime().handlePointerMove({ x: event.clientX, y: event.clientY })
  }

  function startDrag(event) {
    if (event.button !== 0) return
    event.preventDefault()
    runtime().startDrag({ x: event.clientX, y: event.clientY })
    root?.setPointerCapture?.(event.pointerId)
  }

  function onDrag(event) {
    runtime().moveDrag({ x: event.clientX, y: event.clientY }, event.movementX)
  }

  function endDrag(event) {
    runtime().endDrag({ x: event.clientX, y: event.clientY }, event.movementX, event.movementY)
    root?.releasePointerCapture?.(event.pointerId)
  }

  function onClick(event) {
    if (runtime().shouldSuppressClick()) {
      event.preventDefault()
      return
    }
    event.preventDefault()
    agentEntry.open()
  }

  function ensureStyle() {
    if (env.document.getElementById(STYLE_ID)) return
    const style = env.document.createElement('style')
    style.id = STYLE_ID
    style.textContent = `
      ${options.nativeEntryStyle || ''}
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
    env.document.head.appendChild(style)
  }

  function mount() {
    if (root) return
    ensureStyle()
    root = env.document.createElement('button')
    root.id = ROOT_ID
    root.type = 'button'
    root.setAttribute('aria-label', '打开智能体助手')
    img = env.document.createElement('img')
    img.alt = ''
    shadow = env.document.createElement('span')
    shadow.className = 'agentmascot-global-shadow'
    root.append(img, shadow)
    env.document.body.appendChild(root)
    env.document.addEventListener('pointermove', onPointerMove, { passive: true })
    root.addEventListener('pointerdown', startDrag)
    root.addEventListener('pointermove', onDrag)
    root.addEventListener('pointerup', endDrag)
    root.addEventListener('pointercancel', endDrag)
    root.addEventListener('click', onClick)
  }

  function unmount() {
    env.document.removeEventListener('pointermove', onPointerMove)
    root?.remove()
    root = null
    img = null
    shadow = null
  }

  function onResize() {
    runtime().clampToBounds()
  }

  return {
    bounds,
    collectSurfaceLanes,
    mount,
    onResize,
    render,
    unmount,
  }
}
