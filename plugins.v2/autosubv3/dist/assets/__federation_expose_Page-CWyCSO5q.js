import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {computed: computed$3,ref: ref$1} = await importShared('vue');


function resolveValue(source) {
  if (typeof source === 'function') return source()
  return source?.value ?? source
}

function unwrapResponse(response) {
  return response?.data?.data || response?.data || response || {}
}

function errorMessage(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback
}

function canCancelTask(task) {
  return Boolean(task?.active || ['pending', 'in_progress'].includes(task?.status))
}

function canRestartTask(task) {
  return Boolean(task?.video_file && ['completed', 'cancelled', 'failed', 'ignored', 'no_audio'].includes(task?.status))
}

function canDeleteTask(task) {
  return Boolean(task?.task_id && !['in_progress'].includes(task?.status))
}

function useAutoSubTasks({ api, pluginBase, confirmDelete = window.confirm } = {}) {
  const loading = ref$1(false);
  const operating = ref$1(false);
  const operation = ref$1('');
  const sortOrder = ref$1('desc');
  const statusFilter = ref$1('all');
  const selectedTaskIds = ref$1([]);
  const error = ref$1('');
  const message = ref$1('');
  const status = ref$1({});
  const tasks = ref$1([]);
  const restartDialog = ref$1(false);
  const restartTargets = ref$1([]);
  const restartSourcePolicy = ref$1('reuse');
  const restartSourceOptions = [
    { title: '沿用原任务来源', value: 'reuse' },
    { title: '自动选择', value: 'auto' },
    { title: '本地外挂字幕', value: 'local_external' },
    { title: '视频内嵌字幕', value: 'embedded' },
    { title: '音轨 ASR', value: 'asr' },
  ];

  const sortedTasks = computed$3(() => {
    const items = [...tasks.value];
    items.sort((a, b) => {
      const left = new Date(a.add_time || 0).getTime();
      const right = new Date(b.add_time || 0).getTime();
      return sortOrder.value === 'desc' ? right - left : left - right
    });
    return items
  });

  const visibleTasks = computed$3(() => {
    if (statusFilter.value === 'all') return sortedTasks.value
    return sortedTasks.value.filter(task => task.status === statusFilter.value)
  });

  const visibleTaskIds = computed$3(() => new Set(visibleTasks.value.map(task => task.task_id)));
  const allVisibleSelected = computed$3(() => (
    Boolean(visibleTasks.value.length)
    && visibleTasks.value.every(task => selectedTaskIds.value.includes(task.task_id))
  ));
  const selectedTasks = computed$3(() => {
    const picked = new Set(selectedTaskIds.value);
    return visibleTasks.value.filter(task => picked.has(task.task_id))
  });
  const cancellableSelected = computed$3(() => selectedTasks.value.filter(canCancelTask));
  const restartableSelected = computed$3(() => selectedTasks.value.filter(canRestartTask));
  const deletableSelected = computed$3(() => selectedTasks.value.filter(canDeleteTask));
  const statusChips = computed$3(() => [
    { value: 'all', label: '总数', count: tasks.value.length },
    { value: 'pending', label: '等待', count: status.value.counts?.pending || 0, color: 'info' },
    { value: 'in_progress', label: '处理中', count: status.value.counts?.in_progress || 0, color: 'warning' },
    { value: 'completed', label: '完成', count: status.value.counts?.completed || 0, color: 'success' },
    { value: 'failed', label: '失败', count: status.value.counts?.failed || 0, color: 'error' },
    { value: 'cancelled', label: '已取消', count: status.value.counts?.cancelled || 0 },
  ]);

  function apiClient() {
    return resolveValue(api) || {}
  }

  function basePath() {
    return resolveValue(pluginBase)
  }

  async function loadTasks() {
    loading.value = true;
    error.value = '';
    try {
      const response = await apiClient().get(`${basePath()}/tasks?limit=1000`);
      const data = unwrapResponse(response);
      status.value = data.status || {};
      tasks.value = data.tasks || [];
      selectedTaskIds.value = selectedTaskIds.value.filter(id => tasks.value.some(task => task.task_id === id));
    } catch (err) {
      error.value = errorMessage(err, '读取 AI 字幕任务失败');
    } finally {
      loading.value = false;
    }
  }

  async function cancelTasks(inputTasks) {
    const picked = (inputTasks || []).filter(canCancelTask);
    if (!picked.length || operating.value) return
    operating.value = true;
    operation.value = 'cancel';
    error.value = '';
    message.value = '';
    try {
      const response = await apiClient().post(`${basePath()}/cancel`, {
        task_ids: picked.map(task => task.task_id),
      });
      message.value = response?.message || `已取消 ${picked.length} 个任务`;
      await loadTasks();
    } catch (err) {
      error.value = errorMessage(err, '取消 AI 字幕任务失败');
    } finally {
      operation.value = '';
      operating.value = false;
    }
  }

  async function restartTasks(inputTasks) {
    const picked = (inputTasks || []).filter(canRestartTask);
    if (!picked.length || operating.value) return
    restartTargets.value = picked;
    restartSourcePolicy.value = 'reuse';
    restartDialog.value = true;
  }

  async function confirmRestartTasks() {
    const picked = (restartTargets.value || []).filter(canRestartTask);
    if (!picked.length || operating.value) return
    operating.value = true;
    operation.value = 'restart';
    error.value = '';
    message.value = '';
    try {
      const response = await apiClient().post(`${basePath()}/restart`, {
        task_ids: picked.map(task => task.task_id),
        source_policy: restartSourcePolicy.value,
        overwrite_policy: restartSourcePolicy.value === 'reuse' ? 'backup_replace' : 'new_variant',
      });
      message.value = response?.message || `已重新提交 ${picked.length} 个任务`;
      restartDialog.value = false;
      await loadTasks();
    } catch (err) {
      error.value = errorMessage(err, '重新生成 AI 字幕任务失败');
    } finally {
      operation.value = '';
      operating.value = false;
    }
  }

  async function deleteTasks(inputTasks) {
    const picked = (inputTasks || []).filter(canDeleteTask);
    if (!picked.length || operating.value) return
    const confirmed = confirmDelete(`确定删除 ${picked.length} 个 AI 字幕任务记录吗？`);
    if (!confirmed) return
    operating.value = true;
    operation.value = 'delete';
    error.value = '';
    message.value = '';
    try {
      const response = await apiClient().post(`${basePath()}/delete`, {
        task_ids: picked.map(task => task.task_id),
      });
      message.value = response?.message || `已删除 ${picked.length} 个任务记录`;
      await loadTasks();
    } catch (err) {
      error.value = errorMessage(err, '删除 AI 字幕任务失败');
    } finally {
      operation.value = '';
      operating.value = false;
    }
  }

  function toggleTask(task, checked) {
    const set = new Set(selectedTaskIds.value);
    if (checked) {
      set.add(task.task_id);
    } else {
      set.delete(task.task_id);
    }
    selectedTaskIds.value = Array.from(set);
  }

  function toggleAll() {
    if (allVisibleSelected.value) {
      selectedTaskIds.value = selectedTaskIds.value.filter(id => !visibleTaskIds.value.has(id));
      return
    }
    selectedTaskIds.value = Array.from(new Set([
      ...selectedTaskIds.value,
      ...visibleTasks.value.map(task => task.task_id),
    ]));
  }

  function setStatusFilter(value) {
    statusFilter.value = value;
    const visibleIds = new Set(visibleTasks.value.map(task => task.task_id));
    selectedTaskIds.value = selectedTaskIds.value.filter(id => visibleIds.has(id));
  }

  return {
    loading,
    operating,
    operation,
    sortOrder,
    statusFilter,
    selectedTaskIds,
    error,
    message,
    status,
    tasks,
    restartDialog,
    restartTargets,
    restartSourcePolicy,
    restartSourceOptions,
    sortedTasks,
    visibleTasks,
    allVisibleSelected,
    selectedTasks,
    cancellableSelected,
    restartableSelected,
    deletableSelected,
    statusChips,
    loadTasks,
    cancelTasks,
    restartTasks,
    confirmRestartTasks,
    deleteTasks,
    toggleTask,
    toggleAll,
    canCancelTask,
    canRestartTask,
    canDeleteTask,
    setStatusFilter,
  }
}

