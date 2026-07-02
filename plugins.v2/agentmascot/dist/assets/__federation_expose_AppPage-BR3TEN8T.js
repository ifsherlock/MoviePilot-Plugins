import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { c as cloneConfig, S as SHIMEJI_ACTIONS, m as mascotIcon, u as unwrapResponse } from './provider-0b6avniP.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {unref:_unref,createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,createBlock:_createBlock,normalizeClass:_normalizeClass,normalizeStyle:_normalizeStyle} = await importShared('vue');


const _hoisted_1 = { class: "agentmascot-shell" };
const _hoisted_2 = {
  key: 0,
  class: "agentmascot-header"
};
const _hoisted_3 = { class: "agentmascot-title" };
const _hoisted_4 = ["src"];
const _hoisted_5 = { class: "agentmascot-actions" };
const _hoisted_6 = ["src"];
const _hoisted_7 = { class: "agentmascot-controls" };
const _hoisted_8 = { class: "control-slider" };
const _hoisted_9 = { class: "control-slider" };

const {computed,nextTick,onBeforeUnmount,onMounted,reactive,ref,watch} = await importShared('vue');

const SHIMEJI_CANVAS_SIZE = 128;
const SHIMEJI_TICK_MS = 33;
const ROAM_INTERVAL = 3200;
const ROAM_REST_MIN = 9000;
const ROAM_REST_RANGE = 26000;
const WALL_REST_MIN = 9000;
const WALL_REST_RANGE = 24000;
const FOLLOW_DEAD_ZONE = 92;
const RUN_DISTANCE = 260;
const GROUND_PADDING = 18;
const MAX_GROUND_STEP = 260;
const WALL_MARGIN = 72;
const LANE_MIN_GAP = 54;
const Y_FOLLOW_DWELL_MS = 1100;
const Y_FOLLOW_COOLDOWN_MS = 4200;
const Y_FOLLOW_LANE_RADIUS = 120;
const Y_FOLLOW_MOUSE_SPEED_MAX = 0.45;
const Y_FOLLOW_MIN_DELTA = 90;
const AIR_GRAVITY = 1.05;
const AIR_DRAG_X = 0.982;
const AIR_DRAG_Y = 0.99;

const _sfc_main = {
  __name: 'AppPage',
  props: {
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
},
  setup(__props, { expose: __expose }) {

const props = __props;

const loading = ref(false);
const saving = ref(false);
const error = ref('');
const stageRef = ref(null);
const mascotRef = ref(null);
const config = ref(cloneConfig(props.config));
const action = ref('stand');
const poseIndex = ref(0);
const poseTicks = ref(0);
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
});
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
});

let roamTimer = 0;
let rafId = 0;
let lastTick = 0;
let pointerOffset = { x: 0, y: 0 };
let actionLockedUntil = 0;
let mouseActiveUntil = 0;
let roamPausedUntil = 0;

const ACTION_MIN_DURATION = {
  stand: 520,
  walk: 620,
  run: 700,
  dash: 700,
  drag: 0,
  resist: 0,
  lie: 9000,
  sit: 9000,
  relaxedSit: 9000,
  sitFeetDown: 5000,
  dangleFeet: 12000,
  lookUp: 8000,
  crawl: 1600,
  jump: 500,
  fall: 500,
  bounce: 450,
  holdWall: 7000,
  climbWallUp: 700,
  climbWallDown: 700,
  holdCeiling: 7000,
  crawlCeiling: 700,
  split: 1500,
};
const REST_ACTIONS = ['stand', 'sit', 'lie', 'relaxedSit', 'dangleFeet', 'lookUp'];

const currentAction = computed(() => SHIMEJI_ACTIONS[action.value] || SHIMEJI_ACTIONS.stand);
const currentPose = computed(() => {
  const poses = currentAction.value.poses;
  return poses[poseIndex.value % poses.length] || SHIMEJI_ACTIONS.stand.poses[0]
});
const currentFrame = computed(() => currentPose.value.image);
const petSize = computed(() => Math.round(92 * Number(config.value.scale || 1)));
const poseScale = computed(() => petSize.value / SHIMEJI_CANVAS_SIZE);
const stageStyle = computed(() => ({
  '--pet-size': `${petSize.value}px`,
}));
const petStyle = computed(() => {
  const anchor = visualAnchor(currentPose.value);
  const left = pet.anchorX - anchor.x;
  const top = pet.anchorY - anchor.y;
  return {
    transform: `translate3d(${left}px, ${top}px, 0) scaleX(${pet.lookRight ? -1 : 1})`,
    '--pet-facing': pet.lookRight ? -1 : 1,
  }
});

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
  loading.value = true;
  error.value = '';
  try {
    const data = unwrapResponse(await apiGet('/status'));
    config.value = cloneConfig(data?.config);
  } catch (err) {
    error.value = err?.message || String(err);
  } finally {
    loading.value = false;
  }
}

