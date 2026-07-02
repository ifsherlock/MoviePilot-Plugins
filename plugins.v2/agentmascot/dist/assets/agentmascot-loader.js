import { V as VIEWPORT_PADDING, u as unwrapResponse, r as normalizeConfig, D as DEFAULT_CONFIG, S as SHIMEJI_ACTIONS, G as GROUND_PADDING, R as ROAM_INTERVAL, a as SHIMEJI_CANVAS_SIZE, f as Y_FOLLOW_LANE_RADIUS, g as Y_FOLLOW_MIN_DELTA, A as ACTION_MIN_DURATION, s as SURFACE_SCAN_MS, t as DOM_SURFACE_SELECTORS, L as LANE_MIN_GAP, b as REST_ACTIONS, d as ROAM_REST_MIN, e as ROAM_REST_RANGE, F as FOLLOW_DEAD_ZONE, h as RUN_DISTANCE, i as Y_FOLLOW_COOLDOWN_MS, j as AIR_DRAG_X, k as AIR_DRAG_Y, l as AIR_GRAVITY, W as WALL_REST_MIN, n as WALL_REST_RANGE, o as Y_FOLLOW_MOUSE_SPEED_MAX, Y as Y_FOLLOW_DWELL_MS, p as WALL_MARGIN, q as SHIMEJI_TICK_MS } from './provider-DmELBvnQ.js';

const PLUGIN_ID = 'AgentMascot';
const ROOT_ID = 'agentmascot-global-root';
const STYLE_ID = 'agentmascot-global-style';
const HIDDEN_CLASS = 'agentmascot-native-hidden';
const STATUS_PATH = `/api/v1/plugin/${PLUGIN_ID}/status`;
const PUBLIC_STATUS_PATH = `/api/v1/plugin/${PLUGIN_ID}/public_status`;
const CONFIG_POLL_MS = 15000;
let config = { ...DEFAULT_CONFIG };
let root = null;
let img = null;
let shadow = null;
let nativeEntry = null;
let nativeTrigger = null;
let rafId = 0;
let roamTimer = 0;
let lastTick = 0;
let action = 'stand';
let poseIndex = 0;
let poseTicks = 0;
let actionLockedUntil = 0;
let roamPausedUntil = 0;
let pointerOffset = { x: 0, y: 0 };
let dragStart = null;
let suppressClickUntil = 0;
let restoreNativeTimer = 0;
let nativeObserver = null;
let surfaceLanes = [];
let lastSurfaceScan = 0;

const mouse = {
  x: 0,
  y: 0,
  lastX: 0,
  lastY: 0,
  lastMoveAt: 0,
  speed: 0,
  activeUntil: 0,
  candidateLaneY: null,
  candidateSince: 0,
  yCooldownUntil: 0,
};

const pet = {
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
};

function looksLikeJwt(value) {
  return typeof value === 'string' && /^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(value.trim())
}

function pickToken(value, depth = 0) {
  if (!value || depth > 5) return ''
  if (looksLikeJwt(value)) return value.trim()
  if (typeof value === 'string') {
    try {
      return pickToken(JSON.parse(value), depth + 1)
    } catch {
      return ''
    }
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const token = pickToken(item, depth + 1);
      if (token) return token
    }
    return ''
  }
  if (typeof value !== 'object') return ''

  for (const key of ['access_token', 'accessToken', 'token', 'jwt', 'id_token']) {
    const token = pickToken(value[key], depth + 1);
    if (token) return token
  }
  for (const nested of ['state', 'user', 'auth', 'data']) {
    const token = pickToken(value[nested], depth + 1);
    if (token) return token
  }
  for (const item of Object.values(value)) {
    const token = pickToken(item, depth + 1);
    if (token) return token
  }
  return ''
}

function readStorageToken(area) {
  try {
    if (!area) return ''
    for (const key of ['auth', 'user', 'userStore', 'authStore', 'moviepilot-auth']) {
      const token = pickToken(area.getItem(key));
      if (token) return token
    }
    for (let index = 0; index < area.length; index += 1) {
      const token = pickToken(area.getItem(area.key(index)));
      if (token) return token
    }
  } catch {
    return ''
  }
  return ''
}

function getToken() {
  return (
    pickToken(window.__AgentMascotAccessToken)
    || readStorageToken(window.localStorage)
    || readStorageToken(window.sessionStorage)
  )
}

function apiBasePath() {
  const pathname = window.location.pathname.replace(/\/$/, '');
  if (!pathname || pathname === '/') return ''
  return pathname
}

function apiUrl(path) {
  return `${window.location.origin}${apiBasePath()}${path}`
}

