<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { SHIMEJI_ACTIONS, mascotIcon } from '../assets/shimeji/frames'
import { cloneConfig, unwrapResponse } from '../provider'
import {
  ACTION_MIN_DURATION,
  AIR_DRAG_X,
  AIR_DRAG_Y,
  AIR_GRAVITY,
  FOLLOW_DEAD_ZONE,
  GROUND_PADDING,
  MAX_GROUND_STEP,
  REST_ACTIONS,
  ROAM_INTERVAL,
  ROAM_REST_MIN,
  ROAM_REST_RANGE,
  RUN_DISTANCE,
  SHIMEJI_TICK_MS,
  WALL_MARGIN,
  WALL_REST_MIN,
  WALL_REST_RANGE,
} from '../mascot/config'
import {
  dragAnchor as calculateDragAnchor,
  dragLookRight,
  pointerOffset as calculatePointerOffset,
  resolveDragRelease,
} from '../mascot/drag'
import {
  ceilingAnchorY as calculateCeilingAnchorY,
  clampAnchorX as calculateClampAnchorX,
  clampAnchorY as calculateClampAnchorY,
  groundAnchorY as calculateGroundAnchorY,
  laneGap as calculateLaneGap,
  normalizeLaneY as calculateNormalizeLaneY,
  petSize as calculatePetSize,
  poseScale as calculatePoseScale,
  randomGroundX as calculateRandomGroundX,
  visualAnchor as calculateVisualAnchor,
  wallAnchorX as calculateWallAnchorX,
  wallTargetY as calculateWallTargetY,
} from '../mascot/geometry'
import {
  resolveMouseYFollow,
  updateMouseIntent as updateMouseIntentState,
} from '../mascot/mouse'
import {
  buildSurfaceLanes,
  chooseSurfaceLane,
  crossedSurfaceLane,
  nearestSurfaceLane,
} from '../mascot/surfaces'

const props = defineProps({
  api: {
    type: Object,
    default: () => ({}),
  },
  pluginId: {
    type: String,
    default: 'AgentMascot',
  },
  config: {
    type: Object,
    default: null,
  },
  hideTitle: {
    type: Boolean,
    default: false,
  },
})

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const stageRef = ref(null)
const mascotRef = ref(null)
const config = ref(cloneConfig(props.config))
const action = ref('stand')
const poseIndex = ref(0)
const poseTicks = ref(0)
const mouse = reactive({
  x: 0,
  y: 0,
  lastX: 0,
  lastY: 0,
  lastMoveAt: 0,
  speed: 0,
  active: false,
  candidateLaneY: null,
  candidateSince: 0,
  yCooldownUntil: 0,
})
const pet = reactive({
  anchorX: 100,
  anchorY: 120,
  targetX: 320,
  targetY: 120,
  lookRight: false,
  dragging: false,
  surface: 'ground',
  state: 'groundMove',
  stateUntil: 0,
  wallSide: 'left',
  laneY: 120,
  vx: 0,
  vy: 0,
  lastAnchorX: 100,
  lastAnchorY: 120,
})

let roamTimer = 0
let rafId = 0
let lastTick = 0
let pointerOffset = { x: 0, y: 0 }
let actionLockedUntil = 0
let mouseActiveUntil = 0
let roamPausedUntil = 0

const currentAction = computed(() => SHIMEJI_ACTIONS[action.value] || SHIMEJI_ACTIONS.stand)
const currentPose = computed(() => {
  const poses = currentAction.value.poses
  return poses[poseIndex.value % poses.length] || SHIMEJI_ACTIONS.stand.poses[0]
})
const currentFrame = computed(() => currentPose.value.image)
const petSize = computed(() => calculatePetSize(config.value.scale))
const poseScale = computed(() => calculatePoseScale(petSize.value))
const stageStyle = computed(() => ({
  '--pet-size': `${petSize.value}px`,
}))
const petStyle = computed(() => {
  const anchor = visualAnchor(currentPose.value)
  const left = pet.anchorX - anchor.x
  const top = pet.anchorY - anchor.y
  return {
    transform: `translate3d(${left}px, ${top}px, 0) scaleX(${pet.lookRight ? -1 : 1})`,
    '--pet-facing': pet.lookRight ? -1 : 1,
  }
})

function endpoint(path) {
  return `plugin/${props.pluginId}${path}`
}

async function apiGet(path) {
  if (props.api?.get) {
    return props.api.get(endpoint(path))
  }
  return null
}

