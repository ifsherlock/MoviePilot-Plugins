import { SHIMEJI_ACTIONS } from './actions'

export const ACTION_FRAMES = {
  idle: SHIMEJI_ACTIONS.stand.poses.map(item => item.imageName),
  walk: SHIMEJI_ACTIONS.walk.poses.map(item => item.imageName),
  run: SHIMEJI_ACTIONS.run.poses.map(item => item.imageName),
  follow: SHIMEJI_ACTIONS.dash.poses.map(item => item.imageName),
  drag: SHIMEJI_ACTIONS.drag.poses.map(item => item.imageName),
  sleep: SHIMEJI_ACTIONS.lie.poses.map(item => item.imageName),
  celebrate: SHIMEJI_ACTIONS.split.poses.map(item => item.imageName),
}
