import {
  groundAnchorY as calculateGroundAnchorY,
  laneGap as calculateLaneGap,
  normalizeLaneY as calculateNormalizeLaneY,
} from './geometry'

export const PREVIEW_SURFACE_RATIOS = [0.3, 0.44, 0.58, 0.72, 0.86]
export const DOM_SURFACE_RATIOS = [0.32, 0.46, 0.6, 0.74, 0.88]

function viewportDimension(bounds, key) {
  const value = Number(bounds?.[key])
  return Number.isFinite(value) ? value : 0
}

function normalizeLane(anchorY, context) {
  return calculateNormalizeLaneY(
    anchorY,
    context.bounds,
    context.pose,
    context.size,
    context.scale,
    context.lookRight,
    context.groundPadding,
    context.viewportPadding || 0,
  )
}

function groundLane(context) {
  return calculateGroundAnchorY(context.bounds, context.groundPadding, context.viewportPadding || 0)
}

function surfaceGap(context) {
  return calculateLaneGap(context.size, context.scale)
}

export function buildSurfaceLanes(context, options = {}) {
  const ratios = options.ratios || PREVIEW_SURFACE_RATIOS
  const candidates = ratios.map(ratio => viewportDimension(context.bounds, 'height') * ratio)
  candidates.push(...(options.extraAnchors || []), groundLane(context))
  return thinSurfaceLanes(candidates, context, options)
}

export function thinSurfaceLanes(lanes, context, options = {}) {
  const gap = surfaceGap(context)
  const sorted = lanes
    .map(lane => normalizeLane(lane, context))
    .filter(Number.isFinite)
    .sort((a, b) => a - b)
  const thinned = []
  for (const lane of sorted) {
    if (!thinned.some(existing => Math.abs(existing - lane) < gap)) thinned.push(lane)
  }
  const ground = groundLane(context)
  if (!thinned.some(lane => Math.abs(lane - ground) < gap * 0.5)) thinned.push(ground)
  const result = thinned.sort((a, b) => a - b)
  return options.limit ? result.slice(-options.limit) : result
}

export function collectElementSurfaceAnchors(elements, bounds, options = {}) {
  const {
    getStyle,
    horizontalPadding = 48,
    laneOffset = 2,
    minHeight = 44,
    minWidth = 160,
    onError,
    shouldIgnoreElement,
    topPadding = 64,
    viewportPadding = 0,
  } = options
  const anchors = []
  for (const element of Array.from(elements || [])) {
    try {
      if (!element || shouldIgnoreElement?.(element)) continue
      const style = getStyle?.(element)
      if (style?.display === 'none' || style?.visibility === 'hidden' || Number(style?.opacity) === 0) continue
      const rect = element.getBoundingClientRect?.()
      if (!rect) continue
      if (rect.width < minWidth || rect.height < minHeight) continue
      if (rect.bottom < viewportPadding + topPadding || rect.top > viewportDimension(bounds, 'height') - viewportPadding) continue
      if (rect.left > viewportDimension(bounds, 'width') - horizontalPadding || rect.right < horizontalPadding) continue
      anchors.push(rect.top + laneOffset, rect.bottom + laneOffset)
    } catch (error) {
      onError?.(error)
    }
  }
  return anchors
}

export function buildDomSurfaceLanes(context, elements, options = {}) {
  const extraAnchors = collectElementSurfaceAnchors(elements, context.bounds, options)
  return buildSurfaceLanes(context, {
    extraAnchors,
    limit: options.limit || 9,
    ratios: options.ratios || DOM_SURFACE_RATIOS,
  })
}

export function nearestSurfaceLane(anchorY, lanes, fallbackLane) {
  return lanes.reduce(
    (best, lane) => (Math.abs(lane - anchorY) < Math.abs(best - anchorY) ? lane : best),
    lanes[0] ?? fallbackLane,
  )
}

export function chooseSurfaceLane(lanes, options = {}) {
  const {
    current,
    fallbackLane,
    gap,
    preferCurrent = true,
    random = Math.random,
  } = options
  if (preferCurrent && random() < 0.62) return nearestSurfaceLane(current, lanes, fallbackLane)
  const playable = lanes.filter(lane => Math.abs(lane - current) > gap * 0.8)
  const candidates = playable.length ? playable : lanes
  return candidates[Math.floor(random() * candidates.length)] ?? fallbackLane
}

export function crossedSurfaceLane(previousY, currentY, lanes, tolerance) {
  return lanes.find(lane => lane >= previousY - tolerance && lane <= currentY + tolerance) ?? null
}
