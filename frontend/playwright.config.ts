import { defineConfig, devices } from '@playwright/test';
import { join } from 'node:path';

// The runner owns the isolated stack; never fall back to the developer's server.
const baseURL = process.env.E2E_BASE_URL;
const artifacts = process.env.E2E_ARTIFACTS_DIR;
if (!baseURL || !artifacts || !process.env.E2E_SEED_PATH || !process.env.E2E_API_URL) {
  throw new Error('Use npm run test:e2e to start an isolated test environment.');
}

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  outputDir: join(artifacts, 'test-results'),
  reporter: [
    ['list'],
    ['html', { outputFolder: join(artifacts, 'report'), open: 'never' }],
    ['json', { outputFile: join(artifacts, 'results.json') }],
  ],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    locale: 'es-ES',
    timezoneId: 'Europe/Madrid',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
