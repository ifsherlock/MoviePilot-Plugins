<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  initialConfig: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['save', 'close'])
const localConfig = ref({
  enabled: false,
  show_sidebar_nav: true,
})

function normalizeConfig(input) {
  return {
    enabled: Boolean(input?.enabled),
    show_sidebar_nav: input?.show_sidebar_nav !== false,
  }
}

function saveConfig() {
  emit('save', normalizeConfig(localConfig.value))
}

onMounted(() => {
  localConfig.value = normalizeConfig(props.initialConfig)
})
</script>

<template>
  <div class="subtitlemanualupload-config">
    <VToolbar density="comfortable" color="transparent">
      <div class="text-h6 ms-3">字幕手传匹配配置</div>
      <VSpacer />
      <VBtn icon="mdi-content-save" variant="text" color="primary" @click="saveConfig" />
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <div class="config-shell">
      <VCard rounded="xl" elevation="0" class="config-card">
        <VCardText>
          <div class="config-grid">
            <VSwitch
              v-model="localConfig.enabled"
              label="启用插件"
              color="primary"
              hide-details
            />
            <VSwitch
              v-model="localConfig.show_sidebar_nav"
              label="显示侧边栏入口"
              color="primary"
              hide-details
            />
          </div>
          <VAlert
            class="mt-4"
            type="info"
            variant="tonal"
            text="当前版本用于手动上传字幕或 ZIP，并匹配本地媒体库中的电影或剧集文件。"
          />
        </VCardText>
      </VCard>
    </div>
  </div>
</template>

<style scoped>
.config-shell {
  padding: 20px;
}

.config-card {
  border: 1px solid rgba(127, 151, 185, 0.18);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(12px);
  box-shadow: 0 18px 50px rgba(30, 63, 108, 0.08);
}

.config-grid {
  display: grid;
  gap: 16px;
}
</style>