async function loadConfig() {
  const token = getToken();
  const response = token
    ? await fetch(apiUrl(STATUS_PATH), {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      credentials: 'same-origin',
      cache: 'no-store',
    })
    : await fetch(apiUrl(PUBLIC_STATUS_PATH), {
      credentials: 'same-origin',
      cache: 'no-store',
    });
  if (!response.ok && token) {
    const publicResponse = await fetch(apiUrl(PUBLIC_STATUS_PATH), {
      credentials: 'same-origin',
      cache: 'no-store',
    });
    if (!publicResponse.ok) throw new Error(`AgentMascot public status ${publicResponse.status}`)
    const data = unwrapResponse(await publicResponse.json());
    config = normalizeConfig(data?.config);
    return config
  }
  if (!response.ok) throw new Error(`AgentMascot status ${response.status}`)
  const data = unwrapResponse(await response.json());
  config = normalizeConfig(data?.config);
  return config
}

function isEnabled() {
  return Boolean(config.enabled && config.replace_agent_entry)
}

function viewportBounds() {
  const width = window.visualViewport?.width || window.innerWidth || document.documentElement.clientWidth || 0;
  const height = window.visualViewport?.height || window.innerHeight || document.documentElement.clientHeight || 0;
  return { width, height }
}

function petSize() {
  return Math.round(92 * Number(config.scale || 1))
}

function poseScale() {
  return petSize() / SHIMEJI_CANVAS_SIZE
}

function currentAction() {
  return SHIMEJI_ACTIONS[action] || SHIMEJI_ACTIONS.stand
}

function currentPose() {
  const poses = currentAction().poses;
  return poses[poseIndex % poses.length] || SHIMEJI_ACTIONS.stand.poses[0]
}

function visualAnchor(pose) {
  const scaledAnchorX = pose.anchor[0] * poseScale();
  return {
    x: pet.lookRight ? petSize() - scaledAnchorX : scaledAnchorX,
    y: pose.anchor[1] * poseScale(),
  }
}

function groundAnchorY() {
  return Math.max(viewportBounds().height - VIEWPORT_PADDING - GROUND_PADDING, 0)
}

function ceilingAnchorY() {
  return VIEWPORT_PADDING + visualAnchor(currentPose()).y
}

function clampAnchorX(anchorX) {
  const bounds = viewportBounds();
  const anchor = visualAnchor(currentPose());
  const minX = VIEWPORT_PADDING + anchor.x;
  const maxX = Math.max(bounds.width - VIEWPORT_PADDING - (petSize() - anchor.x), minX);
  return Math.min(Math.max(anchorX, minX), maxX)
}

function clampAnchorY(anchorY) {
  return Math.min(Math.max(anchorY, ceilingAnchorY()), groundAnchorY())
}

function laneGap() {
  return Math.max(LANE_MIN_GAP * poseScale(), petSize() * 0.42)
}

function normalizeLaneY(anchorY) {
  const minY = ceilingAnchorY() + 28 * poseScale();
  return Math.min(Math.max(anchorY, minY), groundAnchorY())
}

function addSurfaceLane(lanes, anchorY) {
  const lane = normalizeLaneY(anchorY);
  if (!Number.isFinite(lane)) return
  lanes.push(lane);
}

function thinSurfaceLanes(lanes) {
  const gap = laneGap();
  const sorted = lanes
    .map(normalizeLaneY)
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  const thinned = [];
  for (const lane of sorted) {
    if (!thinned.some(existing => Math.abs(existing - lane) < gap)) thinned.push(lane);
  }
  const ground = groundAnchorY();
  if (!thinned.some(lane => Math.abs(lane - ground) < gap * 0.5)) thinned.push(ground);
  return thinned.sort((a, b) => a - b).slice(-9)
}

function collectSurfaceLanes(force = false) {
  const now = performance.now();
  if (!force && surfaceLanes.length && now - lastSurfaceScan < SURFACE_SCAN_MS) return surfaceLanes

  const bounds = viewportBounds();
  const lanes = []
  ;[0.32, 0.46, 0.6, 0.74, 0.88].forEach(ratio => addSurfaceLane(lanes, bounds.height * ratio));
  addSurfaceLane(lanes, groundAnchorY());

  try {
    document.querySelectorAll(DOM_SURFACE_SELECTORS).forEach(element => {
      if (!element || element === root || root?.contains(element) || nativeEntry?.contains(element)) return
      const style = window.getComputedStyle(element);
      if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return
      const rect = element.getBoundingClientRect();
      if (rect.width < 160 || rect.height < 44) return
      if (rect.bottom < VIEWPORT_PADDING + 64 || rect.top > bounds.height - VIEWPORT_PADDING) return
      if (rect.left > bounds.width - 48 || rect.right < 48) return
      addSurfaceLane(lanes, rect.top + 2);
      addSurfaceLane(lanes, rect.bottom + 2);
    });
  } catch (error) {
    console.debug('[AgentMascot] surface scan skipped', error);
  }

  surfaceLanes = thinSurfaceLanes(lanes);
  lastSurfaceScan = now;
  return surfaceLanes
}

