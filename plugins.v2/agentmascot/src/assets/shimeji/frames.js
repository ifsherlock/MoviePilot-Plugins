import icon from './icon.png'
import shime1 from './shime1.png'
import shime2 from './shime2.png'
import shime3 from './shime3.png'
import shime4 from './shime4.png'
import shime5 from './shime5.png'
import shime6 from './shime6.png'
import shime7 from './shime7.png'
import shime8 from './shime8.png'
import shime9 from './shime9.png'
import shime10 from './shime10.png'
import shime11 from './shime11.png'
import shime12 from './shime12.png'
import shime13 from './shime13.png'
import shime14 from './shime14.png'
import shime15 from './shime15.png'
import shime16 from './shime16.png'
import shime17 from './shime17.png'
import shime18 from './shime18.png'
import shime19 from './shime19.png'
import shime20 from './shime20.png'
import shime21 from './shime21.png'
import shime22 from './shime22.png'
import shime23 from './shime23.png'
import shime24 from './shime24.png'
import shime25 from './shime25.png'
import shime26 from './shime26.png'
import shime27 from './shime27.png'
import shime28 from './shime28.png'
import shime29 from './shime29.png'
import shime30 from './shime30.png'
import shime31 from './shime31.png'
import shime32 from './shime32.png'
import shime33 from './shime33.png'
import shime34 from './shime34.png'
import shime35 from './shime35.png'
import shime36 from './shime36.png'
import shime37 from './shime37.png'
import shime38 from './shime38.png'
import shime39 from './shime39.png'
import shime40 from './shime40.png'
import shime41 from './shime41.png'
import shime42 from './shime42.png'
import shime43 from './shime43.png'
import shime44 from './shime44.png'
import shime45 from './shime45.png'
import shime46 from './shime46.png'
import shime47 from './shime47.png'
import shime48 from './shime48.png'
import shime49 from './shime49.png'
import shime50 from './shime50.png'
import shime51 from './shime51.png'
import shime52 from './shime52.png'
import shime53 from './shime53.png'
import shime54 from './shime54.png'
import shime55 from './shime55.png'
import shime56 from './shime56.png'
import shime57 from './shime57.png'
import shime58 from './shime58.png'
import shime59 from './shime59.png'
import shime60 from './shime60.png'
import shime61 from './shime61.png'
import shime62 from './shime62.png'
import shime63 from './shime63.png'
import shime64 from './shime64.png'
import shime65 from './shime65.png'
import shime66 from './shime66.png'

export const mascotIcon = icon

export const SHIMEJI_IMAGES = {
  shime1,
  shime2,
  shime3,
  shime4,
  shime5,
  shime6,
  shime7,
  shime8,
  shime9,
  shime10,
  shime11,
  shime12,
  shime13,
  shime14,
  shime15,
  shime16,
  shime17,
  shime18,
  shime19,
  shime20,
  shime21,
  shime22,
  shime23,
  shime24,
  shime25,
  shime26,
  shime27,
  shime28,
  shime29,
  shime30,
  shime31,
  shime32,
  shime33,
  shime34,
  shime35,
  shime36,
  shime37,
  shime38,
  shime39,
  shime40,
  shime41,
  shime42,
  shime43,
  shime44,
  shime45,
  shime46,
  shime47,
  shime48,
  shime49,
  shime50,
  shime51,
  shime52,
  shime53,
  shime54,
  shime55,
  shime56,
  shime57,
  shime58,
  shime59,
  shime60,
  shime61,
  shime62,
  shime63,
  shime64,
  shime65,
  shime66,
}

function pose(name, anchor = [64, 128], velocity = [0, 0], duration = 250) {
  return {
    image: SHIMEJI_IMAGES[name],
    imageName: name,
    anchor,
    velocity,
    duration,
  }
}

