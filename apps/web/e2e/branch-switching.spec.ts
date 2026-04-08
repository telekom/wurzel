import { expect, test } from "@playwright/test";
import { addStepFromCatalog, onboardToWorkspace } from "./helpers";

test.describe("Branches", () => {
  test("creates a feature branch and switches back to main", async ({ page }, testInfo) => {
    const { suffix } = await onboardToWorkspace(page, testInfo);

    await addStepFromCatalog(page);
    await expect(page.locator(".react-flow__node")).toHaveCount(1, { timeout: 15_000 });
    await page.getByTestId("save-revision").click();
    await expect(page.getByTestId("status-success")).toContainText("Revision saved.", { timeout: 30_000 });

    const branchName = `feat-switch-${suffix}`;
    page.once("dialog", (d) => {
      expect(d.type()).toBe("prompt");
      void d.accept(branchName);
    });
    await page.getByTestId("branch-select").click();
    await page.getByTestId("new-branch").click();
    await expect(page.getByTestId("branch-select")).toHaveAttribute("data-active-branch", branchName, {
      timeout: 15_000,
    });
    await page.getByTestId("branch-select").click();
    await expect(page.getByTestId("branch-menu-option").filter({ hasText: branchName })).toBeVisible();

    await page.getByTestId("branch-menu-option").filter({ hasText: /^main$/ }).click();
    await expect(page.getByTestId("branch-select")).toHaveAttribute("data-active-branch", "main");
    await expect(page.getByTestId("revision-summary")).toContainText(/Revision:/, { timeout: 20_000 });
  });
});
