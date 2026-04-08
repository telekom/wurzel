import { expect, test } from "@playwright/test";
import { addStepFromCatalog, onboardToWorkspace } from "./helpers";

test.describe("DAG editor", () => {
  test("adds multiple nodes, changes step type, and saves a revision", async ({ page }, testInfo) => {
    await onboardToWorkspace(page, testInfo);

    await addStepFromCatalog(page);
    await addStepFromCatalog(page);
    await expect(page.locator(".react-flow__node")).toHaveCount(2, { timeout: 15_000 });

    await page.locator(".react-flow__node").first().click();
    await expect(page.getByTestId("edit-node-panel")).toBeVisible();

    const stepSelect = page.getByTestId("step-type-select");
    const optionCount = await stepSelect.locator("option").count();
    if (optionCount >= 2) {
      const secondValue = await stepSelect.locator("option").nth(1).getAttribute("value");
      expect(secondValue).toBeTruthy();
      await stepSelect.selectOption(secondValue!);
      await expect(stepSelect).toHaveValue(secondValue!);
    }

    await page.getByTestId("save-revision").click();
    await expect(page.getByTestId("status-success")).toContainText("Revision saved.", { timeout: 30_000 });
  });

  test("run pipeline surfaces success or error (Temporal optional)", async ({ page }, testInfo) => {
    await onboardToWorkspace(page, testInfo);
    await page.getByTestId("save-revision").click();
    await expect(page.getByTestId("status-success")).toContainText("Revision saved.", { timeout: 30_000 });

    await page.getByTestId("run-pipeline").click();
    const outcome = page.getByTestId("status-success").or(page.getByTestId("status-error"));
    await expect(outcome.first()).toBeVisible({ timeout: 45_000 });
  });
});
