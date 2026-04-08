import { expect, test } from "@playwright/test";
import { addStepFromCatalog, onboardToWorkspace } from "./helpers";

/**
 * Requires local Supabase (`supabase start`) with migrations, same as other KaaS e2e specs.
 * Asserts debounced auto-save hits `create_config_revision` and the UI shows the new revision id.
 */
test.describe("DAG autosave", () => {
  test("persists via create_config_revision without clicking Save", async ({ page }, testInfo) => {
    await onboardToWorkspace(page, testInfo);

    const revisionLine = page.getByTestId("revision-summary");

    const autosaveResponse = page.waitForResponse(
      (r) =>
        r.request().method() === "POST" &&
        r.url().includes("create_config_revision"),
      { timeout: 30_000 },
    );

    await addStepFromCatalog(page);
    await expect(page.locator(".react-flow__node")).toHaveCount(1, { timeout: 15_000 });

    const response = await autosaveResponse;
    expect(response.ok(), `autosave RPC failed: HTTP ${response.status()}`).toBeTruthy();

    const createdRevisionId: unknown = await response.json();
    expect(typeof createdRevisionId).toBe("string");
    expect(createdRevisionId as string).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );

    await expect(revisionLine).toContainText(createdRevisionId as string, { timeout: 15_000 });
  });
});
