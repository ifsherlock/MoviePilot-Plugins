<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  onlineTitle: { type: String, default: '' },
  onlineTargets: { type: Array, default: () => [] },
  selectedOnlineResults: { type: Array, default: () => [] },
  onlineAiDownloading: { type: Boolean, default: false },
  onlinePreviewDownloading: { type: Boolean, default: false },
  canSubmitOnlineAiTranslate: { type: Boolean, default: false },
  onlineDownloading: { type: Boolean, default: false },
  onlineKeyword: { type: String, default: '' },
  onlineSelectedProviders: { type: Array, default: () => [] },
  onlineProviderItems: { type: Array, default: () => [] },
  onlineSearching: { type: Boolean, default: false },
  onlineError: { type: String, default: '' },
  onlineMessages: { type: Array, default: () => [] },
  onlineMessagesCollapsed: { type: Boolean, default: false },
  onlineMessageType: { type: String, default: 'info' },
  onlineMessageSummary: { type: String, default: '' },
  hasOnlineResults: { type: Boolean, default: false },
  filteredOnlineResults: { type: Array, default: () => [] },
  onlineResults: { type: Array, default: () => [] },
  onlineLanguageFilter: { type: String, default: 'all' },
  onlineLanguageFilterItems: { type: Array, default: () => [] },
  onlineProviderFilter: { type: String, default: 'all' },
  onlineProviderFilterItems: { type: Array, default: () => [] },
  onlineProviderProgressItems: { type: Array, default: () => [] },
  selectedOnlineResultIds: { type: Array, default: () => [] },
  onlineManualLinks: { type: Array, default: () => [] },
  onlineAiConfirmDialog: { type: Boolean, default: false },
  onlineAiConfirmText: { type: String, default: '' },
  providerProgressColor: { type: Function, required: true },
  providerProgressText: { type: Function, required: true },
  providerName: { type: Function, required: true },
  onlineResultKey: { type: Function, required: true },
  onlineResultMeta: { type: Function, required: true },
  isOnlineResultDownloadable: { type: Function, required: true },
})

