import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import AppPage from './__federation_expose_AppPage-xNs_lxLw.js';
import { c as cloneConfig } from './runtime-Y3O8ATVv.js';

const {createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "agentmascot-config" };

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
const localConfig = ref(cloneConfig());
const pageRef = ref(null);

function saveConfig() {
  emit('save', cloneConfig(pageRef.value?.config || localConfig.value));
}

onMounted(() => {
  localConfig.value = cloneConfig(props.initialConfig);
});

return (_ctx, _cache) => {
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      color: "transparent"
    }, {
      default: _withCtx(() => [
        _cache[1] || (_cache[1] = _createElementVNode("div", { class: "text-h6 ms-3" }, "Agent 桌宠配置", -1)),
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
    _createVNode(AppPage, {
      ref_key: "pageRef",
      ref: pageRef,
      config: localConfig.value,
      "plugin-id": "AgentMascot",
      "hide-title": ""
    }, null, 8, ["config"])
  ]))
}
}

};

export { _sfc_main as default };