async function saveConfig() {
  if (!props.api?.post) return
  saving.value = true;
  error.value = '';
  try {
    const data = unwrapResponse(await apiPost('/config', cloneConfig(config.value)));
    config.value = cloneConfig(data?.config);
  } catch (err) {
    error.value = err?.message || String(err);
  } finally {
    saving.value = false;
  }
}

function stageBounds() {
  const rect = stageRef.value?.getBoundingClientRect();
  return {
    width: rect?.width || window.innerWidth,
    height: rect?.height || window.innerHeight,
  }
}

function groundAnchorY() {
  const bounds = stageBounds();
  return Math.max(bounds.height - GROUND_PADDING, 0)
}

function visualAnchor(pose) {
  const scaledAnchorX = pose.anchor[0] * poseScale.value;
  return {
    x: pet.lookRight ? petSize.value - scaledAnchorX : scaledAnchorX,
    y: pose.anchor[1] * poseScale.value,
  }
}

function clampAnchorX(anchorX) {
  const bounds = stageBounds();
  const anchor = visualAnchor(currentPose.value);
  const minX = anchor.x;
  const maxX = Math.max(bounds.width - (petSize.value - anchor.x), minX);
  return Math.min(Math.max(anchorX, minX), maxX)
}

function clampAnchorY(anchorY) {
  const anchor = visualAnchor(currentPose.value);
  return Math.min(Math.max(anchorY, anchor.y), groundAnchorY())
}

function laneGap() {
  return Math.max(LANE_MIN_GAP * poseScale.value, petSize.value * 0.42)
}

function normalizeLaneY(anchorY) {
  const minY = ceilingAnchorY() + 28 * poseScale.value;
  return Math.min(Math.max(anchorY, minY), groundAnchorY())
}

function surfaceLanes() {
  const bounds = stageBounds();
  const candidates = [0.3, 0.44, 0.58, 0.72, 0.86].map(ratio => normalizeLaneY(bounds.height * ratio));
  candidates.push(groundAnchorY());
  const sorted = candidates.filter(Number.isFinite).sort((a, b) => a - b);
  const lanes = [];
  const gap = laneGap();
  for (const lane of sorted) {
    if (!lanes.some(existing => Math.abs(existing - lane) < gap)) lanes.push(lane);
  }
  const ground = groundAnchorY();
  if (!lanes.some(lane => Math.abs(lane - ground) < gap * 0.5)) lanes.push(ground);
  return lanes.sort((a, b) => a - b)
}

function nearestLaneToY(anchorY) {
  const lanes = surfaceLanes();
  return lanes.reduce((best, lane) => (Math.abs(lane - anchorY) < Math.abs(best - anchorY) ? lane : best), lanes[0] ?? groundAnchorY())
}

function chooseLaneY(preferCurrent = true) {
  const lanes = surfaceLanes();
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
  const tolerance = Math.max(8 * poseScale.value, 4);
  return surfaceLanes().find(lane => lane >= previousY - tolerance && lane <= currentY + tolerance) ?? null
}

