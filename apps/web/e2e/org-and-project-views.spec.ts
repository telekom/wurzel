import { expect, test } from "@playwright/test";
import {
  goToOrganizationView,
  goToProjectOverview,
  goToProjectView,
  goToWorkspace,
  onboardToWorkspace,
} from "./helpers";

test.describe("Organization and project views", () => {
  test("organization view shows current org; return to pipeline", async ({ page }, testInfo) => {
    const { suffix } = await onboardToWorkspace(page, testInfo);

    await goToOrganizationView(page);
    await expect(page.getByTestId("org-detail-name")).toContainText(`E2E Org ${suffix}`, { timeout: 15_000 });

    await goToWorkspace(page);
    await expect(page.getByTestId("flow-canvas")).toBeVisible({ timeout: 15_000 });
  });

  test("project overview metrics and project list; open pipeline shows revision summary", async ({ page }, testInfo) => {
    const { suffix } = await onboardToWorkspace(page, testInfo);

    await goToProjectOverview(page);
    await expect(page.getByTestId("metric-branches")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("metric-revisions")).toBeVisible();

    await goToProjectView(page);
    await expect(page.getByTestId("project-list")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("project-list-item").filter({ hasText: `E2E Project ${suffix}` })).toBeVisible();

    await page.getByTestId("project-list-item").filter({ hasText: `E2E Project ${suffix}` }).click();
    await expect(page.getByTestId("project-overview")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("nav-workspace").click();
    await expect(page.getByTestId("workspace")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("revision-summary")).toContainText(`E2E Project ${suffix}`, { timeout: 30_000 });
  });

  test("second organization: empty projects then create project in new org", async ({ page }, testInfo) => {
    const { suffix } = await onboardToWorkspace(page, testInfo);

    await goToOrganizationView(page);
    await page.getByRole("button", { name: "+ New organization" }).click();
    await page.getByTestId("new-org-name").fill(`E2E Org B ${suffix}`);
    await page.getByTestId("create-additional-org-submit").click();

    await expect(page.getByTestId("project-view")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("project-empty")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("project-view-org-name")).toContainText(`E2E Org B ${suffix}`);

    await page.getByTestId("project-name").fill(`E2E Project B ${suffix}`);
    await page.getByTestId("create-project-submit").click();

    await expect(page.getByTestId("project-overview")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("nav-workspace").click();
    await expect(page.getByTestId("workspace")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("revision-summary")).toContainText(`E2E Project B ${suffix}`, { timeout: 30_000 });
    await expect(page.getByTestId("branch-select")).toBeVisible();
  });

  test("project switcher updates pipeline context for same org", async ({ page }, testInfo) => {
    const { suffix } = await onboardToWorkspace(page, testInfo);
    const firstName = `E2E Project ${suffix}`;
    const secondName = `Second Project ${suffix}`;

    await goToProjectView(page);
    await page.getByTestId("project-name").fill(secondName);
    await page.getByTestId("create-project-submit").click();
    await expect(page.getByTestId("project-overview")).toBeVisible({ timeout: 30_000 });

    await goToProjectView(page);
    await expect(page.getByTestId("project-list-item")).toHaveCount(2, { timeout: 15_000 });

    const switcher = page.getByTestId("project-switcher");
    await switcher.selectOption({ index: 1 });
    await expect(page.getByTestId("project-overview")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("nav-workspace").click();
    await expect(page.getByTestId("revision-summary")).toContainText(secondName, { timeout: 15_000 });

    await goToProjectView(page);
    await switcher.selectOption({ index: 0 });
    await expect(page.getByTestId("project-overview")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("nav-workspace").click();
    await expect(page.getByTestId("revision-summary")).toContainText(firstName, { timeout: 15_000 });
  });
});
