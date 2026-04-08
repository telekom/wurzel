import { expect, type Page, type TestInfo } from "@playwright/test";

export const E2E_PASSWORD = "E2E-playwright-test-pass!2026";

export type OnboardedUser = {
  email: string;
  password: string;
  suffix: string;
};

/**
 * Sign up, create org + project, open pipeline editor (DAG workspace).
 */
export async function onboardToWorkspace(page: Page, testInfo: TestInfo): Promise<OnboardedUser> {
  const suffix = `${Date.now()}-w${testInfo.workerIndex}`;
  const email = `e2e.${suffix}@example.com`;

  await page.goto("/");
  await expect(page.getByTestId("sign-in-form")).toBeVisible();
  await page.getByTestId("auth-email").fill(email);
  await page.getByTestId("auth-password").fill(E2E_PASSWORD);
  await page.getByTestId("sign-up-submit").click();
  await expect(page.getByRole("heading", { name: /Create your organization/i })).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("org-name").fill(`E2E Org ${suffix}`);
  await page.getByTestId("create-org-submit").click();
  await expect(page.getByRole("heading", { name: /^Projects$/i })).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("project-name").fill(`E2E Project ${suffix}`);
  await page.getByTestId("create-project-submit").click();
  await expect(page.getByTestId("project-overview")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("nav-workspace").click();
  await expect(page.getByTestId("workspace")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("revision-summary")).toContainText(/Revision:/, { timeout: 30_000 });

  return { email, password: E2E_PASSWORD, suffix };
}

export async function goToOrganizationView(page: Page): Promise<void> {
  await page.getByTestId("nav-organization").click();
  await expect(page.getByTestId("org-view")).toBeVisible({ timeout: 15_000 });
}

export async function goToProjectView(page: Page): Promise<void> {
  await page.getByTestId("nav-project").click();
  await expect(page.getByTestId("project-view")).toBeVisible({ timeout: 15_000 });
}

export async function goToProjectOverview(page: Page): Promise<void> {
  await page.getByTestId("nav-overview").click();
  await expect(page.getByTestId("project-overview")).toBeVisible({ timeout: 15_000 });
}

export async function goToWorkspace(page: Page): Promise<void> {
  await page.getByTestId("nav-workspace").click();
  await expect(page.getByTestId("workspace")).toBeVisible({ timeout: 15_000 });
}

/**
 * Open the step catalog dialog, optionally filter, pick a row, and confirm.
 * Waits for catalog rows so async JSON/Supabase loads do not race the UI.
 */
export async function addStepFromCatalog(
  page: Page,
  options?: { search?: string; stepKeyContains?: string; stepKeyExact?: string },
): Promise<void> {
  await page.getByTestId("add-step-node").click();
  await expect(page.getByTestId("step-selector-dialog")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("step-catalog-list").getByTestId("step-catalog-item").first()).toBeVisible({
    timeout: 30_000,
  });
  if (options?.search) {
    await page.getByTestId("step-catalog-search").fill(options.search);
  }
  if (options?.stepKeyExact) {
    await page.locator(`[data-testid="step-catalog-item"][data-step-key="${options.stepKeyExact}"]`).click();
  } else if (options?.stepKeyContains) {
    await page
      .locator(`[data-testid="step-catalog-item"][data-step-key*="${options.stepKeyContains}"]`)
      .first()
      .click();
  } else {
    await page.getByTestId("step-catalog-item").first().click();
  }
  await page.getByTestId("step-selector-add").click();
  await expect(page.getByTestId("step-selector-dialog")).toBeHidden();
}
