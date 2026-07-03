import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { c as cloneConfig, a as createActionState, b as createMouseState, d as createPetState, e as createMascotRuntime, m as mascotIcon, f as buildSurfaceLanes, u as unwrapResponse } from './provider-BDWNYDUs.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {unref:_unref,createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,createBlock:_createBlock,normalizeClass:_normalizeClass,normalizeStyle:_normalizeStyle} = await importShared('vue');


const _hoisted_1 = { class: "agentmascot-shell" };
const _hoisted_2 = {
  key: 0,
  class: "agentmascot-header"
};
const _hoisted_3 = { class: "agentmascot-title" };
const _hoisted_4 = ["src"];
const _hoisted_5 = { class: "agentmascot-actions" };
const _hoisted_6 = ["src"];
const _hoisted_7 = { class: "agentmascot-controls" };
const _hoisted_8 = { class: "control-slider" };
const _hoisted_9 = { class: "control-slider" };

const {computed,nextTick,onBeforeUnmount,onMounted,reactive,ref,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'AppPage',
  props: {
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
},
  setup(__props, { expose: __expose }) {

const props = __props;

const loading = ref(false);
const saving = ref(false);
const error = ref('');
const stageRef = ref(null);
const mascotRef = ref(null);
const config = ref(cloneConfig(props.config));
const actionState = reactive(createActionState());
const mouse = reactive(createMouseState({ active: false }));
const pet = reactive(createPetState({
  anchorX: 100,
  anchorY: 120,
  targetX: 320,
  targetY: 120,
  laneY: 120,
  lastAnchorX: 100,
  lastAnchorY: 120,
}));

function stageBounds() {
  const rect = stageRef.value?.getBoundingClientRect();
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

const runtime = createMascotRuntime({
  actionState,
  bounds: stageBounds,
  getConfig: () => config.value,
  getSurfaceLanes: context => buildSurfaceLanes(context),
  mouse,
  pet,
  scheduler: {
    setInterval: (...args) => window.setInterval(...args),
    clearInterval: id => window.clearInterval(id),
    setTimeout: (...args) => window.setTimeout(...args),
    requestAnimationFrame: callback => window.requestAnimationFrame(callback),
    cancelAnimationFrame: id => window.cancelAnimationFrame(id),
  },
  snapGroundOnDragRelease: true,
});

const currentPose = computed(() => runtime.currentPose());
const currentFrame = computed(() => currentPose.value.image);
const petSize = computed(() => runtime.petSize());
const stageStyle = computed(() => ({
  '--pet-size': `${petSize.value}px`,
}));
const petStyle = computed(() => {
  const state = runtime.renderState();
  return {
    transform: `translate3d(${state.left}px, ${state.top}px, 0) scaleX(${pet.lookRight ? -1 : 1})`,
    '--pet-facing': pet.lookRight ? -1 : 1,
  }
});

function endpoint(path) {
  return `plugin/${props.pluginId}${path}`
}

async function apiGet(path) {
  if (props.api?.get) {
    return props.api.get(endpoint(path))
  }
  return null
}

async function apiPost(path, payload) {
  if (props.api?.post) {
    return props.api.post(endpoint(path), payload)
  }
  return null
}

async function loadStatus() {
  if (!props.api?.get) return
  loading.value = true;
  error.value = '';
  try {
    const data = unwrapResponse(await apiGet('/status'));
    config.value = cloneConfig(data?.config);
    runtime.updateConfig(config.value);
  } catch (err) {
    error.value = err?.message || String(err);
  } finally {
    loading.value = false;
  }
}

async function saveConfig() {
  if (!props.api?.post) return
  saving.value = true;
  error.value = '';
  try {
    const data = unwrapResponse(await apiPost('/config', cloneConfig(config.value)));
    config.value = cloneConfig(data?.config);
    runtime.updateConfig(config.value);
  } catch (err) {
    error.value = err?.message || String(err);
  } finally {
    saving.value = false;
  }
}

function stagePoint(event) {
  const rect = stageRef.value?.getBoundingClientRect();
  if (!rect) return null
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

function updateMouse(event) {
  const point = stagePoint(event);
  if (point) runtime.handlePointerMove(point);
}

function leaveMouse() {
  runtime.handlePointerLeave();
}

function startDrag(event) {
  const point = stagePoint(event);
  if (!point) return
  event.preventDefault();
  runtime.startDrag(point);
  mascotRef.value?.setPointerCapture?.(event.pointerId);
}

function onDrag(event) {
  const point = stagePoint(event);
  if (point) runtime.moveDrag(point, event.movementX);
}

function endDrag(event) {
  const point = stagePoint(event) || { x: pet.anchorX, y: pet.anchorY };
  runtime.endDrag(point, event.movementX, event.movementY);
  mascotRef.value?.releasePointerCapture?.(event.pointerId);
}

function celebrate() {
  runtime.celebrate();
}

watch(
  () => props.config,
  nextValue => {
    if (nextValue) {
      config.value = cloneConfig(nextValue);
      runtime.updateConfig(config.value);
    }
  },
  { deep: true },
);

onMounted(async () => {
  await nextTick();
  runtime.start();
  if (!props.config) {
    await loadStatus();
  }
});

onBeforeUnmount(() => {
  runtime.stop();
});

__expose({
  loading,
  saving,
  config,
  loadStatus,
  saveConfig,
});

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VSlider = _resolveComponent("VSlider");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _createElementVNode("div", _hoisted_3, [
            _createElementVNode("img", {
              src: _unref(mascotIcon),
              alt: ""
            }, null, 8, _hoisted_4),
            _cache[8] || (_cache[8] = _createElementVNode("div", null, [
              _createElementVNode("h2", null, "Agent 桌宠"),
              _createElementVNode("p", null, "小天照 Shimeji demo")
            ], -1))
          ]),
          _createElementVNode("div", _hoisted_5, [
            _createVNode(_component_VBtn, {
              icon: "mdi-refresh",
              variant: "text",
              loading: loading.value,
              onClick: loadStatus
            }, null, 8, ["loading"]),
            _createVNode(_component_VBtn, {
              icon: "mdi-content-save",
              variant: "text",
              color: "primary",
              loading: saving.value,
              onClick: saveConfig
            }, null, 8, ["loading"])
          ])
        ]))
      : _createCommentVNode("", true),
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: "error",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(error.value), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createElementVNode("div", {
      class: "agentmascot-stage",
      style: _normalizeStyle(stageStyle.value),
      ref_key: "stageRef",
      ref: stageRef,
      onPointermove: updateMouse,
      onPointerleave: leaveMouse
    }, [
      _cache[9] || (_cache[9] = _createElementVNode("div", { class: "stage-grid" }, null, -1)),
      _cache[10] || (_cache[10] = _createElementVNode("div", { class: "stage-panel" }, [
        _createElementVNode("div", { class: "panel-title" }, "MoviePilot Agent"),
        _createElementVNode("div", { class: "panel-copy" }, "全屏游走、飞跃、爬墙、吸顶、鼠标跟随")
      ], -1)),
      _createElementVNode("button", {
        class: "stage-chip",
        type: "button",
        onClick: celebrate
      }, "动作测试"),
      _createElementVNode("div", {
        ref_key: "mascotRef",
        ref: mascotRef,
        class: _normalizeClass(["mascot", { 'mascot-shadow': config.value.shadow }]),
        style: _normalizeStyle(petStyle.value),
        onPointerdown: startDrag,
        onPointermove: onDrag,
        onPointerup: endDrag,
        onPointercancel: endDrag,
        onDblclick: celebrate
      }, [
        _createElementVNode("img", {
          src: currentFrame.value,
          alt: "Agent mascot",
          draggable: "false"
        }, null, 8, _hoisted_6)
      ], 38)
    ], 36),
    _createElementVNode("div", _hoisted_7, [
      _createVNode(_component_VSwitch, {
        modelValue: config.value.enabled,
        "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((config.value.enabled) = $event)),
        label: "启用插件",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createVNode(_component_VSwitch, {
        modelValue: config.value.replace_agent_entry,
        "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((config.value.replace_agent_entry) = $event)),
        label: "替换智能体入口",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createVNode(_component_VSwitch, {
        modelValue: config.value.show_sidebar_nav,
        "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((config.value.show_sidebar_nav) = $event)),
        label: "侧栏入口",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createVNode(_component_VSwitch, {
        modelValue: config.value.follow_mouse,
        "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((config.value.follow_mouse) = $event)),
        label: "跟随鼠标",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createVNode(_component_VSwitch, {
        modelValue: config.value.auto_roam,
        "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((config.value.auto_roam) = $event)),
        label: "自动游走",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createVNode(_component_VSwitch, {
        modelValue: config.value.shadow,
        "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((config.value.shadow) = $event)),
        label: "地面阴影",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createElementVNode("div", _hoisted_8, [
        _cache[11] || (_cache[11] = _createElementVNode("span", null, "缩放", -1)),
        _createVNode(_component_VSlider, {
          modelValue: config.value.scale,
          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((config.value.scale) = $event)),
          min: 0.6,
          max: 2,
          step: 0.05,
          "hide-details": "",
          color: "primary"
        }, null, 8, ["modelValue"])
      ]),
      _createElementVNode("div", _hoisted_9, [
        _cache[12] || (_cache[12] = _createElementVNode("span", null, "速度", -1)),
        _createVNode(_component_VSlider, {
          modelValue: config.value.speed,
          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((config.value.speed) = $event)),
          min: 0.4,
          max: 2,
          step: 0.05,
          "hide-details": "",
          color: "primary"
        }, null, 8, ["modelValue"])
      ])
    ])
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-d23734cb"]]);

export { _export_sfc as _, AppPage as default };
