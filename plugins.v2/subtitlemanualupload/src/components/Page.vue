<script setup>
import { ref } from 'vue'
import AppPage from './AppPage.vue'

const props = defineProps({
  api: {
    type: Object,
    default: () => ({}),
  },
  pluginId: {
    type: String,
    default: 'SubtitleManualUpload',
  },
  navKey: {
    type: String,
    default: 'main',
  },
})

const emit = defineEmits(['close'])
const pageRef = ref(null)
</script>

<template>
  <div class="subtitlemanualupload-page-wrapper">
    <VToolbar density="comfortable" class="sticky-toolbar">
      <div class="text-h6 ms-3">字幕手传匹配</div>
      <VSpacer />
      <VBtn
        icon="mdi-refresh"
        variant="text"
        :loading="pageRef?.loading || pageRef?.refreshing"
        @click="pageRef?.loadStatus()"
      />
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <AppPage
      ref="pageRef"
      :api="props.api"
      :plugin-id="props.pluginId"
      :nav-key="props.navKey"
      hide-title
    />
  </div>
</template>

<style scoped>
.sticky-toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgb(var(--v-theme-surface));
}
</style>
