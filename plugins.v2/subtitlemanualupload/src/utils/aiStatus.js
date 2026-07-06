const INSTALL_HINT = '请安装 AI字幕生成(联动版) 以启用相关功能'

export function buildAiStatusDetail(aiStatus = {}) {
  const message = String(aiStatus?.message || '').trim()
  const normalizedMessage = message.replace(/\s+/g, '')
  const alreadySaysInstall = normalizedMessage.includes('请安装AI字幕生成(联动版)')
    || normalizedMessage.includes('请先安装并启用AI字幕生成(联动版)')
  if (!message || message === '插件未启用' || alreadySaysInstall) return INSTALL_HINT
  return message
}

export function buildAiSummaryText({ aiEnabled, aiAvailable, aiStatus, aiSummary }) {
  const pluginName = aiStatus?.plugin_name || 'AI字幕生成(联动版)'
  if (!aiEnabled) return 'AI 字幕联动'
  if (!aiAvailable) return pluginName

  const summary = aiSummary || {}
  const parts = []
  if (summary.in_progress) parts.push(`${summary.in_progress} 个生成中`)
  if (summary.pending) parts.push(`${summary.pending} 个排队`)
  if (summary.failed) parts.push(`${summary.failed} 个失败`)
  if (summary.completed) parts.push(`${summary.completed} 个完成`)
  if (summary.ignored) parts.push(`${summary.ignored} 个忽略`)
  if (summary.no_audio) parts.push(`${summary.no_audio} 个无音轨`)
  if (summary.cancelled) parts.push(`${summary.cancelled} 个取消`)
  return parts.length ? `AI：${parts.join(' / ')}` : `${pluginName}：暂无当前资源任务`
}
