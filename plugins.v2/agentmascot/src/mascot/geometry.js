import {
  LANE_MIN_GAP,
  SHIMEJI_CANVAS_SIZE,
} from './config'

const BASE_PET_SIZE = 92

function viewportDimension(bounds, key) {
  const value = Number(bounds?.[key])
  return Number.isFinite(value) ? value : 0
}

function clampNumber(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), maximum)
}

export function petSize(scale, baseSize = BASE_PET_SIZE) {
  return Math.round(baseSize * Number(scale || 1))
}

export function poseScale(size, canvasSize = SHIMEJI_CANVAS_SIZE) {
  return size / canvasSize
}

export function visualAnchor(pose, size, scale, lookRight = false) {
  const scaledAnchorX = pose.anchor[0] * scale
  return {
    x: lookRight ? size - scaledAnchorX : scaledAnchorX,
    y: pose.anchor[1] * scale,
  }
}

export function groundAnchorY(bounds, groundPadding, viewportPadding = 0) {
  return Math.max(viewportDimension(bounds, 'height') - viewportPadding - groundPadding, 0)
}

export function ceilingAnchorY(pose, size, scale, lookRight = false, viewportPadding = 0) {
  return viewportPadding + visualAnchor(pose, size, scale, lookRight).y
}

export function clampAnchorX(anchorX, bounds, pose, size, scale, lookRight = false, viewportPadding = 0) {
  const anchor = visualAnchor(pose, size, scale, lookRight)
  const minX = viewportPadding + anchor.x
  const maxX = Math.max(viewportDimension(bounds, 'width') - viewportPadding - (size - anchor.x), minX)
  return clampNumber(anchorX, minX, maxX)
}

export function clampAnchorY(anchorY, bounds, pose, size, scale, lookRight = false, groundPadding, viewportPadding = 0) {
  const minY = ceilingAnchorY(pose, size, scale, lookRight, viewportPadding)
  const maxY = groundAnchorY(bounds, groundPadding, viewportPadding)
  return clampNumber(anchorY, minY, maxY)
}

export function laneGap(size, scale, minGap = LANE_MIN_GAP) {
  return Math.max(minGap * scale, size * 0.42)
}

export function normalizeLaneY(anchorY, bounds, pose, size, scale, lookRight = false, groundPadding, viewportPadding = 0) {
  const minY = ceilingAnchorY(pose, size, scale, lookRight, viewportPadding) + 28 * scale
  const maxY = groundAnchorY(bounds, groundPadding, viewportPadding)
  return clampNumber(anchorY, minY, maxY)
}

export function wallAnchorX(side, bounds, viewportPadding = 0) {
  if (side === 'left') return viewportPadding
  return Math.max(viewportDimension(bounds, 'width') - viewportPadding, viewportPadding)
}

export function randomGroundX(bounds, size, viewportPadding = 0, random = Math.random) {
  const margin = size * 1.15 + viewportPadding
  const minX = margin
  const maxX = Math.max(viewportDimension(bounds, 'width') - margin, minX)
  return minX + random() * (maxX - minX)
}

export function wallTargetY(
  bounds,
  pose,
  size,
  scale,
  lookRight,
  groundPadding,
  viewportPadding,
  wallMargin,
  random = Math.random,
) {
  const top = Math.max(
    wallMargin * scale,
    ceilingAnchorY(pose, size, scale, lookRight, viewportPadding) + 24 * scale,
  )
  const bottom = Math.max(
    groundAnchorY(bounds, groundPadding, viewportPadding) - wallMargin * scale,
    top,
  )
  return top + random() * Math.max(bottom - top, 1)
}
