<script setup>
const props = defineProps({
  config: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['update:config'])

function updateConfig(key, value) {
  emit('update:config', {
    ...props.config,
    [key]: value,
  })
}
</script>

<template>
  <div class="agentmascot-controls">
    <VSwitch :model-value="config.enabled" label="启用插件" color="primary" hide-details @update:model-value="updateConfig('enabled', $event)" />
    <VSwitch :model-value="config.replace_agent_entry" label="替换智能体入口" color="primary" hide-details @update:model-value="updateConfig('replace_agent_entry', $event)" />
    <VSwitch :model-value="config.show_sidebar_nav" label="侧栏入口" color="primary" hide-details @update:model-value="updateConfig('show_sidebar_nav', $event)" />
    <VSwitch :model-value="config.follow_mouse" label="跟随鼠标" color="primary" hide-details @update:model-value="updateConfig('follow_mouse', $event)" />
    <VSwitch :model-value="config.auto_roam" label="自动游走" color="primary" hide-details @update:model-value="updateConfig('auto_roam', $event)" />
    <VSwitch :model-value="config.shadow" label="地面阴影" color="primary" hide-details @update:model-value="updateConfig('shadow', $event)" />
    <div class="control-slider">
      <span>缩放</span>
      <VSlider :model-value="config.scale" :min="0.6" :max="2" :step="0.05" hide-details color="primary" @update:model-value="updateConfig('scale', $event)" />
    </div>
    <div class="control-slider">
      <span>速度</span>
      <VSlider :model-value="config.speed" :min="0.4" :max="2" :step="0.05" hide-details color="primary" @update:model-value="updateConfig('speed', $event)" />
    </div>
  </div>
</template>

<style scoped>
.agentmascot-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
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
  .control-slider {
    width: 100%;
    grid-template-columns: 42px 1fr;
  }
}
</style>
