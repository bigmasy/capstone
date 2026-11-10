import { uk } from "../src/i18n/uk";
import { startSession } from "./support/api";
import { expect, test } from "./support/fixtures";
import { headingProblems, landmarkProblems } from "./support/probes";
import { appReady, passwordLabel } from "./support/ui";
import type { World } from "./support/world";

/** Document structure: one h1, no skipped heading levels, unique landmarks; live regions that report changes. */
const PAGES: { name: string; path: string; as?: (world: World) => string; ready?: string }[] = [
  { name: "landing, visitor", path: "/" },
  { name: "landing, signed in", path: "/", as: (w) => w.rich.token },
  { name: "about", path: "/about" },
  { name: "login", path: "/login" },
  { name: "register", path: "/register" },
  { name: "not found", path: "/there-is-no-such-page" },
  { name: "profile, onboarding", path: "/profile", as: (w) => w.bare.token },
  { name: "profile, edit", path: "/profile", as: (w) => w.rich.token },
  { name: "matches", path: "/matches", as: (w) => w.rich.token, ready: "article" },
  { name: "invitations", path: "/invitations", as: (w) => w.rich.token },
];

for (const width of [320, 1280]) {
  test.describe(`structure at ${width}px`, () => {
    test.use({ viewport: { width, height: 900 } });

    for (const entry of PAGES) {
      test(`${entry.name}: headings and landmarks`, async ({ page, world }) => {
        if (entry.as) await startSession(page.context(), entry.as(world));
        await page.goto(entry.path);
        await appReady(page);
        await page.waitForLoadState("networkidle");
        if (entry.ready) await expect(page.getByRole(entry.ready as "article").first()).toBeVisible();
        expect(await headingProblems(page)).toEqual([]);
        expect(await landmarkProblems(page)).toEqual([]);
      });
    }
  });
}

test.describe("page identity and names", () => {
  test("every page has the language set, a title built from its heading and a unique one", async ({
    browser,
    world,
  }) => {
    const titles = new Map<string, string>();
    for (const entry of PAGES) {
      // A context of its own, so that the session of one entry does not leak into the next
      const context = await browser.newContext({ ignoreHTTPSErrors: true });
      try {
        if (entry.as) await startSession(context, entry.as(world));
        const page = await context.newPage();
        await page.goto(entry.path);
        await appReady(page);
        await page.waitForLoadState("networkidle");
        expect(await page.locator("html").getAttribute("lang"), entry.name).toBe("uk");
        const heading = (await page.locator("main h1").first().innerText()).trim();
        await expect(page, entry.name).toHaveTitle(`${heading}${uk.app.titleSeparator}${uk.app.name}`);
        const title = await page.title();
        // The two variants of the landing page and of the profile page share a title
        const previous = titles.get(title);
        const sameFamily = previous?.split(",")[0] === entry.name.split(",")[0];
        expect(previous === undefined || sameFamily, `${entry.name} reuses the title of ${previous}`).toBe(true);
        titles.set(title, entry.name);
      } finally {
        await context.close();
      }
    }
  });

  test("the visible text of a control is part of its accessible name (WCAG 2.5.3)", async ({ page, world }) => {
    await startSession(page.context(), world.rich.token);
    for (const path of ["/matches", "/profile", "/invitations"]) {
      await page.goto(path);
      await appReady(page);
      await page.waitForLoadState("networkidle");
      const mismatches = await page.evaluate(() => {
        const normalise = (text: string) => text.replace(/\s+/g, " ").trim().toLowerCase();
        return [...document.querySelectorAll<HTMLElement>("button[aria-label], a[aria-label], [role=tab][aria-label]")]
          .filter((element) => normalise(element.textContent ?? "") !== "")
          .filter((element) => !normalise(element.getAttribute("aria-label") ?? "").includes(normalise(element.textContent ?? "")))
          .map((element) => `${element.getAttribute("aria-label")} / ${element.textContent}`);
      });
      expect(mismatches, path).toEqual([]);
    }
  });
});

test.describe("live regions", () => {
  test("the number of results is announced when a filter changes", async ({ page, world }) => {
    await startSession(page.context(), world.rich.token);
    await page.goto("/matches");
    const summary = page.getByRole("status").filter({ hasText: /Показано|не знайдено/ });
    await expect(summary).toBeVisible();
    const before = await summary.innerText();
    await page.getByLabel(uk.feed.filters.radius).selectOption("5");
    await expect(summary).not.toHaveText(before);
    await expect(summary).toHaveText(/Показано \d+–\d+ з \d+|Підходящих партнерів не знайдено/);
  });

  test("an empty submit reports errors in text and moves focus to the first invalid field", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: uk.auth.submitLogin }).click();
    const email = page.getByLabel(uk.auth.email);
    await expect(email).toBeFocused();
    await expect(email).toHaveAttribute("aria-invalid", "true");
    const message = page.locator(`#${await email.getAttribute("aria-describedby")}`);
    await expect(message).toContainText(uk.form.errorPrefix);
    await expect(message).toHaveAttribute("aria-live", "polite");
  });

  test("a rejected sign-in is announced as an alert", async ({ page }) => {
    // Answered locally: the proxy allows only a few sign-in attempts a minute, and the point
    // here is how the page reports a rejection, not the server's check
    await page.route("**/api/v1/auth/login", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"Invalid credentials"}' }),
    );
    await page.goto("/login");
    await page.getByLabel(uk.auth.email).fill("e2e-nobody@example.invalid");
    await page.getByLabel(passwordLabel).fill("Wrong-password-0000");
    await page.getByRole("button", { name: uk.auth.submitLogin }).click();
    await expect(page.getByRole("alert")).toContainText(uk.auth.invalidCredentials);
  });

  test("saving the profile shows a status toast", async ({ page, world }) => {
    await startSession(page.context(), world.rich.token);
    await page.goto("/profile");
    await expect(page.getByLabel(uk.profile.about.displayName)).toHaveValue("E2E Rich");
    await page.getByRole("button", { name: uk.profile.submit }).click();
    const toast = page.getByRole("status").filter({ hasText: uk.profile.saved });
    await expect(toast).toBeVisible();
    await expect(toast).toHaveAttribute("aria-live", "polite");
  });

  test("a route change moves focus to the heading and announces the page", async ({ page }) => {
    await page.goto("/");
    await appReady(page);
    await page.getByRole("navigation", { name: uk.a11y.mainNavigation }).getByRole("link", { name: uk.nav.about }).click();
    const heading = page.getByRole("heading", { level: 1 });
    await expect(heading).toHaveText(uk.pages.about.title);
    await expect(heading).toBeFocused();
    await expect(page).toHaveTitle(`${uk.pages.about.title}${uk.app.titleSeparator}${uk.app.name}`);
    await expect(page.locator('[role="status"].visually-hidden')).toHaveText(uk.pages.about.title);
  });
});
