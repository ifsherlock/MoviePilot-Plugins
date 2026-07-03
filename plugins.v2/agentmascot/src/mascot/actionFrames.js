import {
  mascotActionFrames,
  semanticActionFrames,
} from './semanticActions'

export const ACTION_FRAMES = mascotActionFrames('chibiterasu', [
  'idle',
  'walk',
  'run',
  'follow',
  'drag',
  'sleep',
  'cheer',
])

export function actionFramesForMascot(mascot, semanticName) {
  return semanticActionFrames(mascot, semanticName)
}

export function actionFrameGroupsForMascot(mascot) {
  return mascotActionFrames(mascot)
}
