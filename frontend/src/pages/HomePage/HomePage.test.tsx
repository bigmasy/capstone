import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { adaptiveSportColumns } from "../../content/adaptiveSport";
import { uk } from "../../i18n/uk";
import { jsonResponse, makeProfile, routeFetch, taxonomy } from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";
import HomePage from "./HomePage";

describe("HomePage (landing)", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    routeFetch(fetchMock, {
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

    it("does not call the API", () => {
      renderWithProviders(<HomePage />);

      expect(fetchMock).not.toHaveBeenCalled();
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
      expect(section).toHaveTextContent("4 × 4 км");
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

  describe("adaptive sport sources", () => {
    it("shows three columns with every verified link opening safely in a new tab", () => {
      renderWithProviders(<HomePage />);

      const section = screen.getByRole("region", { name: uk.landing.sources.heading });
      for (const column of adaptiveSportColumns) {
        const heading = within(section).getByRole("heading", { level: 3, name: column.heading });
        const columnElement = heading.parentElement as HTMLElement;
        expect(within(columnElement).getAllByRole("link")).toHaveLength(column.items.length);
        for (const item of column.items) {
          const link = within(columnElement).getByRole("link", {
            name: `${item.title} (${uk.a11y.opensInNewTab})`,
          });
          expect(link).toHaveAttribute("href", item.href);
          expect(link).toHaveAttribute("target", "_blank");
          expect(link).toHaveAttribute("rel", "noopener noreferrer");
          expect(link).toHaveTextContent(uk.a11y.opensInNewTab);
        }
      }
    });

    it("carries the disclaimer and the date on which the links were checked", () => {
      renderWithProviders(<HomePage />);

      const section = screen.getByRole("region", { name: uk.landing.sources.heading });
      expect(section).toHaveTextContent("Матеріали зібрано з відкритих джерел; ми не відповідаємо за їхній зміст.");
      expect(section).toHaveTextContent(/6 листопада 2026/);
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
