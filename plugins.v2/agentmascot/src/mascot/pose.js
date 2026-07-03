import { SHIMEJI_IMAGES } from './assets'

export function pose(name, anchor = [64, 128], velocity = [0, 0], duration = 250) {
  return {
    image: SHIMEJI_IMAGES[name],
    imageName: name,
    anchor,
    velocity,
    duration,
  }
}
