import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { createActionState, createMouseState, createPetState } from '../mascot/motion'
import { createMascotRuntime } from '../mascot/runtime'
import { buildSurfaceLanes } from '../mascot/surfaces'
import { cloneConfig, unwrapResponse } from '../provider'

export function useMascotPreview(props) {
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')
  const stageRef = ref(null)
  const config = ref(cloneConfig(props.config))
  const actionState = reactive(createActionState())
  const mouse = reactive(createMouseState({ active: false }))
  const pet = reactive(createPetState({
    anchorX: 100,
    anchorY: 120,
    targetX: 320,
    targetY: 120,
    laneY: 120,
    lastAnchorX: 100,
    lastAnchorY: 120,
  }))

  function stageBounds() {
    return stageRef.value?.bounds?.() || {
      height: 520,
      width: 720,
    }
  }

  const runtime = createMascotRuntime({
    actionState,
    bounds: stageBounds,
    getConfig: () => config.value,
    getSurfaceLanes: context => buildSurfaceLanes(context),
    mouse,
    pet,
    scheduler: {
      setInterval: (...args) => window.setInterval(...args),
      clearInterval: id => window.clearInterval(id),
      setTimeout: (...args) => window.setTimeout(...args),
      requestAnimationFrame: callback => window.requestAnimationFrame(callback),
      cancelAnimationFrame: id => window.cancelAnimationFrame(id),
    },
    snapGroundOnDragRelease: true,
  })

  const currentPose = computed(() => runtime.currentPose())
  const currentFrame = computed(() => runtime.currentFrame())
  const debugState = computed(() => runtime.debugState())
  const petSize = computed(() => runtime.petSize())
  const stageStyle = computed(() => ({
    '--pet-size': `${petSize.value}px`,
  }))
  const petStyle = computed(() => {
    const state = runtime.renderState()
    return {
      transform: `translate3d(${state.left}px, ${state.top}px, 0) scaleX(${pet.lookRight ? -1 : 1})`,
      '--pet-facing': pet.lookRight ? -1 : 1,
    }
  })

  function applyConfig(nextConfig) {
    config.value = cloneConfig(nextConfig)
    runtime.updateConfig(config.value)
  }

  function endpoint(path) {
    return `plugin/${props.pluginId}${path}`
  }

  async function apiGet(path) {
    if (props.api?.get) {
      return props.api.get(endpoint(path))
    }
    return null
  }

  async function apiPost(path, payload) {
    if (props.api?.post) {
      return props.api.post(endpoint(path), payload)
    }
    return null
  }

  async function loadStatus() {
    if (!props.api?.get) return
    loading.value = true
    error.value = ''
    try {
      const data = unwrapResponse(await apiGet('/status'))
      applyConfig(data?.config)
    } catch (err) {
      error.value = err?.message || String(err)
    } finally {
      loading.value = false
    }
  }

  async function saveConfig() {
    if (!props.api?.post) return
    saving.value = true
    error.value = ''
    try {
      const data = unwrapResponse(await apiPost('/config', cloneConfig(config.value)))
      applyConfig(data?.config)
    } catch (err) {
      error.value = err?.message || String(err)
    } finally {
      saving.value = false
    }
  }

  function updatePreviewConfig(nextConfig) {
    applyConfig(nextConfig)
  }

  function updateMouse(point) {
    if (point) runtime.handlePointerMove(point)
  }

  function leaveMouse() {
    runtime.handlePointerLeave()
  }

  function startDrag(point) {
    if (point) runtime.startDrag(point)
  }

  function onDrag({ point, movementX }) {
    if (point) runtime.moveDrag(point, movementX)
  }

  function endDrag({ point, movementX, movementY }) {
    runtime.endDrag(point || { x: pet.anchorX, y: pet.anchorY }, movementX, movementY)
  }

  function celebrate() {
    runtime.celebrate()
  }

  function playAction(name, options) {
    return runtime.playAction(name, options)
  }

  function playBehavior(id, options) {
    return runtime.playBehavior(id, options)
  }

  function resetPose() {
    runtime.resetPose()
  }

  watch(
    () => props.config,
    nextValue => {
      if (nextValue) applyConfig(nextValue)
    },
    { deep: true },
  )

  onMounted(async () => {
    await nextTick()
    runtime.start()
    if (!props.config) {
      await loadStatus()
    }
  })

  onBeforeUnmount(() => {
    runtime.stop()
  })

  return {
    celebrate,
    config,
    currentFrame,
    debugState,
    endDrag,
    error,
    leaveMouse,
    loadStatus,
    loading,
    onDrag,
    petStyle,
    playAction,
    playBehavior,
    resetPose,
    saveConfig,
    saving,
    stageRef,
    stageStyle,
    startDrag,
    updateMouse,
    updatePreviewConfig,
  }
}
