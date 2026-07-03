<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { mascotIcon } from '../assets/shimeji/frames'
import { createActionState, createMouseState, createPetState } from '../mascot/motion'
import { createMascotRuntime } from '../mascot/runtime'
import { buildSurfaceLanes } from '../mascot/surfaces'
import { cloneConfig, unwrapResponse } from '../provider'

const props = defineProps({
  api: {
    type: Object,
    default: () => ({}),
  },
  pluginId: {
    type: String,
    default: 'AgentMascot',
  },
  config: {
    type: Object,
    default: null,
  },
  hideTitle: {
    type: Boolean,
    default: false,
  },
})

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const stageRef = ref(null)
const mascotRef = ref(null)
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
  const rect = stageRef.value?.getBoundingClientRect()
  if (rect?.width && rect?.height) {
    return {
      height: rect.height,
      width: rect.width,
    }
  }
  return {
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
const currentFrame = computed(() => currentPose.value.image)
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
    config.value = cloneConfig(data?.config)
    runtime.updateConfig(config.value)
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
    config.value = cloneConfig(data?.config)
    runtime.updateConfig(config.value)
  } catch (err) {
    error.value = err?.message || String(err)
  } finally {
    saving.value = false
  }
}

function stagePoint(event) {
  const rect = stageRef.value?.getBoundingClientRect()
  if (!rect) return null
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

function updateMouse(event) {
  const point = stagePoint(event)
  if (point) runtime.handlePointerMove(point)
}

function leaveMouse() {
  runtime.handlePointerLeave()
}

function startDrag(event) {
  const point = stagePoint(event)
  if (!point) return
  event.preventDefault()
  runtime.startDrag(point)
  mascotRef.value?.setPointerCapture?.(event.pointerId)
}

function onDrag(event) {
  const point = stagePoint(event)
  if (point) runtime.moveDrag(point, event.movementX)
}

function endDrag(event) {
  const point = stagePoint(event) || { x: pet.anchorX, y: pet.anchorY }
  runtime.endDrag(point, event.movementX, event.movementY)
  mascotRef.value?.releasePointerCapture?.(event.pointerId)
}

function celebrate() {
  runtime.celebrate()
}

watch(
  () => props.config,
  nextValue => {
    if (nextValue) {
      config.value = cloneConfig(nextValue)
      runtime.updateConfig(config.value)
    }
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

defineExpose({
  loading,
  saving,
  config,
  loadStatus,
  saveConfig,
})
</script>

<template>
  <div class="agentmascot-shell">
    <div v-if="!hideTitle" class="agentmascot-header">
      <div class="agentmascot-title">
        <img :src="mascotIcon" alt="" />
        <div>
          <h2>Agent 桌宠</h2>
          <p>小天照 Shimeji demo</p>
        </div>
      </div>
      <div class="agentmascot-actions">
        <VBtn icon="mdi-refresh" variant="text" :loading="loading" @click="loadStatus" />
        <VBtn icon="mdi-content-save" variant="text" color="primary" :loading="saving" @click="saveConfig" />
      </div>
    </div>

    <VAlert v-if="error" type="error" variant="tonal" density="compact" class="mb-3">
      {{ error }}
    </VAlert>

    <div class="agentmascot-stage" :style="stageStyle" ref="stageRef" @pointermove="updateMouse" @pointerleave="leaveMouse">
      <div class="stage-grid"></div>
      <div class="stage-panel">
        <div class="panel-title">MoviePilot Agent</div>
        <div class="panel-copy">全屏游走、飞跃、爬墙、吸顶、鼠标跟随</div>
      </div>
      <button class="stage-chip" type="button" @click="celebrate">动作测试</button>

      <div
        ref="mascotRef"
        class="mascot"
        :class="{ 'mascot-shadow': config.shadow }"
        :style="petStyle"
        @pointerdown="startDrag"
        @pointermove="onDrag"
        @pointerup="endDrag"
        @pointercancel="endDrag"
        @dblclick="celebrate"
      >
        <img :src="currentFrame" alt="Agent mascot" draggable="false" />
      </div>
    </div>

    <div class="agentmascot-controls">
      <VSwitch v-model="config.enabled" label="启用插件" color="primary" hide-details />
      <VSwitch v-model="config.replace_agent_entry" label="替换智能体入口" color="primary" hide-details />
      <VSwitch v-model="config.show_sidebar_nav" label="侧栏入口" color="primary" hide-details />
      <VSwitch v-model="config.follow_mouse" label="跟随鼠标" color="primary" hide-details />
      <VSwitch v-model="config.auto_roam" label="自动游走" color="primary" hide-details />
      <VSwitch v-model="config.shadow" label="地面阴影" color="primary" hide-details />
      <div class="control-slider">
        <span>缩放</span>
        <VSlider v-model="config.scale" :min="0.6" :max="2" :step="0.05" hide-details color="primary" />
      </div>
      <div class="control-slider">
        <span>速度</span>
        <VSlider v-model="config.speed" :min="0.4" :max="2" :step="0.05" hide-details color="primary" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.agentmascot-shell {
  min-height: 100%;
  padding: 18px;
  color: rgb(var(--v-theme-on-surface));
}
.agentmascot-header,
.agentmascot-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
}
.agentmascot-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.agentmascot-title img {
  width: 44px;
  height: 44px;
  object-fit: contain;
}
.agentmascot-title h2 {
  margin: 0;
  font-size: 1.35rem;
  line-height: 1.2;
}
.agentmascot-title p {
  margin: 2px 0 0;
  opacity: 0.72;
}
.agentmascot-actions {
  display: flex;
  gap: 4px;
}
.agentmascot-stage {
  position: relative;
  min-height: min(72vh, 760px);
  height: clamp(520px, 72vh, 820px);
  margin-top: 14px;
  overflow: hidden;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  background:
    radial-gradient(circle at 18% 12%, rgba(255, 241, 179, 0.34), transparent 28%),
    radial-gradient(circle at 74% 22%, rgba(111, 206, 194, 0.22), transparent 30%),
    linear-gradient(135deg, rgba(19, 30, 43, 0.94), rgba(42, 48, 54, 0.92));
  touch-action: none;
  user-select: none;
}
.stage-grid {
  position: absolute;
  inset: 0;
  opacity: 0.18;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.18) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.18) 1px, transparent 1px);
  background-size: 44px 44px;
}
.stage-panel {
  position: absolute;
  top: 22px;
  left: 22px;
  padding: 14px 16px;
  max-width: min(360px, calc(100% - 44px));
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 8px;
  color: #f8fafc;
  background: rgba(8, 13, 18, 0.76);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
}
.panel-title {
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.25;
}
.panel-copy {
  margin-top: 4px;
  font-size: 0.82rem;
  line-height: 1.4;
  color: #dbe5ea;
}
.stage-chip {
  position: absolute;
  top: 22px;
  right: 22px;
  height: 36px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 8px;
  color: #f9efd0;
  background: rgba(8, 13, 18, 0.44);
  cursor: pointer;
}
.mascot {
  position: absolute;
  top: 0;
  left: 0;
  width: var(--pet-size);
  height: var(--pet-size);
  display: grid;
  place-items: center;
  cursor: grab;
  will-change: transform;
  z-index: 3;
}
.mascot:active {
  cursor: grabbing;
}
.mascot img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: auto;
  pointer-events: none;
}
.mascot-shadow::after {
  content: '';
  position: absolute;
  left: 17%;
  right: 17%;
  bottom: 3px;
  height: 12px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.26);
  filter: blur(5px);
  transform: scaleX(var(--pet-facing, 1));
  z-index: -1;
}
.agentmascot-controls {
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
}
.control-slider {
  display: grid;
  grid-template-columns: 42px minmax(160px, 240px);
  align-items: center;
  gap: 10px;
}
.control-slider span {
  font-size: 0.9rem;
  opacity: 0.78;
}
@media (max-width: 720px) {
  .agentmascot-shell {
    padding: 12px;
  }
  .agentmascot-stage {
    height: 66vh;
    min-height: 430px;
  }
  .stage-panel {
    left: 12px;
    right: 12px;
  }
  .stage-chip {
    top: auto;
    right: 12px;
    bottom: 12px;
  }
  .control-slider {
    width: 100%;
    grid-template-columns: 42px 1fr;
  }
}
</style>