defineEmits([
  'update:modelValue',
  'update:onlineKeyword',
  'update:onlineSelectedProviders',
  'update:onlineMessagesCollapsed',
  'update:onlineLanguageFilter',
  'update:onlineProviderFilter',
  'update:onlineAiConfirmDialog',
  'download-online-preview',
  'request-online-ai-translate',
  'stop-online-download',
  'close-online-dialog',
  'run-online-search',
  'stop-online-search',
  'toggle-online-result',
  'confirm-online-ai-translate',
])
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="1080"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <VCard class="online-dialog" rounded="xl">
      <VCardTitle class="dialog-title online-dialog-title">
        <div>
          <span>{{ onlineTitle || '在线字幕搜索' }}</span>
          <p>{{ onlineTargets.length }} 个目标 · 下载会进入匹配预览，提交 AI 翻译会直接进入 AI 状态</p>
        </div>
        <div class="online-title-actions">
          <VBtn
            class="mobile-touch-target"
            color="success"
            :disabled="!selectedOnlineResults.length || onlineAiDownloading"
            :loading="onlinePreviewDownloading"
            @click="$emit('download-online-preview')"
          >
            下载并生成预览
          </VBtn>
          <VBtn
            class="mobile-touch-target"
            color="primary"
            variant="tonal"
            :disabled="!canSubmitOnlineAiTranslate || onlinePreviewDownloading"
            :loading="onlineAiDownloading"
            @click="$emit('request-online-ai-translate')"
          >
            提交 AI 翻译
          </VBtn>
          <VBtn
            v-if="onlineDownloading"
            class="mobile-touch-target"
            color="warning"
            variant="tonal"
            @click="$emit('stop-online-download')"
          >
            停止等待
          </VBtn>
          <VBtn
            class="mobile-touch-target"
            icon="mdi-close"
            variant="text"
            aria-label="关闭在线字幕搜索"
            @click="$emit('close-online-dialog')"
          />
        </div>
      </VCardTitle>
      <VDivider />
      <VCardActions class="online-search-actions">
        <VTextField
          :model-value="onlineKeyword"
          label="手动关键词（可选）"
          placeholder="留空按资源名、季集号自动生成"
          variant="outlined"
          density="comfortable"
          hide-details
          clearable
          @update:model-value="$emit('update:onlineKeyword', $event)"
          @keyup.enter="$emit('run-online-search')"
        />
        <VSelect
          :model-value="onlineSelectedProviders"
          :items="onlineProviderItems"
          label="字幕源"
          variant="outlined"
          density="comfortable"
          hide-details
          multiple
          chips
          @update:model-value="$emit('update:onlineSelectedProviders', $event)"
        />
        <VBtn
          class="mobile-touch-target"
          color="primary"
          :disabled="!onlineSelectedProviders.length"
          :loading="onlineSearching"
          @click="$emit('run-online-search')"
        >
          搜索
        </VBtn>
        <VBtn
          v-if="onlineSearching"
          class="mobile-touch-target"
          color="warning"
          variant="tonal"
          @click="$emit('stop-online-search')"
        >
          停止等待
        </VBtn>
      </VCardActions>
      <VDivider />
      <VCardText class="online-dialog-body">
        <VAlert
          v-if="onlineError"
          class="mb-4"
          type="error"
          variant="tonal"
          :text="onlineError"
        />
        <VAlert
          v-if="onlineMessages.length && !onlineMessagesCollapsed"
          class="online-message-summary"
          :type="onlineMessageType"
          variant="tonal"
          density="compact"
        >
          <div class="online-message-summary-content">
            <span>{{ onlineMessageSummary }}</span>
            <VBtn
              size="x-small"
              variant="text"
              @click="$emit('update:onlineMessagesCollapsed', true)"
            >
              收起
            </VBtn>
          </div>
        </VAlert>

        <div class="online-layout">
          <section class="online-results-panel">
            <div class="online-panel-head">
              <div>
                <div class="section-kicker">自动搜索</div>
                <h3>选择要下载的字幕</h3>
              </div>
              <span>{{ hasOnlineResults ? `${filteredOnlineResults.length}/${onlineResults.length} 条结果` : '暂无结果' }}</span>
            </div>
            <VChipGroup
              v-if="hasOnlineResults"
              :model-value="onlineLanguageFilter"
              class="online-provider-filter"
              mandatory
              selected-class="online-provider-filter-active"
              @update:model-value="$emit('update:onlineLanguageFilter', $event)"
            >
              <VChip
                v-for="item in onlineLanguageFilterItems"
                :key="item.value"
                :value="item.value"
                size="small"
                variant="tonal"
              >
                {{ item.title }}
              </VChip>
            </VChipGroup>
            <VChipGroup
              v-if="hasOnlineResults"
              :model-value="onlineProviderFilter"
              class="online-provider-filter"
              mandatory
              selected-class="online-provider-filter-active"
              @update:model-value="$emit('update:onlineProviderFilter', $event)"
            >
              <VChip
                v-for="item in onlineProviderFilterItems"
                :key="item.value"
                :value="item.value"
                size="small"
                variant="tonal"
              >
                {{ item.title }}
              </VChip>
            </VChipGroup>
            <div v-if="onlineProviderProgressItems.length" class="online-provider-progress">
              <VChip
                v-for="item in onlineProviderProgressItems"
                :key="item.provider"
                size="small"
                variant="tonal"
                :color="providerProgressColor(item.state)"
              >
                {{ providerName(item.provider) }} · {{ providerProgressText(item.state) }}
              </VChip>
            </div>

            <div v-if="onlineSearching && !filteredOnlineResults.length" class="online-loading">
              正在从 API 搜索字幕，先返回的结果会先显示...
            </div>
            <div v-if="filteredOnlineResults.length" class="online-result-list">
              <div
                v-for="item in filteredOnlineResults"
                :key="onlineResultKey(item)"
                class="online-result-card"
                :class="{
                  active: selectedOnlineResultIds.includes(onlineResultKey(item)),
                  disabled: !isOnlineResultDownloadable(item),
                }"
              >
                <VCheckbox
                  :model-value="selectedOnlineResultIds.includes(onlineResultKey(item))"
                  density="compact"
                  hide-details
                  :disabled="!isOnlineResultDownloadable(item)"
                  @update:model-value="value => $emit('toggle-online-result', item, value)"
                />
                <div class="online-result-main">
                  <div class="online-result-title">{{ item.title }}</div>
                  <div class="online-result-meta">
                    <span>{{ providerName(item.provider) }}</span>
                    <span>{{ onlineResultMeta(item) }}</span>
                    <span v-if="!isOnlineResultDownloadable(item)" class="online-manual-badge">
                      需手动下载
                    </span>
                  </div>
                  <p v-if="item.note">{{ item.note }}</p>
                  <p v-if="item.match_detail" class="online-match-detail">{{ item.match_detail }}</p>
                </div>
                <a
                  v-if="item.page_url"
                  class="online-open-link online-result-action"
                  :href="item.page_url"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  查看
                </a>
              </div>
            </div>
            <div v-else-if="!onlineSearching" class="empty-state">
              {{ hasOnlineResults ? '当前平台筛选下没有结果。' : '没有可自动下载的字幕结果。可以换关键词重试，或使用右侧手动搜索。' }}
            </div>
          </section>

          <aside class="manual-links-panel">
            <div class="section-kicker">手动搜索</div>
            <h3>跳转字幕站</h3>
            <p>自动搜索失败或源站需要验证时，可打开链接下载字幕包后回到本页上传。</p>
            <div
              v-for="provider in onlineManualLinks"
              :key="provider.provider"
              class="manual-provider"
            >
              <div class="manual-provider-head">
                <strong>{{ provider.name }}</strong>
              </div>
              <div class="manual-keywords">
                <a
                  v-for="link in provider.links"
                  :key="`${provider.provider}-${link.keyword}`"
                  :href="link.url"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ link.keyword }}
                </a>
              </div>
            </div>
          </aside>
        </div>
      </VCardText>
    </VCard>
  </VDialog>

  <VDialog
    :model-value="onlineAiConfirmDialog"
    max-width="520"
    @update:model-value="$emit('update:onlineAiConfirmDialog', $event)"
  >
    <VCard rounded="lg">
      <VCardTitle class="dialog-title compact">
        <div>
          <span>确认提交 AI 翻译</span>
          <p>{{ onlineAiConfirmText }}</p>
        </div>
      </VCardTitle>
      <VDivider />
      <VCardText>
        <VAlert
          type="warning"
          variant="tonal"
          text="确认后会在后台下载所选外语字幕，智能调轴后提交到 AI 字幕生成队列；不会打开匹配预览，误触后可在 AI 状态里取消。"
        />
      </VCardText>
      <VCardActions class="justify-end">
        <VBtn class="mobile-touch-target" variant="text" @click="$emit('update:onlineAiConfirmDialog', false)">取消</VBtn>
        <VBtn
          class="mobile-touch-target"
          color="primary"
          variant="flat"
          :loading="onlineAiDownloading"
          @click="$emit('confirm-online-ai-translate')"
        >
          确认提交
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped>
.online-dialog {
  background: var(--smu-dialog-bg);
  color: var(--smu-text);
  backdrop-filter: blur(16px);
}

