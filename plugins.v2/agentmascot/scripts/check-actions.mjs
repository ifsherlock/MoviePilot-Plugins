import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const pluginRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sourceRoot = path.join(pluginRoot, 'src')
const shimejiRoot = path.join(sourceRoot, 'assets', 'shimeji')
const kurisuRoot = path.join(sourceRoot, 'assets', 'kurisu', 'frames')
const nailongRoot = path.join(sourceRoot, 'assets', 'nailong', 'frames')
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
  const actionsStart = source.indexOf('export const SHIMEJI_ACTIONS = {')
  const overridesStart = source.indexOf('const CUSTOM_STAND = {')
  const actionsSource = source.slice(actionsStart, overridesStart > actionsStart ? overridesStart : undefined)
  return new Set([...actionsSource.matchAll(/^  ([A-Za-z]\w*): \{/gm)].map(match => match[1]))
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

async function readPngInfo(filePath) {
  const data = await fs.readFile(filePath)
  if (data.toString('ascii', 1, 4) !== 'PNG') {
    fail(`Not a PNG file: ${filePath}`)
    return null
  }
  const width = data.readUInt32BE(16)
  const height = data.readUInt32BE(20)
  const bitDepth = data.readUInt8(24)
  const colorType = data.readUInt8(25)
  return { bitDepth, colorType, data, height, width }
}

function eachPngChunk(data, callback) {
  let offset = 8
  while (offset < data.length) {
    const length = data.readUInt32BE(offset)
    const type = data.toString('ascii', offset + 4, offset + 8)
    const start = offset + 8
    const chunk = data.subarray(start, start + length)
    callback(type, chunk)
    offset = start + length + 4
    if (type === 'IEND') break
  }
}

async function readPngMetrics(filePath) {
  const info = await readPngInfo(filePath)
  if (!info) return null
  if (info.bitDepth !== 8 || info.colorType !== 6) {
    fail(`${path.basename(filePath)} must be an 8-bit RGBA PNG`)
    return null
  }

  const zlib = await import('node:zlib')
  const idat = []
  const paletteAlpha = []

  eachPngChunk(info.data, (type, chunk) => {
    if (type === 'IDAT') idat.push(chunk)
    if (type === 'tRNS') {
      for (const value of chunk.values()) paletteAlpha.push(value)
    }
  })

  const bytesPerPixel = info.colorType === 6 ? 4 : 1
  const raw = zlib.inflateSync(Buffer.concat(idat))
  const rowLength = info.width * bytesPerPixel
  let offset = 0
  let previous = Buffer.alloc(rowLength)
  let minX = info.width
  let minY = info.height
  let maxX = -1
  let maxY = -1
  let edgeOpaquePixels = 0
  let maxAlpha = 0

  for (let y = 0; y < info.height; y += 1) {
    const filter = raw[offset]
    offset += 1
    const scanline = raw.subarray(offset, offset + rowLength)
    offset += rowLength
    const row = Buffer.alloc(rowLength)

    for (let index = 0; index < rowLength; index += 1) {
      const left = index >= bytesPerPixel ? row[index - bytesPerPixel] : 0
      const up = previous[index]
      const upLeft = index >= bytesPerPixel ? previous[index - bytesPerPixel] : 0
      let predictor = 0
      if (filter === 1) predictor = left
      else if (filter === 2) predictor = up
      else if (filter === 3) predictor = Math.floor((left + up) / 2)
      else if (filter === 4) {
        const guess = left + up - upLeft
        const pa = Math.abs(guess - left)
        const pb = Math.abs(guess - up)
        const pc = Math.abs(guess - upLeft)
        predictor = pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft
      } else if (filter !== 0) {
        fail(`${path.basename(filePath)} has unsupported PNG filter: ${filter}`)
        return null
      }
      row[index] = (scanline[index] + predictor) & 0xff
    }

    for (let x = 0; x < info.width; x += 1) {
      const alpha = info.colorType === 6 ? row[x * 4 + 3] : (paletteAlpha[row[x]] ?? 255)
      if (alpha > maxAlpha) maxAlpha = alpha
      if (alpha <= 8) continue
      if (x === 0 || y === 0 || x === info.width - 1 || y === info.height - 1) edgeOpaquePixels += 1
      minX = Math.min(minX, x)
      minY = Math.min(minY, y)
      maxX = Math.max(maxX, x)
      maxY = Math.max(maxY, y)
    }

    previous = row
  }

  return {
    ...info,
    bbox: maxX >= 0 ? { x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1 } : null,
    edgeOpaquePixels,
    maxAlpha,
    size: info.data.length,
  }
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

function collectMascotImages(source, mascotName) {
  const mascotStart = source.indexOf(`  ${mascotName}: {`)
  if (mascotStart < 0) {
    fail(`Missing mascot profile: ${mascotName}`)
    return new Map()
  }
  const imagesStart = source.indexOf('    images: {', mascotStart)
  const imagesEnd = source.indexOf('    },', imagesStart)
  if (imagesStart < 0 || imagesEnd < 0) {
    fail(`Missing images map for mascot: ${mascotName}`)
    return new Map()
  }

  const imagesSource = source.slice(imagesStart, imagesEnd)
  const images = new Map()
  const pattern = /^\s+(shime\d+):\s+(\w+),$/gm
  for (const match of imagesSource.matchAll(pattern)) {
    images.set(match[1], match[2])
  }
  return images
}

function validateMascotMotionAssets(source) {
  const nailong = collectMascotImages(source, 'nailong')
  if (nailong.get('shime2') && nailong.get('shime2') === nailong.get('shime3')) {
    fail('Nailong walk poses shime2 and shime3 must use different frame variables')
  }
  for (const frameName of ['shime3', 'shime15', 'shime16', 'shime17']) {
    const variableName = nailong.get(frameName)
    if (!/^nailongRun\d$/.test(variableName || '')) {
      fail(`Nailong run pose ${frameName} must use a dedicated run frame, got ${variableName || '<missing>'}`)
    }
  }

  const kurisu = collectMascotImages(source, 'kurisu')
  for (const frameName of ['shime47', 'shime48', 'shime49']) {
    if (kurisu.get(frameName) === 'kurisuSpin') {
      fail(`Kurisu movement pose ${frameName} must not use kurisuSpin`)
    }
  }
}

async function validateKurisuSpinFrames() {
  const required = ['spin.png', 'spin1.png', 'spin2.png', 'spin3.png', 'spin4.png', 'spin5.png', 'spin6.png', 'spin7.png']
  for (const fileName of required) {
    const filePath = path.join(kurisuRoot, fileName)
    try {
      const info = await readPngInfo(filePath)
      if (!info) continue
      if (info.width !== 384 || info.height !== 384) {
        fail(`Kurisu ${fileName} must be 384x384, got ${info.width}x${info.height}`)
      }
    } catch {
      fail(`Missing Kurisu spin frame: ${fileName}`)
    }
  }
}

async function validateNailongMotionFrames() {
  const groups = [
    ['idle', ['idle1.png', 'idle2.png', 'idle3.png', 'idle4.png'], { maxHeightDelta: 8, minHeight: 292, maxHeight: 308 }],
    ['walk', ['walk1.png', 'walk2.png', 'walk3.png', 'walk4.png'], { maxHeightDelta: 6, minHeight: 307, maxHeight: 323 }],
    ['run', ['run1.png', 'run2.png', 'run3.png', 'run4.png'], { maxHeightDelta: 6, minHeight: 307, maxHeight: 323 }],
    ['jump', ['jump1.png', 'jump2.png', 'jump3.png', 'jump4.png'], { maxHeightDelta: 8, minHeight: 292, maxHeight: 308 }],
    ['leap', ['leap1.png', 'leap2.png', 'leap3.png', 'leap4.png'], { maxHeightDelta: 40, minHeight: 255, maxHeight: 308 }],
    ['drag', ['drag1.png', 'drag2.png', 'drag3.png', 'drag4.png'], { maxHeightDelta: 8, minHeight: 292, maxHeight: 308 }],
    ['sleep', ['sleep1.png', 'sleep2.png', 'sleep3.png', 'sleep4.png'], { maxWidthDelta: 8, minWidth: 292, maxWidth: 308 }],
  ]

  for (const [groupName, fileNames, rules] of groups) {
    const heights = []
    const widths = []
    for (const fileName of fileNames) {
      const filePath = path.join(nailongRoot, fileName)
      try {
        const info = await readPngMetrics(filePath)
        if (!info) continue
        if (info.width !== 384 || info.height !== 384) {
          fail(`Nailong ${fileName} must be 384x384, got ${info.width}x${info.height}`)
        }
        if (info.edgeOpaquePixels > 0) {
          fail(`Nailong ${fileName} has opaque edge pixels; background was not cut out cleanly`)
        }
        if (!info.bbox) {
          fail(`Nailong ${fileName} has no visible subject`)
          continue
        }
        if (info.bbox.x < 20 || info.bbox.y < 20 || info.bbox.x + info.bbox.width > 364 || info.bbox.y + info.bbox.height > 364) {
          fail(`Nailong ${fileName} subject is too close to canvas edge: ${JSON.stringify(info.bbox)}`)
        }
        if (rules.minHeight && info.bbox.height < rules.minHeight) {
          fail(`Nailong ${fileName} subject is too short: ${info.bbox.height}px`)
        }
        if (rules.maxHeight && info.bbox.height > rules.maxHeight) {
          fail(`Nailong ${fileName} subject is too tall: ${info.bbox.height}px`)
        }
        if (rules.minWidth && info.bbox.width < rules.minWidth) {
          fail(`Nailong ${fileName} subject is too narrow: ${info.bbox.width}px`)
        }
        if (rules.maxWidth && info.bbox.width > rules.maxWidth) {
          fail(`Nailong ${fileName} subject is too wide: ${info.bbox.width}px`)
        }
        heights.push(info.bbox.height)
        widths.push(info.bbox.width)
        if (info.size > 180000) {
          fail(`Nailong ${fileName} is too large after compression: ${info.size} bytes`)
        }
      } catch (error) {
        fail(`Invalid Nailong ${groupName} frame ${fileName}: ${error.message}`)
      }
    }
    if (rules.maxHeightDelta && heights.length === fileNames.length && Math.max(...heights) - Math.min(...heights) > rules.maxHeightDelta) {
      fail(`Nailong ${groupName} frames have inconsistent subject heights: ${heights.join(', ')}`)
    }
    if (rules.maxWidthDelta && widths.length === fileNames.length && Math.max(...widths) - Math.min(...widths) > rules.maxWidthDelta) {
      fail(`Nailong ${groupName} frames have inconsistent subject widths: ${widths.join(', ')}`)
    }
  }
}

async function validateKurisuScaledFrames() {
  const groups = [
    ['idle', 300, 160000],
    ['walk', 300, 160000],
    ['drag', 250, 180000],
    ['sleep', 170, 160000],
    ['think', 230, 160000],
    ['land', 250, 220000],
    ['climb', 320, 180000],
    ['cheer', 290, 170000],
    ['surprise', 280, 170000],
  ]

  for (const [prefix, minHeight, maxSize] of groups) {
    for (const filePath of (await fs.readdir(kurisuRoot)).filter(name => new RegExp(`^${prefix}\\d+\\.png$`).test(name))) {
      const fullPath = path.join(kurisuRoot, filePath)
      try {
        const info = await readPngMetrics(fullPath)
        if (!info) continue
        if (info.width !== 384 || info.height !== 384) {
          fail(`Kurisu ${filePath} must be 384x384, got ${info.width}x${info.height}`)
        }
        if (info.edgeOpaquePixels > 0) {
          fail(`Kurisu ${filePath} has opaque edge pixels`)
        }
        if (
          info.bbox &&
          (info.bbox.x < 12 || info.bbox.y < 12 || info.bbox.x + info.bbox.width > 372 || info.bbox.y + info.bbox.height > 372)
        ) {
          fail(`Kurisu ${filePath} subject is too close to canvas edge: ${JSON.stringify(info.bbox)}`)
        }
        if (!info.bbox || info.bbox.height < minHeight) {
          fail(`Kurisu ${filePath} subject is too small: ${info.bbox?.height || 0}px tall`)
        }
        if (info.size > maxSize) {
          fail(`Kurisu ${filePath} is too large after compression: ${info.size} bytes`)
        }
      } catch (error) {
        fail(`Invalid Kurisu frame ${filePath}: ${error.message}`)
      }
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
validateMascotMotionAssets(assetsSource)
await validateKurisuSpinFrames()
await validateNailongMotionFrames()
await validateKurisuScaledFrames()

if (failures.length) {
  console.error('[AgentMascot] asset/action validation failed')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log(`[AgentMascot] asset/action validation passed: ${assets.size} images, ${actionNames.size} actions, ${poseCount} poses`)
