<script setup>
import { ref } from 'vue'
import '../styles/theme.css'
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
      <div class="text-h6 ms-3">字幕匹配</div>
      <VSpacer />
      <VBtn
        class="mobile-touch-target"
        aria-label="刷新字幕匹配状态"
        icon="mdi-refresh"
        variant="text"
        :loading="pageRef?.loading || pageRef?.refreshing"
        @click="pageRef?.loadStatus()"
      />
      <VBtn class="mobile-touch-target" aria-label="关闭字幕匹配" icon="mdi-close" variant="text" @click="emit('close')" />
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
.subtitlemanualupload-page-wrapper {
  min-width: 0;
}

.sticky-toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgb(var(--v-theme-surface));
}

.sticky-toolbar .text-h6 {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

<style>
@media (max-width: 900px) {
  .subtitlemanualupload-page-wrapper .mobile-touch-target {
    --v-btn-height: 44px;
    min-width: 44px;
    min-height: 44px;
    width: 44px;
    height: 44px;
  }
}
</style>
