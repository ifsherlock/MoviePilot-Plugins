export function isStreamTarget(target) {
  if (!target) return false
  if (target.is_stream === true) return true
  const text = `${target.path || ''} ${target.relative_path || ''} ${target.basename || ''}`.toLowerCase()
  return /\.strm(?:$|[\s?#])/.test(text)
}
