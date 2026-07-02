<script setup>
import { onMounted, ref } from 'vue'
import AppPage from './AppPage.vue'
import { cloneConfig } from '../provider'

const props = defineProps({
  initialConfig: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['save', 'close'])
const localConfig = ref(cloneConfig())
const pageRef = ref(null)

function saveConfig() {
  emit('save', cloneConfig(pageRef.value?.config || localConfig.value))
}

onMounted(() => {
  localConfig.value = cloneConfig(props.initialConfig)
})
</script>

<template>
  <div class="agentmascot-config">
    <VToolbar density="comfortable" color="transparent">
      <div class="text-h6 ms-3">Agent 桌宠配置</div>
      <VSpacer />
      <VBtn icon="mdi-content-save" variant="text" color="primary" @click="saveConfig" />
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <AppPage ref="pageRef" :config="localConfig" plugin-id="AgentMascot" hide-title />
  </div>
</template>