function nearestLaneToY(anchorY) {
  const lanes = collectSurfaceLanes();
  return lanes.reduce((best, lane) => (Math.abs(lane - anchorY) < Math.abs(best - anchorY) ? lane : best), lanes[0] ?? groundAnchorY())
}

function chooseLaneY(preferCurrent = true) {
  const lanes = collectSurfaceLanes();
  const current = pet.laneY || nearestLaneToY(pet.anchorY);
  if (preferCurrent && Math.random() < 0.62) return nearestLaneToY(current)
  const playable = lanes.filter(lane => Math.abs(lane - current) > laneGap() * 0.8);
  const candidates = playable.length ? playable : lanes;
  return candidates[Math.floor(Math.random() * candidates.length)] ?? groundAnchorY()
}

function setLaneY(anchorY) {
  pet.laneY = normalizeLaneY(anchorY);
  pet.anchorY = pet.laneY;
  pet.targetY = pet.laneY;
}

function crossedLandingY(previousY, currentY) {
  const lanes = collectSurfaceLanes();
  const tolerance = Math.max(8 * poseScale(), 4);
  return lanes.find(lane => lane >= previousY - tolerance && lane <= currentY + tolerance) ?? null
}

function updateMouseIntent(event, timestamp = performance.now()) {
  const previousX = mouse.x;
  const previousY = mouse.y;
  const previousMoveAt = mouse.lastMoveAt || timestamp;
  const elapsed = Math.max(timestamp - previousMoveAt, 1);

  mouse.lastX = previousX;
  mouse.lastY = previousY;
  mouse.x = event.clientX;
  mouse.y = event.clientY;
  mouse.lastMoveAt = timestamp;
  mouse.activeUntil = timestamp + Y_FOLLOW_DWELL_MS + 1200;
  mouse.speed = Math.hypot(mouse.x - previousX, mouse.y - previousY) / elapsed;

  const targetLaneY = nearestLaneToY(mouse.y);
  const currentLaneY = pet.laneY || nearestLaneToY(pet.anchorY);
  const closeToLane = Math.abs(targetLaneY - mouse.y) <= Y_FOLLOW_LANE_RADIUS * poseScale();
  const meaningfulShift = Math.abs(targetLaneY - currentLaneY) >= Y_FOLLOW_MIN_DELTA * poseScale();

  if (!closeToLane || !meaningfulShift) {
    mouse.candidateLaneY = null;
    mouse.candidateSince = 0;
    return
  }
  if (mouse.candidateLaneY === targetLaneY) return
  mouse.candidateLaneY = targetLaneY;
  mouse.candidateSince = timestamp;
}

function canFollowMouseY(timestamp) {
  if (!config.follow_mouse || timestamp >= mouse.activeUntil) return false
  if (timestamp < mouse.yCooldownUntil) return false
  if (mouse.candidateLaneY === null || !mouse.candidateSince) return false
  const idleMs = timestamp - mouse.lastMoveAt;
  const effectiveSpeed = idleMs > 260 ? 0 : mouse.speed;
  if (effectiveSpeed > Y_FOLLOW_MOUSE_SPEED_MAX) return false
  if (timestamp - mouse.candidateSince < Y_FOLLOW_DWELL_MS) return false
  if (pet.surface !== 'ground') return false
  if (['rest', 'bounce', 'toWall'].includes(pet.state)) return false
  return Math.abs(mouse.candidateLaneY - (pet.laneY || pet.anchorY)) >= Y_FOLLOW_MIN_DELTA * poseScale()
}

function applyMouseYFollow(timestamp) {
  if (!canFollowMouseY(timestamp)) return false
  const targetLaneY = mouse.candidateLaneY;
  const deltaY = targetLaneY - pet.anchorY;
  mouse.candidateLaneY = null;
  mouse.candidateSince = 0;
  mouse.yCooldownUntil = timestamp + Y_FOLLOW_COOLDOWN_MS;

  if (Math.abs(deltaY) <= laneGap() * 0.9) {
    setLaneY(targetLaneY);
    return true
  }
  if (deltaY > 0) {
    startFall(timestamp, 0, 0.8);
    return true
  }
  startLeap(timestamp, mouse.x < pet.anchorX ? 'left' : 'right');
  return true
}

function wallAnchorX(side) {
  const bounds = viewportBounds();
  if (side === 'left') return VIEWPORT_PADDING
  return Math.max(bounds.width - VIEWPORT_PADDING, VIEWPORT_PADDING)
}

