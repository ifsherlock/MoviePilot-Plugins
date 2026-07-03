import {
  DEFAULT_CONFIG,
  VIEWPORT_PADDING,
} from '../mascot/config'
import {
  createMoviePilotAgentEntry,
  nativeAgentEntryStyle,
} from '../adapters/moviepilotAgentEntry'
import { createGlobalDomAdapter } from '../adapters/globalDomAdapter'
import { loadMoviePilotPluginConfig } from '../adapters/moviepilotAuth'
import { createMascotRuntime } from '../mascot/runtime'

const PLUGIN_ID = 'AgentMascot'
const HIDDEN_CLASS = 'agentmascot-native-hidden'
const CONFIG_POLL_MS = 15000

export function startAgentMascotPatchEntry(env = globalThis) {
  if (env.__AgentMascotGlobalLoaderStarted) return null
  env.__AgentMascotGlobalLoaderStarted = true

  let config = { ...DEFAULT_CONFIG }
  let configTimer = 0
  let mounted = false
  let runtime = null
  const isEnabled = () => Boolean(config.enabled && config.replace_agent_entry)
  const agentEntry = createMoviePilotAgentEntry({
    env,
    hiddenClass: HIDDEN_CLASS,
    isEnabled,
  })
  const adapter = createGlobalDomAdapter({
    agentEntry,
    env,
    getRuntime: () => runtime,
    nativeEntryStyle: nativeAgentEntryStyle(HIDDEN_CLASS),
  })

  runtime = createMascotRuntime({
    bounds: adapter.bounds,
    getConfig: () => config,
    getSurfaceLanes: adapter.collectSurfaceLanes,
    initialPet: {
      anchorX: 180,
      anchorY: 180,
      targetX: 360,
      targetY: 180,
      laneY: 180,
    },
    onUpdate: adapter.render,
    scheduler: {
      setInterval: (...args) => env.setInterval(...args),
      clearInterval: id => env.clearInterval(id),
      setTimeout: (...args) => env.setTimeout(...args),
      requestAnimationFrame: callback => env.requestAnimationFrame(callback),
      cancelAnimationFrame: id => env.cancelAnimationFrame(id),
    },
    viewportPadding: VIEWPORT_PADDING,
  })

  async function loadConfig() {
    config = await loadMoviePilotPluginConfig(PLUGIN_ID, { env })
    runtime.updateConfig(config)
    return config
  }

  function mount() {
    if (mounted) {
      agentEntry.hide()
      return
    }
    adapter.mount()
    agentEntry.startObserver()
    agentEntry.hide()
    runtime.start()
    mounted = true
  }

  function unmount() {
    if (!mounted) return
    runtime.stop()
    agentEntry.destroy()
    adapter.unmount()
    mounted = false
  }

  async function syncFromConfig() {
    try {
      await loadConfig()
      if (isEnabled()) {
        mount()
        agentEntry.hide()
        adapter.render()
      } else {
        unmount()
      }
    } catch (error) {
      console.debug('[AgentMascot] 全局入口配置读取失败', error)
    }
  }

  syncFromConfig()
  configTimer = env.setInterval(syncFromConfig, CONFIG_POLL_MS)
  env.addEventListener('resize', adapter.onResize)

  return {
    stop() {
      env.clearInterval(configTimer)
      env.removeEventListener('resize', adapter.onResize)
      unmount()
    },
  }
}
