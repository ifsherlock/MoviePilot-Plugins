import { defineConfig, devices } from '@playwright/test'

const frontendPort = Number(process.env.MP_FRONTEND_PORT || 5173)

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    serviceWorkers: 'block',
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
    cwd: '/home/jaysherlock/文档/MoviePilot-Frontend',
    url: `http://127.0.0.1:${frontendPort}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 390, height: 844 },
      },
    },
  ],
})
