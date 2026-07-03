<script setup>
import { computed } from 'vue'
import ActionLab from './ActionLab.vue'
import MascotControls from './MascotControls.vue'
import MascotStage from './MascotStage.vue'
import { useMascotPreview } from '../composables/useMascotPreview'
import { resolveMascotProfile } from '../mascot/assets'

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

const {
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
} = useMascotPreview(props)

const mascotProfile = computed(() => resolveMascotProfile(config.value.mascot))

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
        <img :src="mascotProfile.icon" alt="" />
        <div>
          <h2>Agent 桌宠</h2>
          <p>{{ mascotProfile.label }} {{ mascotProfile.subtitle }}</p>
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

    <MascotStage
      ref="stageRef"
      :current-frame="currentFrame"
      :pet-style="petStyle"
      :shadow="config.shadow"
      :stage-style="stageStyle"
      @celebrate="celebrate"
      @drag-end="endDrag"
      @drag-move="onDrag"
      @drag-start="startDrag"
      @pointer-leave="leaveMouse"
      @pointer-move="updateMouse"
    />

    <ActionLab
      :debug-state="debugState"
      :mascot="config.mascot"
      @play-action="playAction"
      @play-behavior="playBehavior"
      @reset="resetPose"
    />

    <MascotControls :config="config" @update:config="updatePreviewConfig" />
  </div>
</template>

<style scoped>
.agentmascot-shell {
  min-height: 100%;
  padding: 18px;
  color: rgb(var(--v-theme-on-surface));
}
.agentmascot-header {
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

@media (max-width: 720px) {
  .agentmascot-shell {
    padding: 12px;
  }
}
</style>