async function apiPost(path, payload) {
  if (props.api?.post) {
    return props.api.post(endpoint(path), payload)
  }
  return null
}

async function loadStatus() {
  if (!props.api?.get) return
  loading.value = true
  error.value = ''
  try {
    const data = unwrapResponse(await apiGet('/status'))
    config.value = cloneConfig(data?.config)
  } catch (err) {
    error.value = err?.message || String(err)
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (!props.api?.post) return
  saving.value = true
  error.value = ''
  try {
    const data = unwrapResponse(await apiPost('/config', cloneConfig(config.value)))
    config.value = cloneConfig(data?.config)
  } catch (err) {
    error.value = err?.message || String(err)
  } finally {
    saving.value = false
  }
}

function stageBounds() {
  const rect = stageRef.value?.getBoundingClientRect()
  return {
    width: rect?.width || window.innerWidth,
    height: rect?.height || window.innerHeight,
  }
}

function clampPet() {
  pet.anchorX = clampAnchorX(pet.anchorX)
  pet.anchorY = clampAnchorY(pet.anchorY)
}

function groundAnchorY() {
  return calculateGroundAnchorY(stageBounds(), GROUND_PADDING)
}

function visualAnchor(pose) {
  return calculateVisualAnchor(pose, petSize.value, poseScale.value, pet.lookRight)
}

function clampAnchorX(anchorX) {
  return calculateClampAnchorX(anchorX, stageBounds(), currentPose.value, petSize.value, poseScale.value, pet.lookRight)
}

function clampAnchorY(anchorY) {
  return calculateClampAnchorY(anchorY, stageBounds(), currentPose.value, petSize.value, poseScale.value, pet.lookRight, GROUND_PADDING)
}

function laneGap() {
  return calculateLaneGap(petSize.value, poseScale.value)
}

function normalizeLaneY(anchorY) {
  return calculateNormalizeLaneY(anchorY, stageBounds(), currentPose.value, petSize.value, poseScale.value, pet.lookRight, GROUND_PADDING)
}

function surfaceContext() {
  return {
    bounds: stageBounds(),
    pose: currentPose.value,
    size: petSize.value,
    scale: poseScale.value,
    lookRight: pet.lookRight,
    groundPadding: GROUND_PADDING,
  }
}

function surfaceLanes() {
  return buildSurfaceLanes(surfaceContext())
}

function nearestLaneToY(anchorY) {
  const lanes = surfaceLanes()
  return nearestSurfaceLane(anchorY, lanes, groundAnchorY())
}

function chooseLaneY(preferCurrent = true) {
  const lanes = surfaceLanes()
  const current = pet.laneY || nearestLaneToY(pet.anchorY)
  return chooseSurfaceLane(lanes, {
    current,
    fallbackLane: groundAnchorY(),
    gap: laneGap(),
    preferCurrent,
  })
}

function setLaneY(anchorY) {
  pet.laneY = normalizeLaneY(anchorY)
  pet.anchorY = pet.laneY
  pet.targetY = pet.laneY
}

function crossedLandingY(previousY, currentY) {
  const tolerance = Math.max(8 * poseScale.value, 4)
  return crossedSurfaceLane(previousY, currentY, surfaceLanes(), tolerance)
}

function updateMouseIntent(x, y, timestamp = performance.now()) {
  mouse.active = true
  mouseActiveUntil = updateMouseIntentState(mouse, { x, y }, {
    anchorY: pet.anchorY,
    currentLaneY: pet.laneY || nearestLaneToY(pet.anchorY),
    nearestLaneToY,
    scale: poseScale.value,
    timestamp,
  })
}

function applyMouseYFollow(timestamp) {
  const result = resolveMouseYFollow(mouse, pet, {
    active: mouse.active,
    activeUntil: mouseActiveUntil,
    followMouse: config.value.follow_mouse,
    laneGap: laneGap(),
    scale: poseScale.value,
    timestamp,
  })
  if (!result.applied) return false
  if (result.type === 'lane') {
    setLaneY(result.targetLaneY)
    return true
  }
  if (result.type === 'fall') {
    startFall(timestamp, result.vx, result.vy)
    return true
  }
  startLeap(timestamp, result.side)
  return true
}

function wallAnchorX(side) {
  return calculateWallAnchorX(side, stageBounds())
}

function ceilingAnchorY() {
  return calculateCeilingAnchorY(currentPose.value, petSize.value, poseScale.value, pet.lookRight)
}

function wallTargetY() {
  return calculateWallTargetY(
    stageBounds(),
    currentPose.value,
    petSize.value,
    poseScale.value,
    pet.lookRight,
    GROUND_PADDING,
    0,
    WALL_MARGIN,
  )
}

function pickRoamTarget() {
  const bounds = stageBounds()
  const margin = petSize.value * 0.5
  const minX = margin
  const maxX = Math.max(bounds.width - margin, minX)
  const direction = Math.random() < 0.5 ? -1 : 1
  const distance = 120 + Math.random() * Math.min(MAX_GROUND_STEP, maxX - minX)
  pet.targetX = Math.min(Math.max(pet.anchorX + direction * distance, minX), maxX)
}

function setAction(nextAction, timestamp = performance.now(), options = {}) {
  if (action.value === nextAction) return
  if (!options.force && timestamp < actionLockedUntil && nextAction !== 'drag' && nextAction !== 'resist' && nextAction !== 'split') return
  action.value = nextAction
  poseIndex.value = 0
  poseTicks.value = 0
  actionLockedUntil = timestamp + (options.duration ?? ACTION_MIN_DURATION[nextAction] ?? 600)
}

function updateGroundAction(distance, timestamp, isFollowingMouse) {
  if (pet.dragging) {
    setAction(distance > 56 ? 'resist' : 'drag', timestamp)
    return
  }
  if (distance > FOLLOW_DEAD_ZONE) {
    setAction(isFollowingMouse && distance > RUN_DISTANCE ? 'dash' : 'run', timestamp)
    return
  }
  if (distance > 8) {
    setAction('walk', timestamp)
    return
  }
  if (action.value === 'walk' || action.value === 'run' || action.value === 'dash') {
    actionLockedUntil = 0
  }
  setAction('stand', timestamp)
}

function pauseBeforeNextRoam(timestamp) {
  roamPausedUntil = timestamp + ROAM_REST_MIN + Math.random() * ROAM_REST_RANGE
  pet.targetX = pet.anchorX
}

function startRest(timestamp, choices = REST_ACTIONS, min = ROAM_REST_MIN, range = ROAM_REST_RANGE) {
  const nextAction = choices[Math.floor(Math.random() * choices.length)] || 'stand'
  const duration = min + Math.random() * range
  pet.targetX = pet.anchorX
  pet.targetY = pet.anchorY
  pet.stateUntil = timestamp + duration
  if (nextAction === 'holdWall') {
    pet.surface = 'wall'
    pet.state = 'wallHold'
  } else if (nextAction === 'holdCeiling') {
    pet.surface = 'ceiling'
    pet.state = 'ceilingHold'
  } else {
    pet.surface = 'ground'
    pet.state = 'rest'
    roamPausedUntil = pet.stateUntil
  }
  setAction(nextAction, timestamp, { force: true, duration })
}

function startGroundMove(timestamp, targetX = null, state = 'groundMove') {
  pet.surface = 'ground'
  pet.state = state
  pet.stateUntil = 0
  const shouldShiftLane = state === 'groundMove' && Math.random() < 0.38
  setLaneY(chooseLaneY(!shouldShiftLane))
  pet.targetX = targetX ?? randomGroundX()
  updateGroundAction(Math.abs(pet.targetX - pet.anchorX), timestamp, false)
}

function startMoveToWall(timestamp, side = Math.random() < 0.5 ? 'left' : 'right') {
  pet.surface = 'ground'
  pet.state = 'toWall'
  pet.wallSide = side
  setLaneY(nearestLaneToY(pet.anchorY))
  pet.targetX = wallAnchorX(side)
  setAction(Math.abs(pet.targetX - pet.anchorX) > RUN_DISTANCE ? 'run' : 'walk', timestamp, { force: true })
}

function startWall(side, timestamp, targetY = null) {
  pet.surface = 'wall'
  pet.state = 'wallHold'
  pet.wallSide = side
  pet.targetY = targetY ?? pet.anchorY
  pet.anchorX = wallAnchorX(side)
  pet.anchorY = clampAnchorY(pet.anchorY)
  pet.lookRight = side === 'right'
  setAction('holdWall', timestamp, { force: true, duration: WALL_REST_MIN })
  pet.stateUntil = timestamp + 1800 + Math.random() * 3200
}

function startWallClimb(timestamp, targetY = null) {
  pet.surface = 'wall'
  pet.state = 'wallClimb'
  pet.targetY = targetY ?? (Math.random() < 0.62 ? ceilingAnchorY() + 12 * poseScale.value : wallTargetY())
  pet.anchorX = wallAnchorX(pet.wallSide)
  setAction(pet.targetY < pet.anchorY ? 'climbWallUp' : 'climbWallDown', timestamp, { force: true })
}

function startCeiling(timestamp, targetX = null) {
  pet.surface = 'ceiling'
  pet.state = 'ceilingHold'
  pet.anchorY = ceilingAnchorY()
  pet.targetX = targetX ?? randomGroundX()
  setAction('holdCeiling', timestamp, { force: true, duration: WALL_REST_MIN })
  pet.stateUntil = timestamp + WALL_REST_MIN + Math.random() * WALL_REST_RANGE
}

function startCeilingCrawl(timestamp, targetX = null) {
  pet.surface = 'ceiling'
  pet.state = 'ceilingCrawl'
  pet.anchorY = ceilingAnchorY()
  pet.targetX = targetX ?? randomGroundX()
  setAction('crawlCeiling', timestamp, { force: true })
}

function startFall(timestamp, vx = 0, vy = 0) {
  pet.surface = 'air'
  pet.state = 'fall'
  pet.vx = vx
  pet.vy = vy
  setAction(vy < 0 ? 'jump' : 'fall', timestamp, { force: true })
}

function startLeap(timestamp, side = Math.random() < 0.5 ? 'left' : 'right') {
  const direction = side === 'left' ? -1 : 1
  pet.surface = 'air'
  pet.state = 'leap'
  pet.wallSide = side
  pet.vx = direction * (7 + Math.random() * 5.5) * Number(config.value.speed || 1)
  pet.vy = -(14 + Math.random() * 9) * Number(config.value.speed || 1)
  setAction('jump', timestamp, { force: true })
}

function randomGroundX() {
  return calculateRandomGroundX(stageBounds(), petSize.value)
}

function chooseGroundBehavior(timestamp) {
  const roll = Math.random()
  if (roll < 0.24) {
    startRest(timestamp)
    return
  }
  if (roll < 0.44) {
    startGroundMove(timestamp)
    return
  }
  if (roll < 0.74) {
    startMoveToWall(timestamp)
    return
  }
  startLeap(timestamp)
}

function chooseWallBehavior(timestamp) {
  const nearTop = pet.anchorY <= ceilingAnchorY() + 56 * poseScale.value
  const roll = Math.random()
  if (nearTop && roll < 0.66) {
    startCeiling(timestamp)
    return
  }
  if (roll < 0.3) {
    startRest(timestamp, ['holdWall'], WALL_REST_MIN, WALL_REST_RANGE)
    pet.surface = 'wall'
    pet.state = 'wallHold'
    return
  }
  if (roll < 0.86) {
    startWallClimb(timestamp)
    return
  }
  startFall(timestamp, pet.wallSide === 'left' ? 2.2 : -2.2, -2)
}

function chooseCeilingBehavior(timestamp) {
  const roll = Math.random()
  if (roll < 0.52) {
    startRest(timestamp, ['holdCeiling'], WALL_REST_MIN, WALL_REST_RANGE)
    pet.surface = 'ceiling'
    pet.state = 'ceilingHold'
    return
  }
  if (roll < 0.88) {
    startCeilingCrawl(timestamp)
    return
  }
  startFall(timestamp, (Math.random() < 0.5 ? -1 : 1) * (2 + Math.random() * 2), 0.8)
}

function advancePose(elapsedTicks) {
  poseTicks.value += elapsedTicks
  const poses = currentAction.value.poses
  while (poseTicks.value >= currentPose.value.duration) {
    poseTicks.value -= currentPose.value.duration
    const nextIndex = poseIndex.value + 1
    if (nextIndex >= poses.length && !currentAction.value.loop) {
      setAction('stand')
      return
    }
    poseIndex.value = nextIndex % poses.length
  }
}

function moveByCurrentPose(elapsedTicks, targetX) {
  const distance = targetX - pet.anchorX
  if (Math.abs(distance) <= 2) {
    pet.anchorX = targetX
    return
  }

  pet.lookRight = distance > 0
  const directionMultiplier = pet.lookRight ? -1 : 1
  const vx = currentPose.value.velocity[0] * directionMultiplier * poseScale.value * Number(config.value.speed || 1)
  if (vx === 0) return

  const step = vx * elapsedTicks
  if (Math.sign(step) !== Math.sign(distance) || Math.abs(step) >= Math.abs(distance)) {
    pet.anchorX = targetX
    return
  }
  pet.anchorX += step
}

function moveWallByCurrentPose(elapsedTicks) {
  const distance = pet.targetY - pet.anchorY
  if (Math.abs(distance) <= 3) {
    pet.anchorY = pet.targetY
    return true
  }
  setAction(distance < 0 ? 'climbWallUp' : 'climbWallDown', performance.now(), { force: true })
  const vy = currentPose.value.velocity[1] * poseScale.value * Number(config.value.speed || 1)
  const step = vy * elapsedTicks
  if (!step || Math.sign(step) !== Math.sign(distance) || Math.abs(step) >= Math.abs(distance)) {
    pet.anchorY = pet.targetY
    return true
  }
  pet.anchorY += step
  return false
}

function moveCeilingByCurrentPose(elapsedTicks) {
  const distance = pet.targetX - pet.anchorX
  if (Math.abs(distance) <= 3) {
    pet.anchorX = pet.targetX
    return true
  }
  pet.lookRight = distance > 0
  const directionMultiplier = pet.lookRight ? -1 : 1
  const vx = currentPose.value.velocity[0] * directionMultiplier * poseScale.value * Number(config.value.speed || 1)
  const step = vx * elapsedTicks
  if (!step || Math.sign(step) !== Math.sign(distance) || Math.abs(step) >= Math.abs(distance)) {
    pet.anchorX = pet.targetX
    return true
  }
  pet.anchorX += step
  return false
}

function updateAir(elapsedTicks, timestamp) {
  const previousY = pet.anchorY
  pet.anchorX += pet.vx * elapsedTicks * poseScale.value
  pet.anchorY += pet.vy * elapsedTicks * poseScale.value
  pet.vx *= Math.pow(AIR_DRAG_X, elapsedTicks)
  pet.vy = pet.vy * Math.pow(AIR_DRAG_Y, elapsedTicks) + AIR_GRAVITY * elapsedTicks * Number(config.value.speed || 1)
  pet.lookRight = pet.vx > 0
  setAction(pet.vy < -0.4 ? 'jump' : 'fall', timestamp)

  const bounds = stageBounds()
  const leftX = wallAnchorX('left')
  const rightX = wallAnchorX('right')
  const highEnoughForWall = pet.anchorY < groundAnchorY() - 60 * poseScale.value

  if (pet.anchorX <= leftX) {
    pet.anchorX = leftX
    if (highEnoughForWall && pet.vx < 0) {
      startWall('left', timestamp, clampAnchorY(pet.anchorY))
      return
    }
    pet.vx = Math.abs(pet.vx) * 0.55
  }

  if (pet.anchorX >= rightX) {
    pet.anchorX = rightX
    if (highEnoughForWall && pet.vx > 0) {
      startWall('right', timestamp, clampAnchorY(pet.anchorY))
      return
    }
    pet.vx = -Math.abs(pet.vx) * 0.55
  }

  if (pet.anchorY <= ceilingAnchorY()) {
    pet.anchorY = ceilingAnchorY()
    if (pet.vy < 0 && Math.random() < 0.55) {
      startCeiling(timestamp)
      return
    }
    pet.vy = Math.abs(pet.vy) * 0.45
  }

  const landingY = pet.vy >= -0.2 ? crossedLandingY(previousY, pet.anchorY) : null
  if (landingY !== null) {
    setLaneY(landingY)
    pet.anchorX = Math.min(Math.max(pet.anchorX, leftX), rightX || bounds.width)
    pet.surface = 'ground'
    pet.state = 'bounce'
    pet.vx = 0
    pet.vy = 0
    setAction('bounce', timestamp, { force: true, duration: 520 })
    pet.stateUntil = timestamp + 520
  }
}

function animate(timestamp) {
  const elapsedMs = lastTick ? Math.min(timestamp - lastTick, 100) : SHIMEJI_TICK_MS
  const elapsedTicks = elapsedMs / SHIMEJI_TICK_MS
  lastTick = timestamp

  if (!pet.dragging) {
    const isMouseFresh = config.value.follow_mouse && mouse.active && timestamp < mouseActiveUntil
    const mouseTargetX = mouse.x
    if (isMouseFresh && pet.surface !== 'air') {
      pet.surface = 'ground'
      pet.state = 'groundMove'
      applyMouseYFollow(timestamp)
      pet.targetX = mouseTargetX
      roamPausedUntil = 0
    }

    if (pet.surface === 'air') {
      updateAir(elapsedTicks, timestamp)
      advancePose(elapsedTicks)
    } else if (pet.surface === 'wall') {
      pet.anchorX = wallAnchorX(pet.wallSide)
      if (pet.state === 'wallClimb') {
        const arrived = moveWallByCurrentPose(elapsedTicks)
        advancePose(elapsedTicks)
        pet.anchorY = clampAnchorY(pet.anchorY)
        if (arrived) {
          if (pet.anchorY <= ceilingAnchorY() + 8 * poseScale.value) {
            startCeiling(timestamp)
          } else {
            pet.state = 'wallHold'
            pet.stateUntil = timestamp + 1200 + Math.random() * 1800
            setAction('holdWall', timestamp, { force: true })
          }
        }
      } else {
        advancePose(elapsedTicks)
        if (timestamp >= pet.stateUntil) chooseWallBehavior(timestamp)
      }
    } else if (pet.surface === 'ceiling') {
      pet.anchorY = ceilingAnchorY()
      if (pet.state === 'ceilingCrawl') {
        const arrived = moveCeilingByCurrentPose(elapsedTicks)
        advancePose(elapsedTicks)
        pet.anchorX = clampAnchorX(pet.anchorX)
        if (arrived) {
          pet.state = 'ceilingHold'
          pet.stateUntil = timestamp + 1600 + Math.random() * 2200
          setAction('holdCeiling', timestamp, { force: true })
        }
      } else {
        advancePose(elapsedTicks)
        if (timestamp >= pet.stateUntil) chooseCeilingBehavior(timestamp)
      }
    } else {
      pet.surface = 'ground'
      setLaneY(pet.laneY || nearestLaneToY(pet.anchorY))
      const targetX = isMouseFresh ? mouseTargetX : pet.targetX
      const distance = Math.abs(targetX - pet.anchorX)

      if (pet.state === 'rest' && timestamp < pet.stateUntil) {
        advancePose(elapsedTicks)
      } else if (pet.state === 'bounce' && timestamp < pet.stateUntil) {
        advancePose(elapsedTicks)
      } else {
        if (pet.state === 'rest') {
          roamPausedUntil = 0
          chooseGroundBehavior(timestamp)
          advancePose(elapsedTicks)
          pet.anchorX = clampAnchorX(pet.anchorX)
          setLaneY(pet.laneY || nearestLaneToY(pet.anchorY))
          pet.lastAnchorX = pet.anchorX
          pet.lastAnchorY = pet.anchorY
          rafId = requestAnimationFrame(animate)
          return
        }
        if (distance <= 4) {
          if (pet.state === 'toWall') {
            startWall(pet.wallSide, timestamp, pet.anchorY)
          } else if (config.value.auto_roam && !isMouseFresh) {
            if (!roamPausedUntil) pauseBeforeNextRoam(timestamp)
            if (timestamp >= roamPausedUntil) {
              roamPausedUntil = 0
              chooseGroundBehavior(timestamp)
            } else {
              startRest(timestamp, REST_ACTIONS, Math.max(roamPausedUntil - timestamp, 900), 1)
            }
          } else {
            updateGroundAction(distance, timestamp, false)
          }
        } else {
          updateGroundAction(distance, timestamp, isMouseFresh && distance > FOLLOW_DEAD_ZONE)
          moveByCurrentPose(elapsedTicks, targetX)
        }
        advancePose(elapsedTicks)
      }
      pet.anchorX = clampAnchorX(pet.anchorX)
      setLaneY(pet.laneY || nearestLaneToY(pet.anchorY))
    }
  } else {
    advancePose(elapsedTicks)
  }

  pet.lastAnchorX = pet.anchorX
  pet.lastAnchorY = pet.anchorY
  rafId = requestAnimationFrame(animate)
}

function startLoops() {
  stopLoops()
  roamTimer = window.setInterval(() => {
    const canScheduleGroundBehavior =
      pet.surface === 'ground' && pet.state !== 'rest' && pet.state !== 'bounce' && pet.state !== 'toWall'
    if (config.value.auto_roam && !mouse.active && !pet.dragging && !roamPausedUntil && canScheduleGroundBehavior) {
      chooseGroundBehavior(performance.now())
    }
  }, ROAM_INTERVAL)
  rafId = requestAnimationFrame(animate)
}

function stopLoops() {
  if (roamTimer) window.clearInterval(roamTimer)
  if (rafId) cancelAnimationFrame(rafId)
  roamTimer = 0
  rafId = 0
  lastTick = 0
}

function updateMouse(event) {
  const rect = stageRef.value?.getBoundingClientRect()
  if (!rect) return
  updateMouseIntent(event.clientX - rect.left, event.clientY - rect.top)
  roamPausedUntil = 0
}

function leaveMouse() {
  mouse.active = false
  mouseActiveUntil = 0
}

function startDrag(event) {
  event.preventDefault()
  const stage = stageRef.value?.getBoundingClientRect()
  if (!stage) return
  pointerOffset = calculatePointerOffset(
    { x: event.clientX - stage.left, y: event.clientY - stage.top },
    { x: pet.anchorX, y: pet.anchorY },
  )
  pet.dragging = true
  setAction('drag')
  mascotRef.value?.setPointerCapture?.(event.pointerId)
}

function onDrag(event) {
  if (!pet.dragging) return
  const stage = stageRef.value?.getBoundingClientRect()
  if (!stage) return
  const anchor = calculateDragAnchor(
    { x: event.clientX - stage.left, y: event.clientY - stage.top },
    pointerOffset,
  )
  pet.anchorX = anchor.x
  pet.anchorY = anchor.y
  pet.lookRight = dragLookRight(pet.lookRight, event.movementX)
  pet.anchorX = clampAnchorX(pet.anchorX)
  pet.anchorY = clampAnchorY(pet.anchorY)
  pet.surface = 'air'
}

function endDrag(event) {
  if (!pet.dragging) return
  pet.dragging = false
  mascotRef.value?.releasePointerCapture?.(event.pointerId)
  roamPausedUntil = 0
  const release = resolveDragRelease(pet.anchorY, {
    groundY: groundAnchorY(),
    movementX: event.movementX,
    movementY: event.movementY,
    nearestLaneToY,
    scale: poseScale.value,
  })
  if (release.type === 'lane') {
    setLaneY(release.laneY)
    pet.lastAnchorY = pet.anchorY
    startGroundMove(performance.now())
  } else if (release.type === 'fall') {
    startFall(performance.now(), release.vx, release.vy)
  } else {
    setLaneY(release.laneY)
    pet.lastAnchorY = pet.anchorY
    startGroundMove(performance.now())
  }
}

function celebrate() {
  pet.surface = 'ground'
  pet.state = 'rest'
  setLaneY(pet.laneY || nearestLaneToY(pet.anchorY))
  setAction('split', performance.now(), { force: true })
  window.setTimeout(() => {
    pet.stateUntil = 0
    setAction('stand', performance.now(), { force: true })
  }, 1600)
}

watch(
  () => props.config,
  nextValue => {
    if (nextValue) config.value = cloneConfig(nextValue)
  },
  { deep: true },
)

onMounted(async () => {
  await nextTick()
  setLaneY(chooseLaneY(false))
  pet.lastAnchorY = pet.anchorY
  pickRoamTarget()
  startLoops()
  if (!props.config) {
    await loadStatus()
  }
})

onBeforeUnmount(() => {
  stopLoops()
})

defineExpose({
  loading,
  saving,
  config,
  loadStatus,
  saveConfig,
})
</script>

<template>
  <div class="agentmascot-shell">
    <div v-if="!hideTitle" class="agentmascot-header">
      <div class="agentmascot-title">
        <img :src="mascotIcon" alt="" />
        <div>
          <h2>Agent 桌宠</h2>
          <p>小天照 Shimeji demo</p>
        </div>
      </div>
      <div class="agentmascot-actions">
        <VBtn icon="mdi-refresh" variant="text" :loading="loading" @click="loadStatus" />
        <VBtn icon="mdi-content-save" variant="text" color="primary" :loading="saving" @click="saveConfig" />
      </div>
    </div>

    <VAlert v-if="error" type="error" variant="tonal" density="compact" class="mb-3">
      {{ error }}
    </VAlert>

    <div class="agentmascot-stage" :style="stageStyle" ref="stageRef" @pointermove="updateMouse" @pointerleave="leaveMouse">
      <div class="stage-grid"></div>
      <div class="stage-panel">
        <div class="panel-title">MoviePilot Agent</div>
        <div class="panel-copy">全屏游走、飞跃、爬墙、吸顶、鼠标跟随</div>
      </div>
      <button class="stage-chip" type="button" @click="celebrate">动作测试</button>

      <div
        ref="mascotRef"
        class="mascot"
        :class="{ 'mascot-shadow': config.shadow }"
        :style="petStyle"
        @pointerdown="startDrag"
        @pointermove="onDrag"
        @pointerup="endDrag"
        @pointercancel="endDrag"
        @dblclick="celebrate"
      >
        <img :src="currentFrame" alt="Agent mascot" draggable="false" />
      </div>
    </div>

    <div class="agentmascot-controls">
      <VSwitch v-model="config.enabled" label="启用插件" color="primary" hide-details />
      <VSwitch v-model="config.replace_agent_entry" label="替换智能体入口" color="primary" hide-details />
      <VSwitch v-model="config.show_sidebar_nav" label="侧栏入口" color="primary" hide-details />
      <VSwitch v-model="config.follow_mouse" label="跟随鼠标" color="primary" hide-details />
      <VSwitch v-model="config.auto_roam" label="自动游走" color="primary" hide-details />
      <VSwitch v-model="config.shadow" label="地面阴影" color="primary" hide-details />
      <div class="control-slider">
        <span>缩放</span>
        <VSlider v-model="config.scale" :min="0.6" :max="2" :step="0.05" hide-details color="primary" />
      </div>
      <div class="control-slider">
        <span>速度</span>
        <VSlider v-model="config.speed" :min="0.4" :max="2" :step="0.05" hide-details color="primary" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.agentmascot-shell {
  min-height: 100%;
  padding: 18px;
  color: rgb(var(--v-theme-on-surface));
}

.agentmascot-header,
.agentmascot-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
}

