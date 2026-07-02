export const DEFAULT_CONFIG = {
  enabled: false,
  replace_agent_entry: true,
  show_sidebar_nav: true,
  scale: 1,
  speed: 1,
  follow_mouse: true,
  auto_roam: true,
  shadow: true,
}

export function cloneConfig(config) {
  return JSON.parse(JSON.stringify({ ...DEFAULT_CONFIG, ...(config || {}) }))
}

export function unwrapResponse(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'data') && response.success !== undefined) {
    return response.data
  }
  return response?.data ?? response
}
