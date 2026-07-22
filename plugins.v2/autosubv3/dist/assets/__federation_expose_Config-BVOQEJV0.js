import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {createElementVNode:_createElementVNode$1,resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,createTextVNode:_createTextVNode$1,withCtx:_withCtx$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock$1,toDisplayString:_toDisplayString,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1$1 = { class: "api-endpoint-settings" };
const _hoisted_2$1 = { class: "api-toolbar" };
const _hoisted_3$1 = { class: "api-toolbar-actions" };
const _hoisted_4$1 = { class: "endpoint-list" };
const _hoisted_5$1 = { class: "endpoint-header" };
const _hoisted_6$1 = { class: "endpoint-identity" };
const _hoisted_7$1 = { class: "endpoint-header-actions" };
const _hoisted_8 = { class: "endpoint-footer" };
const _hoisted_9 = { class: "endpoint-options" };
const _hoisted_10 = { class: "endpoint-test-actions" };

const {computed: computed$1,reactive: reactive$1,ref: ref$1,watch: watch$1} = await importShared('vue');



const _sfc_main$1 = {
  __name: 'ApiEndpointSettings',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginBase: { type: String, default: 'plugin/AutoSubv3' },
  endpoints: { type: Array, default: () => [] },
  activeEndpoint: { type: String, default: '' },
  fallbackEnabled: { type: Boolean, default: true },
},
  emits: [
  'update:endpoints',
  'update:activeEndpoint',
  'update:fallbackEnabled',
],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;

const localEndpoints = ref$1([]);
const loadingModels = reactive$1({});
const testingModels = reactive$1({});
const modelOptions = reactive$1({});
const feedback = reactive$1({});
const apiReady = computed$1(() => typeof props.api?.post === 'function');

function normalizeModelValue(value) {
  if (typeof value === 'string') {
    const text = value.trim();
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

watch$1(
  () => props.endpoints,
  value => {
    localEndpoints.value = cloneEndpoints(value);
  },
  { deep: true, immediate: true },
);

function notifyEndpoints() {
  emit('update:endpoints', cloneEndpoints(localEndpoints.value));
}

function endpointModels(endpoint) {
  const current = normalizeModelValue(endpoint.model);
  const items = (modelOptions[endpoint.id] || []).map(normalizeModelValue).filter(Boolean);
  if (current && !items.includes(current)) items.unshift(current);
  return [...new Set(items)]
}

function updateEndpointModel(endpoint, value) {
  endpoint.model = normalizeModelValue(value);
  notifyEndpoints();
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
  feedback[endpointId] = { type, message };
}

function addEndpoint() {
  const id = `endpoint-${Date.now().toString(36)}-${localEndpoints.value.length + 1}`;
  localEndpoints.value.push({
    id,
    name: `API 线路 ${localEndpoints.value.length + 1}`,
    api_url: 'https://api.openai.com',
    api_key: '',
    model: '',
    use_proxy: false,
    compatible: false,
    enabled: true,
  });
  notifyEndpoints();
  if (!props.activeEndpoint) emit('update:activeEndpoint', id);
}

function deleteEndpoint(endpoint) {
  if (localEndpoints.value.length <= 1) return
  if (!window.confirm(`确定删除“${endpoint.name || '未命名线路'}”吗？`)) return
  localEndpoints.value = localEndpoints.value.filter(item => item.id !== endpoint.id);
  if (props.activeEndpoint === endpoint.id) {
    emit('update:activeEndpoint', localEndpoints.value.find(item => item.enabled)?.id || localEndpoints.value[0]?.id || '');
  }
  notifyEndpoints();
}

function setPrimary(endpoint) {
  endpoint.enabled = true;
  notifyEndpoints();
  emit('update:activeEndpoint', endpoint.id);
}

function toggleEndpoint(endpoint, enabled) {
  endpoint.enabled = Boolean(enabled);
  const enabledEndpoints = localEndpoints.value.filter(item => item.enabled);
  if (!enabledEndpoints.length) {
    endpoint.enabled = true;
    setFeedback(endpoint.id, 'error', '至少保留一条启用线路');
    notifyEndpoints();
    return
  }
  if (!endpoint.enabled && props.activeEndpoint === endpoint.id) {
    emit('update:activeEndpoint', enabledEndpoints[0].id);
  }
  notifyEndpoints();
}

function moveEndpoint(index, offset) {
  const nextIndex = index + offset;
  if (nextIndex < 0 || nextIndex >= localEndpoints.value.length) return
  const items = [...localEndpoints.value];
  const [moved] = items.splice(index, 1);
  items.splice(nextIndex, 0, moved);
  localEndpoints.value = items;
  notifyEndpoints();
}

async function fetchModels(endpoint) {
  if (loadingModels[endpoint.id] || testingModels[endpoint.id]) return
  if (!apiReady.value) {
    setFeedback(endpoint.id, 'error', '当前页面未注入插件 API 客户端，请刷新后重试');
    return
  }
  loadingModels[endpoint.id] = true;
  setFeedback(endpoint.id, '', '');
  try {
    const response = await props.api.post(`${props.pluginBase}/models`, endpointPayload(endpoint));
    const data = unwrapResponse(response);
    modelOptions[endpoint.id] = (data.models || []).map(normalizeModelValue).filter(Boolean);
    setFeedback(endpoint.id, 'success', responseMessage(response) || `已获取 ${modelOptions[endpoint.id].length} 个模型`);
  } catch (err) {
    setFeedback(endpoint.id, 'error', errorMessage(err, '获取模型列表失败'));
  } finally {
    loadingModels[endpoint.id] = false;
  }
}

async function testModel(endpoint) {
  if (loadingModels[endpoint.id] || testingModels[endpoint.id]) return
  if (!apiReady.value) {
    setFeedback(endpoint.id, 'error', '当前页面未注入插件 API 客户端，请刷新后重试');
    return
  }
  testingModels[endpoint.id] = true;
  setFeedback(endpoint.id, '', '');
  try {
    const response = await props.api.post(`${props.pluginBase}/test_model`, endpointPayload(endpoint));
    const data = unwrapResponse(response);
    setFeedback(endpoint.id, 'success', responseMessage(response) || `模型 ${data.model || endpoint.model} 可用`);
  } catch (err) {
    setFeedback(endpoint.id, 'error', errorMessage(err, '测试模型失败'));
  } finally {
    testingModels[endpoint.id] = false;
  }
}

return (_ctx, _cache) => {
  const _component_VSwitch = _resolveComponent$1("VSwitch");
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VTextField = _resolveComponent$1("VTextField");
  const _component_VCol = _resolveComponent$1("VCol");
  const _component_VCombobox = _resolveComponent$1("VCombobox");
  const _component_VRow = _resolveComponent$1("VRow");

  return (_openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
    _createElementVNode$1("div", _hoisted_2$1, [
      _cache[2] || (_cache[2] = _createElementVNode$1("div", null, [
        _createElementVNode$1("strong", null, "API 线路"),
        _createElementVNode$1("p", null, "主线路失败后，按列表顺序尝试其他已启用线路。")
      ], -1)),
      _createElementVNode$1("div", _hoisted_3$1, [
        _createVNode$1(_component_VSwitch, {
          "model-value": __props.fallbackEnabled,
          label: "自动 fallback",
          color: "primary",
          "hide-details": "",
          "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => (emit('update:fallbackEnabled', Boolean($event))))
        }, null, 8, ["model-value"]),
        _createVNode$1(_component_VBtn, {
          "prepend-icon": "mdi-plus",
          variant: "tonal",
          color: "primary",
          onClick: addEndpoint
        }, {
          default: _withCtx$1(() => [...(_cache[1] || (_cache[1] = [
            _createTextVNode$1(" 添加线路 ", -1)
          ]))]),
          _: 1
        })
      ])
    ]),
    (!__props.fallbackEnabled && localEndpoints.value.length > 1)
      ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
          key: 0,
          class: "mb-3",
          type: "info",
          variant: "tonal",
          density: "compact",
          text: "自动 fallback 已关闭，运行时只使用主线路。"
        }))
      : _createCommentVNode$1("", true),
    _createElementVNode$1("div", _hoisted_4$1, [
      (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(localEndpoints.value, (endpoint, index) => {
        return (_openBlock$1(), _createElementBlock$1("section", {
          key: endpoint.id,
          class: _normalizeClass(["endpoint-item", { primary: endpoint.id === __props.activeEndpoint, disabled: !endpoint.enabled }])
        }, [
          _createElementVNode$1("header", _hoisted_5$1, [
            _createElementVNode$1("div", _hoisted_6$1, [
              _createVNode$1(_component_VIcon, {
                icon: endpoint.id === __props.activeEndpoint ? 'mdi-star' : 'mdi-server-outline',
                color: endpoint.id === __props.activeEndpoint ? 'warning' : undefined
              }, null, 8, ["icon", "color"]),
              _createElementVNode$1("div", null, [
                _createElementVNode$1("strong", null, _toDisplayString(endpoint.name || '未命名线路'), 1),
                _createElementVNode$1("span", null, _toDisplayString(endpoint.id === __props.activeEndpoint ? '主线路' : `Fallback 顺序 ${index + 1}`), 1)
              ])
            ]),
            _createElementVNode$1("div", _hoisted_7$1, [
              _createVNode$1(_component_VBtn, {
                size: "small",
                variant: "text",
                "prepend-icon": endpoint.id === __props.activeEndpoint ? 'mdi-star' : 'mdi-star-outline',
                color: endpoint.id === __props.activeEndpoint ? 'warning' : undefined,
                onClick: $event => (setPrimary(endpoint))
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(_toDisplayString(endpoint.id === __props.activeEndpoint ? '当前主线路' : '设为主线路'), 1)
                ]),
                _: 2
              }, 1032, ["prepend-icon", "color", "onClick"]),
              _createVNode$1(_component_VSwitch, {
                "model-value": endpoint.enabled,
                label: "启用",
                density: "compact",
                "hide-details": "",
                "onUpdate:modelValue": $event => (toggleEndpoint(endpoint, $event))
              }, null, 8, ["model-value", "onUpdate:modelValue"]),
              _createVNode$1(_component_VBtn, {
                icon: "mdi-arrow-up",
                size: "small",
                variant: "text",
                disabled: index === 0,
                title: "上移线路",
                onClick: $event => (moveEndpoint(index, -1))
              }, null, 8, ["disabled", "onClick"]),
              _createVNode$1(_component_VBtn, {
                icon: "mdi-arrow-down",
                size: "small",
                variant: "text",
                disabled: index === localEndpoints.value.length - 1,
                title: "下移线路",
                onClick: $event => (moveEndpoint(index, 1))
              }, null, 8, ["disabled", "onClick"]),
              _createVNode$1(_component_VBtn, {
                icon: "mdi-delete-outline",
                size: "small",
                variant: "text",
                color: "error",
                disabled: localEndpoints.value.length <= 1,
                title: "删除线路",
                onClick: $event => (deleteEndpoint(endpoint))
              }, null, 8, ["disabled", "onClick"])
            ])
          ]),
          _createVNode$1(_component_VRow, { dense: "" }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VCol, {
                cols: "12",
                md: "4"
              }, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VTextField, {
                    modelValue: endpoint.name,
                    "onUpdate:modelValue": [$event => ((endpoint.name) = $event), notifyEndpoints],
                    label: "线路名称",
                    placeholder: "主线路 / 备用线路",
                    "hide-details": "auto"
                  }, null, 8, ["modelValue", "onUpdate:modelValue"])
                ]),
                _: 2
              }, 1024),
              _createVNode$1(_component_VCol, {
                cols: "12",
                md: "8"
              }, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VTextField, {
                    modelValue: endpoint.api_url,
                    "onUpdate:modelValue": [$event => ((endpoint.api_url) = $event), notifyEndpoints],
                    label: "API URL",
                    placeholder: "https://api.openai.com",
                    "hide-details": "auto"
                  }, null, 8, ["modelValue", "onUpdate:modelValue"])
                ]),
                _: 2
              }, 1024),
              _createVNode$1(_component_VCol, {
                cols: "12",
                md: "6"
              }, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VTextField, {
                    modelValue: endpoint.api_key,
                    "onUpdate:modelValue": [$event => ((endpoint.api_key) = $event), notifyEndpoints],
                    label: "API 密钥",
                    type: "password",
                    autocomplete: "new-password",
                    placeholder: "sk-xxx",
                    "hide-details": "auto"
                  }, null, 8, ["modelValue", "onUpdate:modelValue"])
                ]),
                _: 2
              }, 1024),
              _createVNode$1(_component_VCol, {
                cols: "12",
                md: "6"
              }, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VCombobox, {
                    "model-value": normalizeModelValue(endpoint.model),
                    items: endpointModels(endpoint),
                    label: "模型",
                    placeholder: "输入或获取模型",
                    "hide-details": "auto",
                    "onUpdate:modelValue": $event => (updateEndpointModel(endpoint, $event))
                  }, null, 8, ["model-value", "items", "onUpdate:modelValue"])
                ]),
                _: 2
              }, 1024)
            ]),
            _: 2
          }, 1024),
          _createElementVNode$1("div", _hoisted_8, [
            _createElementVNode$1("div", _hoisted_9, [
              _createVNode$1(_component_VSwitch, {
                modelValue: endpoint.use_proxy,
                "onUpdate:modelValue": [$event => ((endpoint.use_proxy) = $event), notifyEndpoints],
                label: "使用代理",
                density: "compact",
                "hide-details": ""
              }, null, 8, ["modelValue", "onUpdate:modelValue"]),
              _createVNode$1(_component_VSwitch, {
                modelValue: endpoint.compatible,
                "onUpdate:modelValue": [$event => ((endpoint.compatible) = $event), notifyEndpoints],
                label: "URL 已包含版本路径",
                density: "compact",
                "hide-details": ""
              }, null, 8, ["modelValue", "onUpdate:modelValue"])
            ]),
            _createElementVNode$1("div", _hoisted_10, [
              _createVNode$1(_component_VBtn, {
                "prepend-icon": "mdi-database-search-outline",
                variant: "tonal",
                size: "small",
                loading: loadingModels[endpoint.id],
                disabled: testingModels[endpoint.id] || !endpoint.enabled || !apiReady.value,
                onClick: $event => (fetchModels(endpoint))
              }, {
                default: _withCtx$1(() => [...(_cache[3] || (_cache[3] = [
                  _createTextVNode$1(" 获取模型 ", -1)
                ]))]),
                _: 1
              }, 8, ["loading", "disabled", "onClick"]),
              _createVNode$1(_component_VBtn, {
                "prepend-icon": "mdi-connection",
                variant: "tonal",
                color: "success",
                size: "small",
                loading: testingModels[endpoint.id],
                disabled: loadingModels[endpoint.id] || !endpoint.enabled || !apiReady.value,
                onClick: $event => (testModel(endpoint))
              }, {
                default: _withCtx$1(() => [...(_cache[4] || (_cache[4] = [
                  _createTextVNode$1(" 测试 API ", -1)
                ]))]),
                _: 1
              }, 8, ["loading", "disabled", "onClick"])
            ])
          ]),
          (feedback[endpoint.id]?.message)
            ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                key: 0,
                class: "endpoint-feedback",
                type: feedback[endpoint.id].type || 'info',
                variant: "tonal",
                density: "compact",
                text: feedback[endpoint.id].message
              }, null, 8, ["type", "text"]))
            : _createCommentVNode$1("", true)
        ], 2))
      }), 128))
    ])
  ]))
}
}

};
const ApiEndpointSettings = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-5e720711"]]);

