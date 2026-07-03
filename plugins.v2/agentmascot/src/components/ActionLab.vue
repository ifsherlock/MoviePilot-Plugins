<script setup>
import { computed } from 'vue'
import { actionLabGroupsForMascot } from '../mascot/actionLab'

const props = defineProps({
  debugState: {
    type: Object,
    required: true,
  },
  mascot: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['play-action', 'play-behavior', 'reset'])

const groups = computed(() => actionLabGroupsForMascot(props.mascot))

function trigger(item) {
  if (item.kind === 'behavior') emit('play-behavior', item.id)
  else emit('play-action', item.id)
}
</script>

<template>
  <section class="action-lab">
    <div class="action-lab__hud">
      <div>
        <span>surface</span>
        <strong>{{ debugState.surface }}</strong>
      </div>
      <div>
        <span>state</span>
        <strong>{{ debugState.state }}</strong>
      </div>
      <div>
        <span>action</span>
        <strong>{{ debugState.action }}</strong>
      </div>
      <div>
        <span>pose</span>
        <strong>{{ debugState.poseIndex }}</strong>
      </div>
      <button class="action-lab__reset" type="button" @click="$emit('reset')">复位</button>
    </div>

    <details class="action-lab__details">
      <summary>目标与速度</summary>
      <div class="action-lab__metrics">
        <span>x {{ Math.round(debugState.targetX) }}</span>
        <span>y {{ Math.round(debugState.targetY) }}</span>
        <span>vx {{ debugState.vx.toFixed(2) }}</span>
        <span>vy {{ debugState.vy.toFixed(2) }}</span>
      </div>
    </details>

    <div class="action-lab__groups">
      <div v-for="group in groups" :key="group.id" class="action-lab__group">
        <div class="action-lab__title">{{ group.title }}</div>
        <div class="action-lab__buttons">
          <button
            v-for="item in group.items"
            :key="`${item.kind}-${item.id}`"
            class="action-lab__button"
            type="button"
            @click="trigger(item)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.action-lab {
  display: grid;
  gap: 12px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
}
.action-lab__hud {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.action-lab__hud div {
  min-width: 92px;
}
.action-lab__hud span {
  display: block;
  font-size: 0.72rem;
  line-height: 1.2;
  opacity: 0.62;
}
.action-lab__hud strong {
  display: block;
  max-width: 140px;
  overflow: hidden;
  font-size: 0.9rem;
  font-weight: 650;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.action-lab__reset,
.action-lab__button {
  min-height: 34px;
  border: 1px solid rgba(15, 23, 42, 0.22);
  border-radius: 8px;
  color: #111827;
  background: rgba(255, 255, 255, 0.86);
  cursor: pointer;
  font: inherit;
  line-height: 1.2;
}
.action-lab__reset {
  padding: 0 14px;
  margin-left: auto;
}
.action-lab__reset:hover,
.action-lab__button:hover {
  border-color: rgba(37, 99, 235, 0.72);
  background: rgba(37, 99, 235, 0.08);
}
.action-lab__details {
  font-size: 0.85rem;
  opacity: 0.86;
}
.action-lab__details summary {
  cursor: pointer;
}
.action-lab__metrics {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 8px;
}
.action-lab__groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
}
.action-lab__group {
  display: grid;
  gap: 8px;
  align-content: start;
}
.action-lab__title {
  font-size: 0.86rem;
  font-weight: 650;
  opacity: 0.78;
}
.action-lab__buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.action-lab__button {
  min-width: 72px;
  padding: 0 12px;
}

@media (max-width: 720px) {
  .action-lab {
    padding: 10px 12px;
  }
  .action-lab__groups {
    grid-template-columns: 1fr;
  }
  .action-lab__reset {
    margin-left: 0;
  }
}
</style>