.agentmascot-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agentmascot-title img {
  width: 44px;
  height: 44px;
  object-fit: contain;
}

.agentmascot-title h2 {
  margin: 0;
  font-size: 1.35rem;
  line-height: 1.2;
}

.agentmascot-title p {
  margin: 2px 0 0;
  opacity: 0.72;
}

.agentmascot-actions {
  display: flex;
  gap: 4px;
}

.agentmascot-stage {
  position: relative;
  min-height: min(72vh, 760px);
  height: clamp(520px, 72vh, 820px);
  margin-top: 14px;
  overflow: hidden;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  background:
    radial-gradient(circle at 18% 12%, rgba(255, 241, 179, 0.34), transparent 28%),
    radial-gradient(circle at 74% 22%, rgba(111, 206, 194, 0.22), transparent 30%),
    linear-gradient(135deg, rgba(19, 30, 43, 0.94), rgba(42, 48, 54, 0.92));
  touch-action: none;
  user-select: none;
}

.stage-grid {
  position: absolute;
  inset: 0;
  opacity: 0.18;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.18) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.18) 1px, transparent 1px);
  background-size: 44px 44px;
}

.stage-panel {
  position: absolute;
  top: 22px;
  left: 22px;
  padding: 14px 16px;
  max-width: min(360px, calc(100% - 44px));
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 8px;
  color: #f8fafc;
  background: rgba(8, 13, 18, 0.76);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
}