function randomGroundX() {
  const bounds = viewportBounds();
  const margin = petSize() * 0.5 + VIEWPORT_PADDING;
  const minX = margin;
  const maxX = Math.max(bounds.width - margin, minX);
  return minX + Math.random() * (maxX - minX)
}

function wallTargetY() {
  const top = Math.max(WALL_MARGIN * poseScale(), ceilingAnchorY() + 24 * poseScale());
  const bottom = Math.max(groundAnchorY() - WALL_MARGIN * poseScale(), top);
  return top + Math.random() * Math.max(bottom - top, 1)
}

function setAction(nextAction, timestamp = performance.now(), options = {}) {
  if (action === nextAction) return
  if (!options.force && timestamp < actionLockedUntil && !['drag', 'resist', 'split'].includes(nextAction)) return
  action = nextAction;
  poseIndex = 0;
  poseTicks = 0;
  actionLockedUntil = timestamp + (options.duration ?? ACTION_MIN_DURATION[nextAction] ?? 600);
}

function advancePose(elapsedTicks) {
  poseTicks += elapsedTicks;
  const poses = currentAction().poses;
  while (poseTicks >= currentPose().duration) {
    poseTicks -= currentPose().duration;
    const nextIndex = poseIndex + 1;
    if (nextIndex >= poses.length && !currentAction().loop) {
      setAction('stand');
      return
    }
    poseIndex = nextIndex % poses.length;
  }
}

function updateGroundAction(distance, timestamp, isFollowingMouse) {
  if (pet.dragging) {
    setAction(distance > 56 ? 'resist' : 'drag', timestamp);
    return
  }
  if (distance > FOLLOW_DEAD_ZONE) {
    setAction(isFollowingMouse && distance > RUN_DISTANCE ? 'dash' : 'run', timestamp);
    return
  }
  if (distance > 8) {
    setAction('walk', timestamp);
    return
  }
  if (['walk', 'run', 'dash'].includes(action)) actionLockedUntil = 0;
  setAction('stand', timestamp);
}

function startRest(timestamp, choices = REST_ACTIONS, min = ROAM_REST_MIN, range = ROAM_REST_RANGE) {
  const nextAction = choices[Math.floor(Math.random() * choices.length)] || 'stand';
  const duration = min + Math.random() * range;
  pet.targetX = pet.anchorX;
  pet.targetY = pet.anchorY;
  pet.stateUntil = timestamp + duration;
  if (nextAction === 'holdWall') {
    pet.surface = 'wall';
    pet.state = 'wallHold';
  } else if (nextAction === 'holdCeiling') {
    pet.surface = 'ceiling';
    pet.state = 'ceilingHold';
  } else {
    pet.surface = 'ground';
    pet.state = 'rest';
    roamPausedUntil = pet.stateUntil;
  }
  setAction(nextAction, timestamp, { force: true, duration });
}

function startGroundMove(timestamp, targetX = null, state = 'groundMove') {
  pet.surface = 'ground';
  pet.state = state;
  pet.stateUntil = 0;
  const shouldShiftLane = state === 'groundMove' && Math.random() < 0.38;
  setLaneY(chooseLaneY(!shouldShiftLane));
  pet.targetX = targetX ?? randomGroundX();
  updateGroundAction(Math.abs(pet.targetX - pet.anchorX), timestamp, false);
}

function startMoveToWall(timestamp, side = Math.random() < 0.5 ? 'left' : 'right') {
  pet.surface = 'ground';
  pet.state = 'toWall';
  pet.wallSide = side;
  setLaneY(nearestLaneToY(pet.anchorY));
  pet.targetX = wallAnchorX(side);
  setAction(Math.abs(pet.targetX - pet.anchorX) > RUN_DISTANCE ? 'run' : 'walk', timestamp, { force: true });
}

function startWall(side, timestamp, targetY = null) {
  pet.surface = 'wall';
  pet.state = 'wallHold';
  pet.wallSide = side;
  pet.targetY = targetY ?? pet.anchorY;
  pet.anchorX = wallAnchorX(side);
  pet.anchorY = clampAnchorY(pet.anchorY);
  pet.lookRight = side === 'right';
  setAction('holdWall', timestamp, { force: true, duration: WALL_REST_MIN });
  pet.stateUntil = timestamp + 1800 + Math.random() * 3200;
}

function startWallClimb(timestamp, targetY = null) {
  pet.surface = 'wall';
  pet.state = 'wallClimb';
  pet.targetY = targetY ?? (Math.random() < 0.62 ? ceilingAnchorY() + 12 * poseScale() : wallTargetY());
  pet.anchorX = wallAnchorX(pet.wallSide);
  setAction(pet.targetY < pet.anchorY ? 'climbWallUp' : 'climbWallDown', timestamp, { force: true });
}

