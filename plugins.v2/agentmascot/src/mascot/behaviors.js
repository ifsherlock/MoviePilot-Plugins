export const GROUND_BEHAVIORS = [
  { id: 'rest', surface: 'ground', weight: 42, minDurationMs: 12000 },
  { id: 'roam', surface: 'ground', weight: 48, minDurationMs: 620 },
  { id: 'goWall', surface: 'ground', weight: 6, minDurationMs: 700 },
  { id: 'leap', surface: 'ground', weight: 4, minDurationMs: 500 },
]

export const WALL_BEHAVIORS = [
  { id: 'goCeiling', surface: 'wall', weight: 66, minDurationMs: 700, when: 'nearTop' },
  { id: 'holdWall', surface: 'wall', weight: 30, minDurationMs: 9000 },
  { id: 'climbWall', surface: 'wall', weight: 56, minDurationMs: 700 },
  { id: 'fallFromWall', surface: 'wall', weight: 14, minDurationMs: 500 },
]

export const CEILING_BEHAVIORS = [
  { id: 'holdCeiling', surface: 'ceiling', weight: 52, minDurationMs: 9000 },
  { id: 'crawlCeiling', surface: 'ceiling', weight: 36, minDurationMs: 700 },
  { id: 'dropFromCeiling', surface: 'ceiling', weight: 12, minDurationMs: 500 },
]

export function chooseWeightedBehavior(behaviors, context = {}) {
  const candidates = behaviors.filter(behavior => !behavior.when || context[behavior.when])
  const totalWeight = candidates.reduce((sum, behavior) => sum + Math.max(behavior.weight, 0), 0)
  if (!totalWeight) return candidates[0] || null
  let cursor = (context.random?.() ?? Math.random()) * totalWeight
  for (const behavior of candidates) {
    cursor -= Math.max(behavior.weight, 0)
    if (cursor < 0) return behavior
  }
  return candidates[candidates.length - 1] || null
}
