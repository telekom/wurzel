import { expect, test } from "@playwright/test";
import { onboardToWorkspace } from "./helpers";

/**
 * Requires a full stack: Supabase local, Temporal dev server, Wurzel worker, and (for CI)
 * the FastAPI KaaS gateway with `VITE_KAAS_GATEWAY_URL` so the UI can poll Temporal workflow status.
 * Set `E2E_TEMPORAL=1`.
 *
 * With an empty DAG, the workflow completes quickly; the UI polls `/api/v1/workflow-status` until
 * Temporal reports COMPLETED (DB row may still show `running` until a future completion hook).
 */
test.describe("KaaS + Temporal", () => {
  test("run pipeline starts workflow and UI shows Temporal status through gateway", async ({ page }, testInfo) => {
    test.skip(
      process.env.E2E_TEMPORAL !== "1",
      "Set E2E_TEMPORAL=1 with Temporal, worker, and gateway (VITE_KAAS_GATEWAY_URL in CI).",
    );

    await onboardToWorkspace(page, testInfo);
    await page.getByTestId("save-revision").click();
    await expect(page.getByTestId("status-success")).toContainText("Revision saved.", { timeout: 30_000 });

    await page.getByTestId("run-pipeline").click();
    await expect(page.getByTestId("status-success")).toContainText(/Started workflow:\s*wurzel-pipeline-/i, {
      timeout: 60_000,
    });
    await expect(page.getByTestId("status-error")).toBeHidden();

    await expect(page.getByTestId("workflow-run-status")).toContainText(/Temporal:\s*COMPLETED/i, {
      timeout: 90_000,
    });
  });
});
