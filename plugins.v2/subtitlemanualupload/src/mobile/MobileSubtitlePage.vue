<script setup>
import MatchHistoryPanel from '../components/MatchHistoryPanel.vue'
import './mobile.css'
import MobileSubtitleDetail from './MobileSubtitleDetail.vue'
import MobileSubtitleHome from './MobileSubtitleHome.vue'

defineProps({
  view: { type: Object, required: true },
  actions: { type: Object, required: true },
})
</script>

<template>
  <main class="smu-mobile-page">
    <VAlert
      v-if="view.feedback.error"
      type="error"
      variant="tonal"
      :text="view.feedback.error"
    />
    <VAlert
      v-else-if="view.feedback.message"
      type="success"
      variant="tonal"
      :text="view.feedback.message"
    />

    <MobileSubtitleDetail
      v-if="view.detail.selectedMedia"
      :detail="view.detail"
      :actions="actions.detail"
    />

    <template v-else>
      <MobileSubtitleHome
        v-if="view.home.rootTab === 'match'"
        :home="view.home"
        :actions="actions.home"
      />

      <section v-else class="smu-mobile-history">
        <header class="smu-mobile-history-header">
          <VBtn
            icon="mdi-arrow-left"
            variant="text"
            title="返回字幕匹配"
            @click="actions.home.setRootTab('match')"
          />
          <h2>匹配历史</h2>
          <VBtn
            icon="mdi-tray-full"
            variant="text"
            title="自动队列"
            @click="actions.home.openAutoQueue()"
          />
        </header>

        <MatchHistoryPanel
          mobile
          v-bind="view.history.panelProps"
          @open-auto-queue="actions.home.openAutoQueue()"
          @load-more-match-history="actions.history.loadMoreMatchHistory()"
        />
      </section>
    </template>
  </main>
</template>
