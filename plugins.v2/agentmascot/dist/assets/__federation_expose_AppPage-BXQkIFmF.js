import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { M as MASCOT_OPTIONS, c as cloneConfig, a as createActionState, b as createMouseState, d as createPetState, e as createMascotRuntime, f as buildSurfaceLanes, r as resolveMascotProfile } from './runtime-DUcdETvQ.js';
import { u as unwrapResponse } from './provider-mBbtEwEX.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {unref:_unref$1,resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,createElementVNode:_createElementVNode$2,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2} = await importShared('vue');


const _hoisted_1$2 = { class: "agentmascot-controls" };
const _hoisted_2$1 = { class: "control-slider" };
const _hoisted_3$1 = { class: "control-slider" };


const _sfc_main$2 = {
  __name: 'MascotControls',
  props: {
  config: {
    type: Object,
    required: true,
  },
},
  emits: ['update:config'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;

function updateConfig(key, value) {
  emit('update:config', {
    ...props.config,
    [key]: value,
  });
}

return (_ctx, _cache) => {
  const _component_VSelect = _resolveComponent$1("VSelect");
  const _component_VSwitch = _resolveComponent$1("VSwitch");
  const _component_VSlider = _resolveComponent$1("VSlider");

  return (_openBlock$2(), _createElementBlock$2("div", _hoisted_1$2, [
    _createVNode$1(_component_VSelect, {
      items: _unref$1(MASCOT_OPTIONS),
      "model-value": __props.config.mascot,
      class: "control-select",
      density: "compact",
      "hide-details": "",
      label: "形象",
      variant: "outlined",
      "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => (updateConfig('mascot', $event)))
    }, null, 8, ["items", "model-value"]),
    _createVNode$1(_component_VSwitch, {
      "model-value": __props.config.enabled,
      label: "启用插件",
      color: "primary",
      "hide-details": "",
      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => (updateConfig('enabled', $event)))
    }, null, 8, ["model-value"]),
    _createVNode$1(_component_VSwitch, {
      "model-value": __props.config.replace_agent_entry,
      label: "替换智能体入口",
      color: "primary",
      "hide-details": "",
      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => (updateConfig('replace_agent_entry', $event)))
    }, null, 8, ["model-value"]),
    _createVNode$1(_component_VSwitch, {
      "model-value": __props.config.show_sidebar_nav,
      label: "侧栏入口",
      color: "primary",
      "hide-details": "",
      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => (updateConfig('show_sidebar_nav', $event)))
    }, null, 8, ["model-value"]),
    _createVNode$1(_component_VSwitch, {
      "model-value": __props.config.follow_mouse,
      label: "跟随鼠标",
      color: "primary",
      "hide-details": "",
      "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => (updateConfig('follow_mouse', $event)))
    }, null, 8, ["model-value"]),
    _createVNode$1(_component_VSwitch, {
      "model-value": __props.config.auto_roam,
      label: "自动游走",
      color: "primary",
      "hide-details": "",
      "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => (updateConfig('auto_roam', $event)))
    }, null, 8, ["model-value"]),
    _createVNode$1(_component_VSwitch, {
      "model-value": __props.config.shadow,
      label: "地面阴影",
      color: "primary",
      "hide-details": "",
      "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => (updateConfig('shadow', $event)))
    }, null, 8, ["model-value"]),
    _createElementVNode$2("div", _hoisted_2$1, [
      _cache[9] || (_cache[9] = _createElementVNode$2("span", null, "缩放", -1)),
      _createVNode$1(_component_VSlider, {
        "model-value": __props.config.scale,
        min: 0.6,
        max: 4,
        step: 0.05,
        "hide-details": "",
        color: "primary",
        "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => (updateConfig('scale', $event)))
      }, null, 8, ["model-value"])
    ]),
    _createElementVNode$2("div", _hoisted_3$1, [
      _cache[10] || (_cache[10] = _createElementVNode$2("span", null, "速度", -1)),
      _createVNode$1(_component_VSlider, {
        "model-value": __props.config.speed,
        min: 0.4,
        max: 2,
        step: 0.05,
        "hide-details": "",
        color: "primary",
        "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => (updateConfig('speed', $event)))
      }, null, 8, ["model-value"])
    ])
  ]))
}
}

};
const MascotControls = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-dff81f2d"]]);

const {createElementVNode:_createElementVNode$1,normalizeClass:_normalizeClass,normalizeStyle:_normalizeStyle,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1} = await importShared('vue');


