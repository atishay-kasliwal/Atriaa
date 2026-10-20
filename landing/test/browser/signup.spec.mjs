import { test, expect } from "@playwright/test";
import axe from "axe-core";

for (const colorScheme of ["light", "dark"]) {
  test(`text stays readable with the system set to ${colorScheme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme, reducedMotion: "reduce" });
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const route of ["/", "/privacy", "/not-a-real-page"]) {
        await page.goto(route);
        await page.evaluate(axe.source);
        const violations = await page.evaluate(async () => {
          const result = await axe.run(document, {
            runOnly: { type: "rule", values: ["color-contrast"] },
          });
          return result.violations.map(({ id, nodes }) => ({
            id,
            targets: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })),
          }));
        });
        expect(violations, `${route} at ${width}px with ${colorScheme} preference`).toEqual([]);
      }
    }
  });
}

test("landing and waitlist work at desktop and mobile widths", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "blind spot",
  );
  await expect(page.getByText("Winner · Best Use of Tiger Data")).toBeVisible();
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    if (width < 768) {
      await page.getByRole("button", { name: "Open menu" }).click();
      await expect(
        page
          .getByRole("navigation", { name: "Mobile navigation" })
          .getByRole("link", { name: "Join early access" }),
      ).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(
        page.getByRole("button", { name: "Open menu" }),
      ).toBeFocused();
    } else {
      await expect(
        page
          .getByRole("navigation", { name: "Main navigation" })
          .getByRole("link", { name: "Join early access" }),
      ).toBeVisible();
    }
  }
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.screenshot({
    path: ".wrangler/landing-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: ".wrangler/landing-mobile.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Get early access" }).click();
  await page
    .getByLabel("Email address")
    .fill(`browser-${Date.now()}@example.com`);
  await page.getByLabel("Your name").fill("Browser test");
  await page.getByLabel("I’m here as a").selectOption("builder");
  await page.getByRole("checkbox").check();
  await page
    .getByRole("button", { name: "Join the early-access list" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Thanks for being here early." }),
  ).toBeVisible();
  await expect(page.locator("#signup-form")).toBeHidden();
  expect(errors).toEqual([]);
});

test("a server failure keeps the form visible and offers a retry", async ({
  page,
}) => {
  await page.route("**/api/waitlist", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: "We couldn’t save your signup. Please try again in a moment.",
      }),
    }),
  );
  await page.goto("/#early-access");
  await page.getByLabel("Email address").fill("retry@example.com");
  await page.getByLabel("I’m here as a").selectOption("care-team");
  await page.getByRole("checkbox").check();
  await page
    .getByRole("button", { name: "Join the early-access list" })
    .click();
  await expect(page.getByRole("status")).toContainText("couldn’t save");
  await expect(
    page.getByRole("button", { name: "Join the early-access list" }),
  ).toBeEnabled();
  await expect(page.locator("#signup-success")).toBeHidden();
});

test("privacy link works and missing pages return 404", async ({ page }) => {
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Your early-access signup.",
  );
  const response = await page.goto("/not-a-real-page");
  expect(response.status()).toBe(404);
});

test("reduced motion keeps all content visible and stops the diagram", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.locator(".flow-figure").scrollIntoViewIfNeeded();
  const before = await page
    .locator("[data-flow-dot]")
    .evaluateAll((dots) =>
      dots.map((dot) => [dot.getAttribute("cx"), dot.getAttribute("cy")]),
    );
  await page.waitForTimeout(400);
  const after = await page
    .locator("[data-flow-dot]")
    .evaluateAll((dots) =>
      dots.map((dot) => [dot.getAttribute("cx"), dot.getAttribute("cy")]),
    );
  expect(after).toEqual(before);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(
    await page.evaluate(
      () =>
        document
          .getAnimations()
          .filter((animation) => animation.playState === "running").length,
    ),
  ).toBe(0);
});

test("without JavaScript the story and early-access instructions remain readable", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "A better view starts with you." }),
  ).toBeVisible();
  await expect(page.locator("noscript p")).toBeVisible();
  await context.close();
});
