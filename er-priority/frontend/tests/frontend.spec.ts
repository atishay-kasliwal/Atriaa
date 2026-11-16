import { test, expect, type Page } from "@playwright/test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
type Axe = { run: () => Promise<{ violations: { id: string; impact: string; nodes: { target: string[] }[] }[] }> };

async function audit(page: Page) {
  await page.bringToFront();
  await page.addScriptTag({ path: require.resolve("axe-core/axe.min.js") });
  const violations = await page.evaluate(async () => {
    const result = await (window as unknown as { axe: Axe }).axe.run();
    return result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  });
  expect(violations).toEqual([]);
  expect(await page.locator("main").count()).toBe(1);
  expect(await page.locator("h1").count()).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}

test.beforeEach(async ({ request }) => {
  expect((await request.post("/api/live/reset", { data: {} })).ok()).toBe(true);
});

for (const screen of [
  { name: "desktop", viewport: { width: 1440, height: 1000 }, colorScheme: "light" as const },
  { name: "phone with dark system preference", viewport: { width: 390, height: 844 }, colorScheme: "dark" as const },
]) {
  test(`${screen.name}: home, intake, and populated nurse station remain readable`, async ({ page, request }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize(screen.viewport);
    await page.emulateMedia({ colorScheme: screen.colorScheme });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("while they wait");
    await audit(page);
    await page.getByRole("link", { name: /I'm a patient/ }).click();
    await expect(page.getByRole("heading", { name: "Check in", exact: true })).toBeVisible();
    await audit(page);
    await request.post("/api/live/sample/load", { data: {} });
    await page.goto("/nurse");
    await expect(page.getByText("Maya Patel", { exact: true })).toBeVisible();
    await audit(page);
    expect(errors).toEqual([]);
  });
}

test("patient check-in, staff priority, re-check, patient update, and bed assignment", async ({ page, context }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/checkin");
  await page.getByLabel("Full name").fill("Atria Browser Demo");
  await page.getByLabel("Date of birth").fill("1990-01-02");
  await page.getByLabel("Headache", { exact: true }).check();
  await page.locator("label.pain-option").filter({ has: page.getByRole("radio", { name: "4", exact: true }) }).click();
  await page.getByRole("button", { name: "Check in", exact: true }).click();
  await expect(page).toHaveURL(/\/status\//);
  await expect(page.getByText("Waiting for a triage nurse", { exact: true })).toBeVisible();
  const patientUrl = page.url();
  const staff = await context.newPage();
  await staff.setViewportSize({ width: 1440, height: 1000 });
  await staff.goto("/nurse");
  await staff.getByLabel("Assign priority for Atria Browser Demo").selectOption("3");
  await page.reload();
  await expect(page.getByText("You're in line", { exact: true })).toBeVisible();
  await staff.getByRole("button", { name: "Request re-check", exact: true }).click();
  await expect(page.getByText("A nurse wants to re-check you", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Worse", exact: true }).click();
  await page.getByRole("button", { name: "Pain 7 of 10", exact: true }).click();
  await page.getByRole("button", { name: "Send update to staff" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Staff can see it now" })).toBeVisible();
  await audit(page);
  await staff.reload();
  await expect(staff.getByText("Patient-reported worsening in notes", { exact: false }).first()).toBeVisible();
  await staff.getByRole("button", { name: "Record re-check", exact: true }).click();
  await staff.getByLabel("Heart rate", { exact: true }).fill("88");
  await staff.getByLabel("SpO2", { exact: true }).fill("98");
  await staff.getByLabel("Pain", { exact: true }).fill("7");
  await staff.getByRole("button", { name: "Save re-check", exact: true }).click();
  await expect(staff.getByRole("button", { name: "Save re-check", exact: true })).toHaveCount(0);
  await staff.getByRole("button", { name: "Assign to Bed 1", exact: true }).click();
  await page.goto(patientUrl);
  await expect(page.getByText("Please go to Bed 1", { exact: true })).toBeVisible();
  await audit(page);
});

test("sample readings produce a flag and a sourced assistant answer", async ({ page, request }) => {
  test.setTimeout(60_000);
  await page.goto("/nurse");
  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Load sample", exact: true }).click();
  await expect(page.getByText("Maya Patel", { exact: true })).toBeVisible();
  const sample = await (await request.get("/api/live/sample")).json();
  for (let i = 1; i <= sample.total; i++) {
    await page.getByRole("button", { name: "Next reading", exact: true }).click();
    await expect(page.getByText(new RegExp(`Reading ${i} of`))).toBeVisible();
  }
  await expect(page.locator(".atria-alert").first()).toBeVisible();
  await page.getByRole("navigation").getByRole("link", { name: /^Ask Atria/ }).click();
  await page.getByLabel("Question for Atria").fill("Who should be re-checked next?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("Recorded-data summary", { exact: true })).toBeVisible();
  await expect(page.locator(".ask-answer")).toContainText(/W-0/);
  await audit(page);
  await request.post("/api/live/reset", { data: {} });
  await page.getByLabel("Question for Atria").fill("Who should be re-checked next?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".ask-answer").first()).toContainText("No patients");
});

test("failed check-in stays editable and can be retried", async ({ page }) => {
  await page.route("**/api/checkin", (route) => route.fulfill({ status: 503, json: { detail: "Temporarily unavailable" } }));
  await page.goto("/checkin");
  await page.getByLabel("Full name").fill("Atria Retry Demo");
  await page.getByLabel("Date of birth").fill("1990-01-02");
  await page.getByLabel("Headache", { exact: true }).check();
  await page.getByRole("button", { name: "Check in", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Check-in failed");
  await expect(page.getByRole("button", { name: "Check in", exact: true })).toBeEnabled();
  await page.unroute("**/api/checkin");
  await page.getByRole("button", { name: "Check in", exact: true }).click();
  await expect(page).toHaveURL(/\/status\//);
});

test("keyboard, reduced motion, route changes, and a real 404", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
  await page.getByRole("link", { name: /Nurse station/ }).click();
  await expect(page.getByRole("heading", { name: "ER Patient Queue" })).toBeVisible();
  await page.getByRole("link", { name: "Front-desk check-in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Check in a patient" })).toBeVisible();
  await audit(page);
  expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length)).toBe(0);
  const response = await page.goto("/this-page-does-not-exist");
  expect(response?.status()).toBe(404);
  await audit(page);
});

test("content and navigation remain available without JavaScript", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:4410/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(await page.content()).toContain("Turn on JavaScript");
  await page.getByRole("link", { name: /I'm a patient/ }).click();
  await expect(page.getByRole("heading", { name: "Check in", exact: true })).toBeVisible();
  await context.close();
});
