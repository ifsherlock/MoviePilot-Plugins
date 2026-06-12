import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "autosub-config" };
const _hoisted_2 = { class: "config-shell" };
const _hoisted_3 = { class: "config-section" };
const _hoisted_4 = { class: "config-section" };
const _hoisted_5 = { class: "config-section" };
const _hoisted_6 = { class: "config-section" };
const _hoisted_7 = { class: "config-section" };

const {reactive,ref,watch} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
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
  context_window: 5,
  max_retries: 3,
  enable_merge: false,
  subtitle_output_mode: 'bilingual',
  enable_batch: true,
  batch_size: 20,
  parallel_workers: 10,
};

function normalizeInitialConfig(value = {}) {
  const merged = { ...defaultConfig, ...(value || {}) };
  merged.generation_mode = merged.generation_mode === 'fallback' ? 'fallback' : 'monitor';
  return merged
}

const config = reactive(normalizeInitialConfig(props.initialConfig));
const saving = ref(false);
const error = ref('');

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

function save() {
  saving.value = true;
  error.value = '';
  try {
    emit('save', { ...config });
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
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextField = _resolveComponent("VTextField");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      density: "comfortable",
      color: "transparent"
    }, {
      default: _withCtx(() => [
        _cache[33] || (_cache[33] = _createElementVNode("div", { class: "text-h6 ms-3" }, "AI字幕生成配置", -1)),
        _createVNode(_component_VSpacer),
        _createVNode(_component_VBtn, {
          variant: "text",
          "prepend-icon": "mdi-format-list-bulleted",
          onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
        }, {
          default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
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
          default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
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
      _createElementVNode("section", _hoisted_3, [
        _cache[34] || (_cache[34] = _createElementVNode("div", { class: "section-title" }, "基础设置", -1)),
        _createVNode(_component_VRow, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCol, {
              cols: "12",
              md: "6"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VSwitch, {
                  modelValue: config.generation_mode,
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((config.generation_mode) = $event)),
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
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((config.enabled) = $event)),
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
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((config.send_notify) = $event)),
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
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((config.clear_history) = $event)),
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
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((config.process_new_only) = $event)),
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
                  "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((config.run_now) = $event)),
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
                  "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((config.translate_zh) = $event)),
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
                  "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((config.skip_chinese) = $event)),
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
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((config.enable_asr) = $event)),
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
        _cache[35] || (_cache[35] = _createElementVNode("div", { class: "section-title" }, "路径", -1)),
        _createVNode(_component_VRow, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCol, { cols: "12" }, {
              default: _withCtx(() => [
                _createVNode(_component_VTextarea, {
                  modelValue: config.path_whitelist,
                  "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((config.path_whitelist) = $event)),
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
                  "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((config.path_list) = $event)),
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
      ]),
      _createElementVNode("section", _hoisted_5, [
        _cache[36] || (_cache[36] = _createElementVNode("div", { class: "section-title" }, "Whisper 与输出", -1)),
        _createVNode(_component_VRow, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCol, {
              cols: "12",
              md: "6"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VSelect, {
                  modelValue: config.faster_whisper_model,
                  "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((config.faster_whisper_model) = $event)),
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
                  "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((config.subtitle_output_mode) = $event)),
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
                  "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((config.max_segment_duration) = $event)),
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
                  "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((config.max_segment_chars) = $event)),
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
                  "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((config.file_size) = $event)),
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
                  "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((config.translate_preference) = $event)),
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
                  "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((config.auto_detect_language) = $event)),
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
                  "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((config.proxy) = $event)),
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
        _cache[37] || (_cache[37] = _createElementVNode("div", { class: "section-title" }, "翻译参数", -1)),
        _createVNode(_component_VRow, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCol, {
              cols: "12",
              md: "4"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VTextField, {
                  modelValue: config.context_window,
                  "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((config.context_window) = $event)),
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
                  "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((config.max_retries) = $event)),
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
                  "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((config.enable_batch) = $event)),
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
                  "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((config.batch_size) = $event)),
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
                  "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((config.parallel_workers) = $event)),
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
      _createElementVNode("section", _hoisted_7, [
        _cache[38] || (_cache[38] = _createElementVNode("div", { class: "section-title" }, "API 配置", -1)),
        _createVNode(_component_VRow, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCol, {
              cols: "12",
              md: "6"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VSwitch, {
                  modelValue: config.openai_proxy,
                  "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((config.openai_proxy) = $event)),
                  label: "使用代理服务器",
                  "hide-details": ""
                }, null, 8, ["modelValue"])
              ]),
              _: 1
            }),
            _createVNode(_component_VCol, {
              cols: "12",
              md: "6"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VSwitch, {
                  modelValue: config.compatible,
                  "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((config.compatible) = $event)),
                  label: "兼容模式",
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
              md: "4"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VTextField, {
                  modelValue: config.openai_url,
                  "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((config.openai_url) = $event)),
                  label: "API URL",
                  placeholder: "https://api.siliconflow.cn"
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
                  modelValue: config.openai_key,
                  "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((config.openai_key) = $event)),
                  label: "API 密钥",
                  type: "password",
                  placeholder: "sk-xxx"
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
                  modelValue: config.openai_model,
                  "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((config.openai_model) = $event)),
                  label: "自定义模型",
                  placeholder: "inclusionAI/Ling-flash-2.0"
                }, null, 8, ["modelValue"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ])
    ])
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-abe96cf8"]]);

export { Config as default };