.online-dialog-body {
  min-height: 0;
}

.dialog-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dialog-title p {
  margin: 4px 0 0;
  color: var(--smu-text-muted);
  font-size: 12px;
  font-weight: 400;
}

.online-title-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}

.online-search-actions {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(220px, 0.7fr) auto;
  gap: 12px;
  padding: 14px 18px;
  background: var(--smu-dialog-bar-bg);
}

.online-message-summary {
  margin-bottom: 14px;
}

.online-message-summary-content {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.online-message-summary-content span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.online-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 16px;
}

.online-results-panel,
.manual-links-panel {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--smu-border);
  border-radius: 22px;
  background: var(--smu-card-bg);
}

.online-panel-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.online-panel-head h3,
.manual-links-panel h3 {
  margin: 4px 0 0;
}

.online-panel-head span,
.manual-links-panel p,
.manual-provider-head span,
.online-result-meta,
.online-result-main p {
  color: var(--smu-text-muted);
  font-size: 12px;
}

.section-kicker {
  color: var(--smu-accent);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.online-provider-filter {
  margin: -4px 0 12px;
}

.online-provider-progress {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.online-provider-filter-active {
  background: var(--smu-accent) !important;
  color: var(--smu-accent-text) !important;
}

.online-loading {
  padding: 24px;
  border-radius: 18px;
  background: var(--smu-card-bg-soft);
  color: var(--smu-text-muted);
  text-align: center;
}

.online-result-list {
  display: grid;
  gap: 10px;
  max-height: 520px;
  overflow-y: auto;
  padding-right: 4px;
}

.online-result-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 12px;
  border: 1px solid var(--smu-border);
  border-radius: 18px;
  background: var(--smu-card-bg);
}

.online-result-card.active {
  border-color: var(--smu-border-active);
  background: var(--smu-card-bg-active);
}

.online-result-card.disabled {
  opacity: 0.72;
  background: var(--smu-card-bg-disabled);
}

.online-result-main {
  min-width: 0;
}

.online-result-title {
  font-weight: 900;
  word-break: break-word;
}

.online-result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.online-manual-badge {
  padding: 1px 8px;
  border: 1px solid var(--smu-border-active);
  border-radius: 999px;
  background: var(--smu-accent-soft);
  color: var(--smu-accent);
  font-weight: 800;
}

.online-result-main p {
  margin: 6px 0 0;
}

.online-match-detail {
  color: var(--smu-accent) !important;
}

.online-open-link,
.manual-keywords a {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--smu-accent-soft);
  color: var(--smu-accent);
  font-size: 12px;
  font-weight: 900;
  text-decoration: none;
}

