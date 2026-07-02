export { DEFAULT_CONFIG, cloneConfig, normalizeConfig } from './mascot/config'

export function unwrapResponse(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'data') && response.success !== undefined) {
    return response.data
  }
  return response?.data ?? response
}
