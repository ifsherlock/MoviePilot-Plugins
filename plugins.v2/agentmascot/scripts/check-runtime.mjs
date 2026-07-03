import { createServer } from 'vite'

const failures = []

function fail(message) {
  failures.push(message)
}

function createFrameDriver() {
  let callback = null
  let intervalCallback = null
  return {
    scheduler: {
      setInterval: next => {
        intervalCallback = next
        return 1
      },
      clearInterval: () => {},
      setTimeout: callback => callback(),
      requestAnimationFrame: next => {
        callback = next
        return 1
      },
      cancelAnimationFrame: () => {},
    },
    tick(timestamp) {
      if (!callback) throw new Error('No animation frame callback registered')
      const next = callback
      callback = null
      next(timestamp)
    },
    triggerInterval() {
      if (!intervalCallback) throw new Error('No interval callback registered')
      intervalCallback()
    },
  }
}

function createSeededRandom(seed = 123456789) {
  let state = seed >>> 0
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0
    return state / 0x100000000
  }
}

async function loadRuntimeModules() {
  const server = await createServer({
    configFile: false,
    logLevel: 'silent',
    server: { middlewareMode: true },
  })
  try {
    const runtimeModule = await server.ssrLoadModule('/src/mascot/runtime.js')
    const motionModule = await server.ssrLoadModule('/src/mascot/motion.js')
    const behaviorModule = await server.ssrLoadModule('/src/mascot/behaviors.js')
    const semanticModule = await server.ssrLoadModule('/src/mascot/semanticActions.js')
    const actionLabModule = await server.ssrLoadModule('/src/mascot/actionLab.js')
    return {
      actionLab: actionLabModule,
      close: () => server.close(),
      behaviors: behaviorModule,
      createActionState: motionModule.createActionState,
      createMascotRuntime: runtimeModule.createMascotRuntime,
      createMouseState: motionModule.createMouseState,
      createPetState: motionModule.createPetState,
      semanticActions: semanticModule,
    }
  } catch (error) {
    await server.close()
    throw error
  }
}

function createFallRuntime(modules) {
  const bounds = { width: 720, height: 520 }
  const driver = createFrameDriver()
  const pet = modules.createPetState({
    anchorX: 320,
    anchorY: 150,
    laneY: 150,
    targetX: 320,
    targetY: 150,
  })
  const runtime = modules.createMascotRuntime({
    actionState: modules.createActionState(),
    bounds: () => bounds,
    getConfig: () => ({
      enabled: true,
      mascot: 'nailong',
      scale: 1,
      speed: 1,
      follow_mouse: false,
      auto_roam: false,
      shadow: true,
      replace_agent_entry: true,
      show_sidebar_nav: true,
    }),
    getSurfaceLanes: () => [170, bounds.height - 18],
    mouse: modules.createMouseState({ active: false }),
    pet,
    scheduler: driver.scheduler,
    snapGroundOnDragRelease: false,
  })
  return { driver, pet, runtime }
}

function createWallRuntime(modules, side) {
  const bounds = { width: 720, height: 520 }
  const driver = createFrameDriver()
  const randomValues = [0.85, side === 'left' ? 0.25 : 0.75]
  const pet = modules.createPetState({
    anchorX: side === 'left' ? 360 : 180,
    anchorY: bounds.height - 18,
    laneY: bounds.height - 18,
    targetX: side === 'left' ? 120 : 600,
    targetY: bounds.height - 18,
  })
  const runtime = modules.createMascotRuntime({
    actionState: modules.createActionState(),
    bounds: () => bounds,
    getConfig: () => ({
      enabled: true,
      mascot: 'nailong',
      scale: 1,
      speed: 1,
      follow_mouse: false,
      auto_roam: true,
      shadow: true,
      replace_agent_entry: true,
      show_sidebar_nav: true,
    }),
    getSurfaceLanes: () => [bounds.height - 18],
    mouse: modules.createMouseState({ active: false }),
    pet,
    random: () => randomValues.shift() ?? 0.5,
    scheduler: driver.scheduler,
    snapGroundOnDragRelease: false,
  })
  return { driver, pet, runtime }
}