function startCeiling(timestamp, targetX = null) {
  pet.surface = 'ceiling';
  pet.state = 'ceilingHold';
  pet.anchorY = ceilingAnchorY();
  pet.targetX = targetX ?? randomGroundX();
  setAction('holdCeiling', timestamp, { force: true, duration: WALL_REST_MIN });
  pet.stateUntil = timestamp + WALL_REST_MIN + Math.random() * WALL_REST_RANGE;
}

function startCeilingCrawl(timestamp, targetX = null) {
  pet.surface = 'ceiling';
  pet.state = 'ceilingCrawl';
  pet.anchorY = ceilingAnchorY();
  pet.targetX = targetX ?? randomGroundX();
  setAction('crawlCeiling', timestamp, { force: true });
}

function startFall(timestamp, vx = 0, vy = 0) {
  pet.surface = 'air';
  pet.state = 'fall';
  pet.vx = vx;
  pet.vy = vy;
  setAction(vy < 0 ? 'jump' : 'fall', timestamp, { force: true });
}

function startLeap(timestamp, side = Math.random() < 0.5 ? 'left' : 'right') {
  const direction = side === 'left' ? -1 : 1;
  pet.surface = 'air';
  pet.state = 'leap';
  pet.wallSide = side;
  pet.vx = direction * (7 + Math.random() * 5.5) * Number(config.speed || 1);
  pet.vy = -(14 + Math.random() * 9) * Number(config.speed || 1);
  setAction('jump', timestamp, { force: true });
}

function chooseGroundBehavior(timestamp) {
  const roll = Math.random();
  if (roll < 0.24) startRest(timestamp);
  else if (roll < 0.44) startGroundMove(timestamp);
  else if (roll < 0.74) startMoveToWall(timestamp);
  else startLeap(timestamp);
}

function chooseWallBehavior(timestamp) {
  const nearTop = pet.anchorY <= ceilingAnchorY() + 56 * poseScale();
  const roll = Math.random();
  if (nearTop && roll < 0.66) startCeiling(timestamp);
  else if (roll < 0.3) startRest(timestamp, ['holdWall'], WALL_REST_MIN, WALL_REST_RANGE);
  else if (roll < 0.86) startWallClimb(timestamp);
  else startFall(timestamp, pet.wallSide === 'left' ? 2.2 : -2.2, -2);
}

function chooseCeilingBehavior(timestamp) {
  const roll = Math.random();
  if (roll < 0.52) startRest(timestamp, ['holdCeiling'], WALL_REST_MIN, WALL_REST_RANGE);
  else if (roll < 0.88) startCeilingCrawl(timestamp);
  else startFall(timestamp, (Math.random() < 0.5 ? -1 : 1) * (2 + Math.random() * 2), 0.8);
}

function moveByCurrentPose(elapsedTicks, targetX) {
  const distance = targetX - pet.anchorX;
  if (Math.abs(distance) <= 2) {
    pet.anchorX = targetX;
    return
  }
  pet.lookRight = distance > 0;
  const directionMultiplier = pet.lookRight ? -1 : 1;
  const vx = currentPose().velocity[0] * directionMultiplier * poseScale() * Number(config.speed || 1);
  if (vx === 0) return
  const step = vx * elapsedTicks;
  if (Math.sign(step) !== Math.sign(distance) || Math.abs(step) >= Math.abs(distance)) {
    pet.anchorX = targetX;
    return
  }
  pet.anchorX += step;
}

function moveWallByCurrentPose(elapsedTicks) {
  const distance = pet.targetY - pet.anchorY;
  if (Math.abs(distance) <= 3) {
    pet.anchorY = pet.targetY;
    return true
  }
  setAction(distance < 0 ? 'climbWallUp' : 'climbWallDown', performance.now(), { force: true });
  const vy = currentPose().velocity[1] * poseScale() * Number(config.speed || 1);
  const step = vy * elapsedTicks;
  if (!step || Math.sign(step) !== Math.sign(distance) || Math.abs(step) >= Math.abs(distance)) {
    pet.anchorY = pet.targetY;
    return true
  }
  pet.anchorY += step;
  return false
}

function moveCeilingByCurrentPose(elapsedTicks) {
  const distance = pet.targetX - pet.anchorX;
  if (Math.abs(distance) <= 3) {
    pet.anchorX = pet.targetX;
    return true
  }
  pet.lookRight = distance > 0;
  const directionMultiplier = pet.lookRight ? -1 : 1;
  const vx = currentPose().velocity[0] * directionMultiplier * poseScale() * Number(config.speed || 1);
  const step = vx * elapsedTicks;
  if (!step || Math.sign(step) !== Math.sign(distance) || Math.abs(step) >= Math.abs(distance)) {
    pet.anchorX = pet.targetX;
    return true
  }
  pet.anchorX += step;
  return false
}

