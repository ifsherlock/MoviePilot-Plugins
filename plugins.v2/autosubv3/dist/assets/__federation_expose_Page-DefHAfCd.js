import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,resolveComponent:_resolveComponent,createVNode:_createVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "autosub-page" };
const _hoisted_2 = { class: "toolbar-subtitle ms-3" };
const _hoisted_3 = { class: "autosub-content" };
const _hoisted_4 = { class: "summary-strip" };
const _hoisted_5 = {
  key: 2,
  class: "empty-state"
};
const _hoisted_6 = {
  key: 3,
  class: "empty-state"
};
const _hoisted_7 = {
  key: 4,
  class: "empty-state"
};
const _hoisted_8 = {
  key: 5,
  class: "task-list"
};
const _hoisted_9 = { class: "task-main" };
const _hoisted_10 = { class: "task-title" };
const _hoisted_11 = { class: "task-path" };
const _hoisted_12 = { key: 0 };
const _hoisted_13 = { class: "task-meta" };
const _hoisted_14 = { key: 0 };
const _hoisted_15 = { class: "task-actions" };

const {computed,onMounted,ref} = await importShared('vue');



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
const loading = ref(false);
const operating = ref(false);
const sortOrder = ref('desc');
const statusFilter = ref('all');
const selectedTaskIds = ref([]);
const error = ref('');
const message = ref('');
const status = ref({});
const tasks = ref([]);

const sortedTasks = computed(() => {
  const items = [...tasks.value];
  items.sort((a, b) => {
    const left = new Date(a.add_time || 0).getTime();
    const right = new Date(b.add_time || 0).getTime();
    return sortOrder.value === 'desc' ? right - left : left - right
  });
  return items
});
const visibleTasks = computed(() => {
  if (statusFilter.value === 'all') return sortedTasks.value
  return sortedTasks.value.filter(task => task.status === statusFilter.value)
});
const visibleTaskIds = computed(() => new Set(visibleTasks.value.map(task => task.task_id)));
const allVisibleSelected = computed(() => (
  Boolean(visibleTasks.value.length)
  && visibleTasks.value.every(task => selectedTaskIds.value.includes(task.task_id))
));
const selectedTasks = computed(() => {
  const picked = new Set(selectedTaskIds.value);
  return visibleTasks.value.filter(task => picked.has(task.task_id))
});
const cancellableSelected = computed(() => selectedTasks.value.filter(canCancelTask));
const restartableSelected = computed(() => selectedTasks.value.filter(canRestartTask));
const statusChips = computed(() => [
  { value: 'all', label: '总数', count: tasks.value.length },
  { value: 'pending', label: '等待', count: status.value.counts?.pending || 0, color: 'info' },
  { value: 'in_progress', label: '处理中', count: status.value.counts?.in_progress || 0, color: 'warning' },
  { value: 'completed', label: '完成', count: status.value.counts?.completed || 0, color: 'success' },
  { value: 'failed', label: '失败', count: status.value.counts?.failed || 0, color: 'error' },
  { value: 'cancelled', label: '已取消', count: status.value.counts?.cancelled || 0 },
]);

function unwrapResponse(response) {
  return response?.data?.data || response?.data || response || {}
}

function errorMessage(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback
}