const {createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "autosub-config" };
const _hoisted_2 = { class: "config-shell" };
const _hoisted_3 = { class: "config-section" };
const _hoisted_4 = { class: "config-section" };
const _hoisted_5 = { class: "config-section" };
const _hoisted_6 = { class: "config-section" };
const _hoisted_7 = { class: "config-footer" };

const {computed,reactive,ref,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: {
    type: Object,
    default: () => ({}),
  },
  pluginId: {
    type: String,
    default: 'AutoSubv3',
  },
  initialConfig: {
    type: Object,
    default: () => ({}),
  },
},
  emits: ['save', 'close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;

const defaultConfig = {
  enabled: false,
  clear_history: false,
  send_notify: false,
  listen_transfer_event: true,
  generation_mode: 'monitor',
  process_new_only: true,
  path_whitelist: '',
  run_now: false,
  path_list: '',
  file_size: '10',
  translate_preference: 'english_first',
  translate_zh: true,
  enable_asr: true,
  auto_detect_language: false,
  skip_chinese: false,
  max_segment_duration: 8,
  max_segment_chars: 50,
  faster_whisper_model: 'base',
  proxy: true,
  openai_proxy: false,
  compatible: false,
  openai_url: 'https://api.siliconflow.cn',
  openai_key: '',
  openai_model: 'inclusionAI/Ling-flash-2.0',
  openai_endpoints: [],
  openai_active_endpoint: '',
  openai_fallback_enabled: true,
  context_window: 5,
  max_retries: 3,
  enable_merge: false,
  subtitle_output_mode: 'bilingual',
  enable_batch: true,
  batch_size: 20,
  parallel_workers: 10,
};

function normalizeModelValue(value) {
  if (typeof value === 'string') {
    const text = value.trim();
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

function normalizeInitialConfig(value = {}) {
  const merged = { ...defaultConfig, ...(value || {}) };
  merged.generation_mode = merged.generation_mode === 'fallback' ? 'fallback' : 'monitor';
  const rawEndpoints = Array.isArray(merged.openai_endpoints) ? merged.openai_endpoints : [];
  merged.openai_endpoints = rawEndpoints.length
    ? rawEndpoints.map((item, index) => ({
        id: item.id || `endpoint-${index + 1}`,
        name: item.name || `API 线路 ${index + 1}`,
        api_url: item.api_url || item.openai_url || 'https://api.openai.com',
        api_key: item.api_key || item.openai_key || '',
        model: normalizeModelValue(item.model || item.openai_model),
        use_proxy: Boolean(item.use_proxy ?? item.openai_proxy),
        compatible: Boolean(item.compatible),
        enabled: item.enabled !== false,
      }))
    : [{
        id: 'default',
        name: '默认线路',
        api_url: merged.openai_url,
        api_key: merged.openai_key,
        model: normalizeModelValue(merged.openai_model),
        use_proxy: Boolean(merged.openai_proxy),
        compatible: Boolean(merged.compatible),
        enabled: true,
      }];
  const activeExists = merged.openai_endpoints.some(item => (
    item.id === merged.openai_active_endpoint && item.enabled
  ));
  if (!activeExists) {
    merged.openai_active_endpoint = merged.openai_endpoints.find(item => item.enabled)?.id || merged.openai_endpoints[0]?.id || '';
  }
  return merged
}

const config = reactive(normalizeInitialConfig(props.initialConfig));
const saving = ref(false);
const error = ref('');
const activeTab = ref('basic');
const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoSubv3'}`);

const whisperModels = [
  { title: 'tiny', value: 'tiny' },
  { title: 'base', value: 'base' },
  { title: 'small', value: 'small' },
  { title: 'medium', value: 'medium' },
  { title: 'large-v3', value: 'large-v3' },
  { title: 'large-v3-turbo', value: 'deepdml/faster-whisper-large-v3-turbo-ct2' },
];
const outputModes = [
  { title: '双语字幕（翻译+原文）', value: 'bilingual' },
  { title: '纯中文字幕', value: 'chinese_only' },
];
const preferences = [
  { title: '仅英文', value: 'english_only' },
  { title: '英文优先', value: 'english_first' },
  { title: '原音优先', value: 'origin_first' },
];
watch(
  () => props.initialConfig,
  (value) => {
    Object.assign(config, normalizeInitialConfig(value));
  },
);

function updateEndpoints(value) {
  config.openai_endpoints = Array.isArray(value)
    ? value.map(item => ({ ...item, model: normalizeModelValue(item.model) }))
    : [];
  const active = config.openai_endpoints.find(item => item.id === config.openai_active_endpoint && item.enabled);
  if (!active) {
    config.openai_active_endpoint = config.openai_endpoints.find(item => item.enabled)?.id || '';
  }
}

function syncLegacyApiFields() {
  const active = config.openai_endpoints.find(item => item.id === config.openai_active_endpoint && item.enabled)
    || config.openai_endpoints.find(item => item.enabled);
  if (!active) return
  active.model = normalizeModelValue(active.model);
  config.openai_active_endpoint = active.id;
  config.openai_url = active.api_url;
  config.openai_key = active.api_key;
  config.openai_model = active.model;
  config.openai_proxy = Boolean(active.use_proxy);
  config.compatible = Boolean(active.compatible);
}

function save() {
  saving.value = true;
  error.value = '';
  try {
    syncLegacyApiFields();
    emit('save', {
      ...config,
      openai_endpoints: config.openai_endpoints.map(item => ({ ...item })),
    });
  } catch (err) {
    error.value = err?.message || '保存配置失败';
  } finally {
    saving.value = false;
  }
}

return (_ctx, _cache) => {
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VTab = _resolveComponent("VTab");
  const _component_VTabs = _resolveComponent("VTabs");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VWindowItem = _resolveComponent("VWindowItem");
  const _component_VWindow = _resolveComponent("VWindow");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      color: "transparent"
    }, {
      default: _withCtx(() => [
        _cache[34] || (_cache[34] = _createElementVNode("div", { class: "text-h6 ms-3" }, "AI字幕生成配置", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          variant: "text",
          "prepend-icon": "mdi-format-list-bulleted",
          onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
        }, {
          default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
            _createTextVNode("查看任务", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VBtn, {
          color: "primary",
          variant: "tonal",
          "prepend-icon": "mdi-content-save",
          loading: saving.value,
          onClick: save
        }, {
          default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
            _createTextVNode("保存", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          icon: "mdi-close",
          variant: "text",
          onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createVNode(_component_VTabs, {
      modelValue: activeTab.value,
      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((activeTab).value = $event)),
      class: "config-tabs",
      color: "primary",
      density: "comfortable"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VTab, {
          value: "basic",
          "prepend-icon": "mdi-tune-variant"
        }, {
          default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
            _createTextVNode("基础设置", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VTab, {
          value: "api",
          "prepend-icon": "mdi-api"
        }, {
          default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
            _createTextVNode("AI API", -1)
          ]))]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_2, [
      (error.value)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 0,
            class: "mb-4",
            type: "error",
            variant: "tonal",
            density: "compact",
            text: error.value
          }, null, 8, ["text"]))
        : _createCommentVNode("", true),
      _createVNode(_component_VWindow, {
        modelValue: activeTab.value,
        "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((activeTab).value = $event))
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VWindowItem, { value: "basic" }, {
            default: _withCtx(() => [
              _createElementVNode("section", _hoisted_3, [
                _cache[37] || (_cache[37] = _createElementVNode("div", { class: "section-title" }, "基础设置", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.generation_mode,
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((config.generation_mode) = $event)),
                          label: "启用独立入库监控",
                          "true-value": "monitor",
                          "false-value": "fallback",
                          hint: "关闭后仍可接收字幕匹配联动任务和手动任务",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.enabled,
                          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((config.enabled) = $event)),
                          label: "启用插件",
                          color: "primary",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.send_notify,
                          "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((config.send_notify) = $event)),
                          label: "发送通知",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.clear_history,
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((config.clear_history) = $event)),
                          label: "清理历史记录",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.process_new_only,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((config.process_new_only) = $event)),
                          label: "仅处理新增视频",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.run_now,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((config.run_now) = $event)),
                          label: "手动执行一次",
                          color: "secondary",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.translate_zh,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((config.translate_zh) = $event)),
                          label: "外语翻译成中文",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.skip_chinese,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((config.skip_chinese) = $event)),
                          label: "中文视频不翻译",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.enable_asr,
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((config.enable_asr) = $event)),
                          label: "允许 ASR 生成字幕",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _createElementVNode("section", _hoisted_4, [
                _cache[38] || (_cache[38] = _createElementVNode("div", { class: "section-title" }, "翻译参数", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: config.context_window,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((config.context_window) = $event)),
                          label: "上下文窗口大小",
                          placeholder: "5"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: config.max_retries,
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((config.max_retries) = $event)),
                          label: "LLM 请求重试次数",
                          placeholder: "3"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.enable_batch,
                          "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((config.enable_batch) = $event)),
                          label: "启用批量翻译",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: config.batch_size,
                          "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((config.batch_size) = $event)),
                          label: "每批翻译行数",
                          placeholder: "20（建议不超过30）"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: config.parallel_workers,
                          "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((config.parallel_workers) = $event)),
                          label: "并发线程数",
                          placeholder: "10"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _createElementVNode("section", _hoisted_5, [
                _cache[39] || (_cache[39] = _createElementVNode("div", { class: "section-title" }, "Whisper 与输出", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: config.faster_whisper_model,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((config.faster_whisper_model) = $event)),
                          items: whisperModels,
                          label: "Whisper 模型",
                          hint: "模型越大效果越好，耗时越久",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: config.subtitle_output_mode,
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((config.subtitle_output_mode) = $event)),
                          items: outputModes,
                          label: "字幕输出模式"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: config.max_segment_duration,
                          "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((config.max_segment_duration) = $event)),
                          label: "每段字幕最大时长（秒）",
                          placeholder: "8"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: config.max_segment_chars,
                          "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((config.max_segment_chars) = $event)),
                          label: "每段字幕最大字符数",
                          placeholder: "50"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "4"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: config.file_size,
                          "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((config.file_size) = $event)),
                          label: "文件最小大小（MB）",
                          placeholder: "10"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: config.translate_preference,
                          "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((config.translate_preference) = $event)),
                          items: preferences,
                          label: "字幕源语言偏好"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.auto_detect_language,
                          "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((config.auto_detect_language) = $event)),
                          label: "自动检测语言",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "3"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: config.proxy,
                          "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((config.proxy) = $event)),
                          label: "使用代理下载模型",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _createElementVNode("section", _hoisted_6, [
                _cache[40] || (_cache[40] = _createElementVNode("div", { class: "section-title" }, "路径", -1)),
                _createVNode(_component_VRow, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          modelValue: config.path_whitelist,
                          "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((config.path_whitelist) = $event)),
                          label: "监控路径（每行一个）",
                          rows: 3,
                          placeholder: "/mnt/media/movies\n/downloads",
                          hint: "目录变化时自动触发字幕生成",
                          "persistent-hint": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_VCol, { cols: "12" }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          modelValue: config.path_list,
                          "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((config.path_list) = $event)),
                          label: "媒体路径（手动执行时使用）",
                          rows: 3,
                          placeholder: "绝对路径，每行一个，支持文件和文件夹"
                        }, null, 8, ["modelValue"])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ])
            ]),
            _: 1
          }),
          _createVNode(_component_VWindowItem, { value: "api" }, {
            default: _withCtx(() => [
              _createVNode(ApiEndpointSettings, {
                api: __props.api,
                "plugin-base": pluginBase.value,
                endpoints: config.openai_endpoints,
                "active-endpoint": config.openai_active_endpoint,
                "fallback-enabled": config.openai_fallback_enabled,
                "onUpdate:endpoints": updateEndpoints,
                "onUpdate:activeEndpoint": _cache[27] || (_cache[27] = $event => (config.openai_active_endpoint = $event)),
                "onUpdate:fallbackEnabled": _cache[28] || (_cache[28] = $event => (config.openai_fallback_enabled = $event))
              }, null, 8, ["api", "plugin-base", "endpoints", "active-endpoint", "fallback-enabled"])
            ]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["modelValue"]),
      _createElementVNode("div", _hoisted_7, [
        _createVNode(_component_VBtn, {
          variant: "text",
          "prepend-icon": "mdi-format-list-bulleted",
          onClick: _cache[30] || (_cache[30] = $event => (emit('switch')))
        }, {
          default: _withCtx(() => [...(_cache[41] || (_cache[41] = [
            _createTextVNode("查看任务", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          variant: "text",
          onClick: _cache[31] || (_cache[31] = $event => (emit('close')))
        }, {
          default: _withCtx(() => [...(_cache[42] || (_cache[42] = [
            _createTextVNode("关闭", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VBtn, {
          color: "primary",
          "prepend-icon": "mdi-content-save",
          loading: saving.value,
          onClick: save
        }, {
          default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
            _createTextVNode("保存", -1)
          ]))]),
          _: 1
        }, 8, ["loading"])
      ])
    ])
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-6130bef9"]]);

export { Config as default };