const {toDisplayString:_toDisplayString$4,createElementVNode:_createElementVNode$4,createTextVNode:_createTextVNode$5,resolveComponent:_resolveComponent$6,withCtx:_withCtx$5,createVNode:_createVNode$5,openBlock:_openBlock$6,createElementBlock:_createElementBlock$5,createCommentVNode:_createCommentVNode$3} = await importShared('vue');


const _hoisted_1$5 = {
  key: 0,
  class: "autosub-mobile-batch-bar",
  "aria-label": "移动端批量操作"
};
const _hoisted_2$4 = { class: "batch-count" };
const _hoisted_3$3 = { class: "batch-actions" };


const _sfc_main$6 = {
  __name: 'MobileBatchActionBar',
  props: {
  selectedCount: {
    type: Number,
    default: 0,
  },
  cancellableSelected: {
    type: Array,
    default: () => [],
  },
  restartableSelected: {
    type: Array,
    default: () => [],
  },
  deletableSelected: {
    type: Array,
    default: () => [],
  },
  operating: {
    type: Boolean,
    default: false,
  },
  operation: {
    type: String,
    default: '',
  },
},
  emits: ['cancel-selected', 'restart-selected', 'delete-selected'],
  setup(__props, { emit: __emit }) {



const emit = __emit;

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent$6("VBtn");

  return (__props.selectedCount)
    ? (_openBlock$6(), _createElementBlock$5("aside", _hoisted_1$5, [
        _createElementVNode$4("div", _hoisted_2$4, [
          _createElementVNode$4("strong", null, _toDisplayString$4(__props.selectedCount), 1),
          _cache[3] || (_cache[3] = _createElementVNode$4("span", null, "个已选", -1))
        ]),
        _createElementVNode$4("div", _hoisted_3$3, [
          _createVNode$5(_component_VBtn, {
            class: "batch-primary-action mobile-touch-target",
            color: "primary",
            variant: "flat",
            disabled: !__props.restartableSelected.length || __props.operating,
            loading: __props.operation === 'restart',
            onClick: _cache[0] || (_cache[0] = $event => (emit('restart-selected')))
          }, {
            default: _withCtx$5(() => [...(_cache[4] || (_cache[4] = [
              _createTextVNode$5(" 重跑 ", -1)
            ]))]),
            _: 1
          }, 8, ["disabled", "loading"]),
          _createVNode$5(_component_VBtn, {
            class: "batch-secondary-action mobile-touch-target",
            color: "warning",
            variant: "tonal",
            disabled: !__props.cancellableSelected.length || __props.operating,
            loading: __props.operation === 'cancel',
            onClick: _cache[1] || (_cache[1] = $event => (emit('cancel-selected')))
          }, {
            default: _withCtx$5(() => [...(_cache[5] || (_cache[5] = [
              _createTextVNode$5(" 取消 ", -1)
            ]))]),
            _: 1
          }, 8, ["disabled", "loading"]),
          _createVNode$5(_component_VBtn, {
            class: "batch-danger-action mobile-touch-target",
            color: "error",
            variant: "text",
            disabled: !__props.deletableSelected.length || __props.operating,
            loading: __props.operation === 'delete',
            onClick: _cache[2] || (_cache[2] = $event => (emit('delete-selected')))
          }, {
            default: _withCtx$5(() => [...(_cache[6] || (_cache[6] = [
              _createTextVNode$5(" 删除 ", -1)
            ]))]),
            _: 1
          }, 8, ["disabled", "loading"])
        ])
      ]))
    : _createCommentVNode$3("", true)
}
}

};
const MobileBatchActionBar = /*#__PURE__*/_export_sfc(_sfc_main$6, [['__scopeId',"data-v-2b046da9"]]);

