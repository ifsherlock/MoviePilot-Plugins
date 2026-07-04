import assert from 'node:assert/strict'
import {
  buildAiStatusDetail,
  buildAiSummaryText,
} from '../plugins.v2/subtitlemanualupload/src/utils/aiStatus.js'

assert.equal(
  buildAiSummaryText({
    aiEnabled: true,
    aiAvailable: false,
    aiStatus: {
      plugin_name: 'AI字幕生成(联动版)',
      message: '插件未启用',
    },
    aiSummary: {},
  }),
  'AI字幕生成(联动版)',
)

assert.equal(
  buildAiStatusDetail({
    plugin_name: 'AI字幕生成(联动版)',
    message: '插件未启用',
  }),
  '插件未启用，请先安装并启用',
)

assert.equal(
  buildAiStatusDetail({
    plugin_name: 'AI字幕生成(联动版)',
    message: '请先安装并启用 AI字幕生成(联动版)',
  }),
  '请先安装并启用',
)

assert.equal(
  buildAiSummaryText({
    aiEnabled: false,
    aiAvailable: false,
    aiStatus: {
      plugin_name: 'AI字幕生成(联动版)',
      message: 'AI 字幕联动已关闭',
    },
    aiSummary: {},
  }),
  'AI 字幕联动',
)

assert.equal(
  buildAiSummaryText({
    aiEnabled: true,
    aiAvailable: true,
    aiStatus: {
      plugin_name: 'AI字幕生成(联动版)',
      message: '可提交 AI 字幕生成任务',
    },
    aiSummary: { pending: 1, in_progress: 2 },
  }),
  'AI：2 个生成中 / 1 个排队',
)
