export function pointerOffset(point, anchor) {
  return {
    x: point.x - anchor.x,
    y: point.y - anchor.y,
  }
}

export function dragAnchor(point, offset) {
  return {
    x: point.x - offset.x,
    y: point.y - offset.y,
  }
}

export function dragLookRight(currentLookRight, movementX) {
  return Math.abs(movementX) > 0 ? movementX > 0 : currentLookRight
}

export function dragDistance(startPoint, point) {
  if (!startPoint) return 0
  return Math.hypot(point.x - startPoint.x, point.y - startPoint.y)
}

export function resolveDragRelease(anchorY, options = {}) {
  const {
    fallGap = 16,
    movementX = 0,
    movementY = 0,
    nearestLaneToY,
    groundY,
    scale = 1,
    snapBase = 24,
  } = options
  const nearestLane = nearestLaneToY(anchorY)
  if (Math.abs(nearestLane - anchorY) <= snapBase * scale) {
    return { laneY: nearestLane, type: 'lane' }
  }
  if (anchorY < groundY - fallGap) {
    return {
      type: 'fall',
      vx: movementX * 0.08,
      vy: Math.min(movementY * 0.06, 2),
    }
  }
  return { laneY: groundY, type: 'ground' }
}
