import { createServer } from 'vite'

const failures = []

function fail(message) {
  failures.push(message)
}

function createFrameDriver() {
  let callback = null
  return {
    scheduler: {
      setInterval: () => 0,
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
    return {
      close: () => server.close(),
      createActionState: motionModule.createActionState,
      createMascotRuntime: runtimeModule.createMascotRuntime,
      createMouseState: motionModule.createMouseState,
      createPetState: motionModule.createPetState,
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

const modules = await loadRuntimeModules()
try {
  runFallVisibilityCheck(modules)
} finally {
  await modules.close()
}

if (failures.length) {
  console.error('[AgentMascot] runtime validation failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log('[AgentMascot] runtime validation passed: fall visibility gate')
