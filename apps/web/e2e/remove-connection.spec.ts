import { expect, test, type Page } from "@playwright/test";
import { addStepFromCatalog, onboardToWorkspace } from "./helpers";

const MANUAL_MD = "wurzel.steps.manual_markdown.ManualMarkdownStep";
const EMBEDDING = "wurzel.steps.embedding.step.EmbeddingStep";

/** Connect source (bottom handle) → target (top handle); React Flow often needs real mouse events. */
async function connectHandles(page: Page): Promise<void> {
  const node0 = page.locator(".react-flow__node").nth(0);
  const node1 = page.locator(".react-flow__node").nth(1);
  const sourceHandle = node0.locator(".react-flow__handle-bottom");
  const targetHandle = node1.locator(".react-flow__handle-top");
  await expect(sourceHandle).toBeVisible();
  await expect(targetHandle).toBeVisible();
  const from = await sourceHandle.boundingBox();
  const to = await targetHandle.boundingBox();
  expect(from, "source handle box").toBeTruthy();
  expect(to, "target handle box").toBeTruthy();
  await page.mouse.move(from!.x + from!.width / 2, from!.y + from!.height / 2);
  await page.mouse.down();
  await page.mouse.move(to!.x + to!.width / 2, to!.y + to!.height / 2, { steps: 12 });
  await page.mouse.up();
}

test.describe("DAG remove connection", () => {
  test("select edge and remove via toolbar (chainable steps)", async ({ page }, testInfo) => {
    await onboardToWorkspace(page, testInfo);

    const removeBtn = page.getByTestId("remove-selected-connection");
    await expect(removeBtn).toBeDisabled();

    await addStepFromCatalog(page, { search: "ManualMarkdown", stepKeyExact: MANUAL_MD });
    await addStepFromCatalog(page, { search: "EmbeddingStep", stepKeyExact: EMBEDDING });
    await expect(page.locator(".react-flow__node")).toHaveCount(2, { timeout: 15_000 });

    await connectHandles(page);

    await expect(page.locator(".react-flow__edge")).toHaveCount(1, { timeout: 15_000 });
    await expect(removeBtn).toBeDisabled();

    const edgeHit = page.locator(".react-flow__edge-interaction").first();
    await edgeHit.click({ force: true });
    await expect(removeBtn).toBeEnabled({ timeout: 10_000 });

    await removeBtn.click();
    await expect(page.locator(".react-flow__edge")).toHaveCount(0, { timeout: 10_000 });
    await expect(removeBtn).toBeDisabled();
  });
});