function updateMouseIntent(x, y, timestamp = performance.now()) {
  const previousX = mouse.x;
  const previousY = mouse.y;
  const previousMoveAt = mouse.lastMoveAt || timestamp;
  const elapsed = Math.max(timestamp - previousMoveAt, 1);

  mouse.lastX = previousX;
  mouse.lastY = previousY;
  mouse.x = x;
  mouse.y = y;
  mouse.lastMoveAt = timestamp;
  mouse.active = true;
  mouseActiveUntil = timestamp + Y_FOLLOW_DWELL_MS + 1200;
  mouse.speed = Math.hypot(mouse.x - previousX, mouse.y - previousY) / elapsed;

  const targetLaneY = nearestLaneToY(mouse.y);
  const currentLaneY = pet.laneY || nearestLaneToY(pet.anchorY);
  const closeToLane = Math.abs(targetLaneY - mouse.y) <= Y_FOLLOW_LANE_RADIUS * poseScale.value;
  const meaningfulShift = Math.abs(targetLaneY - currentLaneY) >= Y_FOLLOW_MIN_DELTA * poseScale.value;

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
  if (!config.value.follow_mouse || !mouse.active || timestamp >= mouseActiveUntil) return false
  if (timestamp < mouse.yCooldownUntil) return false
  if (mouse.candidateLaneY === null || !mouse.candidateSince) return false
  const idleMs = timestamp - mouse.lastMoveAt;
  const effectiveSpeed = idleMs > 260 ? 0 : mouse.speed;
  if (effectiveSpeed > Y_FOLLOW_MOUSE_SPEED_MAX) return false
  if (timestamp - mouse.candidateSince < Y_FOLLOW_DWELL_MS) return false
  if (pet.surface !== 'ground') return false
  if (pet.state === 'rest' || pet.state === 'bounce' || pet.state === 'toWall') return false
  return Math.abs(mouse.candidateLaneY - (pet.laneY || pet.anchorY)) >= Y_FOLLOW_MIN_DELTA * poseScale.value
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
  const bounds = stageBounds();
  if (side === 'left') return 0
  return bounds.width
}

function ceilingAnchorY() {
  return visualAnchor(currentPose.value).y
}

function wallTargetY() {
  stageBounds();
  const top = Math.max(WALL_MARGIN * poseScale.value, ceilingAnchorY() + 24 * poseScale.value);
  const bottom = Math.max(groundAnchorY() - WALL_MARGIN * poseScale.value, top);
  return top + Math.random() * Math.max(bottom - top, 1)
}

function pickRoamTarget() {
  const bounds = stageBounds();
  const margin = petSize.value * 0.5;
  const minX = margin;
  const maxX = Math.max(bounds.width - margin, minX);
  const direction = Math.random() < 0.5 ? -1 : 1;
  const distance = 120 + Math.random() * Math.min(MAX_GROUND_STEP, maxX - minX);
  pet.targetX = Math.min(Math.max(pet.anchorX + direction * distance, minX), maxX);
}

function setAction(nextAction, timestamp = performance.now(), options = {}) {
  if (action.value === nextAction) return
  if (!options.force && timestamp < actionLockedUntil && nextAction !== 'drag' && nextAction !== 'resist' && nextAction !== 'split') return
  action.value = nextAction;
  poseIndex.value = 0;
  poseTicks.value = 0;
  actionLockedUntil = timestamp + (options.duration ?? ACTION_MIN_DURATION[nextAction] ?? 600);
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
  if (action.value === 'walk' || action.value === 'run' || action.value === 'dash') {
    actionLockedUntil = 0;
  }
  setAction('stand', timestamp);
}

function pauseBeforeNextRoam(timestamp) {
  roamPausedUntil = timestamp + ROAM_REST_MIN + Math.random() * ROAM_REST_RANGE;
  pet.targetX = pet.anchorX;
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
  pet.targetY = targetY ?? (Math.random() < 0.62 ? ceilingAnchorY() + 12 * poseScale.value : wallTargetY());
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
  pet.vx = direction * (7 + Math.random() * 5.5) * Number(config.value.speed || 1);
  pet.vy = -(14 + Math.random() * 9) * Number(config.value.speed || 1);
  setAction('jump', timestamp, { force: true });
}

function randomGroundX() {
  const bounds = stageBounds();
  const margin = petSize.value * 0.5;
  const minX = margin;
  const maxX = Math.max(bounds.width - margin, minX);
  return minX + Math.random() * (maxX - minX)
}

function chooseGroundBehavior(timestamp) {
  const roll = Math.random();
  if (roll < 0.24) {
    startRest(timestamp);
    return
  }
  if (roll < 0.44) {
    startGroundMove(timestamp);
    return
  }
  if (roll < 0.74) {
    startMoveToWall(timestamp);
    return
  }
  startLeap(timestamp);
}

function chooseWallBehavior(timestamp) {
  const nearTop = pet.anchorY <= ceilingAnchorY() + 56 * poseScale.value;
  const roll = Math.random();
  if (nearTop && roll < 0.66) {
    startCeiling(timestamp);
    return
  }
  if (roll < 0.3) {
    startRest(timestamp, ['holdWall'], WALL_REST_MIN, WALL_REST_RANGE);
    pet.surface = 'wall';
    pet.state = 'wallHold';
    return
  }
  if (roll < 0.86) {
    startWallClimb(timestamp);
    return
  }
  startFall(timestamp, pet.wallSide === 'left' ? 2.2 : -2.2, -2);
}

