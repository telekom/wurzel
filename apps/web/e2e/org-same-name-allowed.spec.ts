import { expect, test } from "@playwright/test";
import { E2E_PASSWORD } from "./helpers";

/**
 * Slugs are generated server-side from names; two different users can use the same display name.
 */
test.describe("Organization same display name", () => {
  test("two users can create organizations with the same name", async ({ page }, testInfo) => {
    const sharedName = `Shared Org Name ${Date.now()}-w${testInfo.workerIndex}`;

    const runUser = async (workerLabel: string) => {
      const suffix = `${Date.now()}-${workerLabel}${testInfo.workerIndex}`;
      const email = `e2e.${suffix}@example.com`;
      await page.goto("/");
      await expect(page.getByTestId("sign-in-form")).toBeVisible();
      await page.getByTestId("auth-email").fill(email);
      await page.getByTestId("auth-password").fill(E2E_PASSWORD);
      await page.getByTestId("sign-up-submit").click();
      await expect(page.getByRole("heading", { name: /Create your organization/i })).toBeVisible({ timeout: 30_000 });
      await page.getByTestId("org-name").fill(sharedName);
      await page.getByTestId("create-org-submit").click();
      await expect(page.getByRole("heading", { name: /^Projects$/i })).toBeVisible({ timeout: 30_000 });
    };

    await runUser("a");
    await page.getByTestId("sign-out-header").click();
    await expect(page.getByTestId("sign-in-form")).toBeVisible({ timeout: 15_000 });
    await runUser("b");
  });
});
