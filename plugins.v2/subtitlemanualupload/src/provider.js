export function unwrapResponse(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'data') && response.success !== undefined) {
    return response.data
  }
  return response?.data ?? response
}

export function mediaLabel(media) {
  if (!media) return ''
  return media.year ? `${media.title} (${media.year})` : `${media.title || ''}`
}

export function targetLabel(target) {
  return target?.label || target?.target_label || ''
}
