import { n as normalizeConfig, D as DEFAULT_CONFIG, e as createMascotRuntime, V as VIEWPORT_PADDING, f as buildSurfaceLanes } from './runtime-B0INm_qi.js';

const ROOT_CLASS = 'agentmascot-plugin-root';
const SHADOW_CLASS = 'agentmascot-plugin-shadow';
const FALLBACK_BOUNDS = {
  height: 360,
  width: 720,
};

let container = null;
let containerPosition = '';
let config = normalizeConfig(DEFAULT_CONFIG);
let env = globalThis;
let img = null;
let root = null;
let runtime = null;
let onActivate = null;
let shadow = null;

function ownerWindow(element) {
  return element?.ownerDocument?.defaultView || globalThis
}

function schedulerFor(nextEnv) {
  return {
    setInterval: (...args) => nextEnv.setInterval(...args),
    clearInterval: id => nextEnv.clearInterval(id),
    setTimeout: (...args) => nextEnv.setTimeout(...args),
    requestAnimationFrame: callback => nextEnv.requestAnimationFrame(callback),
    cancelAnimationFrame: id => nextEnv.cancelAnimationFrame(id),
  }
}

function requireContainer(nextContainer) {
  if (!nextContainer?.ownerDocument || !nextContainer.appendChild) {
    throw new TypeError('[AgentMascot] pluginEntry.mount(container) requires a DOM container')
  }
}

function bounds() {
  const rect = container?.getBoundingClientRect?.();
  return {
    height: Math.max(rect?.height || 0, FALLBACK_BOUNDS.height),
    width: Math.max(rect?.width || 0, FALLBACK_BOUNDS.width),
  }
}

function pointFromEvent(event) {
  const rect = container.getBoundingClientRect();
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

function render() {
  if (!root || !img || !runtime) return
  const state = runtime.renderState();
  root.style.width = `${state.size}px`;
  root.style.height = `${state.size}px`;
  root.style.transform = [
    `translate3d(${state.left}px, ${state.top}px, 0)`,
    `scaleX(${runtime.pet.lookRight ? -1 : 1})`,
  ].join(' ');
  img.src = state.frame;
  if (shadow) shadow.style.display = runtime.config().shadow ? 'block' : 'none';
}

function onPointerMove(event) {
  runtime?.handlePointerMove(pointFromEvent(event));
}

function onPointerLeave() {
  runtime?.handlePointerLeave();
}

function onDragStart(event) {
  if (event.button !== 0) return
  event.preventDefault();
  runtime.startDrag(pointFromEvent(event));
  root?.setPointerCapture?.(event.pointerId);
}

function onDragMove(event) {
  runtime?.moveDrag(pointFromEvent(event), event.movementX);
}

function onDragEnd(event) {
  runtime?.endDrag(pointFromEvent(event), event.movementX, event.movementY);
  root?.releasePointerCapture?.(event.pointerId);
}

function onClick(event) {
  if (runtime?.shouldSuppressClick()) {
    event.preventDefault();
    return
  }
  onActivate?.(event);
}

function createRoot() {
  const nextRoot = container.ownerDocument.createElement('button');
  nextRoot.type = 'button';
  nextRoot.className = ROOT_CLASS;
  nextRoot.setAttribute('aria-label', '打开智能体助手');
  nextRoot.style.cssText = [
    'position:absolute',
    'top:0',
    'left:0',
    'z-index:1',
    'display:grid',
    'place-items:center',
    'padding:0',
    'border:0',
    'background:transparent',
    'cursor:grab',
    'user-select:none',
    'touch-action:none',
    'will-change:transform',
  ].join(';');

  img = container.ownerDocument.createElement('img');
  img.alt = '';
  img.style.cssText = [
    'width:100%',
    'height:100%',
    'object-fit:contain',
    'pointer-events:none',
    '-webkit-user-drag:none',
  ].join(';');

  shadow = container.ownerDocument.createElement('span');
  shadow.className = SHADOW_CLASS;
  shadow.style.cssText = [
    'position:absolute',
    'left:17%',
    'right:17%',
    'bottom:3px',
    'height:12px',
    'border-radius:999px',
    'background:rgba(0,0,0,.26)',
    'filter:blur(5px)',
    'z-index:-1',
  ].join(';');

  nextRoot.append(img, shadow);
  return nextRoot
}

function attachEvents() {
  container.addEventListener('pointermove', onPointerMove, { passive: true });
  container.addEventListener('pointerleave', onPointerLeave);
  root.addEventListener('pointerdown', onDragStart);
  root.addEventListener('pointermove', onDragMove);
  root.addEventListener('pointerup', onDragEnd);
  root.addEventListener('pointercancel', onDragEnd);
  root.addEventListener('click', onClick);
}

function detachEvents() {
  container?.removeEventListener('pointermove', onPointerMove);
  container?.removeEventListener('pointerleave', onPointerLeave);
  root?.removeEventListener('pointerdown', onDragStart);
  root?.removeEventListener('pointermove', onDragMove);
  root?.removeEventListener('pointerup', onDragEnd);
  root?.removeEventListener('pointercancel', onDragEnd);
  root?.removeEventListener('click', onClick);
}

function mount(nextContainer, options = {}) {
  requireContainer(nextContainer);
  unmount();

  container = nextContainer;
  containerPosition = container.style.position;
  const computedPosition = ownerWindow(container).getComputedStyle(container).position;
  if (!computedPosition || computedPosition === 'static') {
    container.style.position = 'relative';
  }
  env = options.env || ownerWindow(container);
  config = normalizeConfig(options.config || config);
  onActivate = typeof options.onActivate === 'function' ? options.onActivate : null;
  root = createRoot();
  container.appendChild(root);

  runtime = createMascotRuntime({
    bounds,
    getConfig: () => config,
    getSurfaceLanes: options.getSurfaceLanes || (context => buildSurfaceLanes(context)),
    initialPet: {
      anchorX: Math.min(180, bounds().width / 2),
      anchorY: Math.min(180, bounds().height / 2),
      laneY: Math.min(180, bounds().height / 2),
      targetX: Math.min(360, bounds().width - VIEWPORT_PADDING),
      targetY: Math.min(180, bounds().height / 2),
    },
    onUpdate: render,
    scheduler: schedulerFor(env),
    viewportPadding: options.viewportPadding ?? VIEWPORT_PADDING,
  });
  attachEvents();
  runtime.start();
  render();

  return {
    unmount,
    updateConfig,
  }
}

function unmount() {
  runtime?.stop();
  detachEvents();
  root?.remove();
  if (container) container.style.position = containerPosition;
  container = null;
  containerPosition = '';
  env = globalThis;
  img = null;
  root = null;
  runtime = null;
  onActivate = null;
  shadow = null;
}

function updateConfig(nextConfig) {
  config = normalizeConfig(nextConfig || DEFAULT_CONFIG);
  runtime?.updateConfig(config);
}

export { mount, unmount, updateConfig };
