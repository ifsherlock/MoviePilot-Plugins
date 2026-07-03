import { SHIMEJI_ACTIONS } from '../assets/shimeji/frames'
import {
  ACTION_MIN_DURATION,
  AIR_DRAG_X,
  AIR_DRAG_Y,
  AIR_GRAVITY,
  AIR_MIN_FALL_DISTANCE,
  AIR_MIN_FALL_DISTANCE_RATIO,
  DEFAULT_CONFIG,
  FOLLOW_DEAD_ZONE,
  GROUND_PADDING,
  MAX_GROUND_STEP,
  ROAM_INTERVAL,
  ROAM_REST_MIN,
  ROAM_REST_RANGE,
  RUN_DISTANCE,
  SHIMEJI_TICK_MS,
  VIEWPORT_PADDING,
  WALL_MARGIN,
  WALL_REST_MIN,
  WALL_REST_RANGE,
  normalizeConfig,
} from './config'
import {
  CEILING_REST_ACTIONS,
  GROUND_MOVE_ACTIONS,
  INTERRUPT_ACTIONS,
  REST_ACTIONS,
  WALL_REST_ACTIONS,
} from './actionCatalog'
import {
  CEILING_BEHAVIORS,
  GROUND_BEHAVIORS,
  WALL_BEHAVIORS,
  chooseWeightedBehavior,
  nextBehaviorCooldown,
  resolveMascotBehaviors,
} from './behaviors'
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
} from './geometry'
import {
  dragAnchor as calculateDragAnchor,
  dragDistance,
  dragLookRight,
  pointerOffset as calculatePointerOffset,
  resolveDragRelease,
} from './drag'
import {
  buildSurfaceLanes,
  chooseSurfaceLane,
  crossedSurfaceLane,
  nearestSurfaceLane,
} from './surfaces'
import {
  createActionState,
  createMouseState,
  createPetState,
  resolveAction,
  resolvePose,
} from './motion'
import {
  resolveMouseYFollow,
  updateMouseIntent as updateMouseIntentState,
} from './mouse'
import { resolveMascotImage } from './assets'

const BLOCKED_GROUND_ROAM_STATES = ['groundMove', 'rest', 'bounce', 'toWall']

function defaultScheduler() {
  return {
    setInterval: (...args) => globalThis.setInterval?.(...args),
    clearInterval: id => globalThis.clearInterval?.(id),
    setTimeout: (...args) => globalThis.setTimeout?.(...args),
    requestAnimationFrame: callback => globalThis.requestAnimationFrame?.(callback),
    cancelAnimationFrame: id => globalThis.cancelAnimationFrame?.(id),
  }
}