function createRoamRuntime(modules) {
  const bounds = { width: 900, height: 620 }
  const driver = createFrameDriver()
  const pet = modules.createPetState({
    anchorX: 420,
    anchorY: bounds.height - 18,
    laneY: bounds.height - 18,
    targetX: 620,
    targetY: bounds.height - 18,
  })
  const runtime = modules.createMascotRuntime({
    actionState: modules.createActionState(),
    bounds: () => bounds,
    getConfig: () => ({
      enabled: true,
      mascot: 'kurisu',
      scale: 1,
      speed: 1,
      follow_mouse: false,
      auto_roam: true,
      shadow: true,
      replace_agent_entry: true,
      show_sidebar_nav: true,
    }),
    getSurfaceLanes: () => [190, 310, 430, bounds.height - 18],
    mouse: modules.createMouseState({ active: false }),
    pet,
    random: createSeededRandom(20260704),
    scheduler: driver.scheduler,
    snapGroundOnDragRelease: false,
  })
  return { bounds, driver, pet, runtime }
}

function assertFinitePet(pet, label) {
  for (const key of ['anchorX', 'anchorY', 'targetX', 'targetY', 'vx', 'vy']) {
    if (!Number.isFinite(pet[key])) fail(`${label}: pet.${key} is not finite: ${pet[key]}`)
  }
}

function assertWithinBounds(pet, bounds, label) {
  const horizontalSlack = 4
  const verticalSlack = 4
  if (pet.anchorX < -horizontalSlack || pet.anchorX > bounds.width + horizontalSlack) {
    fail(`${label}: anchorX out of bounds: ${pet.anchorX}`)
  }
  if (pet.anchorY < -verticalSlack || pet.anchorY > bounds.height + verticalSlack) {
    fail(`${label}: anchorY out of bounds: ${pet.anchorY}`)
  }
}

function runFallVisibilityCheck(modules) {
  const { driver, pet, runtime } = createFallRuntime(modules)
  runtime.start()
  pet.anchorX = 320
  pet.anchorY = 150
  pet.laneY = 150

  runtime.startDrag({ x: pet.anchorX, y: pet.anchorY }, 0)
  runtime.endDrag({ x: pet.anchorX, y: pet.anchorY + 24 }, 0, 0, 0)

  if (pet.surface !== 'air' || pet.state !== 'fall') {
    fail(`Expected drag release to start fall, got surface=${pet.surface} state=${pet.state}`)
    runtime.stop()
    return
  }

  const startY = pet.airStartedY
  const minLandingY = pet.minLandingY
  if (!Number.isFinite(startY) || !Number.isFinite(minLandingY) || minLandingY <= startY) {
    fail(`Invalid fall gate: startY=${startY} minLandingY=${minLandingY}`)
    runtime.stop()
    return
  }

  let crossedEarlyLane = false
  let landedBeforeGate = false
  let maxAirY = pet.anchorY

  for (let tick = 1; tick <= 240; tick += 1) {
    driver.tick(tick * 33)
    maxAirY = Math.max(maxAirY, pet.anchorY)
    if (pet.anchorY >= 170) crossedEarlyLane = true
    if (pet.surface !== 'air') {
      landedBeforeGate = pet.anchorY < minLandingY - 0.1
      break
    }
  }

  if (!crossedEarlyLane) fail('Fall simulation never crossed the near landing lane')
  if (landedBeforeGate) fail(`Fall landed before minimum gate: landedY=${pet.anchorY} minLandingY=${minLandingY}`)
  if (maxAirY < minLandingY) fail(`Fall did not remain airborne until visible gate: maxAirY=${maxAirY} minLandingY=${minLandingY}`)
  if (pet.surface !== 'ground' || pet.state !== 'bounce') {
    fail(`Fall did not eventually land into bounce: surface=${pet.surface} state=${pet.state}`)
  }
  if (Math.abs(pet.anchorY - (520 - 18)) > 0.1) {
    fail(`Fall should land on ground lane after ignoring near lane: anchorY=${pet.anchorY}`)
  }

  runtime.stop()
}

