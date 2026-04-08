import { expect, test } from "@playwright/test";

test.describe("Auth validation", () => {
  test("shows an error for invalid sign-in credentials", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("sign-in-form")).toBeVisible();
    await page.getByTestId("auth-email").fill("not-a-real-user@example.com");
    await page.getByTestId("auth-password").fill("definitely-wrong-password");
    await page.getByTestId("sign-in-submit").click();
    await expect(page.getByTestId("auth-error")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("auth-error")).not.toBeEmpty();
    await expect(page.getByTestId("sign-in-form")).toBeVisible();
  });
});
