import type { Page } from "@playwright/test";
import { uk } from "../src/i18n/uk";
import { startSession } from "./support/api";
import { expectNoViolations } from "./support/axe";
import { expect, test } from "./support/fixtures";
import { appReady, mainNav, stubTiles } from "./support/ui";
import type { World } from "./support/world";

/**
 * axe-core on every page and meaningful state, in the matrix of colour scheme and viewport width.
 * Rules of WCAG 2.0/2.1 A and AA fail the test; best-practice findings are only reported.
 */
const WIDTHS = [320, 360, 768, 1280] as const;
const SCHEMES = ["light", "dark"] as const;

interface PageState {
  name: string;
  path: string;
  /** The account whose session the page starts with; absent for a visitor. */
  as?: (world: World) => string;
  /** Needs the demo accounts (E2E_DEMO_PASSWORD). */
  needsDemo?: boolean;
  /** Brings the page into the state under test and waits until it has settled. */
  prepare?: (page: Page) => Promise<void>;
}

const profile = uk.profile;
const invitations = uk.invitations;

const STATES: PageState[] = [
  { name: "landing, visitor", path: "/" },
  { name: "landing, signed in", path: "/", as: (w) => w.rich.token },
  { name: "about", path: "/about" },
  { name: "login", path: "/login" },
  {
    name: "login, validation errors",
    path: "/login",
    prepare: async (page) => {
      await page.getByRole("button", { name: uk.auth.submitLogin }).click();
      await expect(page.getByText(uk.form.validation.required).first()).toBeVisible();
    },
  },
  { name: "register", path: "/register" },
  {
    name: "register, validation errors",
    path: "/register",
    prepare: async (page) => {
      await page.getByLabel(uk.auth.email).fill("not-an-address");
      await page.getByLabel(uk.auth.password).fill("short");
      await page.getByRole("button", { name: uk.auth.submitRegister }).click();
      await expect(page.getByText(uk.form.validation.passwordMin)).toBeVisible();
    },
  },
  {
    name: "profile, empty onboarding",
    path: "/profile",
    as: (w) => w.bare.token,
    prepare: async (page) => {
      await expect(page.getByRole("heading", { name: profile.onboarding.title })).toBeVisible();
    },
  },
  {
    name: "profile, map shown",
    path: "/profile",
    as: (w) => w.bare.token,
    prepare: async (page) => {
      await page.getByLabel(profile.location.place).selectOption("kyiv");
      await expect(page.locator(".leaflet-container")).toBeVisible();
      await expect(page.locator(".leaflet-marker-icon")).toBeVisible();
    },
  },
  {
    name: "profile, validation errors",
    path: "/profile",
    as: (w) => w.bare.token,
    prepare: async (page) => {
      await page.getByRole("button", { name: profile.submit }).click();
      await expect(page.locator('[aria-invalid="true"]').first()).toBeVisible();
    },
  },
  {
    name: "profile, consent and capabilities editor",
    path: "/profile",
    as: (w) => w.rich.token,
    prepare: async (page) => {
      await expect(page.getByRole("group", { name: profile.functional.capabilitiesLegend })).toBeVisible();
    },
  },
  {
    name: "profile, delete confirmation",
    path: "/profile",
    as: (w) => w.rich.token,
    prepare: async (page) => {
      await page.getByRole("button", { name: profile.manage.deleteAll.trigger }).click();
      await expect(page.getByRole("heading", { name: profile.manage.deleteAll.title })).toBeVisible();
    },
  },
  {
    name: "matches, learned ranking",
    path: "/matches",
    as: (w) => w.rich.token,
    prepare: async (page) => {
      await expect(page.getByRole("article").first()).toBeVisible();
      // Scan the explanation open: it holds the badge, the bars and the influence of each criterion
      await page.getByRole("article").first().getByText(uk.feed.card.explanationHeading).click();
      await expect(page.getByText(uk.feed.card.rankSource.learned).first()).toBeVisible();
    },
  },
  {
    name: "matches, empty",
    path: "/matches",
    as: (w) => w.farAway.token,
    prepare: async (page) => {
      await expect(page.getByText(uk.feed.emptyAdvice)).toBeVisible();
    },
  },
  {
    name: "matches, filtered",
    path: "/matches",
    as: (w) => w.rich.token,
    prepare: async (page) => {
      await expect(page.getByRole("article").first()).toBeVisible();
      await page.getByLabel(uk.feed.filters.sport).selectOption("swimming");
      await expect(page.getByRole("status").filter({ hasText: /Показано|не знайдено/ })).toBeVisible();
    },
  },
  {
    name: "matches, invitation confirmation",
    path: "/matches",
    as: (w) => w.rich.token,
    prepare: async (page) => {
      await page.getByRole("button", { name: uk.feed.invite.trigger }).first().click();
      await expect(page.getByRole("heading", { name: uk.feed.invite.title })).toBeVisible();
    },
  },
  {
    name: "matches, contact required notice",
    path: "/matches",
    as: (w) => w.noContact.token,
    prepare: async (page) => {
      await page.getByRole("button", { name: uk.feed.invite.trigger }).first().click();
      await page.getByRole("button", { name: uk.feed.invite.confirm }).click();
      await expect(page.getByRole("alert").filter({ hasText: uk.contactRequired.message })).toBeVisible();
    },
  },
  {
    name: "invitations, incoming",
    path: "/invitations",
    as: (w) => w.rich.token,
    needsDemo: true,
    prepare: async (page) => {
      await expect(page.getByRole("article").first()).toBeVisible();
    },
  },
  {
    name: "invitations, outgoing",
    path: "/invitations",
    as: (w) => w.rich.token,
    needsDemo: true,
    prepare: async (page) => {
      await page.getByRole("tab", { name: invitations.outgoing }).click();
      await expect(page.getByRole("article").first()).toBeVisible();
    },
  },
  {
    name: "invitations, accept confirmation",
    path: "/invitations",
    as: (w) => w.rich.token,
    needsDemo: true,
    prepare: async (page) => {
      await page.getByRole("button", { name: invitations.actions.accept.trigger }).first().click();
      await expect(page.getByRole("heading", { name: invitations.actions.accept.title })).toBeVisible();
    },
  },
  {
    name: "invitations, decline confirmation",
    path: "/invitations",
    as: (w) => w.rich.token,
    needsDemo: true,
    prepare: async (page) => {
      await page.getByRole("button", { name: invitations.actions.decline.trigger }).first().click();
      await expect(page.getByRole("heading", { name: invitations.actions.decline.title })).toBeVisible();
    },
  },
  {
    name: "invitations, cancel confirmation",
    path: "/invitations",
    as: (w) => w.rich.token,
    needsDemo: true,
    prepare: async (page) => {
      await page.getByRole("tab", { name: invitations.outgoing }).click();
      await page.getByRole("button", { name: invitations.actions.cancel.trigger }).first().click();
      await expect(page.getByRole("heading", { name: invitations.actions.cancel.title })).toBeVisible();
    },
  },
  {
    name: "invitations, empty filtered list",
    path: "/invitations",
    as: (w) => w.rich.token,
    prepare: async (page) => {
      await page.getByLabel(invitations.statusFilter).selectOption("declined");
      await expect(page.getByRole("status").filter({ hasText: invitations.emptyFiltered })).toBeVisible();
    },
  },
  {
    name: "invitations, empty outgoing",
    path: "/invitations",
    as: (w) => w.bare.token,
    prepare: async (page) => {
      await page.getByRole("tab", { name: invitations.outgoing }).click();
      await expect(page.getByRole("status").filter({ hasText: invitations.emptyOutgoing })).toBeVisible();
    },
  },
  { name: "not found", path: "/there-is-no-such-page" },
  {
    name: "mobile menu open",
    path: "/",
    prepare: async (page) => {
      const button = page.getByRole("button", { name: uk.nav.menu });
      test.skip(!(await button.isVisible()), "the menu is always open on a wide screen");
      await button.click();
      await expect(button).toHaveAttribute("aria-expanded", "true");
      await expect(mainNav(page).getByRole("link", { name: uk.nav.login })).toBeVisible();
    },
  },
  {
    name: "mobile menu open, signed in",
    path: "/matches",
    as: (w) => w.rich.token,
    prepare: async (page) => {
      const button = page.getByRole("button", { name: uk.nav.menu });
      test.skip(!(await button.isVisible()), "the menu is always open on a wide screen");
      await button.click();
      await expect(mainNav(page).getByRole("button", { name: uk.nav.logout })).toBeVisible();
    },
  },
];

for (const scheme of SCHEMES) {
  for (const width of WIDTHS) {
    test.describe(`${scheme}, ${width}px`, () => {
      test.use({ colorScheme: scheme, viewport: { width, height: 900 }, ignoreHTTPSErrors: true });

      for (const state of STATES) {
        test(state.name, async ({ page, world }, testInfo) => {
          test.skip(Boolean(state.needsDemo) && !world.demo, "E2E_DEMO_PASSWORD is not set");
          await stubTiles(page.context());
          // Transitions would make the measured colours depend on timing; motion has its own tests
          await page.emulateMedia({ reducedMotion: "reduce" });
          if (state.as) await startSession(page.context(), state.as(world));
          await page.goto(state.path);
          await appReady(page);
          if (state.prepare) await state.prepare(page);
          await page.waitForLoadState("networkidle");
          await expectNoViolations(page, testInfo, `${state.name} / ${scheme} / ${width}`);
        });
      }
    });
  }
}
