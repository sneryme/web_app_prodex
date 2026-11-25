import { expect, test } from "@playwright/test";
import { answerCurrentQuestion, completeStage, DEMO_ENTRY_CODE, readParticipantToken, startTesting } from "./support/participant";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000/api";

test("FR-13: bundle assignment, resume, completion lock, and isolated progress", async ({ page, request }) => {
  let completedBundleAnswer: Record<string, unknown> | null = null;
  page.on("request", (requestEvent) => {
    if (requestEvent.url().includes("/answers/") && requestEvent.method() === "POST" && completedBundleAnswer === null) {
      completedBundleAnswer = requestEvent.postDataJSON() as Record<string, unknown>;
    }
  });

  await startTesting(page, DEMO_ENTRY_CODE, "dummy-bundle");
  const token = await readParticipantToken(page);
  expect(token).toBeTruthy();

  // Save a partial answer, reload the browser, and resume the same bundle.
  await answerCurrentQuestion(page);
  const progressBeforeReload = await page.locator(".progress-fill").getAttribute("style");
  await page.reload();
  await expect(page.locator('.bundle-menu__item[data-bundle-code="dummy-bundle"]')).toBeVisible();
  await page.locator('.bundle-menu__item[data-bundle-code="dummy-bundle"]').click();
  await expect(page.locator(".progress-track")).toBeVisible();
  await expect(page.locator(".progress-fill")).toHaveAttribute("style", progressBeforeReload ?? "");

  await completeStage(page);
  await completeStage(page);
  await expect(page.locator(".report-grid")).toBeVisible();
  expect(completedBundleAnswer).not.toBeNull();

  // The report's return button leads back to bundle selection with refreshed status.
  await page.locator(".card button.ghost").last().click();
  const dummyBundle = page.locator('.bundle-menu__item[data-bundle-code="dummy-bundle"]');
  await expect(dummyBundle.locator(".bundle-menu__status")).toHaveClass(/bundle-menu__status--completed/);
  const completedStageProgress = await dummyBundle.locator(".bundle-menu__details").innerText();
  const stageRatios = completedStageProgress.match(/\d+\/\d+/g) ?? [];
  expect(stageRatios).toHaveLength(2);
  for (const ratio of stageRatios) {
    const [answered, total] = ratio.split("/").map(Number);
    expect(answered).toBe(total);
  }

  // Reopening a finished bundle opens its report; it never exposes questions again.
  await dummyBundle.click();
  await expect(page.locator(".report-grid")).toBeVisible();
  await expect(page.locator(".option-card")).toHaveCount(0);
  await page.locator(".card button.ghost").last().click();

  // A second bundle starts with independent progress and remains in progress after one answer.
  await page.locator('.bundle-menu__item[data-bundle-code="prodex-v1"]').click();
  await expect(page.locator(".test-menu")).toBeVisible();
  await page.locator(".test-menu__item").first().click();
  await page.locator(".option-card").first().click();
  await page.locator(".actions .ghost").first().click();
  await page.locator("section.card > button.ghost").click();

  const prodexBundle = page.locator('.bundle-menu__item[data-bundle-code="prodex-v1"]');
  await expect(prodexBundle.locator(".bundle-menu__details")).toContainText("1/60");
  await expect(prodexBundle.locator(".bundle-menu__status")).toHaveClass(/bundle-menu__status--in_progress/);
  await expect(dummyBundle.locator(".bundle-menu__status")).toHaveClass(/bundle-menu__status--completed/);

  const homeResponse = await request.get(`${API_URL}/participant/sessions/${token}/`);
  expect(homeResponse.ok()).toBeTruthy();
  const home = await homeResponse.json();
  expect(home.bundles.find((bundle: { code: string }) => bundle.code === "dummy-bundle").status).toBe("completed");
  expect(home.bundles.find((bundle: { code: string }) => bundle.code === "prodex-v1").status).toBe("in_progress");

  const dummyReport = await request.get(
    `${API_URL}/participant/reports/${token}/?bundle_id=${home.bundles.find((bundle: { code: string }) => bundle.code === "dummy-bundle").id}`,
  );
  expect(dummyReport.status()).toBe(200);
  const incompleteProdexReport = await request.get(
    `${API_URL}/participant/reports/${token}/?bundle_id=${home.bundles.find((bundle: { code: string }) => bundle.code === "prodex-v1").id}`,
  );
  expect(incompleteProdexReport.status()).toBe(404);

  const retakeResponse = await request.post(`${API_URL}/participant/sessions/${token}/answers/`, {
    data: completedBundleAnswer,
  });
  expect(retakeResponse.status()).toBe(409);
});
