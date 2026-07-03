import { SHIMEJI_ACTIONS } from '../assets/shimeji/frames'

export function createActionState(overrides = {}) {
  return {
    name: 'stand',
    poseIndex: 0,
    poseTicks: 0,
    ...overrides,
  }
}

export function createMouseState(overrides = {}) {
  return {
    x: 0,
    y: 0,
    lastX: 0,
    lastY: 0,
    lastMoveAt: 0,
    speed: 0,
    active: false,
    activeUntil: 0,
    candidateLaneY: null,
    candidateSince: 0,
    yCooldownUntil: 0,
    ...overrides,
  }
}

export function createPetState(overrides = {}) {
  return {
    anchorX: 180,
    anchorY: 180,
    targetX: 360,
    targetY: 180,
    lookRight: false,
    dragging: false,
    surface: 'ground',
    state: 'groundMove',
    stateUntil: 0,
    wallSide: 'left',
    laneY: 180,
    vx: 0,
    vy: 0,
    lastAnchorX: 180,
    lastAnchorY: 180,
    ...overrides,
  }
}

export function resolveAction(actionState) {
  return SHIMEJI_ACTIONS[actionState.name] || SHIMEJI_ACTIONS.stand
}

export function resolvePose(actionState) {
  const action = resolveAction(actionState)
  return action.poses[actionState.poseIndex % action.poses.length] || SHIMEJI_ACTIONS.stand.poses[0]
}