function runWallApproachCheck(modules, side) {
  const { driver, pet, runtime } = createWallRuntime(modules, side)
  runtime.start()
  pet.anchorX = side === 'left' ? 360 : 180
  pet.anchorY = 520 - 18
  pet.laneY = 520 - 18
  pet.surface = 'ground'
  pet.state = 'stand'
  runtime.handlePointerLeave()
  driver.triggerInterval()

  for (let tick = 1; tick <= 260; tick += 1) {
    driver.tick(tick * 33)
    if (pet.surface === 'wall' && pet.state === 'wallHold') break
  }

  if (pet.surface !== 'wall' || pet.state !== 'wallHold') {
    fail(`Expected ${side} wall approach to reach wallHold, got surface=${pet.surface} state=${pet.state} anchorX=${pet.anchorX} targetX=${pet.targetX}`)
  }
  if (pet.wallSide !== side) {
    fail(`Expected wallSide=${side}, got ${pet.wallSide}`)
  }

  runtime.stop()
}

function runLongRoamCheck(modules) {
  const { bounds, driver, pet, runtime } = createRoamRuntime(modules)
  runtime.start()

  let stagnantMoveTicks = 0
  let previousDistance = Math.abs(pet.targetX - pet.anchorX)

  for (let tick = 1; tick <= 3600; tick += 1) {
    if (tick % 157 === 1) driver.triggerInterval()
    driver.tick(tick * 33)
    assertFinitePet(pet, `long roam tick ${tick}`)
    assertWithinBounds(pet, bounds, `long roam tick ${tick}`)

    if (['groundMove', 'toWall'].includes(pet.state)) {
      const distance = Math.abs(pet.targetX - pet.anchorX)
      if (distance > 16 && distance >= previousDistance - 0.05) stagnantMoveTicks += 1
      else stagnantMoveTicks = 0
      previousDistance = distance
      if (stagnantMoveTicks > 180) {
        fail(`Long roam appears stuck in ${pet.state}: anchorX=${pet.anchorX} targetX=${pet.targetX} distance=${distance}`)
        break
      }
    } else {
      stagnantMoveTicks = 0
      previousDistance = Math.abs(pet.targetX - pet.anchorX)
    }
  }

  runtime.stop()
}

function runBehaviorSelectionCheck(modules) {
  const {
    GROUND_BEHAVIORS,
    chooseWeightedBehavior,
    nextBehaviorCooldown,
    resolveMascotBehaviors,
  } = modules.behaviors
  const samples = [
    chooseWeightedBehavior(GROUND_BEHAVIORS, { random: () => 0.1 })?.id,
    chooseWeightedBehavior(GROUND_BEHAVIORS, { random: () => 0.5 })?.id,
    chooseWeightedBehavior(GROUND_BEHAVIORS, { random: () => 0.92 })?.id,
    chooseWeightedBehavior(GROUND_BEHAVIORS, { random: () => 0.98 })?.id,
  ]
  const expected = ['rest', 'roam', 'goWall', 'leap']
  for (let index = 0; index < expected.length; index += 1) {
    if (samples[index] !== expected[index]) {
      fail(`Behavior selection mismatch at ${index}: expected ${expected[index]}, got ${samples[index]}`)
    }
  }
  const goWall = GROUND_BEHAVIORS.find(behavior => behavior.id === 'goWall')
  const cooldownUntil = nextBehaviorCooldown(goWall, 1000)
  const cooledSample = chooseWeightedBehavior(GROUND_BEHAVIORS, {
    cooldowns: { goWall: cooldownUntil },
    random: () => 0.92,
    timestamp: 1001,
  })?.id
  if (cooledSample === 'goWall') fail('Behavior cooldown did not suppress goWall')

  const nailongGround = resolveMascotBehaviors('ground', GROUND_BEHAVIORS, 'nailong')
  const kurisuGround = resolveMascotBehaviors('ground', GROUND_BEHAVIORS, 'kurisu')
  const nailongLeap = nailongGround.find(behavior => behavior.id === 'leap')?.weight
  const kurisuRest = kurisuGround.find(behavior => behavior.id === 'rest')?.weight
  if (nailongLeap !== 10) fail(`Expected nailong leap weight 10, got ${nailongLeap}`)
  if (kurisuRest !== 52) fail(`Expected kurisu rest weight 52, got ${kurisuRest}`)
}

