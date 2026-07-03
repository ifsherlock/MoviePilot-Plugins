import { SHIMEJI_IMAGES } from './assets'
import { GROUND_FOOT_ANCHOR } from './anchors'

export function pose(name, anchor = GROUND_FOOT_ANCHOR, velocity = [0, 0], duration = 250) {
  return {
    image: SHIMEJI_IMAGES[name],
    imageName: name,
    anchor: [...anchor],
    velocity: [...velocity],
    duration,
  }
}
