<script setup>
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginBase: { type: String, default: 'plugin/AutoSubv3' },
  endpoints: { type: Array, default: () => [] },
  activeEndpoint: { type: String, default: '' },
  fallbackEnabled: { type: Boolean, default: true },
})

const emit = defineEmits([
  'update:endpoints',
  'update:activeEndpoint',
  'update:fallbackEnabled',
])

const localEndpoints = ref([])
const loadingModels = reactive({})
const testingModels = reactive({})
const modelOptions = reactive({})
const feedback = reactive({})
const apiReady = computed(() => typeof props.api?.post === 'function')

function normalizeModelValue(value) {
  if (typeof value === 'string') {
    const text = value.trim()
    if (text === '[object Object]') return ''
    if (text.startsWith('{') || text.startsWith('[')) {
      try {
        return normalizeModelValue(JSON.parse(text))
      } catch {
        const match = text.match(/['"](?:value|id|model|title)['"]\s*:\s*['"]([^'"]+)['"]/);
        if (match) return match[1].trim()
      }
    }
    return text
  }
  if (!value || typeof value !== 'object') return ''
  return String(value.value || value.id || value.model || value.title || '').trim()
}

function cloneEndpoints(value) {
  return (Array.isArray(value) ? value : []).map(item => ({
    ...item,
    model: normalizeModelValue(item.model),
  }))
}

watch(
  () => props.endpoints,
  value => {
    localEndpoints.value = cloneEndpoints(value)
  },
  { deep: true, immediate: true },
)

function notifyEndpoints() {
  emit('update:endpoints', cloneEndpoints(localEndpoints.value))
}

function endpointModels(endpoint) {
  const current = normalizeModelValue(endpoint.model)
  const items = (modelOptions[endpoint.id] || []).map(normalizeModelValue).filter(Boolean)
  if (current && !items.includes(current)) items.unshift(current)
  return [...new Set(items)]
}

function updateEndpointModel(endpoint, value) {
  endpoint.model = normalizeModelValue(value)
  notifyEndpoints()
}

function endpointPayload(endpoint) {
  return {
    endpoint: {
      id: endpoint.id,
      name: endpoint.name,
      api_url: endpoint.api_url,
      api_key: endpoint.api_key,
      model: endpoint.model,
      use_proxy: endpoint.use_proxy,
      compatible: endpoint.compatible,
    },
  }
}

function unwrapResponse(response) {
  return response?.data?.data || response?.data || response || {}
}

function responseMessage(response) {
  return response?.data?.message || response?.message || ''
}

function errorMessage(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback
}

function setFeedback(endpointId, type, message) {
  feedback[endpointId] = { type, message }
}

function addEndpoint() {
  const id = `endpoint-${Date.now().toString(36)}-${localEndpoints.value.length + 1}`
  localEndpoints.value.push({
    id,
    name: `API 线路 ${localEndpoints.value.length + 1}`,
    api_url: 'https://api.openai.com',
    api_key: '',
    model: '',
    use_proxy: false,
    compatible: false,
    enabled: true,
  })
  notifyEndpoints()
  if (!props.activeEndpoint) emit('update:activeEndpoint', id)
}

function deleteEndpoint(endpoint) {
  if (localEndpoints.value.length <= 1) return
  if (!window.confirm(`确定删除“${endpoint.name || '未命名线路'}”吗？`)) return
  localEndpoints.value = localEndpoints.value.filter(item => item.id !== endpoint.id)
  if (props.activeEndpoint === endpoint.id) {
    emit('update:activeEndpoint', localEndpoints.value.find(item => item.enabled)?.id || localEndpoints.value[0]?.id || '')
  }
  notifyEndpoints()
}

function setPrimary(endpoint) {
  endpoint.enabled = true
  notifyEndpoints()
  emit('update:activeEndpoint', endpoint.id)
}

function toggleEndpoint(endpoint, enabled) {
  endpoint.enabled = Boolean(enabled)
  const enabledEndpoints = localEndpoints.value.filter(item => item.enabled)
  if (!enabledEndpoints.length) {
    endpoint.enabled = true
    setFeedback(endpoint.id, 'error', '至少保留一条启用线路')
    notifyEndpoints()
    return
  }
  if (!endpoint.enabled && props.activeEndpoint === endpoint.id) {
    emit('update:activeEndpoint', enabledEndpoints[0].id)
  }
  notifyEndpoints()
}

function moveEndpoint(index, offset) {
  const nextIndex = index + offset
  if (nextIndex < 0 || nextIndex >= localEndpoints.value.length) return
  const items = [...localEndpoints.value]
  const [moved] = items.splice(index, 1)
  items.splice(nextIndex, 0, moved)
  localEndpoints.value = items
  notifyEndpoints()
}

async function fetchModels(endpoint) {
  if (loadingModels[endpoint.id] || testingModels[endpoint.id]) return
  if (!apiReady.value) {
    setFeedback(endpoint.id, 'error', '当前页面未注入插件 API 客户端，请刷新后重试')
    return
  }
  loadingModels[endpoint.id] = true
  setFeedback(endpoint.id, '', '')
  try {
    const response = await props.api.post(`${props.pluginBase}/models`, endpointPayload(endpoint))
    const data = unwrapResponse(response)
    modelOptions[endpoint.id] = (data.models || []).map(normalizeModelValue).filter(Boolean)
    setFeedback(endpoint.id, 'success', responseMessage(response) || `已获取 ${modelOptions[endpoint.id].length} 个模型`)
  } catch (err) {
    setFeedback(endpoint.id, 'error', errorMessage(err, '获取模型列表失败'))
  } finally {
    loadingModels[endpoint.id] = false
  }
}

async function testModel(endpoint) {
  if (loadingModels[endpoint.id] || testingModels[endpoint.id]) return
  if (!apiReady.value) {
    setFeedback(endpoint.id, 'error', '当前页面未注入插件 API 客户端，请刷新后重试')
    return
  }
  testingModels[endpoint.id] = true
  setFeedback(endpoint.id, '', '')
  try {
    const response = await props.api.post(`${props.pluginBase}/test_model`, endpointPayload(endpoint))
    const data = unwrapResponse(response)
    setFeedback(endpoint.id, 'success', responseMessage(response) || `模型 ${data.model || endpoint.model} 可用`)
  } catch (err) {
    setFeedback(endpoint.id, 'error', errorMessage(err, '测试模型失败'))
  } finally {
    testingModels[endpoint.id] = false
  }
}
</script>

<template>
  <div class="api-endpoint-settings">
    <div class="api-toolbar">
      <div>
        <strong>API 线路</strong>
        <p>主线路失败后，按列表顺序尝试其他已启用线路。</p>
      </div>
      <div class="api-toolbar-actions">
        <VSwitch
          :model-value="fallbackEnabled"
          label="自动 fallback"
          color="primary"
          hide-details
          @update:model-value="emit('update:fallbackEnabled', Boolean($event))"
        />
        <VBtn prepend-icon="mdi-plus" variant="tonal" color="primary" @click="addEndpoint">
          添加线路
        </VBtn>
      </div>
    </div>

    <VAlert
      v-if="!fallbackEnabled && localEndpoints.length > 1"
      class="mb-3"
      type="info"
      variant="tonal"
      density="compact"
      text="自动 fallback 已关闭，运行时只使用主线路。"
    />

    <div class="endpoint-list">
      <section
        v-for="(endpoint, index) in localEndpoints"
        :key="endpoint.id"
        class="endpoint-item"
        :class="{ primary: endpoint.id === activeEndpoint, disabled: !endpoint.enabled }"
      >
        <header class="endpoint-header">
          <div class="endpoint-identity">
            <VIcon
              :icon="endpoint.id === activeEndpoint ? 'mdi-star' : 'mdi-server-outline'"
              :color="endpoint.id === activeEndpoint ? 'warning' : undefined"
            />
            <div>
              <strong>{{ endpoint.name || '未命名线路' }}</strong>
              <span>{{ endpoint.id === activeEndpoint ? '主线路' : `Fallback 顺序 ${index + 1}` }}</span>
            </div>
          </div>
          <div class="endpoint-header-actions">
            <VBtn
              size="small"
              variant="text"
              :prepend-icon="endpoint.id === activeEndpoint ? 'mdi-star' : 'mdi-star-outline'"
              :color="endpoint.id === activeEndpoint ? 'warning' : undefined"
              @click="setPrimary(endpoint)"
            >
              {{ endpoint.id === activeEndpoint ? '当前主线路' : '设为主线路' }}
            </VBtn>
            <VSwitch
              :model-value="endpoint.enabled"
              label="启用"
              density="compact"
              hide-details
              @update:model-value="toggleEndpoint(endpoint, $event)"
            />
            <VBtn
              icon="mdi-arrow-up"
              size="small"
              variant="text"
              :disabled="index === 0"
              title="上移线路"
              @click="moveEndpoint(index, -1)"
            />
            <VBtn
              icon="mdi-arrow-down"
              size="small"
              variant="text"
              :disabled="index === localEndpoints.length - 1"
              title="下移线路"
              @click="moveEndpoint(index, 1)"
            />
            <VBtn
              icon="mdi-delete-outline"
              size="small"
              variant="text"
              color="error"
              :disabled="localEndpoints.length <= 1"
              title="删除线路"
              @click="deleteEndpoint(endpoint)"
            />
          </div>
        </header>

        <VRow dense>
          <VCol cols="12" md="4">
            <VTextField
              v-model="endpoint.name"
              label="线路名称"
              placeholder="主线路 / 备用线路"
              hide-details="auto"
              @update:model-value="notifyEndpoints"
            />
          </VCol>
          <VCol cols="12" md="8">
            <VTextField
              v-model="endpoint.api_url"
              label="API URL"
              placeholder="https://api.openai.com"
              hide-details="auto"
              @update:model-value="notifyEndpoints"
            />
          </VCol>
          <VCol cols="12" md="6">
            <VTextField
              v-model="endpoint.api_key"
              label="API 密钥"
              type="password"
              autocomplete="new-password"
              placeholder="sk-xxx"
              hide-details="auto"
              @update:model-value="notifyEndpoints"
            />
          </VCol>
          <VCol cols="12" md="6">
            <VCombobox
              :model-value="normalizeModelValue(endpoint.model)"
              :items="endpointModels(endpoint)"
              label="模型"
              placeholder="输入或获取模型"
              hide-details="auto"
              @update:model-value="updateEndpointModel(endpoint, $event)"
            />
          </VCol>
        </VRow>

        <div class="endpoint-footer">
          <div class="endpoint-options">
            <VSwitch
              v-model="endpoint.use_proxy"
              label="使用代理"
              density="compact"
              hide-details
              @update:model-value="notifyEndpoints"
            />
            <VSwitch
              v-model="endpoint.compatible"
              label="URL 已包含版本路径"
              density="compact"
              hide-details
              @update:model-value="notifyEndpoints"
            />
          </div>
          <div class="endpoint-test-actions">
            <VBtn
              prepend-icon="mdi-database-search-outline"
              variant="tonal"
              size="small"
              :loading="loadingModels[endpoint.id]"
              :disabled="testingModels[endpoint.id] || !endpoint.enabled || !apiReady"
              @click="fetchModels(endpoint)"
            >
              获取模型
            </VBtn>
            <VBtn
              prepend-icon="mdi-connection"
              variant="tonal"
              color="success"
              size="small"
              :loading="testingModels[endpoint.id]"
              :disabled="loadingModels[endpoint.id] || !endpoint.enabled || !apiReady"
              @click="testModel(endpoint)"
            >
              测试 API
            </VBtn>
          </div>
        </div>

        <VAlert
          v-if="feedback[endpoint.id]?.message"
          class="endpoint-feedback"
          :type="feedback[endpoint.id].type || 'info'"
          variant="tonal"
          density="compact"
          :text="feedback[endpoint.id].message"
        />
      </section>
    </div>
  </div>
</template>

<style scoped>
.api-endpoint-settings {
  display: grid;
  gap: 14px;
}

.api-toolbar,
.api-toolbar-actions,
.endpoint-header,
.endpoint-identity,
.endpoint-header-actions,
.endpoint-footer,
.endpoint-options,
.endpoint-test-actions {
  display: flex;
  align-items: center;
}

.api-toolbar,
.endpoint-header,
.endpoint-footer {
  justify-content: space-between;
  gap: 14px;
}

.api-toolbar p {
  margin: 3px 0 0;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
}

.api-toolbar-actions,
.endpoint-header-actions,
.endpoint-options,
.endpoint-test-actions {
  gap: 8px;
  flex-wrap: wrap;
}

.endpoint-list {
  display: grid;
  gap: 10px;
}

.endpoint-item {
  border: 1px solid rgba(var(--v-border-color), 0.22);
  border-radius: 8px;
  padding: 14px;
  background: rgb(var(--v-theme-surface));
}

.endpoint-item.primary {
  border-color: rgba(var(--v-theme-warning), 0.58);
}

.endpoint-item.disabled {
  opacity: 0.66;
}

.endpoint-header {
  margin-bottom: 12px;
}

.endpoint-identity {
  gap: 10px;
  min-width: 0;
}

.endpoint-identity div {
  display: grid;
  min-width: 0;
}

.endpoint-identity span {
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 12px;
}

.endpoint-footer {
  margin-top: 8px;
}

.endpoint-feedback {
  margin-top: 10px;
}

@media (max-width: 760px) {
  .api-toolbar,
  .endpoint-header,
  .endpoint-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .api-toolbar-actions,
  .endpoint-header-actions,
  .endpoint-test-actions {
    width: 100%;
  }
}
</style>
