/**
 * Playwright config — opt-in (not gated in CI yet, see e2e/onboarding.spec.ts
 * for the wiring TODO). Run locally with:
 *
 *   npx playwright install --with-deps chromium
 *   npx playwright test
 */
import type { PlaywrightTestConfig } from "@playwright/test";

const config: PlaywrightTestConfig = {
	testDir: "./e2e",
	timeout: 30_000,
	expect: { timeout: 5_000 },
	fullyParallel: true,
	reporter: [["list"]],
	use: {
		baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
		trace: "on-first-retry",
		headless: true,
	},
};

export default config;
