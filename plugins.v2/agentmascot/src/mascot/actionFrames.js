import { SHIMEJI_ACTIONS } from './actions'

export const ACTION_FRAMES = {
  idle: SHIMEJI_ACTIONS.stand.poses.map(item => item.image),
  walk: SHIMEJI_ACTIONS.walk.poses.map(item => item.image),
  run: SHIMEJI_ACTIONS.run.poses.map(item => item.image),
  follow: SHIMEJI_ACTIONS.dash.poses.map(item => item.image),
  drag: SHIMEJI_ACTIONS.drag.poses.map(item => item.image),
  sleep: SHIMEJI_ACTIONS.lie.poses.map(item => item.image),
  celebrate: SHIMEJI_ACTIONS.split.poses.map(item => item.image),
}
