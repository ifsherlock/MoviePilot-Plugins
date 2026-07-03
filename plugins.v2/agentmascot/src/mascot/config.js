export const DEFAULT_CONFIG = {
  enabled: false,
  mascot: 'chibiterasu',
  replace_agent_entry: true,
  show_sidebar_nav: true,
  scale: 1,
  speed: 1,
  follow_mouse: true,
  auto_roam: true,
  shadow: true,
}

export const CONFIG_LIMITS = {
  scale: { min: 0.6, max: 4, defaultValue: 1 },
  speed: { min: 0.4, max: 2, defaultValue: 1 },
}

export const SHIMEJI_CANVAS_SIZE = 128
export const SHIMEJI_TICK_MS = 33
export const ROAM_INTERVAL = 3200
export const ROAM_REST_MIN = 9000
export const ROAM_REST_RANGE = 26000
export const WALL_REST_MIN = 9000
export const WALL_REST_RANGE = 24000
export const FOLLOW_DEAD_ZONE = 92
export const RUN_DISTANCE = 260
export const VIEWPORT_PADDING = 12
export const GROUND_PADDING = 18
export const MAX_GROUND_STEP = 260
export const WALL_MARGIN = 72
export const SURFACE_SCAN_MS = 1200
export const LANE_MIN_GAP = 54
export const Y_FOLLOW_DWELL_MS = 1100
export const Y_FOLLOW_COOLDOWN_MS = 4200
export const Y_FOLLOW_LANE_RADIUS = 120
export const Y_FOLLOW_MOUSE_SPEED_MAX = 0.45
export const Y_FOLLOW_MIN_DELTA = 90
export const AIR_GRAVITY = 1.05
export const AIR_DRAG_X = 0.982
export const AIR_DRAG_Y = 0.99

export const ACTION_MIN_DURATION = {
  stand: 520,
  walk: 620,
  run: 700,
  dash: 700,
  drag: 0,
  resist: 0,
  lie: 9000,
  sit: 9000,
  relaxedSit: 9000,
  sitFeetDown: 5000,
  dangleFeet: 12000,
  lookUp: 8000,
  crawl: 1600,
  jump: 500,
  fall: 500,
  bounce: 450,
  holdWall: 7000,
  climbWallUp: 700,
  climbWallDown: 700,
  holdCeiling: 7000,
  crawlCeiling: 700,
  split: 1500,
}

function clampNumber(value, minimum, maximum, defaultValue) {
  const number = Number(value)
  if (!Number.isFinite(number)) return defaultValue
  return Math.min(Math.max(number, minimum), maximum)
}

export function normalizeConfig(config) {
  const rawConfig = config || {}
  const normalized = {
    ...DEFAULT_CONFIG,
    ...rawConfig,
    enabled: Boolean(rawConfig.enabled ?? DEFAULT_CONFIG.enabled),
    mascot: ['chibiterasu', 'nailong'].includes(rawConfig.mascot) ? rawConfig.mascot : DEFAULT_CONFIG.mascot,
    replace_agent_entry: Boolean(rawConfig.replace_agent_entry ?? DEFAULT_CONFIG.replace_agent_entry),
    show_sidebar_nav: Boolean(rawConfig.show_sidebar_nav ?? DEFAULT_CONFIG.show_sidebar_nav),
    follow_mouse: Boolean(rawConfig.follow_mouse ?? DEFAULT_CONFIG.follow_mouse),
    auto_roam: Boolean(rawConfig.auto_roam ?? DEFAULT_CONFIG.auto_roam),
    shadow: Boolean(rawConfig.shadow ?? DEFAULT_CONFIG.shadow),
  }
  for (const [key, limit] of Object.entries(CONFIG_LIMITS)) {
    normalized[key] = clampNumber(rawConfig[key], limit.min, limit.max, limit.defaultValue)
  }
  return normalized
}

export function cloneConfig(config) {
  return JSON.parse(JSON.stringify(normalizeConfig(config)))
}
