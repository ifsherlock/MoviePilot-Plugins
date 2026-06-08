export function unwrapResponse(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'data') && response.success !== undefined) {
    return response.data
  }
  return response?.data ?? response
}

export function groupLabel(group) {
  if (!group) return ''
  return group.year ? `${group.title} (${group.year})` : `${group.title || ''}`
}

export function targetLabel(target) {
  return target?.label || target?.target_label || ''
}
