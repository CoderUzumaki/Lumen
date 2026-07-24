/**
 * DATA-06 e2e — the "load sample portfolio" onboarding path.
 *
 * NOT RUN IN CI YET. To run locally:
 *
 *   cd frontend
 *   npm install -D @playwright/test
 *   npx playwright install --with-deps chromium
 *   NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 \
 *     NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co \
 *     NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key> \
 *     npm run build && npm run start &
 *   npx playwright test e2e/onboarding.spec.ts
 *
 * The spec exercises the sample-portfolio path against a signed-in user,
 * mocking the Supabase session via `LUMEN_TEST_USER_JWT` (set in-browser via
 * localStorage before the test navigates). Wiring the mock is the biggest
 * missing piece — Playwright + Supabase Auth needs either a real test user
 * or a JWT-mock injected before the AuthProvider bootstraps. Marked as a
 * DATA-06 deviation in HANDOFF.md.
 */
import { expect, test } from "@playwright/test";

test.describe("DATA-06 onboarding", () => {
	test("loads sample portfolio and lands on /portfolios", async ({ page }) => {
		// Sign-in path requires a real Supabase session. Skipping the sign-in
		// leg and injecting a mock session directly is a future step.
		test.skip(
			!process.env.LUMEN_TEST_USER_JWT,
			"LUMEN_TEST_USER_JWT is unset — see the file header for the wiring TODO.",
		);

		await page.goto("/onboarding/portfolio");
		await expect(
			page.getByRole("heading", { name: /Set up your portfolio/i }),
		).toBeVisible();

		await page.getByTestId("load-sample").click();

		// The sample seeds 6 rows.
		await expect(page.getByTestId("ticker-input-0")).toHaveValue("AAPL");
		await expect(page.getByTestId("ticker-input-5")).toHaveValue("BND");

		await page.getByTestId("submit-onboarding").click();

		await page.waitForURL("**/portfolios");
		await expect(
			page.getByRole("heading", { name: /Your portfolios/i }),
		).toBeVisible();
	});
});
