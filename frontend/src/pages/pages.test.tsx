import { screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../components/App/App";
import { uk } from "../i18n/uk";
import {
  jsonResponse,
  makeFeed,
  makeInvitation,
  makeMatch,
  makeProfile,
  routeFetch,
  taxonomy,
} from "../test/api";
import { loggedIn, renderWithProviders } from "../test/utils";

interface PageCase {
  name: string;
  route: string;
  title: string;
  authenticated: boolean;
}

const pages: PageCase[] = [
  { name: "HomePage", route: "/", title: uk.pages.home.title, authenticated: false },
  { name: "AboutPage", route: "/about", title: uk.pages.about.title, authenticated: false },
  { name: "AboutPage (logged in)", route: "/about", title: uk.pages.about.title, authenticated: true },
  { name: "LoginPage", route: "/login", title: uk.pages.login.title, authenticated: false },
  { name: "RegisterPage", route: "/register", title: uk.pages.register.title, authenticated: false },
  { name: "ProfilePage", route: "/profile", title: uk.pages.profile.title, authenticated: true },
  { name: "MatchesPage", route: "/matches", title: uk.pages.matches.title, authenticated: true },
  {
    name: "InvitationsPage",
    route: "/invitations",
    title: uk.pages.invitations.title,
    authenticated: true,
  },
  { name: "NotFoundPage", route: "/nope", title: uk.pages.notFound.title, authenticated: false },
  { name: "HomePage (logged in)", route: "/", title: uk.pages.home.title, authenticated: true },
];

describe.each(pages)("$name", ({ route, title, authenticated }) => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    routeFetch(fetchMock, {
      "GET /auth/me": () => jsonResponse(200, {}),
      "GET /taxonomy": () => jsonResponse(200, taxonomy),
      "GET /profiles/me": () => jsonResponse(200, makeProfile()),
      "GET /matches": () => jsonResponse(200, makeFeed([makeMatch()])),
      "GET /invitations": () => jsonResponse(200, [makeInvitation("incoming")]),
    });
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const render = () =>
    renderWithProviders(<App />, { route, preloadedState: authenticated ? loggedIn : undefined });

  it("has exactly one h1 with the page title inside main", () => {
    render();

    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(title);
    expect(screen.getByRole("main")).toContainElement(headings[0] as HTMLElement);
  });

  it("has no axe violations", async () => {
    const { container } = render();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("sets the document title", () => {
    render();

    expect(document.title).toBe(`${title}${uk.app.titleSeparator}${uk.app.name}`);
  });
});
