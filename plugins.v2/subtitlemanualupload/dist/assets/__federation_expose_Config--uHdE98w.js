import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "subtitlemanualupload-config" };
const _hoisted_2 = { class: "config-shell" };
const _hoisted_3 = { class: "config-grid" };
const _hoisted_4 = { class: "config-grid two-column" };
const _hoisted_5 = { class: "config-grid" };

const {onMounted,ref} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  initialConfig: {
    type: Object,
    default: () => ({}),
  },
},
  emits: ['save', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;
const localConfig = ref({
  enabled: false,
  show_sidebar_nav: true,
  online_providers: ['subhd', 'zimuku', 'assrt'],
  online_engine: 'cloakbrowser',
  online_use_proxy: false,
  subhd_url: 'https://subhd.tv',
  zimuku_url: 'https://zimuku.org',
  assrt_url: 'https://2.assrt.net',
  rar_dependency_mode: 'none',
  rar_tool_path: '/usr/local/bin/7z',
});

const onlineProviderItems = [
  { title: 'SubHD', value: 'subhd' },
  { title: 'Zimuku', value: 'zimuku' },
  { title: '射手网(伪)', value: 'assrt' },
];

const onlineEngineItems = [
  { title: 'CloakBrowser（默认）', value: 'cloakbrowser' },
  { title: 'MoviePilot 浏览器仿真 / FlareSolverr', value: 'mp_browser' },
];

const rarDependencyModes = [
  { title: '不处理，仅检测', value: 'none' },
  { title: '加载插件时尝试容器内安装', value: 'container_install' },
  { title: '使用宿主机映射文件', value: 'mapped_binary' },
];

function normalizeProviders(value) {
  const allowed = ['subhd', 'zimuku', 'assrt'];
  const providers = Array.isArray(value) ? value.filter(item => allowed.includes(item)) : [];
  return providers.length ? Array.from(new Set(providers)) : allowed
}

function normalizeRootUrl(value, fallback) {
  const text = String(value || '').trim().replace(/\/+$/, '');
  return /^https?:\/\//i.test(text) ? text : fallback
}

function normalizeConfig(input) {
  return {
    enabled: Boolean(input?.enabled),
    show_sidebar_nav: input?.show_sidebar_nav !== false,
    online_providers: normalizeProviders(input?.online_providers),
    online_engine: ['cloakbrowser', 'mp_browser'].includes(input?.online_engine)
      ? input.online_engine
      : 'cloakbrowser',
    online_use_proxy: Boolean(input?.online_use_proxy),
    online_proxy_migrated: true,
    subhd_url: normalizeRootUrl(input?.subhd_url, 'https://subhd.tv'),
    zimuku_url: normalizeRootUrl(input?.zimuku_url, 'https://zimuku.org'),
    assrt_url: normalizeRootUrl(input?.assrt_url, 'https://2.assrt.net'),
    rar_dependency_mode: ['none', 'container_install', 'mapped_binary'].includes(input?.rar_dependency_mode)
      ? input.rar_dependency_mode
      : 'none',
    rar_tool_path: String(input?.rar_tool_path || '/usr/local/bin/7z').trim() || '/usr/local/bin/7z',
  }
}

function saveConfig() {
  emit('save', normalizeConfig(localConfig.value));
}

onMounted(() => {
  localConfig.value = normalizeConfig(props.initialConfig);
});

return (_ctx, _cache) => {
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      color: "transparent"
    }, {
      default: _withCtx(() => [
        _cache[11] || (_cache[11] = _createElementVNode("div", { class: "text-h6 ms-3" }, "字幕匹配配置", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          icon: "mdi-content-save",
          variant: "text",
          color: "primary",
          onClick: saveConfig
        }),
        _createVNode(_component_VBtn, {
          icon: "mdi-close",
          variant: "text",
          onClick: _cache[0] || (_cache[0] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createElementVNode("div", _hoisted_2, [
      _createVNode(_component_VCard, {
        rounded: "xl",
        elevation: "0",
        class: "config-card"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardText, null, {
            default: _withCtx(() => [
              _cache[12] || (_cache[12] = _createElementVNode("div", { class: "config-section" }, [
                _createElementVNode("div", { class: "config-section-title" }, "基础设置")
              ], -1)),
              _createElementVNode("div", _hoisted_3, [
                _createVNode(_component_VSwitch, {
                  modelValue: localConfig.value.enabled,
                  "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((localConfig.value.enabled) = $event)),
                  label: "启用插件",
                  color: "primary",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSwitch, {
                  modelValue: localConfig.value.show_sidebar_nav,
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((localConfig.value.show_sidebar_nav) = $event)),
                  label: "显示侧边栏入口",
                  color: "primary",
                  "hide-details": ""
                }, null, 8, ["modelValue"])
              ]),
              _createVNode(_component_VDivider, { class: "my-5" }),
              _cache[13] || (_cache[13] = _createElementVNode("div", { class: "config-section" }, [
                _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "config-section-title" }, "在线字幕搜索"),
                  _createElementVNode("p", null, "维护字幕站根地址；代理默认关闭，由容器当前网络环境决定。")
                ])
              ], -1)),
              _createElementVNode("div", _hoisted_4, [
                _createVNode(_component_VSelect, {
                  modelValue: localConfig.value.online_providers,
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((localConfig.value.online_providers) = $event)),
                  items: onlineProviderItems,
                  label: "启用字幕源",
                  variant: "outlined",
                  density: "comfortable",
                  multiple: "",
                  chips: "",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSelect, {
                  modelValue: localConfig.value.online_engine,
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((localConfig.value.online_engine) = $event)),
                  items: onlineEngineItems,
                  label: "在线搜索引擎",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VSwitch, {
                  modelValue: localConfig.value.online_use_proxy,
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((localConfig.value.online_use_proxy) = $event)),
                  class: "config-switch-line",
                  label: "在线搜索使用 MoviePilot 系统代理（默认关闭）",
                  color: "primary",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.subhd_url,
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((localConfig.value.subhd_url) = $event)),
                  label: "SubHD 站点地址",
                  placeholder: "https://subhd.tv",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.zimuku_url,
                  "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((localConfig.value.zimuku_url) = $event)),
                  label: "Zimuku 站点地址",
                  placeholder: "https://zimuku.org",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.assrt_url,
                  "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((localConfig.value.assrt_url) = $event)),
                  label: "射手网(伪) 站点地址",
                  placeholder: "https://2.assrt.net",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"])
              ]),
              _createVNode(_component_VAlert, {
                class: "mt-4",
                type: "info",
                variant: "tonal",
                density: "compact",
                text: "站点地址只填写根地址，例如 https://subhd.tv；如果域名或反代地址变化，在这里改根地址即可。"
              }),
              _createVNode(_component_VDivider, { class: "my-5" }),
              _cache[14] || (_cache[14] = _createElementVNode("div", { class: "config-section" }, [
                _createElementVNode("div", { class: "config-section-title" }, "RAR 解压器")
              ], -1)),
              _createElementVNode("div", _hoisted_5, [
                _createVNode(_component_VSelect, {
                  modelValue: localConfig.value.rar_dependency_mode,
                  "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((localConfig.value.rar_dependency_mode) = $event)),
                  items: rarDependencyModes,
                  label: "RAR 解压器处理方式",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: localConfig.value.rar_tool_path,
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((localConfig.value.rar_tool_path) = $event)),
                  label: "容器内映射路径",
                  placeholder: "/usr/local/bin/7z",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue"])
              ]),
              _createVNode(_component_VAlert, {
                class: "mt-4",
                type: "info",
                variant: "tonal",
                text: "RAR 自动安装只适合临时测试；长期建议在宿主机把静态 7zz 放到 MoviePilot 部署目录的 tools/7zz，并映射为容器内 /usr/local/bin/7z。插件不会主动重启 Docker 容器。"
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ])
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-3aaf716c"]]);

export { Config as default };