function updateAir(elapsedTicks, timestamp) {
  const previousY = pet.anchorY;
  pet.anchorX += pet.vx * elapsedTicks * poseScale();
  pet.anchorY += pet.vy * elapsedTicks * poseScale();
  pet.vx *= Math.pow(AIR_DRAG_X, elapsedTicks);
  pet.vy = pet.vy * Math.pow(AIR_DRAG_Y, elapsedTicks) + AIR_GRAVITY * elapsedTicks * Number(config.speed || 1);
  pet.lookRight = pet.vx > 0;
  setAction(pet.vy < -0.4 ? 'jump' : 'fall', timestamp);

  const leftX = wallAnchorX('left');
  const rightX = wallAnchorX('right');
  const highEnoughForWall = pet.anchorY < groundAnchorY() - 60 * poseScale();
  if (pet.anchorX <= leftX) {
    pet.anchorX = leftX;
    if (highEnoughForWall && pet.vx < 0) {
      startWall('left', timestamp, clampAnchorY(pet.anchorY));
      return
    }
    pet.vx = Math.abs(pet.vx) * 0.55;
  }
  if (pet.anchorX >= rightX) {
    pet.anchorX = rightX;
    if (highEnoughForWall && pet.vx > 0) {
      startWall('right', timestamp, clampAnchorY(pet.anchorY));
      return
    }
    pet.vx = -Math.abs(pet.vx) * 0.55;
  }
  if (pet.anchorY <= ceilingAnchorY()) {
    pet.anchorY = ceilingAnchorY();
    if (pet.vy < 0 && Math.random() < 0.55) {
      startCeiling(timestamp);
      return
    }
    pet.vy = Math.abs(pet.vy) * 0.45;
  }
  const landingY = pet.vy >= -0.2 ? crossedLandingY(previousY, pet.anchorY) : null;
  if (landingY !== null) {
    setLaneY(landingY);
    pet.anchorX = Math.min(Math.max(pet.anchorX, leftX), rightX);
    pet.surface = 'ground';
    pet.state = 'bounce';
    pet.vx = 0;
    pet.vy = 0;
    setAction('bounce', timestamp, { force: true, duration: 520 });
    pet.stateUntil = timestamp + 520;
  }
}

function animate(timestamp) {
  const elapsedMs = lastTick ? Math.min(timestamp - lastTick, 100) : SHIMEJI_TICK_MS;
  const elapsedTicks = elapsedMs / SHIMEJI_TICK_MS;
  lastTick = timestamp;

  if (!pet.dragging) {
    const isMouseFresh = config.follow_mouse && timestamp < mouse.activeUntil;
    if (isMouseFresh && pet.surface !== 'air') {
      pet.surface = 'ground';
      pet.state = 'groundMove';
      applyMouseYFollow(timestamp);
      pet.targetX = mouse.x;
      roamPausedUntil = 0;
    }

    if (pet.surface === 'air') {
      updateAir(elapsedTicks, timestamp);
      advancePose(elapsedTicks);
    } else if (pet.surface === 'wall') {
      pet.anchorX = wallAnchorX(pet.wallSide);
      if (pet.state === 'wallClimb') {
        const arrived = moveWallByCurrentPose(elapsedTicks);
        advancePose(elapsedTicks);
        pet.anchorY = clampAnchorY(pet.anchorY);
        if (arrived) {
          if (pet.anchorY <= ceilingAnchorY() + 8 * poseScale()) startCeiling(timestamp);
          else {
            pet.state = 'wallHold';
            pet.stateUntil = timestamp + 1200 + Math.random() * 1800;
            setAction('holdWall', timestamp, { force: true });
          }
        }
      } else {
        advancePose(elapsedTicks);
        if (timestamp >= pet.stateUntil) chooseWallBehavior(timestamp);
      }
    } else if (pet.surface === 'ceiling') {
      pet.anchorY = ceilingAnchorY();
      if (pet.state === 'ceilingCrawl') {
        const arrived = moveCeilingByCurrentPose(elapsedTicks);
        advancePose(elapsedTicks);
        pet.anchorX = clampAnchorX(pet.anchorX);
        if (arrived) {
          pet.state = 'ceilingHold';
          pet.stateUntil = timestamp + 1600 + Math.random() * 2200;
          setAction('holdCeiling', timestamp, { force: true });
        }
      } else {
        advancePose(elapsedTicks);
        if (timestamp >= pet.stateUntil) chooseCeilingBehavior(timestamp);
      }
    } else {
      pet.surface = 'ground';
      setLaneY(pet.laneY || nearestLaneToY(pet.anchorY));
      const targetX = isMouseFresh ? mouse.x : pet.targetX;
      const distance = Math.abs(targetX - pet.anchorX);
      if (pet.state === 'rest' && timestamp < pet.stateUntil) {
        advancePose(elapsedTicks);
      } else if (pet.state === 'bounce' && timestamp < pet.stateUntil) {
        advancePose(elapsedTicks);
      } else {
        if (pet.state === 'rest') {
          roamPausedUntil = 0;
          chooseGroundBehavior(timestamp);
        } else if (distance <= 4) {
          if (pet.state === 'toWall') startWall(pet.wallSide, timestamp, pet.anchorY);
          else if (config.auto_roam && !isMouseFresh) {
            if (!roamPausedUntil) roamPausedUntil = timestamp + ROAM_REST_MIN + Math.random() * ROAM_REST_RANGE;
            if (timestamp >= roamPausedUntil) {
              roamPausedUntil = 0;
              chooseGroundBehavior(timestamp);
            } else {
              startRest(timestamp, REST_ACTIONS, Math.max(roamPausedUntil - timestamp, 900), 1);
            }
          } else updateGroundAction(distance, timestamp, false);
        } else {
          updateGroundAction(distance, timestamp, isMouseFresh && distance > FOLLOW_DEAD_ZONE);
          moveByCurrentPose(elapsedTicks, targetX);
        }
        advancePose(elapsedTicks);
      }
      pet.anchorX = clampAnchorX(pet.anchorX);
      setLaneY(pet.laneY || nearestLaneToY(pet.anchorY));
    }
  } else {
    advancePose(elapsedTicks);
  }

  render();
  rafId = requestAnimationFrame(animate);
}