async function loadTasks() {
  loading.value = true;
  error.value = '';
  try {
    const response = await props.api.get(`${pluginBase.value}/tasks?limit=1000`);
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
  error.value = '';
  message.value = '';
  try {
    const response = await props.api.post(`${pluginBase.value}/cancel`, {
      task_ids: picked.map(task => task.task_id),
    });
    message.value = response?.message || `已取消 ${picked.length} 个任务`;
    await loadTasks();
  } catch (err) {
    error.value = errorMessage(err, '取消 AI 字幕任务失败');
  } finally {
    operating.value = false;
  }
}

async function restartTasks(inputTasks) {
  const picked = (inputTasks || []).filter(canRestartTask);
  if (!picked.length || operating.value) return
  operating.value = true;
  error.value = '';
  message.value = '';
  try {
    const groups = picked.reduce((acc, task) => {
      const source = task.source || 'manual';
      acc[source] = acc[source] || [];
      acc[source].push(task.video_file);
      return acc
    }, {});
    const responses = [];
    for (const [source, paths] of Object.entries(groups)) {
      responses.push(await props.api.post(`${pluginBase.value}/submit`, { source, paths }));
    }
    message.value = responses.length === 1
      ? responses[0]?.message || `已重新提交 ${picked.length} 个任务`
      : `已按来源重新提交 ${picked.length} 个任务`;
    await loadTasks();
  } catch (err) {
    error.value = errorMessage(err, '重启 AI 字幕任务失败');
  } finally {
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

function canCancelTask(task) {
  return Boolean(task?.active || ['pending', 'in_progress'].includes(task?.status))
}

function canRestartTask(task) {
  return Boolean(task?.video_file && ['cancelled', 'failed', 'ignored', 'no_audio'].includes(task?.status))
}

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

function setStatusFilter(value) {
  statusFilter.value = value;
  const visibleIds = new Set(visibleTasks.value.map(task => task.task_id));
  selectedTaskIds.value = selectedTaskIds.value.filter(id => visibleIds.has(id));
}

function pathParts(path) {
  const text = String(path || '');
  const match = text.match(/^(.*?[\\/])((?:Season|S\d{1,2})[^\\/]*(?:[\\/].*)?)$/i);
  if (match) return [match[1], match[2]]
  if (text.length > 72) return [text.slice(0, 72), text.slice(72)]
  return [text]
}

onMounted(loadTasks);

return (_ctx, _cache) => {
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCheckbox = _resolveComponent("VCheckbox");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      color: "transparent",
      class: "autosub-toolbar"
    }, {
      default: _withCtx(() => [
        _createElementVNode("div", null, [
          _cache[4] || (_cache[4] = _createElementVNode("div", { class: "text-h6 ms-3" }, "AI字幕生成(联动版)", -1)),
          _createElementVNode("div", _hoisted_2, _toDisplayString(status.value.message || '查看任务数据'), 1)
        ]),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          variant: "tonal",
          "prepend-icon": sortOrder.value === 'desc' ? 'mdi-sort-clock-descending' : 'mdi-sort-clock-ascending',
          onClick: _cache[0] || (_cache[0] = $event => (sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'))
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(sortOrder.value === 'desc' ? '最新在前' : '最早在前'), 1)
          ]),
          _: 1
        }, 8, ["prepend-icon"]),
        _createVNode(_component_VBtn, {
          variant: "tonal",
          "prepend-icon": "mdi-checkbox-multiple-marked-outline",
          disabled: !visibleTasks.value.length,
          onClick: toggleAll
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(allVisibleSelected.value ? '取消全选' : '全选'), 1)
          ]),
          _: 1
        }, 8, ["disabled"]),
        _createVNode(_component_VBtn, {
          color: "warning",
          variant: "tonal",
          "prepend-icon": "mdi-cancel",
          disabled: !cancellableSelected.value.length || operating.value,
          loading: operating.value && Boolean(cancellableSelected.value.length),
          onClick: _cache[1] || (_cache[1] = $event => (cancelTasks(cancellableSelected.value)))
        }, {
          default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
            _createTextVNode(" 批量取消 ", -1)
          ]))]),
          _: 1
        }, 8, ["disabled", "loading"]),
        _createVNode(_component_VBtn, {
          color: "primary",
          variant: "tonal",
          "prepend-icon": "mdi-restart",
          disabled: !restartableSelected.value.length || operating.value,
          loading: operating.value && Boolean(restartableSelected.value.length),
          onClick: _cache[2] || (_cache[2] = $event => (restartTasks(restartableSelected.value)))
        }, {
          default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
            _createTextVNode(" 批量重启 ", -1)
          ]))]),
          _: 1
        }, 8, ["disabled", "loading"]),
        _createVNode(_component_VBtn, {
          icon: "mdi-refresh",
          variant: "text",
          loading: loading.value,
          onClick: loadTasks
        }, null, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          icon: "mdi-close",
          variant: "text",
          onClick: _cache[3] || (_cache[3] = $event => (emit('close')))
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider),
    _createElementVNode("main", _hoisted_3, [
      (error.value)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 0,
            class: "mb-4",
            type: "error",
            variant: "tonal",
            text: error.value
          }, null, 8, ["text"]))
        : _createCommentVNode("", true),
      (message.value)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 1,
            class: "mb-4",
            type: "success",
            variant: "tonal",
            text: message.value
          }, null, 8, ["text"]))
        : _createCommentVNode("", true),
      _createElementVNode("div", _hoisted_4, [
        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(statusChips.value, (chip) => {
          return (_openBlock(), _createBlock(_component_VChip, {
            key: chip.value,
            size: "small",
            class: "filter-chip",
            variant: statusFilter.value === chip.value ? 'flat' : 'tonal',
            color: chip.color || (statusFilter.value === chip.value ? 'primary' : undefined),
            onClick: $event => (setStatusFilter(chip.value))
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(chip.label) + " " + _toDisplayString(chip.count), 1)
            ]),
            _: 2
          }, 1032, ["variant", "color", "onClick"]))
        }), 128))
      ]),
      (loading.value && !tasks.value.length)
        ? (_openBlock(), _createElementBlock("div", _hoisted_5, "正在读取任务..."))
        : (!tasks.value.length)
          ? (_openBlock(), _createElementBlock("div", _hoisted_6, "暂无 AI 字幕任务"))
          : (!visibleTasks.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_7, "当前筛选暂无任务"))
            : (_openBlock(), _createElementBlock("div", _hoisted_8, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(visibleTasks.value, (task) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: task.task_id,
                    class: _normalizeClass(["task-row", { selected: selectedTaskIds.value.includes(task.task_id) }])
                  }, [
                    _createVNode(_component_VCheckbox, {
                      "model-value": selectedTaskIds.value.includes(task.task_id),
                      density: "compact",
                      "hide-details": "",
                      "onUpdate:modelValue": value => toggleTask(task, value)
                    }, null, 8, ["model-value", "onUpdate:modelValue"]),
                    _createElementVNode("div", _hoisted_9, [
                      _createElementVNode("div", _hoisted_10, [
                        _createElementVNode("strong", null, _toDisplayString(task.video_name || '未知视频'), 1),
                        _createVNode(_component_VChip, {
                          size: "x-small",
                          variant: "tonal",
                          color: statusColor(task)
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(task.status_label || task.status), 1)
                          ]),
                          _: 2
                        }, 1032, ["color"])
                      ]),
                      _createElementVNode("div", _hoisted_11, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(pathParts(task.video_file), (part, index) => {
                          return (_openBlock(), _createElementBlock(_Fragment, {
                            key: `${task.task_id}-${index}`
                          }, [
                            _createElementVNode("span", null, _toDisplayString(part), 1),
                            (index === 0 && pathParts(task.video_file).length > 1)
                              ? (_openBlock(), _createElementBlock("br", _hoisted_12))
                              : _createCommentVNode("", true)
                          ], 64))
                        }), 128))
                      ]),
                      _createElementVNode("div", _hoisted_13, [
                        _createElementVNode("span", null, _toDisplayString(task.source_label || task.source), 1),
                        _createElementVNode("span", null, _toDisplayString(task.add_time || '-'), 1),
                        _createElementVNode("span", null, _toDisplayString(task.complete_time || '-'), 1),
                        (task.message)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_14, _toDisplayString(task.message), 1))
                          : _createCommentVNode("", true)
                      ])
                    ]),
                    _createElementVNode("div", _hoisted_15, [
                      _createVNode(_component_VBtn, {
                        size: "small",
                        color: "warning",
                        variant: "tonal",
                        disabled: !canCancelTask(task) || operating.value,
                        onClick: $event => (cancelTasks([task]))
                      }, {
                        default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                          _createTextVNode(" 取消 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled", "onClick"]),
                      _createVNode(_component_VBtn, {
                        size: "small",
                        color: "primary",
                        variant: "tonal",
                        disabled: !canRestartTask(task) || operating.value,
                        onClick: $event => (restartTasks([task]))
                      }, {
                        default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
                          _createTextVNode(" 重启 ", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled", "onClick"])
                    ])
                  ], 2))
                }), 128))
              ]))
    ])
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-79366bba"]]);

export { Page as default };