export function createMascotRuntime(options = {}) {
  let localConfig = normalizeConfig(options.config || DEFAULT_CONFIG)
  const scheduler = { ...defaultScheduler(), ...(options.scheduler || {}) }
  const now = options.now || (() => globalThis.performance?.now?.() || Date.now())
  const random = options.random || Math.random
  const boundsProvider = options.bounds || (() => ({ width: 720, height: 360 }))
  const getSurfaceLanes = options.getSurfaceLanes || (context => buildSurfaceLanes(context))
  const onUpdate = options.onUpdate || (() => {})
  const pet = options.pet || createPetState(options.initialPet)
  const mouse = options.mouse || createMouseState(options.initialMouse)
  const actionState = options.actionState || createActionState(options.initialAction)
  const viewportPadding = options.viewportPadding ?? 0

  let rafId = 0
  let roamTimer = 0
  let lastTick = 0
  let pointerOffset = { x: 0, y: 0 }
  let actionLockedUntil = 0
  let mouseActiveUntil = 0
  let roamPausedUntil = 0
  let dragStart = null
  let suppressClickUntil = 0

  function config() {
    return normalizeConfig(options.getConfig ? options.getConfig() : localConfig)
  }

  function currentAction() {
    return resolveAction(actionState, config().mascot)
  }

  function currentPose() {
    return resolvePose(actionState, config().mascot)
  }

  function currentFrame() {
    return resolveMascotImage(config().mascot, currentPose().imageName)
  }

  function petSize() {
    return calculatePetSize(config().scale)
  }

  function poseScale() {
    return calculatePoseScale(petSize())
  }

  function bounds() {
    return boundsProvider() || { width: 720, height: 360 }
  }

  function visualAnchor(pose = currentPose()) {
    return calculateVisualAnchor(pose, petSize(), poseScale(), pet.lookRight)
  }

  function groundAnchorY() {
    return calculateGroundAnchorY(bounds(), GROUND_PADDING, viewportPadding)
  }

  function ceilingAnchorY() {
    return calculateCeilingAnchorY(currentPose(), petSize(), poseScale(), pet.lookRight, viewportPadding)
  }

  function clampAnchorX(anchorX) {
    return calculateClampAnchorX(anchorX, bounds(), currentPose(), petSize(), poseScale(), pet.lookRight, viewportPadding)
  }

  function clampAnchorY(anchorY) {
    return calculateClampAnchorY(anchorY, bounds(), currentPose(), petSize(), poseScale(), pet.lookRight, GROUND_PADDING, viewportPadding)
  }

  function laneGap() {
    return calculateLaneGap(petSize())
  }

  function normalizeLaneY(anchorY) {
    return calculateNormalizeLaneY(anchorY, bounds(), currentPose(), petSize(), poseScale(), pet.lookRight, GROUND_PADDING, viewportPadding)
  }

  function surfaceContext() {
    return {
      bounds: bounds(),
      pose: currentPose(),
      size: petSize(),
      scale: poseScale(),
      lookRight: pet.lookRight,
      groundPadding: GROUND_PADDING,
      viewportPadding,
    }
  }

  function surfaceLanes(force = false) {
    return getSurfaceLanes(surfaceContext(), force)
  }

  function nearestLaneToY(anchorY) {
    return nearestSurfaceLane(anchorY, surfaceLanes(), groundAnchorY())
  }

  function chooseLaneY(preferCurrent = true) {
    return chooseSurfaceLane(surfaceLanes(), {
      current: pet.laneY || nearestLaneToY(pet.anchorY),
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
    const tolerance = Math.max(8 * poseScale(), 4)
    return crossedSurfaceLane(previousY, currentY, surfaceLanes(), tolerance)
  }

  function wallAnchorX(side) {
    return calculateWallAnchorX(side, bounds(), viewportPadding)
  }

  function wallApproachX(side) {
    return clampAnchorX(wallAnchorX(side))
  }

  function isAtWallApproach(side) {
    return Math.abs(pet.anchorX - wallApproachX(side)) < Math.max(12 * poseScale(), 8)
  }

  function randomGroundX() {
    return calculateRandomGroundX(bounds(), petSize(), viewportPadding)
  }

  function wallTargetY() {
    return calculateWallTargetY(
      bounds(),
      currentPose(),
      petSize(),
      poseScale(),
      pet.lookRight,
      GROUND_PADDING,
      viewportPadding,
      WALL_MARGIN,
    )
  }

  function clearAirFallState() {
    pet.airStartedAt = 0
    pet.airStartedY = null
    pet.minLandingY = null
  }

  function minimumFallDistance(anchorY) {
    const availableFall = Math.max(groundAnchorY() - anchorY, 0)
    const visibleFall = Math.max(AIR_MIN_FALL_DISTANCE, bounds().height * AIR_MIN_FALL_DISTANCE_RATIO)
    return Math.min(visibleFall, availableFall)
  }

  function startAirFallState(timestamp) {
    pet.airStartedAt = timestamp
    pet.airStartedY = pet.anchorY
    pet.minLandingY = pet.anchorY + minimumFallDistance(pet.anchorY)
  }

  function landingScanStartY(previousY) {
    if (pet.minLandingY === null || pet.minLandingY === undefined) return previousY
    if (pet.anchorY < pet.minLandingY) return null
    return Math.max(previousY, pet.minLandingY)
  }

  function setAction(nextAction, timestamp = now(), actionOptions = {}) {
    if (actionState.name === nextAction) return
    if (!actionOptions.force && timestamp < actionLockedUntil && !INTERRUPT_ACTIONS.includes(nextAction)) return
    actionState.name = nextAction
    actionState.poseIndex = 0
    actionState.poseTicks = 0
    actionLockedUntil = timestamp + (actionOptions.duration ?? ACTION_MIN_DURATION[nextAction] ?? 600)
  }

  function isRoamPaused(timestamp) {
    if (roamPausedUntil && timestamp >= roamPausedUntil) roamPausedUntil = 0
    return Boolean(roamPausedUntil)
  }

  function setBehavior(behavior, timestamp) {
    pet.behavior = behavior?.id || null
    pet.behaviorStartedAt = behavior ? timestamp : 0
    const cooldownUntil = nextBehaviorCooldown(behavior, timestamp)
    if (cooldownUntil) {
      pet.behaviorCooldowns = {
        ...(pet.behaviorCooldowns || {}),
        [behavior.id]: cooldownUntil,
      }
    }
  }

  function clearMoveStagnation() {
    pet.lastMoveDistance = null
    pet.stagnantMoveTicks = 0
  }

  function noteMoveProgress(distance) {
    if (distance <= 16) {
      clearMoveStagnation()
      return false
    }
    if (pet.lastMoveDistance !== null && distance >= pet.lastMoveDistance - 0.05) pet.stagnantMoveTicks += 1
    else pet.stagnantMoveTicks = 0
    pet.lastMoveDistance = distance
    return pet.stagnantMoveTicks > 180
  }

  function recoverGroundMove(timestamp) {
    clearMoveStagnation()
    pet.surface = 'ground'
    pet.state = 'rest'
    pet.targetX = pet.anchorX
    pet.targetY = pet.anchorY
    pet.stateUntil = timestamp + 1200
    roamPausedUntil = pet.stateUntil
    setAction('stand', timestamp, { force: true, duration: 700 })
  }

  function advancePose(elapsedTicks) {
    actionState.poseTicks += elapsedTicks
    const poses = currentAction().poses
    while (actionState.poseTicks >= currentPose().duration) {
      actionState.poseTicks -= currentPose().duration
      const nextIndex = actionState.poseIndex + 1
      if (nextIndex >= poses.length && !currentAction().loop) {
        setAction('stand')
        return
      }
      actionState.poseIndex = nextIndex % poses.length
    }
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
    if (GROUND_MOVE_ACTIONS.includes(actionState.name)) actionLockedUntil = 0
    setAction('stand', timestamp)
  }

  function startRest(timestamp, choices = REST_ACTIONS, min = ROAM_REST_MIN, range = ROAM_REST_RANGE) {
    const nextAction = choices[Math.floor(random() * choices.length)] || 'stand'
    const duration = min + random() * range
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
    roamPausedUntil = 0
    clearMoveStagnation()
    const shouldShiftLane = state === 'groundMove' && random() < 0.38
    setLaneY(chooseLaneY(!shouldShiftLane))
    pet.targetX = targetX ?? randomGroundX()
    updateGroundAction(Math.abs(pet.targetX - pet.anchorX), timestamp, false)
  }

  function startMoveToWall(timestamp, side = random() < 0.5 ? 'left' : 'right') {
    pet.surface = 'ground'
    pet.state = 'toWall'
    roamPausedUntil = 0
    pet.wallSide = side
    clearMoveStagnation()
    setLaneY(nearestLaneToY(pet.anchorY))
    pet.targetX = wallApproachX(side)
    setAction(Math.abs(pet.targetX - pet.anchorX) > RUN_DISTANCE ? 'run' : 'walk', timestamp, { force: true })
  }

  function startWall(side, timestamp, targetY = null) {
    pet.surface = 'wall'
    pet.state = 'wallHold'
    clearMoveStagnation()
    pet.wallSide = side
    pet.targetY = targetY ?? pet.anchorY
    pet.anchorX = wallAnchorX(side)
    pet.anchorY = clampAnchorY(pet.anchorY)
    pet.lookRight = side === 'right'
    setAction('holdWall', timestamp, { force: true, duration: WALL_REST_MIN })
    pet.stateUntil = timestamp + 1800 + random() * 3200
  }

  function startWallClimb(timestamp, targetY = null) {
    pet.surface = 'wall'
    pet.state = 'wallClimb'
    pet.targetY = targetY ?? (random() < 0.62 ? ceilingAnchorY() + 12 * poseScale() : wallTargetY())
    pet.anchorX = wallAnchorX(pet.wallSide)
    setAction(pet.targetY < pet.anchorY ? 'climbWallUp' : 'climbWallDown', timestamp, { force: true })
  }

  function startCeiling(timestamp, targetX = null) {
    pet.surface = 'ceiling'
    pet.state = 'ceilingHold'
    pet.anchorY = ceilingAnchorY()
    pet.targetX = targetX ?? randomGroundX()
    setAction('holdCeiling', timestamp, { force: true, duration: WALL_REST_MIN })
    pet.stateUntil = timestamp + WALL_REST_MIN + random() * WALL_REST_RANGE
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
    startAirFallState(timestamp)
    setAction(vy < 0 ? 'jump' : 'fall', timestamp, { force: true })
  }

  function startLeap(timestamp, side = random() < 0.5 ? 'left' : 'right') {
    const direction = side === 'left' ? -1 : 1
    pet.surface = 'air'
    pet.state = 'leap'
    roamPausedUntil = 0
    pet.wallSide = side
    pet.vx = direction * (7 + random() * 5.5) * Number(config().speed || 1)
    pet.vy = -(14 + random() * 9) * Number(config().speed || 1)
    clearAirFallState()
    setAction('jump', timestamp, { force: true })
  }

  function chooseGroundBehavior(timestamp) {
    const behavior = chooseWeightedBehavior(resolveMascotBehaviors('ground', GROUND_BEHAVIORS, config().mascot), {
      cooldowns: pet.behaviorCooldowns,
      random,
      timestamp,
    })
    setBehavior(behavior, timestamp)
    if (behavior?.id === 'rest') startRest(timestamp)
    else if (behavior?.id === 'roam') startGroundMove(timestamp)
    else if (behavior?.id === 'goWall') startMoveToWall(timestamp)
    else startLeap(timestamp)
  }

  function chooseWallBehavior(timestamp) {
    const nearTop = pet.anchorY <= ceilingAnchorY() + 56 * poseScale()
    const behavior = chooseWeightedBehavior(resolveMascotBehaviors('wall', WALL_BEHAVIORS, config().mascot), {
      cooldowns: pet.behaviorCooldowns,
      nearTop,
      random,
      timestamp,
    })
    setBehavior(behavior, timestamp)
    if (behavior?.id === 'goCeiling') startCeiling(timestamp)
    else if (behavior?.id === 'holdWall') startRest(timestamp, WALL_REST_ACTIONS, WALL_REST_MIN, WALL_REST_RANGE)
    else if (behavior?.id === 'climbWall') startWallClimb(timestamp)
    else startFall(timestamp, pet.wallSide === 'left' ? 2.2 : -2.2, -2)
  }

  function chooseCeilingBehavior(timestamp) {
    const behavior = chooseWeightedBehavior(resolveMascotBehaviors('ceiling', CEILING_BEHAVIORS, config().mascot), {
      cooldowns: pet.behaviorCooldowns,
      random,
      timestamp,
    })
    setBehavior(behavior, timestamp)
    if (behavior?.id === 'holdCeiling') startRest(timestamp, CEILING_REST_ACTIONS, WALL_REST_MIN, WALL_REST_RANGE)
    else if (behavior?.id === 'crawlCeiling') startCeilingCrawl(timestamp)
    else startFall(timestamp, (random() < 0.5 ? -1 : 1) * (2 + random() * 2), 0.8)
  }

  function moveByCurrentPose(elapsedTicks, targetX) {
    const distance = targetX - pet.anchorX
    if (Math.abs(distance) <= 2) {
      pet.anchorX = targetX
      return
    }
    pet.lookRight = distance > 0
    const directionMultiplier = pet.lookRight ? -1 : 1
    const vx = currentPose().velocity[0] * directionMultiplier * poseScale() * Number(config().speed || 1)
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
    setAction(distance < 0 ? 'climbWallUp' : 'climbWallDown', now(), { force: true })
    const vy = currentPose().velocity[1] * poseScale() * Number(config().speed || 1)
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
    const vx = currentPose().velocity[0] * directionMultiplier * poseScale() * Number(config().speed || 1)
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
    pet.anchorX += pet.vx * elapsedTicks * poseScale()
    pet.anchorY += pet.vy * elapsedTicks * poseScale()
    pet.vx *= Math.pow(AIR_DRAG_X, elapsedTicks)
    pet.vy = pet.vy * Math.pow(AIR_DRAG_Y, elapsedTicks) + AIR_GRAVITY * elapsedTicks * Number(config().speed || 1)
    pet.lookRight = pet.vx > 0
    setAction(pet.vy < -0.4 ? 'jump' : 'fall', timestamp)

    const leftX = wallAnchorX('left')
    const rightX = wallAnchorX('right')
    const highEnoughForWall = pet.anchorY < groundAnchorY() - 60 * poseScale()
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
      if (pet.vy < 0 && random() < 0.55) {
        startCeiling(timestamp)
        return
      }
      pet.vy = Math.abs(pet.vy) * 0.45
    }
    const scanStartY = pet.vy >= -0.2 ? landingScanStartY(previousY) : null
    const landingY = scanStartY === null ? null : crossedLandingY(scanStartY, pet.anchorY)
    if (landingY !== null) {
      setLaneY(landingY)
      pet.anchorX = Math.min(Math.max(pet.anchorX, leftX), rightX)
      pet.surface = 'ground'
      pet.state = 'bounce'
      pet.vx = 0
      pet.vy = 0
      clearAirFallState()
      setAction('bounce', timestamp, { force: true, duration: 520 })
      pet.stateUntil = timestamp + 520
    }
  }

  function applyMouseYFollow(timestamp) {
    const result = resolveMouseYFollow(mouse, pet, {
      active: mouse.active,
      activeUntil: mouseActiveUntil || mouse.activeUntil,
      followMouse: config().follow_mouse,
      laneGap: laneGap(),
      scale: poseScale(),
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

  function animate(timestamp) {
    const elapsedMs = lastTick ? Math.min(timestamp - lastTick, 100) : SHIMEJI_TICK_MS
    const elapsedTicks = elapsedMs / SHIMEJI_TICK_MS
    lastTick = timestamp

    if (!pet.dragging) {
      const isMouseFresh = config().follow_mouse && timestamp < (mouseActiveUntil || mouse.activeUntil)
      if (isMouseFresh && pet.surface !== 'air') {
        pet.surface = 'ground'
        pet.state = 'groundMove'
        applyMouseYFollow(timestamp)
        pet.targetX = mouse.x
        roamPausedUntil = 0
      }

      if (pet.surface === 'air') {
        updateAir(elapsedTicks, timestamp)
        advancePose(elapsedTicks)
      } else if (pet.surface === 'wall') {
        pet.anchorX = wallAnchorX(pet.wallSide)
        if (pet.state === 'wallClimb') {
          const arrived = moveWallByCurrentPose(elapsedTicks)
          pet.anchorY = clampAnchorY(pet.anchorY)
          if (arrived) {
            if (pet.anchorY <= ceilingAnchorY() + 8 * poseScale()) startCeiling(timestamp)
            else {
              pet.state = 'wallHold'
              pet.stateUntil = timestamp + 1200 + random() * 1800
              setAction('holdWall', timestamp, { force: true })
            }
          }
        } else if (timestamp >= pet.stateUntil) chooseWallBehavior(timestamp)
        advancePose(elapsedTicks)
      } else if (pet.surface === 'ceiling') {
        pet.anchorY = ceilingAnchorY()
        if (pet.state === 'ceilingCrawl') {
          const arrived = moveCeilingByCurrentPose(elapsedTicks)
          pet.anchorX = clampAnchorX(pet.anchorX)
          if (arrived) {
            pet.state = 'ceilingHold'
            pet.stateUntil = timestamp + 1600 + random() * 2200
            setAction('holdCeiling', timestamp, { force: true })
          }
        } else if (timestamp >= pet.stateUntil) chooseCeilingBehavior(timestamp)
        advancePose(elapsedTicks)
      } else {
        pet.surface = 'ground'
        setLaneY(pet.laneY || nearestLaneToY(pet.anchorY))
        const targetX = isMouseFresh ? mouse.x : pet.targetX
        const distance = Math.abs(targetX - pet.anchorX)
        if (pet.state === 'rest' && timestamp < pet.stateUntil) advancePose(elapsedTicks)
        else if (pet.state === 'bounce' && timestamp < pet.stateUntil) advancePose(elapsedTicks)
        else {
          if (pet.state === 'rest') {
            chooseGroundBehavior(timestamp)
            advancePose(elapsedTicks)
          } else {
            if (pet.state === 'bounce') startGroundMove(timestamp)
            moveByCurrentPose(elapsedTicks, targetX)
            const nextDistance = Math.abs(targetX - pet.anchorX)
            if (GROUND_MOVE_ACTIONS.includes(actionState.name) && noteMoveProgress(nextDistance)) {
              recoverGroundMove(timestamp)
              return
            }
            if (pet.state === 'toWall' && isAtWallApproach(pet.wallSide)) {
              startWall(pet.wallSide, timestamp)
              return
            }
            updateGroundAction(distance, timestamp, isMouseFresh)
            advancePose(elapsedTicks)
            if (Math.abs(targetX - pet.anchorX) < 3 && !isMouseFresh) {
              pet.anchorX = targetX
              if (pet.state === 'toWall') startWall(pet.wallSide, timestamp)
              else {
                pet.state = 'rest'
                pet.stateUntil = timestamp + ROAM_REST_MIN + random() * ROAM_REST_RANGE
                roamPausedUntil = pet.stateUntil
                setAction(random() < 0.5 ? 'stand' : 'sit', timestamp, { force: true })
              }
            }
          }
        }
      }
    } else {
      advancePose(elapsedTicks)
    }

    pet.anchorX = clampAnchorX(pet.anchorX)
    pet.anchorY = clampAnchorY(pet.anchorY)
    onUpdate()
    rafId = scheduler.requestAnimationFrame?.(animate) || 0
  }

  function start() {
    stop()
    setLaneY(chooseLaneY(false))
    pet.lastAnchorY = pet.anchorY
    pet.targetX = randomGroundX()
    roamTimer = scheduler.setInterval?.(() => {
      const canScheduleGroundBehavior = pet.surface === 'ground' && !BLOCKED_GROUND_ROAM_STATES.includes(pet.state)
      if (config().auto_roam && !pet.dragging && !isRoamPaused(now()) && canScheduleGroundBehavior) {
        chooseGroundBehavior(now())
      }
    }, ROAM_INTERVAL) || 0
    rafId = scheduler.requestAnimationFrame?.(animate) || 0
    onUpdate()
  }

  function stop() {
    if (roamTimer) scheduler.clearInterval?.(roamTimer)
    if (rafId) scheduler.cancelAnimationFrame?.(rafId)
    roamTimer = 0
    rafId = 0
    lastTick = 0
  }

  function updateConfig(nextConfig) {
    localConfig = normalizeConfig(nextConfig || DEFAULT_CONFIG)
    onUpdate()
  }

  function handlePointerMove(point, timestamp = now()) {
    mouse.active = true
    mouseActiveUntil = updateMouseIntentState(mouse, point, {
      anchorY: pet.anchorY,
      currentLaneY: pet.laneY || nearestLaneToY(pet.anchorY),
      nearestLaneToY,
      scale: poseScale(),
      timestamp,
    })
    mouse.activeUntil = mouseActiveUntil
    roamPausedUntil = 0
  }

  function handlePointerLeave() {
    mouse.active = false
    mouseActiveUntil = 0
    mouse.activeUntil = 0
  }

  function startDrag(point, timestamp = now()) {
    dragStart = point
    pointerOffset = calculatePointerOffset(point, { x: pet.anchorX, y: pet.anchorY })
    pet.dragging = true
    setAction('drag', timestamp, { force: true })
    onUpdate()
  }

  function moveDrag(point, movementX = 0) {
    if (!pet.dragging) return
    const anchor = calculateDragAnchor(point, pointerOffset)
    pet.anchorX = clampAnchorX(anchor.x)
    pet.anchorY = clampAnchorY(anchor.y)
    pet.lookRight = dragLookRight(pet.lookRight, movementX)
    pet.surface = 'air'
    onUpdate()
  }

  function endDrag(point, movementX = 0, movementY = 0, timestamp = now()) {
    if (!pet.dragging) return { moved: 0 }
    const moved = dragDistance(dragStart, point)
    dragStart = null
    pet.dragging = false
    if (moved > 4) suppressClickUntil = timestamp + 450
    roamPausedUntil = 0
    const release = resolveDragRelease(pet.anchorY, {
      groundY: groundAnchorY(),
      movementX,
      movementY,
      nearestLaneToY,
      scale: poseScale(),
    })
    if (release.type === 'lane') {
      setLaneY(release.laneY)
      pet.lastAnchorY = pet.anchorY
      startGroundMove(timestamp)
    } else if (release.type === 'fall') {
      startFall(timestamp, release.vx, release.vy)
    } else if (options.snapGroundOnDragRelease) {
      setLaneY(release.laneY)
      pet.lastAnchorY = pet.anchorY
      startGroundMove(timestamp)
    } else {
      startGroundMove(timestamp)
    }
    onUpdate()
    return { moved, release }
  }

  function celebrate(timestamp = now(), actionName = 'spinCelebrate') {
    pet.surface = 'ground'
    pet.state = 'rest'
    setLaneY(pet.laneY || nearestLaneToY(pet.anchorY))
    setAction(actionName, timestamp, { force: true })
    scheduler.setTimeout?.(() => {
      pet.stateUntil = 0
      setAction('stand', now(), { force: true })
      onUpdate()
    }, ACTION_MIN_DURATION[actionName] ?? ACTION_MIN_DURATION.split)
    onUpdate()
  }

  function clampToBounds() {
    pet.anchorX = clampAnchorX(pet.anchorX)
    pet.anchorY = clampAnchorY(pet.anchorY)
    onUpdate()
  }

  function renderState() {
    const pose = currentPose()
    const anchor = visualAnchor(pose)
    return {
      action: SHIMEJI_ACTIONS[actionState.name] ? actionState.name : 'stand',
      frame: currentFrame(),
      left: pet.anchorX - anchor.x,
      pose,
      size: petSize(),
      top: pet.anchorY - anchor.y,
    }
  }

  return {
    actionState,
    celebrate,
    clampToBounds,
    config,
    currentAction,
    currentFrame,
    currentPose,
    endDrag,
    handlePointerLeave,
    handlePointerMove,
    mouse,
    moveDrag,
    pet,
    petSize,
    renderState,
    shouldSuppressClick: (timestamp = now()) => pet.dragging || timestamp < suppressClickUntil,
    start,
    startDrag,
    stop,
    updateConfig,
  }
}
