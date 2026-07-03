<script setup>
import { ref } from 'vue'

defineProps({
  currentFrame: {
    type: String,
    required: true,
  },
  petStyle: {
    type: Object,
    required: true,
  },
  shadow: {
    type: Boolean,
    default: true,
  },
  stageStyle: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits([
  'celebrate',
  'drag-end',
  'drag-move',
  'drag-start',
  'pointer-leave',
  'pointer-move',
])

const stageRef = ref(null)
const mascotRef = ref(null)

function bounds() {
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

function stagePoint(event) {
  const rect = stageRef.value?.getBoundingClientRect()
  if (!rect) return null
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

function updateMouse(event) {
  emit('pointer-move', stagePoint(event))
}

function startDrag(event) {
  const point = stagePoint(event)
  if (!point) return
  event.preventDefault()
  emit('drag-start', point)
  mascotRef.value?.setPointerCapture?.(event.pointerId)
}

function onDrag(event) {
  emit('drag-move', {
    movementX: event.movementX,
    point: stagePoint(event),
  })
}

function endDrag(event) {
  emit('drag-end', {
    movementX: event.movementX,
    movementY: event.movementY,
    point: stagePoint(event),
  })
  mascotRef.value?.releasePointerCapture?.(event.pointerId)
}

defineExpose({
  bounds,
})
</script>

<template>
  <div class="agentmascot-stage" :style="stageStyle" ref="stageRef" @pointermove="updateMouse" @pointerleave="$emit('pointer-leave')">
    <div class="stage-grid"></div>
    <div class="stage-panel">
      <div class="panel-title">MoviePilot Agent</div>
      <div class="panel-copy">全屏游走、飞跃、爬墙、吸顶、鼠标跟随</div>
    </div>
    <button class="stage-chip" type="button" @click="$emit('celebrate')">动作测试</button>

    <div
      ref="mascotRef"
      class="mascot"
      :class="{ 'mascot-shadow': shadow }"
      :style="petStyle"
      @pointerdown="startDrag"
      @pointermove="onDrag"
      @pointerup="endDrag"
      @pointercancel="endDrag"
      @dblclick="$emit('celebrate')"
    >
      <img :src="currentFrame" alt="Agent mascot" draggable="false" />
    </div>
  </div>
</template>

<style scoped>
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

@media (max-width: 720px) {
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
}
</style>
