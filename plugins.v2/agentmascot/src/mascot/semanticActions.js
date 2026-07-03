import { SHIMEJI_ACTIONS, resolveMascotAction } from './actions'

export const SEMANTIC_ACTION_ALIASES = {
  idle: 'stand',
  walk: 'walk',
  run: 'run',
  dash: 'dash',
  follow: 'dash',
  jump: 'jump',
  fall: 'fall',
  land: 'bounce',
  sleep: 'lie',
  drag: 'drag',
  resist: 'resist',
  think: 'think',
  surprise: 'surprise',
  cheer: 'cheer',
  spinCelebrate: 'spinCelebrate',
  grabWall: 'holdWall',
  climbWall: 'climbWallUp',
  climbWallDown: 'climbWallDown',
  holdCeiling: 'holdCeiling',
  crawlCeiling: 'crawlCeiling',
}

export const REQUIRED_SEMANTIC_ACTIONS = [
  'idle',
  'walk',
  'run',
  'dash',
  'jump',
  'fall',
  'land',
  'sleep',
  'drag',
  'resist',
  'grabWall',
  'climbWall',
  'holdCeiling',
  'crawlCeiling',
]

export const FEATURE_SEMANTIC_ACTIONS = {
  kurisu: ['think', 'surprise', 'cheer', 'spinCelebrate'],
  nailong: ['jump', 'fall', 'land', 'sleep', 'drag', 'resist'],
}

export function legacyActionName(semanticName) {
  return SEMANTIC_ACTION_ALIASES[semanticName] || semanticName
}

export function resolveSemanticAction(mascot, semanticName) {
  const actionName = legacyActionName(semanticName)
  return resolveMascotAction(mascot, actionName)
}

export function semanticActionFrames(mascot, semanticName) {
  return resolveSemanticAction(mascot, semanticName).poses.map(item => item.imageName)
}

export function mascotActionFrames(mascot = 'chibiterasu', semanticNames = Object.keys(SEMANTIC_ACTION_ALIASES)) {
  return Object.fromEntries(semanticNames.map(name => [name, semanticActionFrames(mascot, name)]))
}

export function hasSemanticAction(mascot, semanticName) {
  const actionName = legacyActionName(semanticName)
  const action = resolveSemanticAction(mascot, semanticName)
  return Boolean(action && (SHIMEJI_ACTIONS[actionName] || action.poses?.length))
}
