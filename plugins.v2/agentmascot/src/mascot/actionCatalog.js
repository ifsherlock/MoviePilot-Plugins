export const ACTION_CATALOG = {
  ground: [
    'stand',
    'walk',
    'run',
    'dash',
    'sit',
    'relaxedSit',
    'sitFeetDown',
    'dangleFeet',
    'lookUp',
    'think',
    'lie',
    'crawl',
    'bounce',
  ],
  air: ['jump', 'fall'],
  wall: ['holdWall', 'climbWallUp', 'climbWallDown'],
  ceiling: ['holdCeiling', 'crawlCeiling'],
  drag: ['drag', 'resist'],
  rest: ['stand', 'sit', 'lie', 'relaxedSit', 'dangleFeet', 'lookUp', 'think'],
  special: ['pullOut', 'split', 'surprise', 'cheer', 'spinCelebrate'],
}

export const GROUND_MOVE_ACTIONS = ['walk', 'run', 'dash']
export const REST_ACTIONS = ACTION_CATALOG.rest
export const WALL_REST_ACTIONS = ['holdWall']
export const CEILING_REST_ACTIONS = ['holdCeiling']
export const INTERRUPT_ACTIONS = [
  ...ACTION_CATALOG.drag,
  'split',
  'surprise',
  'cheer',
  'spinCelebrate',
]