function render() {
  if (!root || !img) return
  const pose = currentPose();
  const anchor = visualAnchor(pose);
  const left = pet.anchorX - anchor.x;
  const top = pet.anchorY - anchor.y;
  const size = petSize();
  root.style.width = `${size}px`;
  root.style.height = `${size}px`;
  root.style.transform = `translate3d(${left}px, ${top}px, 0) scaleX(${pet.lookRight ? -1 : 1})`;
  img.src = pose.image;
  shadow.style.display = config.shadow ? 'block' : 'none';
}

function hideNativeEntry() {
  nativeEntry = document.querySelector('.agent-assistant-fab');
  nativeTrigger = document.querySelector('.agent-assistant-fab__trigger');
  if (nativeEntry) nativeEntry.classList.add(HIDDEN_CLASS);
}

function openNativeAssistant() {
  hideNativeEntry();
  if (!nativeTrigger) return
  triggerNativeAssistant();
  window.setTimeout(() => {
    if (!isNativeAssistantOpen()) triggerNativeAssistant();
  }, 80);
  window.clearTimeout(restoreNativeTimer);
  restoreNativeTimer = window.setTimeout(hideNativeEntry, 300);
}

function triggerNativeAssistant() {
  if (!nativeTrigger) return
  if (typeof nativeTrigger.click === 'function') nativeTrigger.click();
  else nativeTrigger.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
}

function isNativeAssistantOpen() {
  const panel = document.querySelector('.agent-assistant-panel');
  if (!panel) return false
  const style = window.getComputedStyle(panel);
  const rect = panel.getBoundingClientRect();
  return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
}

function onPointerMove(event) {
  updateMouseIntent(event);
  roamPausedUntil = 0;
}

function startDrag(event) {
  if (event.button !== 0) return
  event.preventDefault();
  dragStart = { x: event.clientX, y: event.clientY };
  pointerOffset = {
    x: event.clientX - pet.anchorX,
    y: event.clientY - pet.anchorY,
  };
  pet.dragging = true;
  setAction('drag', performance.now(), { force: true });
  root?.setPointerCapture?.(event.pointerId);
}

function onDrag(event) {
  if (!pet.dragging) return
  pet.anchorX = event.clientX - pointerOffset.x;
  pet.anchorY = event.clientY - pointerOffset.y;
  if (Math.abs(event.movementX) > 0) pet.lookRight = event.movementX > 0;
  pet.anchorX = clampAnchorX(pet.anchorX);
  pet.anchorY = clampAnchorY(pet.anchorY);
  pet.surface = 'air';
  render();
}

function endDrag(event) {
  if (!pet.dragging) return
  const moved = dragStart ? Math.hypot(event.clientX - dragStart.x, event.clientY - dragStart.y) : 0;
  dragStart = null;
  pet.dragging = false;
  root?.releasePointerCapture?.(event.pointerId);
  if (moved > 4) suppressClickUntil = performance.now() + 450;
  roamPausedUntil = 0;
  const nearestLane = nearestLaneToY(pet.anchorY);
  if (Math.abs(nearestLane - pet.anchorY) <= 24 * poseScale()) {
    setLaneY(nearestLane);
    startGroundMove(performance.now());
  } else if (pet.anchorY < groundAnchorY() - 16) startFall(performance.now(), event.movementX * 0.08, Math.min(event.movementY * 0.06, 2));
  else startGroundMove(performance.now());
}

