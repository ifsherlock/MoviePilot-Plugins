<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  rarHelpItems: { type: Array, default: () => [] },
  copyMessage: { type: String, default: '' },
  copyError: { type: String, default: '' },
  rarDependencyStatus: { type: Object, default: () => ({}) },
})

defineEmits([
  'update:modelValue',
  'copy-help-text',
])
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="820"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <VCard class="rar-help-dialog" rounded="xl">
      <VCardTitle class="dialog-title">
        <span>RAR 解压器说明</span>
        <VBtn icon="mdi-close" variant="text" @click="$emit('update:modelValue', false)" />
      </VCardTitle>
      <VDivider />
      <VCardText>
        <div class="rar-help-summary">
          <p><strong>说明：</strong><code>rarfile</code> 只是 Python 调用封装，不是独立解压器。</p>
          <p><strong>要求：</strong>MoviePilot 容器内需要能执行 <code>unrar</code>、<code>7z</code>、<code>7za</code>、<code>7zz</code> 或 <code>bsdtar</code>。</p>
          <p><strong>方案：</strong>临时测试可在容器内安装；长期使用推荐通过国内镜像下载宿主机静态 <code>7zz</code>，设置执行权限后映射到容器内 <code>/usr/local/bin/7z</code>。</p>
        </div>

        <div class="rar-help-list">
          <section
            v-for="item in rarHelpItems"
            :key="item.title"
            class="rar-help-row"
          >
            <div class="rar-help-row-head">
              <div class="rar-help-row-title">
                <span class="rar-help-step">{{ item.badge }}</span>
                <strong>{{ item.title }}</strong>
              </div>
              <button
                type="button"
                class="rar-help-copy"
                @click="$emit('copy-help-text', item.command, item.copyLabel)"
              >
                {{ item.button }}
              </button>
            </div>
            <p>{{ item.description }}</p>
            <div class="command-block">
              <pre>{{ item.command }}</pre>
            </div>
          </section>
        </div>

        <VAlert
          v-if="copyMessage"
          class="mt-4"
          type="success"
          variant="tonal"
          :text="copyMessage"
        />
        <VAlert
          v-else-if="copyError"
          class="mt-4"
          type="warning"
          variant="tonal"
          :text="copyError"
        />

        <VAlert
          v-if="rarDependencyStatus.message"
          class="mt-4"
          :type="rarDependencyStatus.state === 'ready' ? 'success' : 'warning'"
          variant="tonal"
          :text="rarDependencyStatus.message"
        />

        <VAlert
          class="mt-4"
          type="info"
          variant="tonal"
          text="插件不会主动重启 Docker 容器。映射文件后需要按你的部署方式重建或重启 MoviePilot 容器；安装或映射完成后，刷新插件状态即可重新检测。"
        />
      </VCardText>
    </VCard>
  </VDialog>
</template>

<style scoped>
.rar-help-dialog {
  background:
    radial-gradient(circle at 12% 0%, rgba(80, 126, 107, 0.14), transparent 30%),
    #fffaf2;
}

.dialog-title {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.rar-help-summary {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-radius: 16px;
  background: rgba(245, 241, 232, 0.68);
}

.rar-help-summary p,
.rar-help-row p {
  margin: 0;
  color: #53655f;
  line-height: 1.7;
}

.rar-help-list {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.rar-help-row {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid rgba(91, 109, 100, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
}

.rar-help-row-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.rar-help-row-title {
  display: flex;
  gap: 10px;
  align-items: center;
}

.rar-help-step {
  padding: 3px 8px;
  border-radius: 999px;
  background: #fff4da;
  color: #8a5f23;
  font-size: 12px;
  font-weight: 900;
}

.rar-help-copy {
  padding: 7px 11px;
  border: 1px solid rgba(91, 109, 100, 0.16);
  border-radius: 999px;
  background: #fffaf2;
  color: #30443f;
  font-weight: 900;
}

.command-block {
  overflow: hidden;
  border-radius: 12px;
}

.command-block pre {
  padding: 12px;
  margin: 0;
  overflow-x: auto;
  border-radius: 12px;
  background: #2f443d;
  color: #fff6e8;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 900px) {
  .rar-help-row-head {
    align-items: stretch;
    flex-direction: column;
  }

  .rar-help-copy {
    width: 100%;
  }
}
</style>
