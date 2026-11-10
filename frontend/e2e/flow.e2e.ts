import { expect, test, type Page, type Response } from "@playwright/test";
import { uk } from "../src/i18n/uk";
import { apiLogin, confirmationLink } from "./support/api";
import { demoEmail, demoIndexOf, demoPassword, e2ePassword, freshEmail, runId } from "./support/env";
import { paintedContrast } from "./support/probes";
import { findForbiddenKeys, mainNav, stubTiles, passwordLabel, confirmPasswordLabel } from "./support/ui";
import { demoSession, ensureDemoContact } from "./support/world";

/**
 * The whole product path with real users: register, onboarding, matches, invitation, accept,
 * contact exchange, account deletion. Serial, because each step needs the previous one.
 */
test.describe.configure({ mode: "serial" });

const email = freshEmail("flow");
const displayName = `E2E Flow ${runId}`;
const ownContact = `@e2e_flow_${runId}`;

let owner: Page;
let invitedDemo: { index: number; name: string } | null = null;
const publicBodies: { url: string; body: unknown }[] = [];

function captureBodies(page: Page): void {
  page.on("response", (response: Response) => {
    const url = response.url();
    if (/\/api\/v1\/(matches|invitations)/.test(url) && response.request().method() === "GET") {
      void response.json().then(
        (body: unknown) => publicBodies.push({ url, body }),
        () => undefined,
      );
    }
  });
}

test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  await stubTiles(context);
  owner = await context.newPage();
  captureBodies(owner);
});

test.afterAll(async () => {
  await owner.context().close();
});

test("a visitor sees the landing page and is sent to the login page from a private page", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(uk.pages.home.title);
  await expect(mainNav(page).getByRole("link", { name: uk.nav.login })).toBeVisible();
  await expect(mainNav(page).getByRole("link", { name: uk.nav.matches })).toHaveCount(0);

  await page.goto("/matches");
  await expect(page).toHaveURL(/\/login$/);
});

test("registration leads to the onboarding form", async () => {
  await owner.goto("/register");
  await owner.getByLabel(uk.auth.email).fill(email);
  await owner.getByLabel(passwordLabel).fill(e2ePassword);
  await owner.getByLabel(confirmPasswordLabel).fill(e2ePassword);
  await owner.getByRole("button", { name: uk.auth.submitRegister }).click();

  await expect(owner).toHaveURL(/\/profile$/);
  await expect(owner.getByRole("heading", { level: 1 })).toHaveText(uk.pages.profile.title);
  await expect(owner.getByRole("heading", { name: uk.profile.onboarding.title })).toBeVisible();
  // The heading of the new page has focus after the route change
  await expect(owner.getByRole("heading", { level: 1 })).toBeFocused();
  // A new account has not confirmed its address yet and is told how to
  await expect(owner.getByRole("region", { name: uk.verification.bannerLabel })).toBeVisible();
});

test("the e-mailed link confirms the address and the banner goes away", async () => {
  // The test has no mailbox: the same link the message carries is issued by the API image
  await owner.goto(confirmationLink(email));

  await expect(owner.getByText(uk.verification.page.success)).toBeVisible();
  // The token is gone from the address bar
  expect(owner.url()).not.toContain("token");
  await owner.getByRole("link", { name: uk.verification.page.toPartners }).click();
  await expect(owner.getByRole("heading", { level: 1 })).toHaveText(uk.pages.matches.title);
  await expect(owner.getByRole("region", { name: uk.verification.bannerLabel })).toHaveCount(0);
  // A used link does not work a second time
  await owner.goto(confirmationLink(email).replace(/token=.*/, "token=" + "x".repeat(43)));
  await expect(owner.getByText(uk.verification.page.failure)).toBeVisible();
  await owner.goto("/profile");
});