function onClick(event) {
  if (pet.dragging || performance.now() < suppressClickUntil) {
    event.preventDefault();
    return
  }
  event.preventDefault();
  openNativeAssistant();
}

function ensureStyle() {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    .${HIDDEN_CLASS} {
      width: 0 !important;
      height: 0 !important;
      overflow: hidden !important;
    }
    .${HIDDEN_CLASS} > .agent-assistant-fab__trigger,
    .${HIDDEN_CLASS} > .agent-assistant-fab__trigger * {
      opacity: 0 !important;
      visibility: hidden !important;
      pointer-events: none !important;
    }
    .${HIDDEN_CLASS} > .agent-assistant-fab__trigger {
      width: 0 !important;
      height: 0 !important;
      min-width: 0 !important;
      min-height: 0 !important;
      padding: 0 !important;
      border: 0 !important;
      overflow: hidden !important;
    }
    #${ROOT_ID} {
      position: fixed;
      top: 0;
      left: 0;
      z-index: 2147483000;
      display: grid;
      place-items: center;
      cursor: grab;
      user-select: none;
      touch-action: none;
      will-change: transform;
    }
    #${ROOT_ID}:active {
      cursor: grabbing;
    }
    #${ROOT_ID} img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      pointer-events: none;
      -webkit-user-drag: none;
    }
    #${ROOT_ID} .agentmascot-global-shadow {
      position: absolute;
      left: 17%;
      right: 17%;
      bottom: 3px;
      height: 12px;
      border-radius: 999px;
      background: rgba(0, 0, 0, 0.26);
      filter: blur(5px);
      z-index: -1;
    }
  `;
  document.head.appendChild(style);
}

function mount() {
  if (root) return
  ensureStyle();
  startNativeObserver();
  root = document.createElement('button');
  root.id = ROOT_ID;
  root.type = 'button';
  root.setAttribute('aria-label', '打开智能体助手');
  img = document.createElement('img');
  img.alt = '';
  shadow = document.createElement('span');
  shadow.className = 'agentmascot-global-shadow';
  root.append(img, shadow);
  document.body.appendChild(root);
  document.addEventListener('pointermove', onPointerMove, { passive: true });
  root.addEventListener('pointerdown', startDrag);
  root.addEventListener('pointermove', onDrag);
  root.addEventListener('pointerup', endDrag);
  root.addEventListener('pointercancel', endDrag);
  root.addEventListener('click', onClick);
  setLaneY(chooseLaneY(false));
  pet.targetX = randomGroundX();
  hideNativeEntry();
  startLoops();
}

function unmount() {
  stopLoops();
  stopNativeObserver();
  document.removeEventListener('pointermove', onPointerMove);
  window.clearTimeout(restoreNativeTimer);
  nativeEntry?.classList.remove(HIDDEN_CLASS);
  root?.remove();
  root = null;
  img = null;
  shadow = null;
}

function startNativeObserver() {
  hideNativeEntry();
  if (nativeObserver) return
  nativeObserver = new MutationObserver(() => {
    if (isEnabled()) hideNativeEntry();
  });
  nativeObserver.observe(document.body, { childList: true, subtree: true });
}

function stopNativeObserver() {
  nativeObserver?.disconnect();
  nativeObserver = null;
}

function startLoops() {
  stopLoops();
  roamTimer = window.setInterval(() => {
    const canScheduleGroundBehavior = pet.surface === 'ground' && !['rest', 'bounce', 'toWall'].includes(pet.state);
    if (config.auto_roam && !pet.dragging && !roamPausedUntil && canScheduleGroundBehavior) {
      chooseGroundBehavior(performance.now());
    }
  }, ROAM_INTERVAL);
  rafId = requestAnimationFrame(animate);
}

function stopLoops() {
  if (roamTimer) window.clearInterval(roamTimer);
  if (rafId) cancelAnimationFrame(rafId);
  roamTimer = 0;
  rafId = 0;
  lastTick = 0;
}

async function syncFromConfig() {
  try {
    await loadConfig();
    if (isEnabled()) {
      mount();
      hideNativeEntry();
      render();
    } else {
      unmount();
    }
  } catch (error) {
    console.debug('[AgentMascot] 全局入口配置读取失败', error);
  }
}

function start() {
  if (window.__AgentMascotGlobalLoaderStarted) return
  window.__AgentMascotGlobalLoaderStarted = true;
  syncFromConfig();
  window.setInterval(syncFromConfig, CONFIG_POLL_MS);
  window.addEventListener('resize', () => {
    pet.anchorX = clampAnchorX(pet.anchorX);
    pet.anchorY = clampAnchorY(pet.anchorY);
    render();
  });
}

start();