function runSemanticActionCheck(modules) {
  const {
    FEATURE_SEMANTIC_ACTIONS,
    REQUIRED_SEMANTIC_ACTIONS,
    semanticActionFrames,
  } = modules.semanticActions
  for (const mascot of ['chibiterasu', 'nailong', 'kurisu']) {
    for (const name of REQUIRED_SEMANTIC_ACTIONS) {
      const frames = semanticActionFrames(mascot, name)
      if (!frames.length) fail(`Missing required semantic action ${name} for ${mascot}`)
    }
  }
  for (const [mascot, names] of Object.entries(FEATURE_SEMANTIC_ACTIONS)) {
    for (const name of names) {
      const frames = semanticActionFrames(mascot, name)
      if (!frames.length) fail(`Missing feature semantic action ${name} for ${mascot}`)
    }
  }
  const kurisuJump = semanticActionFrames('kurisu', 'jump')
  const kurisuLand = semanticActionFrames('kurisu', 'land')
  const kurisuThink = semanticActionFrames('kurisu', 'think')
  const kurisuSurprise = semanticActionFrames('kurisu', 'surprise')
  const kurisuCheer = semanticActionFrames('kurisu', 'cheer')
  const kurisuSpinCelebrate = semanticActionFrames('kurisu', 'spinCelebrate')
  if (kurisuJump.includes('shime22') || kurisuJump.includes('shime4')) {
    fail(`Kurisu jump should not use fall/land slots: ${kurisuJump.join(',')}`)
  }
  if (!kurisuLand.includes('shime18') || !kurisuLand.includes('shime41')) {
    fail(`Kurisu land should include landing recovery frames: ${kurisuLand.join(',')}`)
  }
  if (!['shime11', 'shime26', 'shime57', 'shime56'].every(frame => kurisuThink.includes(frame))) {
    fail(`Kurisu think should use the explicit think frame group: ${kurisuThink.join(',')}`)
  }
  if (!['shime15', 'shime16', 'shime17', 'shime27'].every(frame => kurisuSurprise.includes(frame))) {
    fail(`Kurisu surprise should use the explicit surprise frame group: ${kurisuSurprise.join(',')}`)
  }
  if (!['shime28', 'shime29', 'shime34', 'shime35'].every(frame => kurisuCheer.includes(frame))) {
    fail(`Kurisu cheer should use only cheer frames: ${kurisuCheer.join(',')}`)
  }
  if (kurisuCheer.some(frame => kurisuSpinCelebrate.includes(frame))) {
    fail(`Kurisu cheer and spinCelebrate should not share frame slots: cheer=${kurisuCheer.join(',')} spin=${kurisuSpinCelebrate.join(',')}`)
  }
  if (!['shime43', 'shime44', 'shime45', 'shime46', 'shime53', 'shime54', 'shime55', 'shime58'].every(frame => kurisuSpinCelebrate.includes(frame))) {
    fail(`Kurisu spinCelebrate should use the explicit spin frame group: ${kurisuSpinCelebrate.join(',')}`)
  }
}

