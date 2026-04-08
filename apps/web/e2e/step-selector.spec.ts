import { expect, test } from "@playwright/test";
import { onboardToWorkspace } from "./helpers";

test.describe("Step selector", () => {
  test("search narrows list, detail summary is shown, add places node on canvas", async ({ page }, testInfo) => {
    await onboardToWorkspace(page, testInfo);

    await page.getByTestId("add-step-node").click();
    await expect(page.getByTestId("step-selector-dialog")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("step-catalog-list").getByTestId("step-catalog-item").first()).toBeVisible({
      timeout: 30_000,
    });

    await page.getByTestId("step-catalog-search").fill("ManualMarkdown");
    await page
      .locator('[data-testid="step-catalog-item"][data-step-key="wurzel.steps.manual_markdown.ManualMarkdownStep"]')
      .click();

    const summary = page.getByTestId("step-detail-summary");
    await expect(summary).toHaveText(/.+/);
    await expect(summary).toContainText("Settings fro ManMdstep");

    await expect(page.getByTestId("step-detail-technical")).toContainText("wurzel.steps.manual_markdown.ManualMarkdownStep");

    await page.getByTestId("step-selector-add").click();
    await expect(page.getByTestId("step-selector-dialog")).toBeHidden();

    await expect(page.locator(".react-flow__node")).toHaveCount(1, { timeout: 15_000 });
    await page.locator(".react-flow__node").first().click();
    await expect(page.getByTestId("step-type-select")).toHaveValue("wurzel.steps.manual_markdown.ManualMarkdownStep");
  });
});
