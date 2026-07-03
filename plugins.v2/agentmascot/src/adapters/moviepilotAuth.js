import { normalizeConfig } from '../mascot/config'
import { unwrapResponse } from '../provider'

function looksLikeJwt(value) {
  return typeof value === 'string' && /^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(value.trim())
}

function pickToken(value, depth = 0) {
  if (!value || depth > 5) return ''
  if (looksLikeJwt(value)) return value.trim()
  if (typeof value === 'string') {
    try {
      return pickToken(JSON.parse(value), depth + 1)
    } catch {
      return ''
    }
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const token = pickToken(item, depth + 1)
      if (token) return token
    }
    return ''
  }
  if (typeof value !== 'object') return ''

  for (const key of ['access_token', 'accessToken', 'token', 'jwt', 'id_token']) {
    const token = pickToken(value[key], depth + 1)
    if (token) return token
  }
  for (const nested of ['state', 'user', 'auth', 'data']) {
    const token = pickToken(value[nested], depth + 1)
    if (token) return token
  }
  for (const item of Object.values(value)) {
    const token = pickToken(item, depth + 1)
    if (token) return token
  }
  return ''
}

function readStorageToken(area) {
  try {
    if (!area) return ''
    for (const key of ['auth', 'user', 'userStore', 'authStore', 'moviepilot-auth']) {
      const token = pickToken(area.getItem(key))
      if (token) return token
    }
    for (let index = 0; index < area.length; index += 1) {
      const token = pickToken(area.getItem(area.key(index)))
      if (token) return token
    }
  } catch {
    return ''
  }
  return ''
}

export function getMoviePilotToken(env = globalThis) {
  return (
    pickToken(env.__AgentMascotAccessToken)
    || readStorageToken(env.localStorage)
    || readStorageToken(env.sessionStorage)
  )
}

export function moviePilotApiBasePath(location = globalThis.location) {
  const pathname = location?.pathname?.replace(/\/$/, '') || ''
  if (!pathname || pathname === '/') return ''
  return pathname
}

export function moviePilotApiUrl(path, location = globalThis.location) {
  return `${location.origin}${moviePilotApiBasePath(location)}${path}`
}

export async function loadMoviePilotPluginConfig(pluginId, options = {}) {
  const env = options.env || globalThis
  const fetchImpl = options.fetchImpl || env.fetch?.bind(env)
  if (!fetchImpl) throw new Error('MoviePilot fetch is unavailable')

  const statusPath = `/api/v1/plugin/${pluginId}/status`
  const publicStatusPath = `/api/v1/plugin/${pluginId}/public_status`
  const token = getMoviePilotToken(env)
  const response = token
    ? await fetchImpl(moviePilotApiUrl(statusPath, env.location), {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      credentials: 'same-origin',
      cache: 'no-store',
    })
    : await fetchImpl(moviePilotApiUrl(publicStatusPath, env.location), {
      credentials: 'same-origin',
      cache: 'no-store',
    })

  if (!response.ok && token) {
    const publicResponse = await fetchImpl(moviePilotApiUrl(publicStatusPath, env.location), {
      credentials: 'same-origin',
      cache: 'no-store',
    })
    if (!publicResponse.ok) throw new Error(`${pluginId} public status ${publicResponse.status}`)
    const data = unwrapResponse(await publicResponse.json())
    return normalizeConfig(data?.config)
  }

  if (!response.ok) throw new Error(`${pluginId} status ${response.status}`)
  const data = unwrapResponse(await response.json())
  return normalizeConfig(data?.config)
}