test("onboarding: place from the gazetteer, map, rounded-area text, sports, consent, contact", async () => {
  const text = uk.profile;
  await owner.getByLabel(text.about.displayName).fill(displayName);
  await owner.getByLabel(text.about.intensity).selectOption("3");

  await owner.getByLabel(text.sports.sport).selectOption("swimming");
  await owner.getByLabel(text.sports.skill).selectOption("intermediate");
  await owner.getByRole("button", { name: text.sports.add }).click();
  await owner.getByLabel(text.sports.sport).nth(1).selectOption("cycling");

  await owner.getByLabel(text.location.place).selectOption("kyiv");
  // The area is described in words, as a rounded cell, never as a point
  const area = owner.locator("#main-content").getByText(text.location.area("", "", "", "").slice(0, 16));
  await expect(area).toContainText("4 км × 4 км");
  await expect(area).not.toContainText("50.450");
  // Choosing a place shows the map
  await expect(owner.locator(".leaflet-container")).toBeVisible();
  await expect(owner.getByRole("button", { name: text.location.hideMap })).toHaveAttribute(
    "aria-expanded",
    "true",
  );

  await owner.getByLabel(text.contact.label).fill(ownContact);
  await owner.getByLabel(text.functional.consent).check();
  await owner.getByRole("button", { name: text.functional.add }).click();
  await owner.getByLabel(text.functional.category).selectOption("mobility_lower");
  await owner.getByLabel(text.functional.level).selectOption("2");

  await owner.getByRole("button", { name: text.submit }).click();
  await expect(owner.getByText(text.saved).first()).toBeVisible();
  // After saving, the area text of the stored profile names the district only
  await expect(owner.getByText(text.location.keepStored)).toBeVisible();
});

test("matches: learned badge, per-criterion explanation, no coordinates or capabilities", async () => {
  await mainNav(owner).getByRole("link", { name: uk.nav.matches }).click();
  await expect(owner.getByRole("heading", { level: 1 })).toHaveText(uk.pages.matches.title);

  const cards = owner.getByRole("article");
  await expect(cards.first()).toBeVisible();
  await expect(owner.getByRole("status").filter({ hasText: /Показано/ })).toBeVisible();

  const first = cards.first();
  // The explanation is a disclosure, closed by default: a user opens it to read the points
  await first.getByText(uk.feed.card.explanationHeading).click();
  await expect(first.getByText(uk.feed.card.rankSource.learned, { exact: true })).toBeVisible();
  await expect(first.getByText(uk.feed.card.explanationHeading)).toBeVisible();
  for (const label of Object.values(uk.feed.card.criteria)) {
    // "Інтенсивність" is also a row of the facts list, hence .first()
    await expect(first.getByText(label, { exact: true }).first()).toBeVisible();
  }
  await expect(first.getByText(/з \d+ балів/).first()).toBeVisible();
  await expect(first.getByText(uk.feed.card.total("").slice(0, 14))).toBeVisible();

  // Nothing about positions or capabilities in the page
  const html = await owner.content();
  expect(html).not.toMatch(/latitude|longitude|"lat"|"lng"/i);
  expect(html).not.toContain("50.45");
  await expect(owner.locator("#main-content")).not.toContainText("Пересування на ногах");

  const name = await first.getByRole("heading", { level: 3 }).innerText();
  invitedDemo = { index: demoIndexOf(name) ?? 0, name };
});

test("invite a partner from the card", async () => {
  test.skip(!demoPassword, "E2E_DEMO_PASSWORD is not set");
  expect(invitedDemo?.index, "the first candidate is a demo account").toBeGreaterThan(0);
  const first = owner.getByRole("article").first();
  await first.getByRole("button", { name: uk.feed.invite.triggerFor(invitedDemo?.name ?? "") }).click();
  await expect(first.getByRole("heading", { name: uk.feed.invite.title })).toBeFocused();
  await first.getByRole("button", { name: uk.feed.invite.confirm }).click();
  await expect(first.getByRole("button", { name: uk.feed.invite.sent })).toBeFocused();
  await expect(owner.getByText(uk.feed.invite.sentToast)).toBeVisible();

  // The "sent" label is the only confirmation on the card, so it must stay legible even though
  // the button is inactive (axe skips inactive controls, hence the direct measurement)
  const sent = first.getByRole("button", { name: uk.feed.invite.sent });
  for (const scheme of ["light", "dark"] as const) {
    await owner.emulateMedia({ colorScheme: scheme });
    // Polled: the colours transition for a moment after the scheme changes
    await expect
      .poll(() => paintedContrast(sent), { message: `contrast of the sent label, ${scheme}` })
      .toBeGreaterThanOrEqual(4.5);
  }
  await owner.emulateMedia({ colorScheme: null });
});