function runPreviewControlCheck(modules) {
  const { bounds, driver, pet, runtime } = createRoamRuntime(modules)
  runtime.start()

  const actionChecks = [
    ['idle', 'stand'],
    ['walk', 'walk'],
    ['run', 'run'],
    ['jump', 'jump'],
    ['fall', 'fall'],
    ['drag', 'drag'],
    ['sleep', 'lie'],
    ['think', 'think'],
  ]

  for (let index = 0; index < actionChecks.length; index += 1) {
    const [semanticName, expectedAction] = actionChecks[index]
    runtime.playAction(semanticName, { timestamp: 5000 + index * 250, duration: 800 })
    const state = runtime.debugState()
    if (state.action !== expectedAction) {
      fail(`Preview playAction(${semanticName}) expected action=${expectedAction}, got ${state.action}`)
    }
    if (!Number.isFinite(state.actionLockedUntil) || state.actionLockedUntil <= 0) {
      fail(`Preview playAction(${semanticName}) did not set a finite action lock`)
    }
  }

  const behaviorResult = runtime.playBehavior('goWall', { timestamp: 9000 })
  if (!behaviorResult.applied || pet.state !== 'toWall') {
    fail(`Preview playBehavior(goWall) should enter toWall, got applied=${behaviorResult.applied} state=${pet.state}`)
  }

  runtime.resetPose(10000)
  const resetState = runtime.debugState()
  if (resetState.surface !== 'ground' || resetState.state !== 'rest' || resetState.action !== 'stand') {
    fail(`Preview resetPose should restore ground rest stand, got ${JSON.stringify(resetState)}`)
  }

  for (let tick = 1; tick <= 120; tick += 1) {
    driver.tick(10000 + tick * 33)
    assertFinitePet(pet, `preview control tick ${tick}`)
    assertWithinBounds(pet, bounds, `preview control tick ${tick}`)
  }

  runtime.stop()
}

function runActionLabCheck(modules) {
  const forbiddenLabels = ['split', 'pullOut', 'shime']
  for (const mascot of ['chibiterasu', 'nailong', 'kurisu']) {
    const groups = modules.actionLab.actionLabGroupsForMascot(mascot)
    const items = groups.flatMap(group => group.items)
    for (const item of items) {
      if (!item.label || forbiddenLabels.some(name => item.label.includes(name))) {
        fail(`ActionLab exposes an implementation label for ${mascot}: ${item.label || '<empty>'}`)
      }
    }
    for (const required of ['idle', 'walk', 'run', 'jump', 'fall', 'drag', 'sleep']) {
      if (!items.some(item => item.kind === 'action' && item.id === required)) {
        fail(`ActionLab missing ${required} action for ${mascot}`)
      }
    }
  }

  const kurisuItems = modules.actionLab.actionLabGroupsForMascot('kurisu').flatMap(group => group.items)
  for (const feature of ['think', 'surprise', 'cheer', 'spinCelebrate']) {
    if (!kurisuItems.some(item => item.kind === 'action' && item.id === feature)) {
      fail(`ActionLab missing Kurisu feature action: ${feature}`)
    }
  }
}

const modules = await loadRuntimeModules()
try {
  runFallVisibilityCheck(modules)
  runWallApproachCheck(modules, 'left')
  runWallApproachCheck(modules, 'right')
  runLongRoamCheck(modules)
  runBehaviorSelectionCheck(modules)
  runSemanticActionCheck(modules)
  runPreviewControlCheck(modules)
  runActionLabCheck(modules)
} finally {
  await modules.close()
}

if (failures.length) {
  console.error('[AgentMascot] runtime validation failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log('[AgentMascot] runtime validation passed: fall visibility gate, wall approach, long roam guards, behavior selection, semantic actions, preview controls, action lab')
