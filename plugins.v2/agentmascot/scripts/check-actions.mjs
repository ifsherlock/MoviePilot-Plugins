import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const pluginRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sourceRoot = path.join(pluginRoot, 'src')
const shimejiRoot = path.join(sourceRoot, 'assets', 'shimeji')
const requiredCatalogKeys = ['ground', 'air', 'wall', 'ceiling', 'drag', 'rest', 'special']
const failures = []

function fail(message) {
  failures.push(message)
}

async function readSource(relativePath) {
  return fs.readFile(path.join(sourceRoot, relativePath), 'utf8')
}

function splitArgs(input) {
  const args = []
  let current = ''
  let bracketDepth = 0
  let quote = ''

  for (const char of input) {
    if (quote) {
      current += char
      if (char === quote) quote = ''
      continue
    }
    if (char === '\'' || char === '"') {
      quote = char
      current += char
      continue
    }
    if (char === '[') bracketDepth += 1
    if (char === ']') bracketDepth -= 1
    if (char === ',' && bracketDepth === 0) {
      args.push(current.trim())
      current = ''
      continue
    }
    current += char
  }

  if (current.trim()) args.push(current.trim())
  return args
}

function parseString(value) {
  const match = value?.match(/^['"]([^'"]+)['"]$/)
  return match?.[1] || ''
}

function parseNumberArray(value) {
  const match = value?.match(/^\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]$/)
  if (!match) return null
  return [Number(match[1]), Number(match[2])]
}

function collectAnchors(source) {
  const anchors = new Map()
  const pattern = /export const ([A-Z0-9_]+_ANCHOR) = (\[[^\]]+\])/g
  for (const match of source.matchAll(pattern)) {
    const value = parseNumberArray(match[2])
    if (!value) fail(`Invalid anchor constant ${match[1]}: ${match[2]}`)
    else anchors.set(match[1], value)
  }
  return anchors
}

function collectActionNames(source) {
  return new Set([...source.matchAll(/^  ([A-Za-z]\w*): \{/gm)].map(match => match[1]))
}

function collectCatalog(source) {
  const categories = new Map()
  const pattern = /^  (\w+): \[([^\]]*)\],$/gm
  for (const match of source.matchAll(pattern)) {
    const names = [...match[2].matchAll(/'([^']+)'/g)].map(nameMatch => nameMatch[1])
    categories.set(match[1], names)
  }
  return categories
}

async function collectAssets(source) {
  const assets = new Map()
  const pattern = /^import (shime\d+) from '\.\.\/assets\/shimeji\/(shime\d+\.png)'$/gm
  for (const match of source.matchAll(pattern)) {
    const variableName = match[1]
    const fileName = match[2]
    if (`${variableName}.png` !== fileName) {
      fail(`Asset import mismatch: ${variableName} -> ${fileName}`)
      continue
    }
    assets.set(variableName, fileName)
  }

  for (let index = 1; index <= 66; index += 1) {
    const imageName = `shime${index}`
    const fileName = `${imageName}.png`
    if (!assets.has(imageName)) fail(`Missing SHIMEJI_IMAGES import for ${imageName}`)
    try {
      await fs.access(path.join(shimejiRoot, fileName))
    } catch {
      fail(`Missing shimeji image file: ${fileName}`)
    }
  }

  return assets
}

function resolveAnchor(value, anchors) {
  if (!value) return anchors.get('GROUND_FOOT_ANCHOR') || null
  if (anchors.has(value)) return anchors.get(value)
  return parseNumberArray(value)
}

function validatePoses(source, assets, anchors) {
  const posePattern = /pose\(([^)]*)\)/g
  let count = 0

  for (const match of source.matchAll(posePattern)) {
    count += 1
    const args = splitArgs(match[1])
    const imageName = parseString(args[0])
    if (!imageName) fail(`Pose #${count} has invalid image argument: ${args[0] || '<missing>'}`)
    else if (!assets.has(imageName)) fail(`Pose #${count} references missing image: ${imageName}`)

    const anchor = resolveAnchor(args[1], anchors)
    if (!anchor || !anchor.every(Number.isFinite)) {
      fail(`Pose #${count} has invalid anchor: ${args[1] || '<default>'}`)
    }

    const velocity = parseNumberArray(args[2] || '[0, 0]')
    if (!velocity || !velocity.every(Number.isFinite)) {
      fail(`Pose #${count} has invalid velocity: ${args[2] || '<default>'}`)
    }

    const duration = Number(args[3] || 250)
    if (!Number.isFinite(duration) || duration <= 0) {
      fail(`Pose #${count} has invalid duration: ${args[3] || '<default>'}`)
    }
  }

  if (count === 0) fail('No pose() calls found in actions.js')
  return count
}

function validateCatalog(categories, actionNames) {
  for (const key of requiredCatalogKeys) {
    if (!categories.has(key)) {
      fail(`ACTION_CATALOG is missing category: ${key}`)
      continue
    }
    if (categories.get(key).length === 0) fail(`ACTION_CATALOG.${key} is empty`)
  }

  for (const [category, names] of categories) {
    for (const name of names) {
      if (!actionNames.has(name)) fail(`ACTION_CATALOG.${category} references unknown action: ${name}`)
    }
  }
}

const [assetsSource, actionsSource, anchorsSource, catalogSource] = await Promise.all([
  readSource('mascot/assets.js'),
  readSource('mascot/actions.js'),
  readSource('mascot/anchors.js'),
  readSource('mascot/actionCatalog.js'),
])

const assets = await collectAssets(assetsSource)
const anchors = collectAnchors(anchorsSource)
const actionNames = collectActionNames(actionsSource)
const categories = collectCatalog(catalogSource)
const poseCount = validatePoses(actionsSource, assets, anchors)
validateCatalog(categories, actionNames)

if (failures.length) {
  console.error('[AgentMascot] asset/action validation failed')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log(`[AgentMascot] asset/action validation passed: ${assets.size} images, ${actionNames.size} actions, ${poseCount} poses`)