const {createTextVNode:_createTextVNode$4,resolveComponent:_resolveComponent$5,withCtx:_withCtx$4,createVNode:_createVNode$4,openBlock:_openBlock$5,createBlock:_createBlock$3} = await importShared('vue');


const {computed: computed$2} = await importShared('vue');



const _sfc_main$5 = {
  __name: 'RestartDialog',
  props: {
  modelValue: {
    type: Boolean,
    default: false,
  },
  restartTargets: {
    type: Array,
    default: () => [],
  },
  restartSourcePolicy: {
    type: String,
    default: 'reuse',
  },
  restartSourceOptions: {
    type: Array,
    default: () => [],
  },
  operation: {
    type: String,
    default: '',
  },
  operating: {
    type: Boolean,
    default: false,
  },
},
  emits: ['update:modelValue', 'update:restartSourcePolicy', 'confirm'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;

const dialog = computed$2({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
});

const sourcePolicy = computed$2({
  get: () => props.restartSourcePolicy,
  set: value => emit('update:restartSourcePolicy', value),
});

return (_ctx, _cache) => {
  const _component_VCardTitle = _resolveComponent$5("VCardTitle");
  const _component_VAlert = _resolveComponent$5("VAlert");
  const _component_VSelect = _resolveComponent$5("VSelect");
  const _component_VCardText = _resolveComponent$5("VCardText");
  const _component_VSpacer = _resolveComponent$5("VSpacer");
  const _component_VBtn = _resolveComponent$5("VBtn");
  const _component_VCardActions = _resolveComponent$5("VCardActions");
  const _component_VCard = _resolveComponent$5("VCard");
  const _component_VDialog = _resolveComponent$5("VDialog");

  return (_openBlock$5(), _createBlock$3(_component_VDialog, {
    modelValue: dialog.value,
    "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((dialog).value = $event)),
    "max-width": "520"
  }, {
    default: _withCtx$4(() => [
      _createVNode$4(_component_VCard, {
        class: "restart-dialog-card",
        rounded: "lg"
      }, {
        default: _withCtx$4(() => [
          _createVNode$4(_component_VCardTitle, null, {
            default: _withCtx$4(() => [...(_cache[4] || (_cache[4] = [
              _createTextVNode$4("重新生成 AI 字幕", -1)
            ]))]),
            _: 1
          }),
          _createVNode$4(_component_VCardText, null, {
            default: _withCtx$4(() => [
              _createVNode$4(_component_VAlert, {
                class: "mb-4",
                type: "info",
                variant: "tonal",
                density: "compact",
                text: `将重新提交 ${__props.restartTargets.length} 个任务；默认沿用原任务来源，并使用当前最新模型配置。`
              }, null, 8, ["text"]),
              _createVNode$4(_component_VSelect, {
                modelValue: sourcePolicy.value,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((sourcePolicy).value = $event)),
                items: __props.restartSourceOptions,
                label: "字幕来源",
                hint: "改选来源会写入来源变体后缀，如 .aiasr.srt 或 .aiembedded.srt",
                "persistent-hint": ""
              }, null, 8, ["modelValue", "items"])
            ]),
            _: 1
          }),
          _createVNode$4(_component_VCardActions, null, {
            default: _withCtx$4(() => [
              _createVNode$4(_component_VSpacer),
              _createVNode$4(_component_VBtn, {
                class: "mobile-touch-target",
                variant: "text",
                onClick: _cache[1] || (_cache[1] = $event => (dialog.value = false))
              }, {
                default: _withCtx$4(() => [...(_cache[5] || (_cache[5] = [
                  _createTextVNode$4("取消", -1)
                ]))]),
                _: 1
              }),
              _createVNode$4(_component_VBtn, {
                class: "mobile-touch-target",
                color: "primary",
                variant: "tonal",
                loading: __props.operation === 'restart',
                disabled: __props.operating || !__props.restartTargets.length,
                onClick: _cache[2] || (_cache[2] = $event => (emit('confirm')))
              }, {
                default: _withCtx$4(() => [...(_cache[6] || (_cache[6] = [
                  _createTextVNode$4(" 重新生成 ", -1)
                ]))]),
                _: 1
              }, 8, ["loading", "disabled"])
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["modelValue"]))
}
}

};
const RestartDialog = /*#__PURE__*/_export_sfc(_sfc_main$5, [['__scopeId',"data-v-3d14acbf"]]);

const {renderList:_renderList$1,Fragment:_Fragment$1,openBlock:_openBlock$4,createElementBlock:_createElementBlock$4,toDisplayString:_toDisplayString$3,createTextVNode:_createTextVNode$3,resolveComponent:_resolveComponent$4,withCtx:_withCtx$3,createBlock:_createBlock$2} = await importShared('vue');


const _hoisted_1$4 = { class: "summary-strip" };


const _sfc_main$4 = {
  __name: 'TaskStatusFilter',
  props: {
  statusChips: {
    type: Array,
    default: () => [],
  },
  statusFilter: {
    type: String,
    default: 'all',
  },
},
  emits: ['select'],
  setup(__props, { emit: __emit }) {



const emit = __emit;

return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent$4("VChip");

  return (_openBlock$4(), _createElementBlock$4("div", _hoisted_1$4, [
    (_openBlock$4(true), _createElementBlock$4(_Fragment$1, null, _renderList$1(__props.statusChips, (chip) => {
      return (_openBlock$4(), _createBlock$2(_component_VChip, {
        key: chip.value,
        size: "small",
        class: "filter-chip",
        variant: __props.statusFilter === chip.value ? 'flat' : 'tonal',
        color: chip.color || (__props.statusFilter === chip.value ? 'primary' : undefined),
        onClick: $event => (emit('select', chip.value))
      }, {
        default: _withCtx$3(() => [
          _createTextVNode$3(_toDisplayString$3(chip.label) + " " + _toDisplayString$3(chip.count), 1)
        ]),
        _: 2
      }, 1032, ["variant", "color", "onClick"]))
    }), 128))
  ]))
}
}

};
const TaskStatusFilter = /*#__PURE__*/_export_sfc(_sfc_main$4, [['__scopeId',"data-v-4ddb4746"]]);

const {resolveComponent:_resolveComponent$3,createVNode:_createVNode$3,toDisplayString:_toDisplayString$2,createElementVNode:_createElementVNode$3,createTextVNode:_createTextVNode$2,withCtx:_withCtx$2,openBlock:_openBlock$3,createElementBlock:_createElementBlock$3,createCommentVNode:_createCommentVNode$2,createBlock:_createBlock$1,normalizeClass:_normalizeClass$1} = await importShared('vue');


const _hoisted_1$3 = { class: "task-mobile-header" };
const _hoisted_2$3 = { class: "task-mobile-title-block" };
const _hoisted_3$2 = { class: "task-mobile-title" };
const _hoisted_4$2 = { class: "task-mobile-subline" };
const _hoisted_5$1 = { class: "task-mobile-time" };
const _hoisted_6$1 = {
  class: "task-mobile-summary",
  "aria-label": "任务摘要"
};
const _hoisted_7$1 = { class: "task-mobile-meta-row" };
const _hoisted_8$1 = { class: "task-mobile-meta-value" };
const _hoisted_9$1 = { class: "task-mobile-meta-row" };
const _hoisted_10$1 = { class: "task-mobile-meta-value" };
const _hoisted_11$1 = {
  key: 0,
  class: "task-mobile-message"
};
const _hoisted_12$1 = { class: "task-mobile-actions" };
const _hoisted_13$1 = {
  key: 0,
  class: "task-mobile-details",
  "aria-label": "任务详情"
};
const _hoisted_14 = {
  key: 0,
  class: "task-mobile-detail-block"
};
const _hoisted_15 = { class: "task-mobile-code" };
const _hoisted_16 = {
  key: 1,
  class: "task-mobile-detail-block"
};
const _hoisted_17 = { class: "task-mobile-detail-block" };
const _hoisted_18 = { class: "task-mobile-code" };
const _hoisted_19 = {
  key: 2,
  class: "task-mobile-danger"
};

const {computed: computed$1,ref} = await importShared('vue');



const _sfc_main$3 = {
  __name: 'TaskMobileCard',
  props: {
  task: {
    type: Object,
    required: true,
  },
  selected: {
    type: Boolean,
    default: false,
  },
  operating: {
    type: Boolean,
    default: false,
  },
  canCancel: {
    type: Boolean,
    default: false,
  },
  canRestart: {
    type: Boolean,
    default: false,
  },
  canDelete: {
    type: Boolean,
    default: false,
  },
},
  emits: ['toggle-task', 'cancel', 'restart', 'delete'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;
const expanded = ref(false);

const statusColor = computed$1(() => ({
  pending: 'info',
  in_progress: 'warning',
  completed: 'success',
  failed: 'error',
  cancelled: 'default',
  ignored: 'default',
  no_audio: 'default',
})[props.task?.status] || 'default');

const sourceText = computed$1(() => {
  const source = props.task?.resolved_source_label
    || props.task?.source_policy_label
    || props.task?.source_label
    || props.task?.source
    || '未标记来源';
  const asset = props.task?.source_asset_name || props.task?.source_subtitle_name || '';
  return asset ? `${source} · ${asset}` : source
});

const timeText = computed$1(() => props.task?.complete_time || props.task?.add_time || '-');
const outputText = computed$1(() => props.task?.output_name || '尚未生成输出文件');
const messageText = computed$1(() => props.task?.message || '');
const hasDetails = computed$1(() => Boolean(props.task?.video_file || messageText.value || outputText.value));

function toggleExpanded() {
  expanded.value = !expanded.value;
}

return (_ctx, _cache) => {
  const _component_VCheckbox = _resolveComponent$3("VCheckbox");
  const _component_VChip = _resolveComponent$3("VChip");
  const _component_VBtn = _resolveComponent$3("VBtn");

  return (_openBlock$3(), _createElementBlock$3("article", {
    class: _normalizeClass$1(["task-mobile-card", { selected: __props.selected }])
  }, [
    _createElementVNode$3("header", _hoisted_1$3, [
      _createVNode$3(_component_VCheckbox, {
        class: "task-mobile-check mobile-touch-target",
        "model-value": __props.selected,
        density: "compact",
        "hide-details": "",
        "aria-label": `选择 ${__props.task.video_name || '任务'}`,
        "onUpdate:modelValue": _cache[0] || (_cache[0] = value => emit('toggle-task', __props.task, value))
      }, null, 8, ["model-value", "aria-label"]),
      _createElementVNode$3("div", _hoisted_2$3, [
        _createElementVNode$3("div", _hoisted_3$2, _toDisplayString$2(__props.task.video_name || '未知视频'), 1),
        _createElementVNode$3("div", _hoisted_4$2, [
          _createVNode$3(_component_VChip, {
            class: "task-mobile-status",
            size: "x-small",
            variant: "tonal",
            color: statusColor.value
          }, {
            default: _withCtx$2(() => [
              _createTextVNode$2(_toDisplayString$2(__props.task.status_label || __props.task.status), 1)
            ]),
            _: 1
          }, 8, ["color"]),
          _createElementVNode$3("span", _hoisted_5$1, _toDisplayString$2(timeText.value), 1)
        ])
      ])
    ]),
    _createElementVNode$3("section", _hoisted_6$1, [
      _createElementVNode$3("div", _hoisted_7$1, [
        _cache[4] || (_cache[4] = _createElementVNode$3("span", { class: "task-mobile-meta-label" }, "来源", -1)),
        _createElementVNode$3("span", _hoisted_8$1, _toDisplayString$2(sourceText.value), 1)
      ]),
      _createElementVNode$3("div", _hoisted_9$1, [
        _cache[5] || (_cache[5] = _createElementVNode$3("span", { class: "task-mobile-meta-label" }, "输出", -1)),
        _createElementVNode$3("span", _hoisted_10$1, _toDisplayString$2(outputText.value), 1)
      ]),
      (messageText.value)
        ? (_openBlock$3(), _createElementBlock$3("p", _hoisted_11$1, _toDisplayString$2(messageText.value), 1))
        : _createCommentVNode$2("", true)
    ]),
    _createElementVNode$3("div", _hoisted_12$1, [
      _createVNode$3(_component_VBtn, {
        class: "task-primary-action mobile-touch-target",
        color: "primary",
        variant: "tonal",
        disabled: !__props.canRestart || __props.operating,
        onClick: _cache[1] || (_cache[1] = $event => (emit('restart', __props.task)))
      }, {
        default: _withCtx$2(() => [...(_cache[6] || (_cache[6] = [
          _createTextVNode$2(" 重新生成 ", -1)
        ]))]),
        _: 1
      }, 8, ["disabled"]),
      (__props.canCancel)
        ? (_openBlock$3(), _createBlock$1(_component_VBtn, {
            key: 0,
            class: "task-secondary-action mobile-touch-target",
            color: "warning",
            variant: "text",
            disabled: __props.operating,
            onClick: _cache[2] || (_cache[2] = $event => (emit('cancel', __props.task)))
          }, {
            default: _withCtx$2(() => [...(_cache[7] || (_cache[7] = [
              _createTextVNode$2(" 取消 ", -1)
            ]))]),
            _: 1
          }, 8, ["disabled"]))
        : _createCommentVNode$2("", true),
      (hasDetails.value)
        ? (_openBlock$3(), _createBlock$1(_component_VBtn, {
            key: 1,
            class: "task-detail-action mobile-touch-target",
            variant: "text",
            "aria-expanded": expanded.value,
            onClick: toggleExpanded
          }, {
            default: _withCtx$2(() => [
              _createTextVNode$2(_toDisplayString$2(expanded.value ? '收起' : '详情'), 1)
            ]),
            _: 1
          }, 8, ["aria-expanded"]))
        : _createCommentVNode$2("", true)
    ]),
    (expanded.value)
      ? (_openBlock$3(), _createElementBlock$3("section", _hoisted_13$1, [
          (__props.task.video_file)
            ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_14, [
                _cache[8] || (_cache[8] = _createElementVNode$3("span", { class: "task-mobile-detail-label" }, "视频路径", -1)),
                _createElementVNode$3("p", _hoisted_15, _toDisplayString$2(__props.task.video_file), 1)
              ]))
            : _createCommentVNode$2("", true),
          (messageText.value)
            ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_16, [
                _cache[9] || (_cache[9] = _createElementVNode$3("span", { class: "task-mobile-detail-label" }, "完整原因", -1)),
                _createElementVNode$3("p", null, _toDisplayString$2(messageText.value), 1)
              ]))
            : _createCommentVNode$2("", true),
          _createElementVNode$3("div", _hoisted_17, [
            _cache[10] || (_cache[10] = _createElementVNode$3("span", { class: "task-mobile-detail-label" }, "输出文件", -1)),
            _createElementVNode$3("p", _hoisted_18, _toDisplayString$2(outputText.value), 1)
          ]),
          (__props.canDelete)
            ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_19, [
                _createVNode$3(_component_VBtn, {
                  class: "task-danger-action mobile-touch-target",
                  color: "error",
                  variant: "tonal",
                  disabled: __props.operating,
                  onClick: _cache[3] || (_cache[3] = $event => (emit('delete', __props.task)))
                }, {
                  default: _withCtx$2(() => [...(_cache[11] || (_cache[11] = [
                    _createTextVNode$2(" 删除记录 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"])
              ]))
            : _createCommentVNode$2("", true)
        ]))
      : _createCommentVNode$2("", true)
  ], 2))
}
}

};
const TaskMobileCard = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-78968305"]]);

const {openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,createCommentVNode:_createCommentVNode$1,renderList:_renderList,Fragment:_Fragment,createVNode:_createVNode$2,resolveComponent:_resolveComponent$2,toDisplayString:_toDisplayString$1,createElementVNode:_createElementVNode$2,createTextVNode:_createTextVNode$1,withCtx:_withCtx$1,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1$2 = {
  key: 0,
  class: "empty-state"
};
const _hoisted_2$2 = {
  key: 1,
  class: "empty-state"
};
const _hoisted_3$1 = {
  key: 2,
  class: "empty-state"
};
const _hoisted_4$1 = {
  key: 3,
  class: "task-list"
};
const _hoisted_5 = { class: "task-main" };
const _hoisted_6 = { class: "task-title" };
const _hoisted_7 = { class: "task-path" };
const _hoisted_8 = { key: 0 };
const _hoisted_9 = { class: "task-meta" };
const _hoisted_10 = { key: 0 };
const _hoisted_11 = { key: 1 };
const _hoisted_12 = { key: 2 };
const _hoisted_13 = { class: "task-actions" };


const _sfc_main$2 = {
  __name: 'TaskTable',
  props: {
  loading: {
    type: Boolean,
    default: false,
  },
  tasks: {
    type: Array,
    default: () => [],
  },
  visibleTasks: {
    type: Array,
    default: () => [],
  },
  selectedTaskIds: {
    type: Array,
    default: () => [],
  },
  operating: {
    type: Boolean,
    default: false,
  },
  canCancelTask: {
    type: Function,
    default: () => false,
  },
  canRestartTask: {
    type: Function,
    default: () => false,
  },
  canDeleteTask: {
    type: Function,
    default: () => false,
  },
},
  emits: ['toggle-task', 'cancel', 'restart', 'delete'],
  setup(__props, { emit: __emit }) {



const emit = __emit;

function statusColor(task) {
  return {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    failed: 'error',
    cancelled: 'default',
    ignored: 'default',
    no_audio: 'default',
  }[task?.status] || 'default'
}

function pathParts(path) {
  const text = String(path || '');
  const match = text.match(/^(.*?[\\/])((?:Season|S\d{1,2})[^\\/]*(?:[\\/].*)?)$/i);
  if (match) return [match[1], match[2]]
  if (text.length > 72) return [text.slice(0, 72), text.slice(72)]
  return [text]
}

function sourceText(task) {
  const source = task?.resolved_source_label || task?.source_policy_label || task?.source_label || task?.source || '';
  const asset = task?.source_asset_name || task?.source_subtitle_name || '';
  return asset ? `${source} · ${asset}` : source
}

return (_ctx, _cache) => {
  const _component_VCheckbox = _resolveComponent$2("VCheckbox");
  const _component_VChip = _resolveComponent$2("VChip");
  const _component_VBtn = _resolveComponent$2("VBtn");

  return (__props.loading && !__props.tasks.length)
    ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_1$2, "正在读取任务..."))
    : (!__props.tasks.length)
      ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_2$2, "暂无 AI 字幕任务"))
      : (!__props.visibleTasks.length)
        ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_3$1, "当前筛选暂无任务"))
        : (_openBlock$2(), _createElementBlock$2("div", _hoisted_4$1, [
            (_openBlock$2(true), _createElementBlock$2(_Fragment, null, _renderList(__props.visibleTasks, (task) => {
              return (_openBlock$2(), _createElementBlock$2("div", {
                key: task.task_id,
                class: _normalizeClass(["task-row", { selected: __props.selectedTaskIds.includes(task.task_id) }])
              }, [
                _createVNode$2(TaskMobileCard, {
                  task: task,
                  selected: __props.selectedTaskIds.includes(task.task_id),
                  operating: __props.operating,
                  "can-cancel": __props.canCancelTask(task),
                  "can-restart": __props.canRestartTask(task),
                  "can-delete": __props.canDeleteTask(task),
                  onToggleTask: _cache[0] || (_cache[0] = (item, value) => emit('toggle-task', item, value)),
                  onCancel: _cache[1] || (_cache[1] = item => emit('cancel', item)),
                  onRestart: _cache[2] || (_cache[2] = item => emit('restart', item)),
                  onDelete: _cache[3] || (_cache[3] = item => emit('delete', item))
                }, null, 8, ["task", "selected", "operating", "can-cancel", "can-restart", "can-delete"]),
                _createVNode$2(_component_VCheckbox, {
                  class: "task-desktop-check",
                  "model-value": __props.selectedTaskIds.includes(task.task_id),
                  density: "compact",
                  "hide-details": "",
                  "onUpdate:modelValue": value => emit('toggle-task', task, value)
                }, null, 8, ["model-value", "onUpdate:modelValue"]),
                _createElementVNode$2("div", _hoisted_5, [
                  _createElementVNode$2("div", _hoisted_6, [
                    _createElementVNode$2("strong", null, _toDisplayString$1(task.video_name || '未知视频'), 1),
                    _createVNode$2(_component_VChip, {
                      size: "x-small",
                      variant: "tonal",
                      color: statusColor(task)
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(task.status_label || task.status), 1)
                      ]),
                      _: 2
                    }, 1032, ["color"])
                  ]),
                  _createElementVNode$2("div", _hoisted_7, [
                    (_openBlock$2(true), _createElementBlock$2(_Fragment, null, _renderList(pathParts(task.video_file), (part, index) => {
                      return (_openBlock$2(), _createElementBlock$2(_Fragment, {
                        key: `${task.task_id}-${index}`
                      }, [
                        _createElementVNode$2("span", null, _toDisplayString$1(part), 1),
                        (index === 0 && pathParts(task.video_file).length > 1)
                          ? (_openBlock$2(), _createElementBlock$2("br", _hoisted_8))
                          : _createCommentVNode$1("", true)
                      ], 64))
                    }), 128))
                  ]),
                  _createElementVNode$2("div", _hoisted_9, [
                    _createElementVNode$2("span", null, _toDisplayString$1(task.source_label || task.source), 1),
                    (sourceText(task))
                      ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_10, _toDisplayString$1(sourceText(task)), 1))
                      : _createCommentVNode$1("", true),
                    (task.output_name)
                      ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_11, "输出：" + _toDisplayString$1(task.output_name), 1))
                      : _createCommentVNode$1("", true),
                    _createElementVNode$2("span", null, _toDisplayString$1(task.add_time || '-'), 1),
                    _createElementVNode$2("span", null, _toDisplayString$1(task.complete_time || '-'), 1),
                    (task.message)
                      ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_12, _toDisplayString$1(task.message), 1))
                      : _createCommentVNode$1("", true)
                  ])
                ]),
                _createElementVNode$2("div", _hoisted_13, [
                  _createVNode$2(_component_VBtn, {
                    class: "mobile-touch-target",
                    size: "small",
                    color: "warning",
                    variant: "tonal",
                    disabled: !__props.canCancelTask(task) || __props.operating,
                    onClick: $event => (emit('cancel', task))
                  }, {
                    default: _withCtx$1(() => [...(_cache[4] || (_cache[4] = [
                      _createTextVNode$1(" 取消 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "onClick"]),
                  _createVNode$2(_component_VBtn, {
                    class: "mobile-touch-target",
                    size: "small",
                    color: "primary",
                    variant: "tonal",
                    disabled: !__props.canRestartTask(task) || __props.operating,
                    onClick: $event => (emit('restart', task))
                  }, {
                    default: _withCtx$1(() => [...(_cache[5] || (_cache[5] = [
                      _createTextVNode$1(" 重新生成 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "onClick"]),
                  _createVNode$2(_component_VBtn, {
                    class: "mobile-touch-target",
                    size: "small",
                    color: "error",
                    variant: "tonal",
                    disabled: !__props.canDeleteTask(task) || __props.operating,
                    onClick: $event => (emit('delete', task))
                  }, {
                    default: _withCtx$1(() => [...(_cache[6] || (_cache[6] = [
                      _createTextVNode$1(" 删除 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "onClick"])
                ])
              ], 2))
            }), 128))
          ]))
}
}

};
const TaskTable = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-a1752aba"]]);

const {createElementVNode:_createElementVNode$1,toDisplayString:_toDisplayString,resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1} = await importShared('vue');


const _hoisted_1$1 = { class: "autosub-toolbar" };
const _hoisted_2$1 = { class: "toolbar-copy" };
const _hoisted_3 = { class: "toolbar-subtitle" };
const _hoisted_4 = { class: "toolbar-actions" };


const _sfc_main$1 = {
  __name: 'TaskToolbar',
  props: {
  status: {
    type: Object,
    default: () => ({}),
  },
  sortOrder: {
    type: String,
    default: 'desc',
  },
  visibleTasks: {
    type: Array,
    default: () => [],
  },
  allVisibleSelected: {
    type: Boolean,
    default: false,
  },
  cancellableSelected: {
    type: Array,
    default: () => [],
  },
  restartableSelected: {
    type: Array,
    default: () => [],
  },
  deletableSelected: {
    type: Array,
    default: () => [],
  },
  operating: {
    type: Boolean,
    default: false,
  },
  operation: {
    type: String,
    default: '',
  },
  loading: {
    type: Boolean,
    default: false,
  },
},
  emits: [
  'update:sortOrder',
  'toggle-all',
  'cancel-selected',
  'restart-selected',
  'delete-selected',
  'refresh',
  'close',
],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;

function toggleSortOrder() {
  emit('update:sortOrder', props.sortOrder === 'desc' ? 'asc' : 'desc');
}

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent$1("VBtn");

  return (_openBlock$1(), _createElementBlock$1("header", _hoisted_1$1, [
    _createElementVNode$1("div", _hoisted_2$1, [
      _cache[7] || (_cache[7] = _createElementVNode$1("div", { class: "toolbar-title" }, "AI字幕生成(联动版)", -1)),
      _createElementVNode$1("div", _hoisted_3, _toDisplayString(__props.status.message || '查看任务数据'), 1)
    ]),
    _createElementVNode$1("div", _hoisted_4, [
      _createVNode$1(_component_VBtn, {
        class: "mobile-refresh-action mobile-touch-target",
        "aria-label": "刷新任务",
        icon: "mdi-refresh",
        variant: "text",
        loading: __props.loading,
        onClick: _cache[0] || (_cache[0] = $event => (emit('refresh')))
      }, null, 8, ["loading"]),
      _createVNode$1(_component_VBtn, {
        class: "sort-action mobile-touch-target",
        variant: "tonal",
        "prepend-icon": __props.sortOrder === 'desc' ? 'mdi-sort-clock-descending' : 'mdi-sort-clock-ascending',
        onClick: toggleSortOrder
      }, {
        default: _withCtx(() => [
          _createTextVNode(_toDisplayString(__props.sortOrder === 'desc' ? '最新在前' : '最早在前'), 1)
        ]),
        _: 1
      }, 8, ["prepend-icon"]),
      _createVNode$1(_component_VBtn, {
        class: "select-action mobile-touch-target",
        variant: "tonal",
        "prepend-icon": "mdi-checkbox-multiple-marked-outline",
        disabled: !__props.visibleTasks.length,
        onClick: _cache[1] || (_cache[1] = $event => (emit('toggle-all')))
      }, {
        default: _withCtx(() => [
          _createTextVNode(_toDisplayString(__props.allVisibleSelected ? '取消全选' : '全选'), 1)
        ]),
        _: 1
      }, 8, ["disabled"]),
      _createVNode$1(_component_VBtn, {
        class: "desktop-batch-action mobile-touch-target",
        color: "warning",
        variant: "tonal",
        "prepend-icon": "mdi-cancel",
        disabled: !__props.cancellableSelected.length || __props.operating,
        loading: __props.operation === 'cancel',
        onClick: _cache[2] || (_cache[2] = $event => (emit('cancel-selected')))
      }, {
        default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
          _createTextVNode(" 批量取消 ", -1)
        ]))]),
        _: 1
      }, 8, ["disabled", "loading"]),
      _createVNode$1(_component_VBtn, {
        class: "desktop-batch-action mobile-touch-target",
        color: "primary",
        variant: "tonal",
        "prepend-icon": "mdi-restart",
        disabled: !__props.restartableSelected.length || __props.operating,
        loading: __props.operation === 'restart',
        onClick: _cache[3] || (_cache[3] = $event => (emit('restart-selected')))
      }, {
        default: _withCtx(() => [...(_cache[9] || (_cache[9] = [
          _createTextVNode(" 批量重新生成 ", -1)
        ]))]),
        _: 1
      }, 8, ["disabled", "loading"]),
      _createVNode$1(_component_VBtn, {
        class: "desktop-batch-action mobile-touch-target",
        color: "error",
        variant: "tonal",
        "prepend-icon": "mdi-delete-outline",
        disabled: !__props.deletableSelected.length || __props.operating,
        loading: __props.operation === 'delete',
        onClick: _cache[4] || (_cache[4] = $event => (emit('delete-selected')))
      }, {
        default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
          _createTextVNode(" 批量删除 ", -1)
        ]))]),
        _: 1
      }, 8, ["disabled", "loading"]),
      _createVNode$1(_component_VBtn, {
        class: "desktop-refresh-action mobile-touch-target",
        "aria-label": "刷新任务",
        icon: "mdi-refresh",
        variant: "text",
        loading: __props.loading,
        onClick: _cache[5] || (_cache[5] = $event => (emit('refresh')))
      }, null, 8, ["loading"]),
      _createVNode$1(_component_VBtn, {
        class: "close-action mobile-touch-target",
        "aria-label": "关闭 AI字幕生成",
        icon: "mdi-close",
        variant: "text",
        onClick: _cache[6] || (_cache[6] = $event => (emit('close')))
      })
    ])
  ]))
}
}

};
const TaskToolbar = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-c5fef992"]]);

const {unref:_unref,isRef:_isRef,createVNode:_createVNode,resolveComponent:_resolveComponent,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "autosub-page" };
const _hoisted_2 = { class: "autosub-content" };

const {computed,onMounted} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: {
  api: {
    type: Object,
    default: () => ({}),
  },
  pluginId: {
    type: String,
    default: 'AutoSubv3',
  },
},
  emits: ['close'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;
const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoSubv3'}`);

const {
  loading,
  operating,
  operation,
  sortOrder,
  statusFilter,
  selectedTaskIds,
  error,
  message,
  status,
  tasks,
  restartDialog,
  restartTargets,
  restartSourcePolicy,
  restartSourceOptions,
  visibleTasks,
  allVisibleSelected,
  cancellableSelected,
  restartableSelected,
  deletableSelected,
  statusChips,
  loadTasks,
  cancelTasks,
  restartTasks,
  confirmRestartTasks,
  deleteTasks,
  toggleTask,
  toggleAll,
  canCancelTask,
  canRestartTask,
  canDeleteTask,
  setStatusFilter,
} = useAutoSubTasks({
  api: () => props.api,
  pluginBase,
});

onMounted(loadTasks);

return (_ctx, _cache) => {
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VAlert = _resolveComponent("VAlert");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(TaskToolbar, {
      "sort-order": _unref(sortOrder),
      "onUpdate:sortOrder": _cache[0] || (_cache[0] = $event => (_isRef(sortOrder) ? (sortOrder).value = $event : null)),
      status: _unref(status),
      "visible-tasks": _unref(visibleTasks),
      "all-visible-selected": _unref(allVisibleSelected),
      "cancellable-selected": _unref(cancellableSelected),
      "restartable-selected": _unref(restartableSelected),
      "deletable-selected": _unref(deletableSelected),
      operating: _unref(operating),
      operation: _unref(operation),
      loading: _unref(loading),
      onToggleAll: _unref(toggleAll),
      onCancelSelected: _cache[1] || (_cache[1] = $event => (_unref(cancelTasks)(_unref(cancellableSelected)))),
      onRestartSelected: _cache[2] || (_cache[2] = $event => (_unref(restartTasks)(_unref(restartableSelected)))),
      onDeleteSelected: _cache[3] || (_cache[3] = $event => (_unref(deleteTasks)(_unref(deletableSelected)))),
      onRefresh: _unref(loadTasks),
      onClose: _cache[4] || (_cache[4] = $event => (emit('close')))
    }, null, 8, ["sort-order", "status", "visible-tasks", "all-visible-selected", "cancellable-selected", "restartable-selected", "deletable-selected", "operating", "operation", "loading", "onToggleAll", "onRefresh"]),
    _createVNode(_component_VDivider),
    _createElementVNode("main", _hoisted_2, [
      (_unref(error))
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 0,
            class: "mb-4",
            type: "error",
            variant: "tonal",
            text: _unref(error)
          }, null, 8, ["text"]))
        : _createCommentVNode("", true),
      (_unref(message))
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 1,
            class: "mb-4",
            type: "success",
            variant: "tonal",
            text: _unref(message)
          }, null, 8, ["text"]))
        : _createCommentVNode("", true),
      _createVNode(TaskStatusFilter, {
        "status-chips": _unref(statusChips),
        "status-filter": _unref(statusFilter),
        onSelect: _unref(setStatusFilter)
      }, null, 8, ["status-chips", "status-filter", "onSelect"]),
      _createVNode(TaskTable, {
        loading: _unref(loading),
        tasks: _unref(tasks),
        "visible-tasks": _unref(visibleTasks),
        "selected-task-ids": _unref(selectedTaskIds),
        operating: _unref(operating),
        "can-cancel-task": _unref(canCancelTask),
        "can-restart-task": _unref(canRestartTask),
        "can-delete-task": _unref(canDeleteTask),
        onToggleTask: _unref(toggleTask),
        onCancel: _cache[5] || (_cache[5] = task => _unref(cancelTasks)([task])),
        onRestart: _cache[6] || (_cache[6] = task => _unref(restartTasks)([task])),
        onDelete: _cache[7] || (_cache[7] = task => _unref(deleteTasks)([task]))
      }, null, 8, ["loading", "tasks", "visible-tasks", "selected-task-ids", "operating", "can-cancel-task", "can-restart-task", "can-delete-task", "onToggleTask"]),
      _createVNode(MobileBatchActionBar, {
        "selected-count": _unref(selectedTaskIds).length,
        "cancellable-selected": _unref(cancellableSelected),
        "restartable-selected": _unref(restartableSelected),
        "deletable-selected": _unref(deletableSelected),
        operating: _unref(operating),
        operation: _unref(operation),
        onCancelSelected: _cache[8] || (_cache[8] = $event => (_unref(cancelTasks)(_unref(cancellableSelected)))),
        onRestartSelected: _cache[9] || (_cache[9] = $event => (_unref(restartTasks)(_unref(restartableSelected)))),
        onDeleteSelected: _cache[10] || (_cache[10] = $event => (_unref(deleteTasks)(_unref(deletableSelected))))
      }, null, 8, ["selected-count", "cancellable-selected", "restartable-selected", "deletable-selected", "operating", "operation"])
    ]),
    _createVNode(RestartDialog, {
      modelValue: _unref(restartDialog),
      "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => (_isRef(restartDialog) ? (restartDialog).value = $event : null)),
      "restart-source-policy": _unref(restartSourcePolicy),
      "onUpdate:restartSourcePolicy": _cache[12] || (_cache[12] = $event => (_isRef(restartSourcePolicy) ? (restartSourcePolicy).value = $event : null)),
      "restart-targets": _unref(restartTargets),
      "restart-source-options": _unref(restartSourceOptions),
      operation: _unref(operation),
      operating: _unref(operating),
      onConfirm: _unref(confirmRestartTasks)
    }, null, 8, ["modelValue", "restart-source-policy", "restart-targets", "restart-source-options", "operation", "operating", "onConfirm"])
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-f1e0c84f"]]);

export { Page as default };