.manual-links-panel {
  align-self: start;
}

.manual-links-panel p {
  margin: 8px 0 14px;
  line-height: 1.6;
}

.manual-provider {
  display: grid;
  gap: 8px;
  padding: 10px 0;
  border-top: 1px solid var(--smu-border);
}

.manual-provider-head {
  display: grid;
  gap: 2px;
}

.manual-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.empty-state {
  padding: 28px 18px;
  border-radius: 22px;
  background: var(--smu-card-bg-soft);
  color: var(--smu-text-muted);
  text-align: center;
}

@media (max-width: 900px) {
  .online-dialog {
    max-height: calc(100dvh - 24px);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .online-dialog-body {
    min-height: 0;
    overflow-y: auto;
  }

  .dialog-title {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .dialog-title > div:first-child {
    min-width: 0;
  }

  .online-search-actions,
  .online-layout {
    grid-template-columns: 1fr;
  }

  .online-title-actions {
    width: 100%;
    justify-content: flex-end;
    flex-wrap: wrap;
  }
}

@media (max-width: 600px) {
  .online-dialog {
    width: 100%;
    max-height: 100dvh;
    border-radius: 20px 20px 0 0 !important;
  }

  .dialog-title {
    padding: 14px 16px;
  }

  .dialog-title span,
  .dialog-title p {
    overflow-wrap: anywhere;
  }

  .online-title-actions .v-btn {
    flex: 1 1 auto;
    min-width: 0;
  }

  .online-title-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr)) 44px;
  }

  .online-title-actions .mobile-touch-target {
    min-width: 44px;
    min-height: 44px;
  }

  .online-title-actions .mobile-touch-target:nth-child(1),
  .online-title-actions .mobile-touch-target:nth-child(2) {
    grid-column: span 1;
  }

  .online-search-actions {
    position: sticky;
    z-index: 3;
    top: 0;
    padding: 12px 16px;
    border-bottom: 1px solid var(--smu-border);
  }

  .online-dialog-body {
    padding-bottom: calc(86px + env(safe-area-inset-bottom, 0px));
  }

  .online-results-panel,
  .manual-links-panel {
    padding: 12px;
    border-radius: 18px;
  }

  .online-panel-head {
    display: grid;
    align-items: stretch;
  }

  .online-result-list {
    max-height: none;
    overflow-y: visible;
  }

  .online-result-card {
    grid-template-columns: auto minmax(0, 1fr);
    align-items: start;
    border-radius: 16px;
  }

  .online-result-action {
    grid-column: 2;
    justify-self: start;
    min-width: 72px;
  }
}
</style>

<style>
@media (max-width: 900px) {
  .online-dialog .mobile-touch-target,
  .online-open-link {
    --v-btn-height: 44px;
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