test("the invited demo user accepts and sees the sender's contact", async ({ browser, playwright }) => {
  test.skip(!demoPassword, "E2E_DEMO_PASSWORD is not set");
  const index = invitedDemo?.index ?? 0;

  // The seeded accounts have no contact; accepting needs one, so give it through the API first
  const api = await playwright.request.newContext({
    baseURL: test.info().project.use.baseURL,
    ignoreHTTPSErrors: true,
  });
  const session = await demoSession(api, index);
  await ensureDemoContact(api, session);
  await api.dispose();

  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  captureBodies(page);
  try {
    // Signing in with the keyboard alone: Tab to the fields, type, Enter
    await page.goto("/login");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(uk.pages.login.title);
    for (let step = 0; step < 12; step += 1) {
      await page.keyboard.press("Tab");
      if (await page.getByLabel(uk.auth.email).evaluate((field) => field === document.activeElement)) break;
    }
    await expect(page.getByLabel(uk.auth.email)).toBeFocused();
    await page.keyboard.type(demoEmail(index));
    await page.keyboard.press("Tab");
    await expect(page.getByLabel(passwordLabel)).toBeFocused();
    await page.keyboard.type(demoPassword ?? "");
    await page.keyboard.press("Enter");

    await mainNav(page).getByRole("link", { name: uk.nav.invitations }).click();
    const card = page.getByRole("article").filter({ hasText: displayName });
    await expect(card).toBeVisible();
    await expect(card.getByText(uk.invitations.status.pending, { exact: true })).toBeVisible();
    // Before accepting, the contact is not on the page
    await expect(card.getByText(ownContact)).toHaveCount(0);

    await card.getByRole("button", { name: uk.invitations.actions.accept.triggerFor(displayName) }).click();
    await card.getByRole("button", { name: uk.invitations.actions.accept.confirm }).click();
    await expect(
      page.getByRole("status").filter({ hasText: uk.invitations.actions.accept.done }),
    ).toBeFocused();
    await expect(card.getByText(uk.invitations.status.accepted, { exact: true })).toBeVisible();
    await expect(card.getByText(ownContact)).toBeVisible();
  } finally {
    await context.close();
  }
});

test("the sender sees the partner's contact on the sent invitation", async () => {
  test.skip(!demoPassword, "E2E_DEMO_PASSWORD is not set");
  await mainNav(owner).getByRole("link", { name: uk.nav.invitations }).click();
  await owner.getByRole("tab", { name: uk.invitations.outgoing }).click();
  const card = owner.getByRole("article").filter({ hasText: invitedDemo?.name ?? "" });
  await expect(card.getByText(uk.invitations.status.accepted, { exact: true })).toBeVisible();
  await expect(card.getByText(/^@demo_participant_\d{4}$/)).toBeVisible();

  // Every public response of the session stayed free of positions and capabilities
  const leaks = publicBodies.flatMap(({ url, body }) =>
    findForbiddenKeys(body).map((path) => `${new URL(url).pathname}${path}`),
  );
  expect(leaks).toEqual([]);
  expect(publicBodies.length).toBeGreaterThan(1);
});

test("one button deletes the account and the user lands on the landing page", async ({ playwright }) => {
  await mainNav(owner).getByRole("link", { name: uk.nav.profile }).click();
  await owner.getByRole("button", { name: uk.profile.manage.deleteAll.trigger }).click();
  await expect(owner.getByRole("heading", { name: uk.profile.manage.deleteAll.title })).toBeFocused();
  await owner.getByRole("button", { name: uk.profile.manage.deleteAll.confirm }).click();

  await expect(owner).toHaveURL(/\/$/);
  await expect(owner.getByRole("heading", { level: 1 })).toHaveText(uk.pages.home.title);
  await expect(mainNav(owner).getByRole("link", { name: uk.nav.login })).toBeVisible();

  // The account is really gone: its credentials no longer work
  const api = await playwright.request.newContext({
    baseURL: test.info().project.use.baseURL,
    ignoreHTTPSErrors: true,
  });
  await expect(apiLogin(api, email, e2ePassword)).rejects.toThrow(/401/);
  await api.dispose();
});
