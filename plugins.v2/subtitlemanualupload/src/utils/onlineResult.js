export const onlineProviderItems = [
  { title: 'SubHD', value: 'subhd' },
  { title: 'Zimuku', value: 'zimuku' },
  { title: '射手网(伪)', value: 'assrt' },
  { title: 'OpenSubtitles', value: 'opensubtitles' },
]

export function onlineResultKey(item) {
  return `${item?.provider || 'unknown'}:${item?.result_id || item?.page_url || item?.title || ''}`
}

export function providerName(providerId) {
  const known = onlineProviderItems.find(item => item.value === providerId)
  return known?.title || providerId || '未知来源'
}

export function providerPriority(providerId) {
  if (providerId === 'subhd') return 35
  if (providerId === 'assrt') return 30
  if (providerId === 'zimuku') return 25
  if (providerId === 'opensubtitles') return 20
  return 0
}

export function onlineResultMeta(item) {
  const parts = []
  if (item.language) parts.push(item.language)
  if (item.format) parts.push(item.format)
  if (item.season || item.episode) {
    parts.push(`S${String(item.season || 0).padStart(2, '0')}E${String(item.episode || 0).padStart(2, '0')}`)
  }
  if (item.score) parts.push(`匹配 ${item.score}`)
  return parts.join(' · ') || '等待下载后自动匹配'
}

export function isOnlineResultDownloadable(item) {
  return item?.downloadable !== false
}

export function onlineResultLanguageCategory(item) {
  const category = String(item?.language_category || '').toLowerCase()
  if (['chinese', 'english', 'japanese', 'korean', 'other'].includes(category)) return category
  const text = `${item?.language || ''} ${item?.title || ''} ${item?.note || ''}`.toLowerCase()
  if (
    text.includes('中文')
    || text.includes('简体')
    || text.includes('繁体')
    || text.includes('双语')
    || text.includes('chinese')
    || /(^|[\s._()\[\]-])(zh|ze|chi|chs|cht|zho)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'chinese'
  if (
    text.includes('英文')
    || text.includes('english')
    || /(^|[\s._()\[\]-])(en|eng)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'english'
  if (
    text.includes('日文')
    || text.includes('日语')
    || text.includes('japanese')
    || /(^|[\s._()\[\]-])(ja|jpn)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'japanese'
  if (
    text.includes('korean')
    || /(^|[\s._()\[\]-])(ko|kor)(?=$|[\s._()\[\]-])/.test(text)
  ) return 'korean'
  return 'other'
}

export function onlineResultLanguageFilterCategory(item) {
  const category = onlineResultLanguageCategory(item)
  return category === 'korean' ? 'other' : category
}

export function onlineResultLanguagePriority(item) {
  const category = onlineResultLanguageCategory(item)
  if (category === 'chinese') return 40
  if (category === 'english') return 30
  if (category === 'japanese' || category === 'korean') return 20
  return 10
}

export function onlineResultIdentityPriority(item) {
  const status = String(item?.identity_status || '').toLowerCase()
  if (status === 'strong') return 30
  if (status === 'weak') return 10
  return 0
}

export function isForeignOnlineResult(item) {
  return onlineResultLanguageCategory(item) !== 'chinese'
}

export function providerProgressText(state) {
  if (state === 'searching') return '搜索中'
  if (state === 'done') return '已完成'
  if (state === 'timeout') return '超时'
  if (state === 'cancelled') return '已停止'
  if (state === 'error') return '失败'
  return '等待'
}

export function providerProgressColor(state) {
  if (state === 'searching') return 'info'
  if (state === 'done') return 'success'
  if (state === 'timeout') return 'warning'
  if (state === 'cancelled') return 'default'
  if (state === 'error') return 'warning'
  return 'default'
}