const _hoisted_1$1 = ["src"];

const {ref: ref$1} = await importShared('vue');



const _sfc_main$1 = {
  __name: 'MascotStage',
  props: {
  currentFrame: {
    type: String,
    required: true,
  },
  petStyle: {
    type: Object,
    required: true,
  },
  shadow: {
    type: Boolean,
    default: true,
  },
  stageStyle: {
    type: Object,
    required: true,
  },
},
  emits: [
  'celebrate',
  'drag-end',
  'drag-move',
  'drag-start',
  'pointer-leave',
  'pointer-move',
],
  setup(__props, { expose: __expose, emit: __emit }) {



const emit = __emit;

const stageRef = ref$1(null);
const mascotRef = ref$1(null);

function bounds() {
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

function stagePoint(event) {
  const rect = stageRef.value?.getBoundingClientRect();
  if (!rect) return null
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

function updateMouse(event) {
  emit('pointer-move', stagePoint(event));
}

function startDrag(event) {
  const point = stagePoint(event);
  if (!point) return
  event.preventDefault();
  emit('drag-start', point);
  mascotRef.value?.setPointerCapture?.(event.pointerId);
}

function onDrag(event) {
  emit('drag-move', {
    movementX: event.movementX,
    point: stagePoint(event),
  });
}

function endDrag(event) {
  emit('drag-end', {
    movementX: event.movementX,
    movementY: event.movementY,
    point: stagePoint(event),
  });
  mascotRef.value?.releasePointerCapture?.(event.pointerId);
}

__expose({
  bounds,
});

return (_ctx, _cache) => {
  return (_openBlock$1(), _createElementBlock$1("div", {
    class: "agentmascot-stage",
    style: _normalizeStyle(__props.stageStyle),
    ref_key: "stageRef",
    ref: stageRef,
    onPointermove: updateMouse,
    onPointerleave: _cache[2] || (_cache[2] = $event => (_ctx.$emit('pointer-leave')))
  }, [
    _cache[3] || (_cache[3] = _createElementVNode$1("div", { class: "stage-grid" }, null, -1)),
    _cache[4] || (_cache[4] = _createElementVNode$1("div", { class: "stage-panel" }, [
      _createElementVNode$1("div", { class: "panel-title" }, "MoviePilot Agent"),
      _createElementVNode$1("div", { class: "panel-copy" }, "全屏游走、飞跃、爬墙、吸顶、鼠标跟随")
    ], -1)),
    _createElementVNode$1("button", {
      class: "stage-chip",
      type: "button",
      onClick: _cache[0] || (_cache[0] = $event => (_ctx.$emit('celebrate')))
    }, "动作测试"),
    _createElementVNode$1("div", {
      ref_key: "mascotRef",
      ref: mascotRef,
      class: _normalizeClass(["mascot", { 'mascot-shadow': __props.shadow }]),
      style: _normalizeStyle(__props.petStyle),
      onPointerdown: startDrag,
      onPointermove: onDrag,
      onPointerup: endDrag,
      onPointercancel: endDrag,
      onDblclick: _cache[1] || (_cache[1] = $event => (_ctx.$emit('celebrate')))
    }, [
      _createElementVNode$1("img", {
        src: __props.currentFrame,
        alt: "Agent mascot",
        draggable: "false"
      }, null, 8, _hoisted_1$1)
    ], 38)
  ], 36))
}
}

};
const MascotStage = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-524b37ef"]]);

const {computed: computed$1,nextTick,onBeforeUnmount,onMounted,reactive,ref,watch} = await importShared('vue');

function useMascotPreview(props) {
  const loading = ref(false);
  const saving = ref(false);
  const error = ref('');
  const stageRef = ref(null);
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
    return stageRef.value?.bounds?.() || {
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

  computed$1(() => runtime.currentPose());
  const currentFrame = computed$1(() => runtime.currentFrame());
  const debugState = computed$1(() => runtime.debugState());
  const petSize = computed$1(() => runtime.petSize());
  const stageStyle = computed$1(() => ({
    '--pet-size': `${petSize.value}px`,
  }));
  const petStyle = computed$1(() => {
    const state = runtime.renderState();
    return {
      transform: `translate3d(${state.left}px, ${state.top}px, 0) scaleX(${pet.lookRight ? -1 : 1})`,
      '--pet-facing': pet.lookRight ? -1 : 1,
    }
  });

  function applyConfig(nextConfig) {
    config.value = cloneConfig(nextConfig);
    runtime.updateConfig(config.value);
  }

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
      applyConfig(data?.config);
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
      applyConfig(data?.config);
    } catch (err) {
      error.value = err?.message || String(err);
    } finally {
      saving.value = false;
    }
  }

  function updatePreviewConfig(nextConfig) {
    applyConfig(nextConfig);
  }

  function updateMouse(point) {
    if (point) runtime.handlePointerMove(point);
  }

  function leaveMouse() {
    runtime.handlePointerLeave();
  }

  function startDrag(point) {
    if (point) runtime.startDrag(point);
  }

  function onDrag({ point, movementX }) {
    if (point) runtime.moveDrag(point, movementX);
  }

  function endDrag({ point, movementX, movementY }) {
    runtime.endDrag(point || { x: pet.anchorX, y: pet.anchorY }, movementX, movementY);
  }

  function celebrate() {
    runtime.celebrate();
  }

  function playAction(name, options) {
    return runtime.playAction(name, options)
  }

  function playBehavior(id, options) {
    return runtime.playBehavior(id, options)
  }

  function resetPose() {
    runtime.resetPose();
  }

  watch(
    () => props.config,
    nextValue => {
      if (nextValue) applyConfig(nextValue);
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

  return {
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
  }
}

const {createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,unref:_unref,resolveComponent:_resolveComponent,createVNode:_createVNode,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,createBlock:_createBlock} = await importShared('vue');


const _hoisted_1 = { class: "agentmascot-shell" };
const _hoisted_2 = {
  key: 0,
  class: "agentmascot-header"
};
const _hoisted_3 = { class: "agentmascot-title" };
const _hoisted_4 = ["src"];
const _hoisted_5 = { class: "agentmascot-actions" };

const {computed} = await importShared('vue');


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

const {
  celebrate,
  config,
  currentFrame,
  endDrag,
  error,
  leaveMouse,
  loadStatus,
  loading,
  onDrag,
  petStyle,
  saveConfig,
  saving,
  stageRef,
  stageStyle,
  startDrag,
  updateMouse,
  updatePreviewConfig,
} = useMascotPreview(props);

const mascotProfile = computed(() => resolveMascotProfile(config.value.mascot));

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

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _createElementVNode("div", _hoisted_3, [
            _createElementVNode("img", {
              src: mascotProfile.value.icon,
              alt: ""
            }, null, 8, _hoisted_4),
            _createElementVNode("div", null, [
              _cache[0] || (_cache[0] = _createElementVNode("h2", null, "Agent 桌宠", -1)),
              _createElementVNode("p", null, _toDisplayString(mascotProfile.value.label) + " " + _toDisplayString(mascotProfile.value.subtitle), 1)
            ])
          ]),
          _createElementVNode("div", _hoisted_5, [
            _createVNode(_component_VBtn, {
              icon: "mdi-refresh",
              variant: "text",
              loading: _unref(loading),
              onClick: _unref(loadStatus)
            }, null, 8, ["loading", "onClick"]),
            _createVNode(_component_VBtn, {
              icon: "mdi-content-save",
              variant: "text",
              color: "primary",
              loading: _unref(saving),
              onClick: _unref(saveConfig)
            }, null, 8, ["loading", "onClick"])
          ])
        ]))
      : _createCommentVNode("", true),
    (_unref(error))
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: "error",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(_unref(error)), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createVNode(MascotStage, {
      ref_key: "stageRef",
      ref: stageRef,
      "current-frame": _unref(currentFrame),
      "pet-style": _unref(petStyle),
      shadow: _unref(config).shadow,
      "stage-style": _unref(stageStyle),
      onCelebrate: _unref(celebrate),
      onDragEnd: _unref(endDrag),
      onDragMove: _unref(onDrag),
      onDragStart: _unref(startDrag),
      onPointerLeave: _unref(leaveMouse),
      onPointerMove: _unref(updateMouse)
    }, null, 8, ["current-frame", "pet-style", "shadow", "stage-style", "onCelebrate", "onDragEnd", "onDragMove", "onDragStart", "onPointerLeave", "onPointerMove"]),
    _createVNode(MascotControls, {
      config: _unref(config),
      "onUpdate:config": _unref(updatePreviewConfig)
    }, null, 8, ["config", "onUpdate:config"])
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-63f502b9"]]);

export { _export_sfc as _, AppPage as default };
