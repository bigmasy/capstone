import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import { jsonResponse, makeNews, makeProfile, routeFetch, taxonomy } from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";
import HomePage from "./HomePage";

describe("HomePage (landing)", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    routeFetch(fetchMock, {
      "GET /news": () => jsonResponse(200, makeNews()),
      "GET /taxonomy": () => jsonResponse(200, taxonomy),
      "GET /profiles/me": () => jsonResponse(200, makeProfile()),
    });
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  describe("for a visitor", () => {
    it("shows the value proposition with registration and information calls to action", () => {
      renderWithProviders(<HomePage />);

      expect(screen.getByRole("heading", { level: 1, name: uk.pages.home.title })).toBeInTheDocument();
      // The hero and the closing band both carry the registration call to action
      const register = screen.getAllByRole("link", { name: uk.landing.hero.registerCta });
      expect(register).toHaveLength(2);
      for (const link of register) expect(link).toHaveAttribute("href", "/register");
      expect(screen.getByRole("link", { name: uk.landing.hero.learnMore })).toHaveAttribute("href", "/about");
      expect(screen.queryByRole("link", { name: uk.landing.hero.memberCta })).toBeNull();
    });

    it("asks the API only for the public news, never for anything that needs a session", async () => {
      renderWithProviders(<HomePage />);

      await screen.findByText("Meet in Brescia");

      const requests = fetchMock.mock.calls.map(([input]) => {
        const request = input as Request;
        return `${request.method} ${new URL(request.url).pathname}`;
      });
      expect(requests).toEqual(["GET /api/v1/news"]);
      expect((fetchMock.mock.calls[0]?.[0] as Request).headers.get("Authorization")).toBeNull();
    });

    it("explains how it works in four steps", () => {
      renderWithProviders(<HomePage />);

      const section = screen.getByRole("region", { name: uk.landing.how.heading });
      expect(within(section).getAllByRole("listitem")).toHaveLength(4);
      for (const step of uk.landing.how.steps) {
        expect(within(section).getByRole("heading", { level: 3, name: step.title })).toBeInTheDocument();
      }
    });

    it("states the privacy promises", () => {
      renderWithProviders(<HomePage />);

      const section = screen.getByRole("region", { name: uk.landing.privacy.heading });
      for (const item of uk.landing.privacy.items) {
        expect(within(section).getByRole("heading", { name: item.title })).toBeInTheDocument();
      }
      expect(section).toHaveTextContent("розмір якої ви обираєте самі");
    });

    it("has the sections why, audience and the final call to action", () => {
      renderWithProviders(<HomePage />);

      expect(screen.getByRole("region", { name: uk.landing.why.heading })).toBeInTheDocument();
      expect(screen.getByRole("region", { name: uk.landing.audience.heading })).toBeInTheDocument();
      const cta = screen.getByRole("region", { name: uk.landing.finalCta.heading });
      expect(within(cta).getByRole("link", { name: uk.landing.hero.registerCta })).toHaveAttribute("href", "/register");
    });

    it("has exactly one h1 and no level skips between h2 and h3", () => {
      renderWithProviders(<HomePage />);

      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      const levels = screen.getAllByRole("heading").map((heading) => Number(heading.tagName.slice(1)));
      levels.reduce((previous, level) => {
        expect(level - previous).toBeLessThanOrEqual(1);
        return level;
      }, 1);
    });

    it("has no axe violations", async () => {
      const { container } = renderWithProviders(<HomePage />);

      expect(await axe(container)).toHaveNoViolations();
    });
  });

  describe("FAQ", () => {
    it("opens and closes a question with the keyboard and keeps the answer out of reach while closed", async () => {
      const user = userEvent.setup();
      renderWithProviders(<HomePage />);
      const [first] = uk.landing.faq.items;
      const button = screen.getByRole("button", { name: first?.question });

      expect(button).toHaveAttribute("aria-expanded", "false");
      expect(screen.getByText(first?.answer ?? "")).not.toBeVisible();

      button.focus();
      await user.keyboard("{Enter}");
      expect(button).toHaveAttribute("aria-expanded", "true");
      expect(screen.getByText(first?.answer ?? "")).toBeVisible();

      await user.keyboard(" ");
      expect(button).toHaveAttribute("aria-expanded", "false");
    });

    it("has one button per question", () => {
      renderWithProviders(<HomePage />);

      const section = screen.getByRole("region", { name: uk.landing.faq.heading });
      expect(within(section).getAllByRole("button")).toHaveLength(uk.landing.faq.items.length);
    });
  });

  describe("adaptive sport news", () => {
    const sources = () => screen.getByRole("region", { name: uk.landing.sources.heading });

    it("shows the collected items in their columns, each link opening safely in a new tab", async () => {
      renderWithProviders(<HomePage />);

      const link = await screen.findByRole("link", {
        name: `Паралімпійці отримають премії (${uk.a11y.opensInNewTab})`,
      });
      expect(link).toHaveAttribute("href", "https://suspilne.media/2");
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
      const column = within(sources())
        .getByRole("heading", { level: 3, name: uk.landing.sources.columns.ukraine })
        .parentElement as HTMLElement;
      expect(within(column).getByText("Суспільне")).toBeInTheDocument();
      expect(within(column).getByText(/9 листопада 2026/)).toBeInTheDocument();
    });

    it("leaves out a column that has nothing yet", async () => {
      renderWithProviders(<HomePage />);

      await screen.findByText("Meet in Brescia");

      expect(
        within(sources()).queryByRole("heading", {
          level: 3,
          name: uk.landing.sources.columns.veterans,
        }),
      ).toBeNull();
      expect(within(sources()).queryByText(uk.landing.sources.empty)).toBeNull();
    });

    it("carries the disclaimer and no date on which anything was checked or updated", async () => {
      renderWithProviders(<HomePage />);

      await screen.findByText("Meet in Brescia");

      expect(sources()).toHaveTextContent(
        "Матеріали зібрано з відкритих джерел; ми не відповідаємо за їхній зміст.",
      );
      expect(sources()).not.toHaveTextContent(/перевірено|оновлено/i);
    });

    it("renders a title as text, never as markup", async () => {
      routeFetch(fetchMock, {
        "GET /news": () =>
          jsonResponse(
            200,
            makeNews({
              columns: [
                {
                  id: "world",
                  items: [
                    {
                      title: "<img src=x onerror=alert(1)>Title",
                      url: "https://www.paralympic.org/n/9",
                      source: "IPC",
                      published_at: "2026-11-06T09:00:00Z",
                    },
                  ],
                },
              ],
            }),
          ),
      });
      renderWithProviders(<HomePage />);

      expect(await screen.findByText(/<img src=x onerror=alert\(1\)>Title/)).toBeInTheDocument();
      expect(sources().querySelector("img")).toBeNull();
    });

    it("offers to try again when the news cannot be loaded and then shows them", async () => {
      const user = userEvent.setup();
      routeFetch(fetchMock, { "GET /news": () => jsonResponse(500, { detail: "boom" }) });
      renderWithProviders(<HomePage />);

      expect(await screen.findByText(uk.landing.sources.failed)).toBeInTheDocument();
      expect(screen.queryByText("boom")).toBeNull();
      routeFetch(fetchMock, { "GET /news": () => jsonResponse(200, makeNews()) });
      await user.click(screen.getByRole("button", { name: uk.landing.sources.retry }));

      expect(await screen.findByText("Meet in Brescia")).toBeInTheDocument();
      expect(screen.queryByText(uk.landing.sources.failed)).toBeNull();
    });

    it("has no axe violations with the news shown", async () => {
      const { container } = renderWithProviders(<HomePage />);
      await screen.findByText("Meet in Brescia");

      expect(await axe(container)).toHaveNoViolations();
    });
  });

  describe("for a logged-in user", () => {
    it("replaces the registration pitch with links into the app and shows the profile panel", async () => {
      const { container } = renderWithProviders(<HomePage />, { preloadedState: loggedIn });

      expect(await screen.findByRole("link", { name: uk.pages.home.openMatches })).toHaveAttribute("href", "/matches");
      expect(screen.getByRole("link", { name: uk.pages.home.openInvitations })).toHaveAttribute("href", "/invitations");
      for (const link of screen.getAllByRole("link", { name: uk.landing.hero.memberCta })) {
        expect(link).toHaveAttribute("href", "/matches");
      }
      expect(screen.queryByRole("link", { name: uk.landing.hero.registerCta })).toBeNull();
      expect(await screen.findByRole("heading", { name: uk.pages.home.summaryHeading })).toBeInTheDocument();
      expect(await axe(container)).toHaveNoViolations();
    });

    it("keeps the landing sections", async () => {
      renderWithProviders(<HomePage />, { preloadedState: loggedIn });

      expect(await screen.findByRole("heading", { name: uk.pages.home.summaryHeading })).toBeInTheDocument();
      expect(screen.getByRole("region", { name: uk.landing.how.heading })).toBeInTheDocument();
      expect(screen.getByRole("region", { name: uk.landing.sources.heading })).toBeInTheDocument();
    });
  });
});
