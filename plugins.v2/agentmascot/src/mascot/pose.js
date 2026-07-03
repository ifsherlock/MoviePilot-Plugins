import { GROUND_FOOT_ANCHOR } from './anchors'

export function pose(name, anchor = GROUND_FOOT_ANCHOR, velocity = [0, 0], duration = 250) {
  return {
    imageName: name,
    anchor: [...anchor],
    velocity: [...velocity],
    duration,
  }
}