// These are the original Chibiterasu Shimeji action poses from actions.xml.
// The Java runtime moves left by default and flips the sprite when it looks right.
export const SHIMEJI_ACTIONS = {
  stand: {
    label: '立つ',
    frame: 'ground',
    loop: true,
    poses: [pose('shime1')],
  },
  walk: {
    label: '歩く',
    frame: 'ground',
    loop: true,
    poses: [
      pose('shime1', [64, 128], [-2, 0], 6),
      pose('shime2', [64, 128], [-2, 0], 6),
      pose('shime1', [64, 128], [-2, 0], 6),
      pose('shime3', [64, 128], [-2, 0], 6),
    ],
  },
  run: {
    label: '走る',
    frame: 'ground',
    loop: true,
    poses: [
      pose('shime47', [64, 138], [-4, 0], 5),
      pose('shime48', [64, 128], [-4, 0], 3),
      pose('shime49', [64, 128], [-4, 0], 3),
    ],
  },
  dash: {
    label: '猛ダッシュ',
    frame: 'ground',
    loop: true,
    poses: [
      pose('shime47', [64, 135], [-8, 0], 5),
      pose('shime48', [64, 128], [-8, 0], 3),
      pose('shime49', [64, 128], [-8, 0], 3),
    ],
  },
  sit: {
    label: '座る',
    frame: 'ground',
    loop: true,
    poses: [pose('shime11')],
  },
  relaxedSit: {
    label: '楽に座る',
    frame: 'ground',
    loop: true,
    poses: [pose('shime30')],
  },
  sitFeetDown: {
    label: '足を下ろして座る',
    frame: 'ground',
    loop: true,
    poses: [pose('shime31')],
  },
  dangleFeet: {
    label: '足をぶらぶらさせる',
    frame: 'ground',
    loop: true,
    poses: [
      pose('shime51', [64, 128], [0, 0], 25),
      pose('shime32', [64, 128], [0, 0], 25),
      pose('shime51', [64, 128], [0, 0], 25),
      pose('shime33', [64, 128], [0, 0], 25),
    ],
  },
  lookUp: {
    label: '座って見上げる',
    frame: 'ground',
    loop: true,
    poses: [pose('shime26')],
  },
  lie: {
    label: '寝そべる',
    frame: 'ground',
    loop: true,
    poses: [pose('shime50')],
  },
  crawl: {
    label: 'ずりずり',
    frame: 'ground',
    loop: true,
    poses: [
      pose('shime20', [64, 128], [0, 0], 28),
      pose('shime20', [64, 128], [-2, 0], 4),
      pose('shime21', [64, 128], [-2, 0], 4),
      pose('shime21', [64, 128], [-1, 0], 4),
      pose('shime21', [64, 128], [0, 0], 24),
    ],
  },
  jump: {
    label: 'ジャンプ',
    frame: 'air',
    loop: true,
    poses: [pose('shime22')],
  },
  fall: {
    label: '落ちる',
    frame: 'air',
    loop: true,
    poses: [pose('shime4')],
  },
  bounce: {
    label: '跳ねる',
    frame: 'ground',
    loop: true,
    poses: [
      pose('shime18', [64, 128], [0, 0], 4),
      pose('shime19', [64, 128], [0, 0], 4),
    ],
  },
  holdWall: {
    label: '壁に掴まる',
    frame: 'wall',
    loop: true,
    poses: [pose('shime63', [41, 128], [0, 0], 250)],
  },
  climbWallUp: {
    label: '壁を登る',
    frame: 'wall',
    loop: true,
    poses: [
      pose('shime14', [41, 128], [0, 0], 16),
      pose('shime14', [41, 128], [0, -1], 4),
      pose('shime12', [41, 128], [0, -1], 4),
      pose('shime13', [41, 128], [0, -1], 4),
      pose('shime13', [41, 128], [0, 0], 16),
      pose('shime13', [41, 128], [0, -2], 4),
      pose('shime12', [41, 128], [0, -2], 4),
      pose('shime14', [41, 128], [0, -2], 4),
    ],
  },
  climbWallDown: {
    label: '壁を降りる',
    frame: 'wall',
    loop: true,
    poses: [
      pose('shime14', [41, 128], [0, 0], 16),
      pose('shime14', [41, 128], [0, 2], 4),
      pose('shime12', [41, 128], [0, 2], 4),
      pose('shime13', [41, 128], [0, 2], 4),
      pose('shime13', [41, 128], [0, 0], 16),
      pose('shime13', [41, 128], [0, 1], 4),
      pose('shime12', [41, 128], [0, 1], 4),
      pose('shime14', [41, 128], [0, 1], 4),
    ],
  },
  holdCeiling: {
    label: '天井に掴まる',
    frame: 'ceiling',
    loop: true,
    poses: [pose('shime65', [64, 48], [0, 0], 250)],
  },
  crawlCeiling: {
    label: '天井を伝う',
    frame: 'ceiling',
    loop: true,
    poses: [
      pose('shime23', [64, 48], [0, 0], 16),
      pose('shime24', [64, 48], [0, 0], 4),
      pose('shime25', [64, 53], [-11, 0], 1),
      pose('shime25', [64, 55], [-10, 0], 2),
      pose('shime25', [64, 58], [-9, 0], 4),
      pose('shime25', [64, 55], [-8, 0], 3),
      pose('shime25', [64, 52], [-7, 0], 2),
      pose('shime64', [64, 48], [0, 0], 5),
      pose('shime23', [64, 48], [0, 0], 4),
    ],
  },
  drag: {
    label: 'つままれる',
    frame: 'air',
    loop: true,
    poses: [
      pose('shime9', [64, 128], [0, 0], 5),
      pose('shime7', [64, 128], [0, 0], 5),
      pose('shime59', [64, 128], [0, 0], 5),
      pose('shime8', [64, 128], [0, 0], 5),
      pose('shime10', [64, 128], [0, 0], 5),
    ],
  },
  resist: {
    label: '抵抗する',
    frame: 'air',
    loop: true,
    poses: [
      pose('shime5', [64, 128], [0, 0], 5),
      pose('shime6', [64, 128], [0, 0], 5),
      pose('shime5', [64, 128], [0, 0], 5),
      pose('shime6', [64, 128], [0, 0], 5),
      pose('shime59', [64, 128], [0, 0], 50),
    ],
  },
  pullOut: {
    label: '引っこ抜く1',
    frame: 'ground',
    loop: false,
    poses: [
      pose('shime1', [64, 128], [0, 0], 16),
      pose('shime38', [96, 128], [0, 0], 30),
      pose('shime39', [96, 128], [0, 0], 20),
      pose('shime40', [96, 128], [0, 0], 20),
      pose('shime39', [96, 128], [0, 0], 10),
      pose('shime40', [96, 128], [0, 0], 10),
      pose('shime41', [96, 128], [0, 0], 40),
    ],
  },
  split: {
    label: '分裂1',
    frame: 'ground',
    loop: false,
    poses: [
      pose('shime42', [64, 128], [0, 0], 20),
      pose('shime43', [64, 128], [0, 0], 10),
      pose('shime44', [64, 128], [0, 0], 5),
      pose('shime45', [64, 128], [0, 0], 15),
      pose('shime46', [64, 128], [0, 0], 5),
      pose('shime52', [64, 128], [0, 0], 15),
      pose('shime53', [64, 128], [0, 0], 7),
      pose('shime54', [64, 128], [0, 0], 5),
      pose('shime55', [64, 128], [0, 0], 15),
      pose('shime56', [64, 128], [0, 0], 15),
      pose('shime57', [64, 128], [0, 0], 10),
      pose('shime58', [64, 128], [0, 0], 30),
    ],
  },
}

export const ACTION_FRAMES = {
  idle: SHIMEJI_ACTIONS.stand.poses.map(item => item.image),
  walk: SHIMEJI_ACTIONS.walk.poses.map(item => item.image),
  run: SHIMEJI_ACTIONS.run.poses.map(item => item.image),
  follow: SHIMEJI_ACTIONS.dash.poses.map(item => item.image),
  drag: SHIMEJI_ACTIONS.drag.poses.map(item => item.image),
  sleep: SHIMEJI_ACTIONS.lie.poses.map(item => item.image),
  celebrate: SHIMEJI_ACTIONS.split.poses.map(item => item.image),
}
