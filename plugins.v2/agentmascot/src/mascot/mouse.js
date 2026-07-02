import {
  Y_FOLLOW_COOLDOWN_MS,
  Y_FOLLOW_DWELL_MS,
  Y_FOLLOW_LANE_RADIUS,
  Y_FOLLOW_MIN_DELTA,
  Y_FOLLOW_MOUSE_SPEED_MAX,
} from './config'

export function updateMouseIntent(mouse, point, options = {}) {
  const {
    activeExtraMs = 1200,
    dwellMs = Y_FOLLOW_DWELL_MS,
    laneRadius = Y_FOLLOW_LANE_RADIUS,
    minDelta = Y_FOLLOW_MIN_DELTA,
    nearestLaneToY,
    scale = 1,
    timestamp = 0,
  } = options
  const previousX = mouse.x
  const previousY = mouse.y
  const previousMoveAt = mouse.lastMoveAt || timestamp
  const elapsed = Math.max(timestamp - previousMoveAt, 1)

  mouse.lastX = previousX
  mouse.lastY = previousY
  mouse.x = point.x
  mouse.y = point.y
  mouse.lastMoveAt = timestamp
  mouse.speed = Math.hypot(mouse.x - previousX, mouse.y - previousY) / elapsed

  const targetLaneY = nearestLaneToY(mouse.y)
  const currentLaneY = options.currentLaneY ?? nearestLaneToY(options.anchorY ?? mouse.y)
  const closeToLane = Math.abs(targetLaneY - mouse.y) <= laneRadius * scale
  const meaningfulShift = Math.abs(targetLaneY - currentLaneY) >= minDelta * scale

  if (!closeToLane || !meaningfulShift) {
    mouse.candidateLaneY = null
    mouse.candidateSince = 0
    return timestamp + dwellMs + activeExtraMs
  }
  if (mouse.candidateLaneY !== targetLaneY) {
    mouse.candidateLaneY = targetLaneY
    mouse.candidateSince = timestamp
  }
  return timestamp + dwellMs + activeExtraMs
}

export function canFollowMouseY(mouse, pet, options = {}) {
  const {
    active = true,
    activeUntil,
    blockedStates = ['rest', 'bounce', 'toWall'],
    dwellMs = Y_FOLLOW_DWELL_MS,
    followMouse = true,
    minDelta = Y_FOLLOW_MIN_DELTA,
    scale = 1,
    speedMax = Y_FOLLOW_MOUSE_SPEED_MAX,
    timestamp = 0,
  } = options
  if (!followMouse || !active || timestamp >= activeUntil) return false
  if (timestamp < mouse.yCooldownUntil) return false
  if (mouse.candidateLaneY === null || !mouse.candidateSince) return false
  const idleMs = timestamp - mouse.lastMoveAt
  const effectiveSpeed = idleMs > 260 ? 0 : mouse.speed
  if (effectiveSpeed > speedMax) return false
  if (timestamp - mouse.candidateSince < dwellMs) return false
  if (pet.surface !== 'ground') return false
  if (blockedStates.includes(pet.state)) return false
  return Math.abs(mouse.candidateLaneY - (pet.laneY || pet.anchorY)) >= minDelta * scale
}

export function resolveMouseYFollow(mouse, pet, options = {}) {
  const {
    cooldownMs = Y_FOLLOW_COOLDOWN_MS,
    laneGap,
    timestamp = 0,
  } = options
  if (!canFollowMouseY(mouse, pet, options)) return { applied: false, type: 'none' }
  const targetLaneY = mouse.candidateLaneY
  const deltaY = targetLaneY - pet.anchorY
  mouse.candidateLaneY = null
  mouse.candidateSince = 0
  mouse.yCooldownUntil = timestamp + cooldownMs

  if (Math.abs(deltaY) <= laneGap * 0.9) {
    return { applied: true, type: 'lane', targetLaneY }
  }
  if (deltaY > 0) {
    return { applied: true, type: 'fall', vx: 0, vy: 0.8 }
  }
  return {
    applied: true,
    side: mouse.x < pet.anchorX ? 'left' : 'right',
    type: 'leap',
  }
}