.panel-title {
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.25;
}

.panel-copy {
  margin-top: 4px;
  font-size: 0.82rem;
  line-height: 1.4;
  color: #dbe5ea;
}

.stage-chip {
  position: absolute;
  top: 22px;
  right: 22px;
  height: 36px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 8px;
  color: #f9efd0;
  background: rgba(8, 13, 18, 0.44);
  cursor: pointer;
}

.mascot {
  position: absolute;
  top: 0;
  left: 0;
  width: var(--pet-size);
  height: var(--pet-size);
  display: grid;
  place-items: center;
  cursor: grab;
  will-change: transform;
  z-index: 3;
}

.mascot:active {
  cursor: grabbing;
}

.mascot img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: auto;
  pointer-events: none;
}

.mascot-shadow::after {
  content: '';
  position: absolute;
  left: 17%;
  right: 17%;
  bottom: 3px;
  height: 12px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.26);
  filter: blur(5px);
  transform: scaleX(var(--pet-facing, 1));
  z-index: -1;
}

.agentmascot-controls {
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
}

.control-slider {
  display: grid;
  grid-template-columns: 42px minmax(160px, 240px);
  align-items: center;
  gap: 10px;
}

.control-slider span {
  font-size: 0.9rem;
  opacity: 0.78;
}

@media (max-width: 720px) {
  .agentmascot-shell {
    padding: 12px;
  }

  .agentmascot-stage {
    height: 66vh;
    min-height: 430px;
  }

  .stage-panel {
    left: 12px;
    right: 12px;
  }

  .stage-chip {
    top: auto;
    right: 12px;
    bottom: 12px;
  }

  .control-slider {
    width: 100%;
    grid-template-columns: 42px 1fr;
  }
}
</style>
