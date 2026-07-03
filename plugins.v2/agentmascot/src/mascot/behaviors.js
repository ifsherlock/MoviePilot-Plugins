export const GROUND_BEHAVIORS = [
  { id: 'rest', surface: 'ground', weight: 42, cooldownMs: 0, minDurationMs: 12000 },
  { id: 'roam', surface: 'ground', weight: 48, cooldownMs: 0, minDurationMs: 620 },
  { id: 'goWall', surface: 'ground', weight: 6, cooldownMs: 18000, minDurationMs: 700 },
  { id: 'leap', surface: 'ground', weight: 4, cooldownMs: 14000, minDurationMs: 500 },
]

export const WALL_BEHAVIORS = [
  { id: 'goCeiling', surface: 'wall', weight: 66, cooldownMs: 16000, minDurationMs: 700, when: 'nearTop' },
  { id: 'holdWall', surface: 'wall', weight: 30, cooldownMs: 0, minDurationMs: 9000 },
  { id: 'climbWall', surface: 'wall', weight: 56, cooldownMs: 4000, minDurationMs: 700 },
  { id: 'fallFromWall', surface: 'wall', weight: 14, cooldownMs: 16000, minDurationMs: 500 },
]

export const CEILING_BEHAVIORS = [
  { id: 'holdCeiling', surface: 'ceiling', weight: 52, cooldownMs: 0, minDurationMs: 9000 },
  { id: 'crawlCeiling', surface: 'ceiling', weight: 36, cooldownMs: 4000, minDurationMs: 700 },
  { id: 'dropFromCeiling', surface: 'ceiling', weight: 12, cooldownMs: 16000, minDurationMs: 500 },
]

export function chooseWeightedBehavior(behaviors, context = {}) {
  const timestamp = context.timestamp ?? 0
  const cooldowns = context.cooldowns || {}
  const candidates = behaviors.filter(behavior => {
    if (behavior.when && !context[behavior.when]) return false
    return timestamp >= (cooldowns[behavior.id] || 0)
  })
  const totalWeight = candidates.reduce((sum, behavior) => sum + Math.max(behavior.weight, 0), 0)
  if (!totalWeight) return candidates[0] || null
  let cursor = (context.random?.() ?? Math.random()) * totalWeight
  for (const behavior of candidates) {
    cursor -= Math.max(behavior.weight, 0)
    if (cursor < 0) return behavior
  }
  return candidates[candidates.length - 1] || null
}

export function nextBehaviorCooldown(behavior, timestamp) {
  if (!behavior?.cooldownMs) return 0
  return timestamp + behavior.cooldownMs
}
