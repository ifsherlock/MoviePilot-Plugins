import {
  CEILING_BEHAVIORS,
  GROUND_BEHAVIORS,
  WALL_BEHAVIORS,
  resolveMascotBehaviors,
} from './behaviors'
import { FEATURE_SEMANTIC_ACTIONS, REQUIRED_SEMANTIC_ACTIONS } from './semanticActions'

const ACTION_LABELS = {
  idle: '待机',
  walk: '走路',
  run: '跑步',
  jump: '跳跃',
  fall: '下坠',
  sleep: '睡觉',
  drag: '拖拽',
  resist: '挣扎',
  think: '思考',
  surprise: '惊讶',
  cheer: '欢呼',
  spinCelebrate: '转圈庆祝',
}

const BEHAVIOR_LABELS = {
  rest: '原地休息',
  roam: '随机游走',
  goWall: '去墙边',
  leap: '飞跃',
  holdWall: '贴墙停留',
  climbWall: '爬墙',
  fallFromWall: '墙面下落',
  goCeiling: '上天花板',
  holdCeiling: '吸顶停留',
  crawlCeiling: '天花板移动',
  dropFromCeiling: '天花板下落',
}

const ACTION_GROUPS = [
  { id: 'daily', title: '日常', actions: ['idle', 'sleep', 'think'] },
  { id: 'move', title: '移动', actions: ['walk', 'run'] },
  { id: 'air', title: '空中', actions: ['jump', 'fall'] },
  { id: 'interact', title: '交互', actions: ['drag', 'resist', 'surprise'] },
  { id: 'feature', title: '角色特色', actions: ['cheer', 'spinCelebrate'] },
]

const BEHAVIOR_GROUPS = [
  { id: 'ground', title: '地面行为', behaviors: GROUND_BEHAVIORS },
  { id: 'wall', title: '墙面行为', behaviors: WALL_BEHAVIORS },
  { id: 'ceiling', title: '天花板行为', behaviors: CEILING_BEHAVIORS },
]

export const ACTION_LAB_CORE_ACTIONS = {
  chibiterasu: ['idle', 'walk', 'run', 'jump', 'fall', 'drag', 'sleep'],
  nailong: ['idle', 'walk', 'run', 'jump', 'fall', 'drag', 'sleep', 'resist'],
  kurisu: ['idle', 'walk', 'run', 'jump', 'fall', 'drag', 'sleep', 'think', 'surprise', 'cheer', 'spinCelebrate'],
}

export const ACTION_LAB_CORE_BEHAVIORS = {
  chibiterasu: ['roam', 'goWall', 'leap', 'holdWall', 'climbWall', 'holdCeiling', 'crawlCeiling'],
  nailong: ['roam', 'goWall', 'leap', 'holdWall', 'climbWall', 'holdCeiling', 'crawlCeiling'],
  kurisu: ['roam', 'goWall', 'leap', 'holdWall', 'climbWall', 'holdCeiling', 'crawlCeiling'],
}

function actionAvailable(mascot, name) {
  return REQUIRED_SEMANTIC_ACTIONS.includes(name) || (FEATURE_SEMANTIC_ACTIONS[mascot] || []).includes(name)
}

export function actionLabGroupsForMascot(mascot = 'chibiterasu') {
  const actionGroups = ACTION_GROUPS.map(group => ({
    ...group,
    items: group.actions
      .filter(name => actionAvailable(mascot, name))
      .map(name => ({
        id: name,
        kind: 'action',
        label: ACTION_LABELS[name] || name,
      })),
  })).filter(group => group.items.length)

  const behaviorGroups = BEHAVIOR_GROUPS.map(group => ({
    ...group,
    items: resolveMascotBehaviors(group.id, group.behaviors, mascot).map(behavior => ({
      id: behavior.id,
      kind: 'behavior',
      label: BEHAVIOR_LABELS[behavior.id] || behavior.id,
    })),
  })).filter(group => group.items.length)

  return [...actionGroups, ...behaviorGroups]
}

export function actionLabCoreScenariosForMascot(mascot = 'chibiterasu') {
  return [
    ...(ACTION_LAB_CORE_ACTIONS[mascot] || ACTION_LAB_CORE_ACTIONS.chibiterasu).map(id => ({ id, kind: 'action' })),
    ...(ACTION_LAB_CORE_BEHAVIORS[mascot] || ACTION_LAB_CORE_BEHAVIORS.chibiterasu).map(id => ({ id, kind: 'behavior' })),
  ]
}
