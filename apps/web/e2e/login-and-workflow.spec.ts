import { expect, test } from "@playwright/test";
import { addStepFromCatalog, goToWorkspace, onboardToWorkspace } from "./helpers";

/**
 * End-to-end journey against a real Supabase (local: `supabase start`).
 * Apply migrations first (`supabase db reset` or equivalent) so RPCs and RLS match the app.
 * Requires apps/web/.env with VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY,
 * or the same variables in the environment for CI.
 *
 * "Run on Temporal" may show an error if the Edge Function cannot reach Temporal;
 * the test only requires that the UI surfaces a success or error outcome.
 */

test.describe("KaaS UI — full journey", () => {
  test("sign up, org, project, DAG, branch, promote, pipeline invoke, sign out, sign in", async ({
    page,
  }, testInfo) => {
    const { email, password, suffix } = await onboardToWorkspace(page, testInfo);

    await test.step("DAG: add step node and save revision", async () => {
      await addStepFromCatalog(page);
      await expect(page.locator(".react-flow__node")).toHaveCount(1, { timeout: 15_000 });
      await page.locator(".react-flow__node").first().click();
      await expect(page.getByTestId("edit-node-panel")).toBeVisible();
      await page.getByTestId("save-revision").click();
      await expect(page.getByTestId("status-success")).toContainText("Revision saved.", {
        timeout: 30_000,
      });
    });

    await test.step("New branch (browser prompt)", async () => {
      const branchName = `feat-${suffix}`;
      page.once("dialog", (dialog) => {
        expect(dialog.type()).toBe("prompt");
        void dialog.accept(branchName);
      });
      await page.getByTestId("branch-select").click();
      await page.getByTestId("new-branch").click();
      await expect(page.getByTestId("branch-select")).toHaveAttribute("data-active-branch", branchName, {
        timeout: 15_000,
      });
      await page.getByTestId("branch-select").click();
      await expect(page.getByTestId("branch-menu-option").filter({ hasText: branchName })).toBeVisible();
      await expect(page.getByTestId("revision-summary")).toContainText(/\b[0-9a-f]{8}-[0-9a-f]{4}-/i, {
        timeout: 20_000,
      });
    });

    await test.step("Promote current revision to main", async () => {
      await page.getByTestId("promote-to-main").click();
      await expect(page.getByTestId("status-success")).toContainText(/Promoted/i, {
        timeout: 30_000,
      });
    });

    await test.step("Invoke pipeline (Edge Function — may error without Temporal)", async () => {
      await page.getByTestId("run-pipeline").click();
      const outcome = page.getByTestId("status-success").or(page.getByTestId("status-error"));
      await expect(outcome.first()).toBeVisible({ timeout: 45_000 });
    });

    await test.step("Sign out and sign in again", async () => {
      await page.getByTestId("sign-out-header").click();
      await expect(page.getByTestId("sign-in-form")).toBeVisible({ timeout: 15_000 });
      await page.getByTestId("auth-email").fill(email);
      await page.getByTestId("auth-password").fill(password);
      const tokenResponse = page.waitForResponse(
        (r) => r.url().includes("/auth/v1/token") && r.request().method() === "POST",
        { timeout: 20_000 },
      );
      await page.getByTestId("sign-in-submit").click();
      const login = await tokenResponse;
      expect(login.ok(), `sign-in failed: HTTP ${login.status()}`).toBeTruthy();
      await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
      await goToWorkspace(page);
      await expect(page.getByTestId("revision-summary")).toBeVisible();
    });
  });
});