function chooseCeilingBehavior(timestamp) {
  const roll = Math.random();
  if (roll < 0.52) {
    startRest(timestamp, ['holdCeiling'], WALL_REST_MIN, WALL_REST_RANGE);
    pet.surface = 'ceiling';
    pet.state = 'ceilingHold';
    return
  }
  if (roll < 0.88) {
    startCeilingCrawl(timestamp);
    return
  }
  startFall(timestamp, (Math.random() < 0.5 ? -1 : 1) * (2 + Math.random() * 2), 0.8);
}

function advancePose(elapsedTicks) {
  poseTicks.value += elapsedTicks;
  const poses = currentAction.value.poses;
  while (poseTicks.value >= currentPose.value.duration) {
    poseTicks.value -= currentPose.value.duration;
    const nextIndex = poseIndex.value + 1;
    if (nextIndex >= poses.length && !currentAction.value.loop) {
      setAction('stand');
      return
    }
    poseIndex.value = nextIndex % poses.length;
  }
}

function moveByCurrentPose(elapsedTicks, targetX) {
  const distance = targetX - pet.anchorX;
  if (Math.abs(distance) <= 2) {
    pet.anchorX = targetX;
    return
  }

  pet.lookRight = distance > 0;
  const directionMultiplier = pet.lookRight ? -1 : 1;
  const vx = currentPose.value.velocity[0] * directionMultiplier * poseScale.value * Number(config.value.speed || 1);
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
  const vy = currentPose.value.velocity[1] * poseScale.value * Number(config.value.speed || 1);
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
  const vx = currentPose.value.velocity[0] * directionMultiplier * poseScale.value * Number(config.value.speed || 1);
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
  pet.anchorX += pet.vx * elapsedTicks * poseScale.value;
  pet.anchorY += pet.vy * elapsedTicks * poseScale.value;
  pet.vx *= Math.pow(AIR_DRAG_X, elapsedTicks);
  pet.vy = pet.vy * Math.pow(AIR_DRAG_Y, elapsedTicks) + AIR_GRAVITY * elapsedTicks * Number(config.value.speed || 1);
  pet.lookRight = pet.vx > 0;
  setAction(pet.vy < -0.4 ? 'jump' : 'fall', timestamp);

  const bounds = stageBounds();
  const leftX = wallAnchorX('left');
  const rightX = wallAnchorX('right');
  const highEnoughForWall = pet.anchorY < groundAnchorY() - 60 * poseScale.value;

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
    pet.anchorX = Math.min(Math.max(pet.anchorX, leftX), rightX || bounds.width);
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
    const isMouseFresh = config.value.follow_mouse && mouse.active && timestamp < mouseActiveUntil;
    const mouseTargetX = mouse.x;
    if (isMouseFresh && pet.surface !== 'air') {
      pet.surface = 'ground';
      pet.state = 'groundMove';
      applyMouseYFollow(timestamp);
      pet.targetX = mouseTargetX;
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
          if (pet.anchorY <= ceilingAnchorY() + 8 * poseScale.value) {
            startCeiling(timestamp);
          } else {
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
      const targetX = isMouseFresh ? mouseTargetX : pet.targetX;
      const distance = Math.abs(targetX - pet.anchorX);

      if (pet.state === 'rest' && timestamp < pet.stateUntil) {
        advancePose(elapsedTicks);
      } else if (pet.state === 'bounce' && timestamp < pet.stateUntil) {
        advancePose(elapsedTicks);
      } else {
        if (pet.state === 'rest') {
          roamPausedUntil = 0;
          chooseGroundBehavior(timestamp);
          advancePose(elapsedTicks);
          pet.anchorX = clampAnchorX(pet.anchorX);
          setLaneY(pet.laneY || nearestLaneToY(pet.anchorY));
          pet.lastAnchorX = pet.anchorX;
          pet.lastAnchorY = pet.anchorY;
          rafId = requestAnimationFrame(animate);
          return
        }
        if (distance <= 4) {
          if (pet.state === 'toWall') {
            startWall(pet.wallSide, timestamp, pet.anchorY);
          } else if (config.value.auto_roam && !isMouseFresh) {
            if (!roamPausedUntil) pauseBeforeNextRoam(timestamp);
            if (timestamp >= roamPausedUntil) {
              roamPausedUntil = 0;
              chooseGroundBehavior(timestamp);
            } else {
              startRest(timestamp, REST_ACTIONS, Math.max(roamPausedUntil - timestamp, 900), 1);
            }
          } else {
            updateGroundAction(distance, timestamp, false);
          }
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

  pet.lastAnchorX = pet.anchorX;
  pet.lastAnchorY = pet.anchorY;
  rafId = requestAnimationFrame(animate);
}

function startLoops() {
  stopLoops();
  roamTimer = window.setInterval(() => {
    const canScheduleGroundBehavior =
      pet.surface === 'ground' && pet.state !== 'rest' && pet.state !== 'bounce' && pet.state !== 'toWall';
    if (config.value.auto_roam && !mouse.active && !pet.dragging && !roamPausedUntil && canScheduleGroundBehavior) {
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

function updateMouse(event) {
  const rect = stageRef.value?.getBoundingClientRect();
  if (!rect) return
  updateMouseIntent(event.clientX - rect.left, event.clientY - rect.top);
  roamPausedUntil = 0;
}

function leaveMouse() {
  mouse.active = false;
  mouseActiveUntil = 0;
}

function startDrag(event) {
  event.preventDefault();
  const stage = stageRef.value?.getBoundingClientRect();
  if (!stage) return
  pointerOffset = {
    x: event.clientX - stage.left - pet.anchorX,
    y: event.clientY - stage.top - pet.anchorY,
  };
  pet.dragging = true;
  setAction('drag');
  mascotRef.value?.setPointerCapture?.(event.pointerId);
}

function onDrag(event) {
  if (!pet.dragging) return
  const stage = stageRef.value?.getBoundingClientRect();
  if (!stage) return
  pet.anchorX = event.clientX - stage.left - pointerOffset.x;
  pet.anchorY = event.clientY - stage.top - pointerOffset.y;
  if (Math.abs(event.movementX) > 0) pet.lookRight = event.movementX > 0;
  const bounds = stageBounds();
  pet.anchorX = clampAnchorX(pet.anchorX);
  pet.anchorY = Math.min(Math.max(pet.anchorY, currentPose.value.anchor[1] * poseScale.value), bounds.height - GROUND_PADDING);
  pet.surface = 'air';
}

function endDrag(event) {
  if (!pet.dragging) return
  pet.dragging = false;
  mascotRef.value?.releasePointerCapture?.(event.pointerId);
  roamPausedUntil = 0;
  const nearestLane = nearestLaneToY(pet.anchorY);
  if (Math.abs(nearestLane - pet.anchorY) <= 24 * poseScale.value) {
    setLaneY(nearestLane);
    pet.lastAnchorY = pet.anchorY;
    startGroundMove(performance.now());
  } else if (pet.anchorY < groundAnchorY() - 16) {
    startFall(performance.now(), event.movementX * 0.08, Math.min(event.movementY * 0.06, 2));
  } else {
    setLaneY(groundAnchorY());
    pet.lastAnchorY = pet.anchorY;
    startGroundMove(performance.now());
  }
}

function celebrate() {
  pet.surface = 'ground';
  pet.state = 'rest';
  setLaneY(pet.laneY || nearestLaneToY(pet.anchorY));
  setAction('split', performance.now(), { force: true });
  window.setTimeout(() => {
    pet.stateUntil = 0;
    setAction('stand', performance.now(), { force: true });
  }, 1600);
}

watch(
  () => props.config,
  nextValue => {
    if (nextValue) config.value = cloneConfig(nextValue);
  },
  { deep: true },
);

onMounted(async () => {
  await nextTick();
  setLaneY(chooseLaneY(false));
  pet.lastAnchorY = pet.anchorY;
  pickRoamTarget();
  startLoops();
  if (!props.config) {
    await loadStatus();
  }
});

onBeforeUnmount(() => {
  stopLoops();
});

__expose({
  loading,
  saving,
  config,
  loadStatus,
  saveConfig,
});

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VSlider = _resolveComponent("VSlider");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _createElementVNode("div", _hoisted_3, [
            _createElementVNode("img", {
              src: _unref(mascotIcon),
              alt: ""
            }, null, 8, _hoisted_4),
            _cache[8] || (_cache[8] = _createElementVNode("div", null, [
              _createElementVNode("h2", null, "Agent 桌宠"),
              _createElementVNode("p", null, "小天照 Shimeji demo")
            ], -1))
          ]),
          _createElementVNode("div", _hoisted_5, [
            _createVNode(_component_VBtn, {
              icon: "mdi-refresh",
              variant: "text",
              loading: loading.value,
              onClick: loadStatus
            }, null, 8, ["loading"]),
            _createVNode(_component_VBtn, {
              icon: "mdi-content-save",
              variant: "text",
              color: "primary",
              loading: saving.value,
              onClick: saveConfig
            }, null, 8, ["loading"])
          ])
        ]))
      : _createCommentVNode("", true),
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: "error",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(error.value), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createElementVNode("div", {
      class: "agentmascot-stage",
      style: _normalizeStyle(stageStyle.value),
      ref_key: "stageRef",
      ref: stageRef,
      onPointermove: updateMouse,
      onPointerleave: leaveMouse
    }, [
      _cache[9] || (_cache[9] = _createElementVNode("div", { class: "stage-grid" }, null, -1)),
      _cache[10] || (_cache[10] = _createElementVNode("div", { class: "stage-panel" }, [
        _createElementVNode("div", { class: "panel-title" }, "MoviePilot Agent"),
        _createElementVNode("div", { class: "panel-copy" }, "全屏游走、飞跃、爬墙、吸顶、鼠标跟随")
      ], -1)),
      _createElementVNode("button", {
        class: "stage-chip",
        type: "button",
        onClick: celebrate
      }, "动作测试"),
      _createElementVNode("div", {
        ref_key: "mascotRef",
        ref: mascotRef,
        class: _normalizeClass(["mascot", { 'mascot-shadow': config.value.shadow }]),
        style: _normalizeStyle(petStyle.value),
        onPointerdown: startDrag,
        onPointermove: onDrag,
        onPointerup: endDrag,
        onPointercancel: endDrag,
        onDblclick: celebrate
      }, [
        _createElementVNode("img", {
          src: currentFrame.value,
          alt: "Agent mascot",
          draggable: "false"
        }, null, 8, _hoisted_6)
      ], 38)
    ], 36),
    _createElementVNode("div", _hoisted_7, [
      _createVNode(_component_VSwitch, {
        modelValue: config.value.enabled,
        "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((config.value.enabled) = $event)),
        label: "启用插件",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createVNode(_component_VSwitch, {
        modelValue: config.value.replace_agent_entry,
        "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((config.value.replace_agent_entry) = $event)),
        label: "替换智能体入口",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createVNode(_component_VSwitch, {
        modelValue: config.value.show_sidebar_nav,
        "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((config.value.show_sidebar_nav) = $event)),
        label: "侧栏入口",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createVNode(_component_VSwitch, {
        modelValue: config.value.follow_mouse,
        "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((config.value.follow_mouse) = $event)),
        label: "跟随鼠标",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createVNode(_component_VSwitch, {
        modelValue: config.value.auto_roam,
        "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((config.value.auto_roam) = $event)),
        label: "自动游走",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createVNode(_component_VSwitch, {
        modelValue: config.value.shadow,
        "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((config.value.shadow) = $event)),
        label: "地面阴影",
        color: "primary",
        "hide-details": ""
      }, null, 8, ["modelValue"]),
      _createElementVNode("div", _hoisted_8, [
        _cache[11] || (_cache[11] = _createElementVNode("span", null, "缩放", -1)),
        _createVNode(_component_VSlider, {
          modelValue: config.value.scale,
          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((config.value.scale) = $event)),
          min: 0.6,
          max: 2,
          step: 0.05,
          "hide-details": "",
          color: "primary"
        }, null, 8, ["modelValue"])
      ]),
      _createElementVNode("div", _hoisted_9, [
        _cache[12] || (_cache[12] = _createElementVNode("span", null, "速度", -1)),
        _createVNode(_component_VSlider, {
          modelValue: config.value.speed,
          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((config.value.speed) = $event)),
          min: 0.4,
          max: 2,
          step: 0.05,
          "hide-details": "",
          color: "primary"
        }, null, 8, ["modelValue"])
      ])
    ])
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-5c170f7e"]]);

export { _export_sfc as _, AppPage as default };
