import providerCatalog from '../../online_subtitles/provider_catalog.json' with { type: 'json' }

export const onlineProviderItems = providerCatalog.map(item => ({ title: item.name, value: item.id }))
export const defaultOnlineProviderIds = providerCatalog.filter(item => item.default_enabled).map(item => item.id)

export const onlineLanguageItems = [
  { title: '中英', value: 'chi&eng' },
  { title: '中日', value: 'chi&jp' },
  { title: '中韩', value: 'chi&kr' },
  { title: '其他双语', value: 'other_bilingual' },
  { title: '中文', value: 'chinese' },
  { title: '英文', value: 'english' },
  { title: '日文', value: 'japanese' },
  { title: '韩文', value: 'korean' },
  { title: '其他', value: 'other' },
  { title: '待确认', value: 'und' },
]

export function onlineResultKey(item) {
  return `${item?.provider || 'unknown'}:${item?.result_id || item?.page_url || item?.title || ''}`
}

export function providerName(providerId) {
  const known = onlineProviderItems.find(item => item.value === providerId)
  return known?.title || providerId || '未知来源'
}

export function providerPriority(providerId) {
  return providerCatalog.find(item => item.id === providerId)?.priority || 0
}

export function onlineResultMeta(item) {
  const parts = []
  if (item.language) parts.push(item.language)
  if (item.translation_source === 'site_translation') parts.push('站点翻译')
  if (item.translation_source === 'original_upload') parts.push('原始上传')
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
  const filter = onlineResultLanguageFilterCategory(item)
  if (['chi&eng', 'chi&jp', 'chi&kr', 'other_bilingual'].includes(filter)) return 'chinese'
  return filter === 'und' ? 'other' : filter
}

export function onlineResultLanguageFilterCategory(item) {
  const bucket = item?.language_bucket || 'und'
  const category = { chi: 'chinese', cht: 'chinese', eng: 'english', jpn: 'japanese', kor: 'korean' }[bucket] || bucket
  return onlineLanguageItems.some(item => item.value === category) ? category : 'und'
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
