<script setup>
import { onMounted, ref } from 'vue'
import Config from './Config.vue'
import { useMobileViewport } from '../mobile/useMobileViewport'
import { errorMessage, unwrapResponse } from '../utils/formatters'

const props = defineProps({
  api: { type: Object, required: true },
  pluginId: { type: String, required: true },
})
const emit = defineEmits(['close', 'saved'])
const isMobileViewport = useMobileViewport()
const loading = ref(false)
const saving = ref(false)
const initialConfig = ref(null)
const error = ref('')

async function loadConfig() {
  loading.value = true
  error.value = ''
  try {
    const response = await props.api.get(`plugin/form/${props.pluginId}`)
    if (response?.success === false) throw new Error(response.message || '加载配置失败')
    const result = unwrapResponse(response)
    if (result?.render_mode !== 'vue' || !result.model || typeof result.model !== 'object' || Array.isArray(result.model)) {
      throw new Error('插件配置响应无效，请升级 MoviePilot 后重试')
    }
    initialConfig.value = result.model
  } catch (err) {
    error.value = errorMessage(err, '加载配置失败')
  } finally {
    loading.value = false
  }
}

async function saveConfig(config) {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    const result = await props.api.put(`plugin/${props.pluginId}`, config)
    if (result?.success !== true) {
      throw new Error(result?.message || '保存配置失败')
    }
    emit('saved')
  } catch (err) {
    error.value = errorMessage(err, '保存配置失败')
  } finally {
    saving.value = false
  }
}

function close() {
  if (!saving.value) emit('close')
}

onMounted(loadConfig)
</script>

<template>
  <VDialog
    :model-value="true"
    :persistent="saving"
    :fullscreen="isMobileViewport"
    max-width="60rem"
    scrollable
    @update:model-value="value => { if (!value) close() }"
  >
    <VCard>
      <VAlert v-if="error" type="error" variant="tonal" class="ma-3" role="alert" :text="error" />
      <VCardText class="pa-0">
        <Config
          v-if="initialConfig"
          :initial-config="initialConfig"
          :saving="saving"
          @save="saveConfig"
          @close="close"
        />
        <div v-else class="pa-6">
          <VProgressLinear v-if="loading" indeterminate aria-label="正在加载配置" />
          <VBtn v-else prepend-icon="mdi-refresh" variant="tonal" @click="loadConfig">重试</VBtn>
        </div>
      </VCardText>
      <VCardActions v-if="!initialConfig">
        <VSpacer />
        <VBtn variant="text" @click="close">关闭</VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>
