import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

function relativeMascotAssets() {
  return {
    name: 'agentmascot-relative-assets',
    generateBundle(_, bundle) {
      const assetPattern = /(["'])\/assets\/([^"']+\.png)\1/g

      for (const chunk of Object.values(bundle)) {
        if (chunk.type !== 'chunk') {
          continue
        }

        chunk.code = chunk.code.replace(assetPattern, (_, __, fileName) => {
          return `new URL('${fileName}', import.meta.url).href`
        })
      }
    },
  }
}

export default defineConfig({
  plugins: [
    vue(),
    federation({
      name: 'AgentMascot',
      filename: 'remoteEntry.js',
      exposes: {
        './Page': './src/components/Page.vue',
        './Config': './src/components/Config.vue',
        './AppPage': './src/components/AppPage.vue',
        './PluginEntry': './src/entry/pluginEntry.js',
      },
      shared: {
        vue: {
          requiredVersion: false,
          generate: false,
        },
      },
      format: 'esm',
    }),
    relativeMascotAssets(),
  ],
  build: {
    target: 'esnext',
    minify: false,
    cssCodeSplit: true,
    assetsInlineLimit: 256 * 1024,
    rollupOptions: {
      input: {
        main: 'index.html',
        'agentmascot-loader': 'src/global-loader.js',
      },
      output: {
        entryFileNames: chunk => {
          if (chunk.name === 'agentmascot-loader') return 'assets/agentmascot-loader.js'
          return 'assets/[name]-[hash].js'
        },
      },
    },
  },
  css: {
    postcss: {
      plugins: [
        {
          postcssPlugin: 'internal:charset-removal',
          AtRule: {
            charset: atRule => {
              if (atRule.name === 'charset') {
                atRule.remove()
              }
            },
          },
        },
        {
          postcssPlugin: 'vuetify-filter',
          Root(root) {
            root.walkRules(rule => {
              if (rule.selector && (rule.selector.includes('.v-') || rule.selector.includes('.mdi-'))) {
                rule.remove()
              }
            })
          },
        },
      ],
    },
  },
})
