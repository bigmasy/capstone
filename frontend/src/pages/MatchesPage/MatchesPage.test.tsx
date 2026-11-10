import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { MatchItem } from "../../api/types";
import App from "../../components/App/App";
import { formatPoints } from "../../i18n/format";
import { uk } from "../../i18n/uk";
import {
  bodiesSentTo,
  calls,
  jsonResponse,
  makeAccount,
  makeFeed,
  makeInvitation,
  makeMatch,
  routeFetch,
  taxonomy,
  type Routes,
} from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";

const text = uk.feed;
const card = text.card;

const CONTACT_REQUIRED = { detail: "server wording", code: "contact_required" };

const learnedInfluence = { sport: "raises", distance: "neutral", functional: "lowers", intensity: "raises" } as const;

describe("MatchesPage", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const routes = (overrides: Routes = {}): Routes => ({
    "GET /auth/me": () => jsonResponse(200, {}),
    "GET /taxonomy": () => jsonResponse(200, taxonomy),
    "GET /matches": () => jsonResponse(200, makeFeed([makeMatch()])),
    ...overrides,
  });

  const renderPage = () => renderWithProviders(<App />, { route: "/matches", preloadedState: loggedIn });
  const feedCalls = () => calls(fetchMock).filter((call) => call.startsWith("GET /matches"));

  /** A feed of `total` candidates that answers each page with its own slice. */
  const pagedFeed = (total: number) => (request: Request) => {
    const params = new URL(request.url).searchParams;
    const skip = Number(params.get("skip"));
    const limit = Number(params.get("limit"));
    const items = Array.from({ length: Math.min(limit, total - skip) }, (_, index) =>
      makeMatch({ id: `id-${skip + index}`, display_name: `Партнер ${skip + index + 1}` }),
    );
    return jsonResponse(200, makeFeed(items, { skip, limit, total }));
  };

  describe("cards", () => {
    it("shows the public fields, the distance band and the baseline explanation", async () => {
      routeFetch(fetchMock, routes());
      renderPage();

      const article = await screen.findByRole("article", { name: "Андрій" });

      expect(within(article).getByText("Київ, Оболонський")).toBeInTheDocument();
      expect(within(article).getByText("4: висока")).toBeInTheDocument();
      expect(within(article).getByText("Плавання (просунутий)")).toBeInTheDocument();
      expect(within(article).getByText("Велоспорт (початківець)")).toBeInTheDocument();
      expect(within(article).getByText(card.distanceBand["5–10 km"])).toBeInTheDocument();
      expect(within(article).getByText(card.points(formatPoints(15), 30))).toBeInTheDocument();
      expect(within(article).getByText(card.points(formatPoints(20), 30))).toBeInTheDocument();
      expect(within(article).getByText(card.points(formatPoints(11.2), 15))).toBeInTheDocument();
      expect(within(article).getByText(card.functionalLevel.high)).toBeInTheDocument();
      expect(within(article).getByText(card.functionalNote)).toBeInTheDocument();
      expect(within(article).getByText(card.total(formatPoints(71.2)))).toBeInTheDocument();
      expect(within(article).getByText(card.rankSource.baseline)).toBeInTheDocument();
      // A baseline feed has no learned influence and does not claim a learned order
      expect(within(article).queryByText(card.rankSource.learned)).toBeNull();
      expect(within(article).queryByText(card.learnedNote)).toBeNull();
      expect(within(article).queryByText(card.influence.raises)).toBeNull();
    });

    it("takes the denominators of the points from the API, not from the client", async () => {
      routeFetch(fetchMock, routes({
        "GET /matches": () =>
          jsonResponse(
            200,
            makeFeed([makeMatch()], { max_points: { sport: 40, distance: 20, intensity: 10 } }),
          ),
      }));
      renderPage();

      const article = await screen.findByRole("article", { name: "Андрій" });

      expect(within(article).getByText(card.points(formatPoints(15), 40))).toBeInTheDocument();
      expect(within(article).getByText(card.points(formatPoints(20), 20))).toBeInTheDocument();
      expect(within(article).getByText(card.points(formatPoints(11.2), 10))).toBeInTheDocument();
    });

    it("says that a medium functional level may also mean there was nothing to compare", async () => {
      routeFetch(fetchMock, routes({
        "GET /matches": () =>
          jsonResponse(
            200,
            makeFeed([
              makeMatch({
                breakdown: { sport: 15, distance: 20, intensity: 11.2, functional: "medium", total: 71.2 },
              }),
            ]),
          ),
      }));
      renderPage();

      const article = await screen.findByRole("article", { name: "Андрій" });

      // The explanation is a disclosure that is closed by default
      await userEvent.setup().click(within(article).getByText(card.explanationHeading));

      expect(within(article).getByText(card.functionalLevel.medium)).toBeInTheDocument();
      expect(within(article).getByText(card.functionalMediumHint)).toBeVisible();
      expect(card.functionalMediumHint).toContain("«Середній»");
    });

    it("does not show the medium hint for a high or a low level", async () => {
      routeFetch(fetchMock, routes({
        "GET /matches": () =>
          jsonResponse(
            200,
            makeFeed([
              makeMatch({ id: "a", display_name: "Андрій" }),
              makeMatch({
                id: "b",
                display_name: "Борис",
                breakdown: { sport: 15, distance: 20, intensity: 11.2, functional: "low", total: 40 },
              }),
            ]),
          ),
      }));
      renderPage();

      await screen.findByRole("article", { name: "Борис" });

      expect(screen.queryByText(card.functionalMediumHint)).toBeNull();
    });

    it("never writes the total as a percentage", async () => {
      routeFetch(fetchMock, routes());
      renderPage();

      const article = await screen.findByRole("article", { name: "Андрій" });

      expect(article.textContent).not.toContain("%");
    });

    it("shows the learned source, the influence of every criterion and the order note", async () => {
      routeFetch(fetchMock, {
        ...routes(),
        "GET /matches": () =>
          jsonResponse(
            200,
            makeFeed([makeMatch({ rank_source: "learned", rank_influence: learnedInfluence })]),
          ),
      });
      renderPage();

      const article = await screen.findByRole("article", { name: "Андрій" });

      expect(within(article).getByText(card.rankSource.learned)).toBeInTheDocument();
      expect(within(article).queryByText(card.rankSource.baseline)).toBeNull();
      expect(within(article).getAllByText(card.influence.raises)).toHaveLength(2);
      expect(within(article).getByText(card.influence.neutral)).toBeInTheDocument();
      expect(within(article).getByText(card.influence.lowers)).toBeInTheDocument();
      expect(within(article).getByText(card.learnedNote)).toBeInTheDocument();
      // The baseline total stays visible beside the learned order
      expect(within(article).getByText(card.total(formatPoints(71.2)))).toBeInTheDocument();
    });

    it("pairs each influence with its criterion", async () => {
      routeFetch(fetchMock, {
        ...routes(),
        "GET /matches": () =>
          jsonResponse(
            200,
            makeFeed([makeMatch({ rank_source: "learned", rank_influence: learnedInfluence })]),
          ),
      });
      renderPage();
      const article = await screen.findByRole("article", { name: "Андрій" });

      const functional = within(article).getByText(card.criteria.functional).closest("div");
      const distance = within(article).getByText(card.criteria.distance).closest("div");

      expect(functional).toHaveTextContent(card.influence.lowers);
      expect(distance).toHaveTextContent(card.influence.neutral);
    });

    it("shows an unknown distance band as the API sent it", async () => {
      routeFetch(fetchMock, {
        ...routes(),
        "GET /matches": () =>
          jsonResponse(
            200,
            makeFeed([makeMatch({ distance_band: "far away" as MatchItem["distance_band"] })]),
          ),
      });
      renderPage();

      expect(await screen.findByText("far away")).toBeInTheDocument();
    });

    it("renders no coordinates and no capability data even if the response carried them", async () => {
      const leaky = {
        ...makeMatch(),
        latitude: 50.4501,
        longitude: 30.5234,
        capabilities: [{ category: "vision", level: 1 }],
        contact: "+380501234567",
      };
      routeFetch(fetchMock, {
        ...routes(),
        "GET /matches": () => jsonResponse(200, makeFeed([leaky])),
      });
      const { container } = renderPage();

      await screen.findByRole("article", { name: "Андрій" });

      const shown = container.textContent ?? "";
      expect(shown).not.toContain("50.45");
      expect(shown).not.toContain("30.52");
      expect(shown).not.toContain("+380501234567");
      expect(shown).not.toContain("Зір і орієнтація");
    });
  });

  describe("states", () => {
    it("shows a loading indicator, then the results with their count announced", async () => {
      routeFetch(fetchMock, routes({ "GET /matches": () => jsonResponse(200, makeFeed([makeMatch()])) }));
      renderPage();

      expect(screen.getByText(text.loading)).toBeInTheDocument();

      const summary = await screen.findByText(text.summary(1, 1, 1));
      expect(summary).toHaveAttribute("role", "status");
    });

    it("explains an empty feed and offers the profile", async () => {
      routeFetch(fetchMock, routes({ "GET /matches": () => jsonResponse(200, makeFeed([])) }));
      renderPage();

      const message = await screen.findByText(text.empty);
      expect(message).toHaveAttribute("role", "status");
      expect(screen.getByText(text.emptyAdvice)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: text.emptyProfileLink })).toHaveAttribute("href", "/profile");
    });

    it("links to the profile page when the API answers 404 because there is no profile", async () => {
      routeFetch(fetchMock, routes({ "GET /matches": () => jsonResponse(404, { detail: "no" }) }));
      renderPage();

      expect(await screen.findByText(text.noProfile)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: text.noProfileLink })).toHaveAttribute("href", "/profile");
      expect(screen.queryByRole("alert")).toBeNull();
    });

    it("shows an alert and retries on a server error", async () => {
      routeFetch(fetchMock, routes({ "GET /matches": () => jsonResponse(500, { detail: "boom" }) }));
      const user = userEvent.setup();
      renderPage();

      expect(await screen.findByRole("alert")).toHaveTextContent(text.loadFailed);
      expect(screen.queryByText("boom")).toBeNull();

      routeFetch(fetchMock, routes());
      await user.click(screen.getByRole("button", { name: text.retry }));

      expect(await screen.findByRole("article", { name: "Андрій" })).toBeInTheDocument();
      expect(screen.queryByRole("alert")).toBeNull();
    });
  });

  it("ends the session and explains it on the login page when the feed answers 401", async () => {
    routeFetch(fetchMock, routes({ "GET /matches": () => jsonResponse(401, { detail: "expired" }) }));

    const { store } = renderPage();

    expect(await screen.findByRole("heading", { level: 1, name: uk.pages.login.title })).toBeInTheDocument();
    expect(screen.getByText(uk.auth.sessionEnded)).toBeInTheDocument();
    expect(store.getState().auth.token).toBeNull();
  });

  describe("filters and pagination", () => {
    it("requests the first page of ten without filters", async () => {
      routeFetch(fetchMock, routes());
      renderPage();

      await screen.findByRole("article", { name: "Андрій" });

      expect(feedCalls()).toEqual(["GET /matches?skip=0&limit=10"]);
    });

    it("offers the radii and every sport of the taxonomy", async () => {
      routeFetch(fetchMock, routes());
      renderPage();
      await screen.findByRole("article", { name: "Андрій" });

      const radius = screen.getByLabelText(text.filters.radius);
      const sport = screen.getByLabelText(text.filters.sport);

      expect(within(radius).getAllByRole("option").map((option) => option.textContent)).toEqual([
        "до 100 км",
        text.filters.radiusOption(5),
        text.filters.radiusOption(10),
        text.filters.radiusOption(25),
      ]);
      expect(within(sport).getAllByRole("option")).toHaveLength(taxonomy.sports.length + 1);
      expect(within(sport).getByRole("option", { name: "Плавання" })).toHaveValue("swimming");
    });

    it("sends the chosen radius and sport and starts again from the first page", async () => {
      routeFetch(fetchMock, routes({ "GET /matches": pagedFeed(25) }));
      const user = userEvent.setup();
      renderPage();
      await screen.findByRole("article", { name: "Партнер 1" });
      await user.click(screen.getByRole("button", { name: uk.pagination.next }));
      await screen.findByRole("article", { name: "Партнер 11" });

      await user.selectOptions(screen.getByLabelText(text.filters.radius), "10");
      await screen.findByRole("article", { name: "Партнер 1" });
      await user.selectOptions(screen.getByLabelText(text.filters.sport), "swimming");
      await screen.findByRole("article", { name: "Партнер 1" });

      expect(feedCalls()).toEqual([
        "GET /matches?skip=0&limit=10",
        "GET /matches?skip=10&limit=10",
        "GET /matches?skip=0&limit=10&radius_km=10",
        "GET /matches?skip=0&limit=10&radius_km=10&sport=swimming",
      ]);
    });

    it("drops a filter again when the empty choice is selected", async () => {
      routeFetch(fetchMock, routes({
        "GET /matches": (request) =>
          jsonResponse(
            200,
            makeFeed([
              makeMatch({
                display_name: new URL(request.url).searchParams.has("radius_km") ? "Борис" : "Андрій",
              }),
            ]),
          ),
      }));
      const user = userEvent.setup();
      renderPage();
      await screen.findByRole("article", { name: "Андрій" });

      await user.selectOptions(screen.getByLabelText(text.filters.radius), "25");
      await screen.findByRole("article", { name: "Борис" });
      await user.selectOptions(screen.getByLabelText(text.filters.radius), text.filters.radiusAll);

      // The unfiltered page is served from the cache, so no third request is needed
      expect(await screen.findByRole("article", { name: "Андрій" })).toBeInTheDocument();
      expect(feedCalls()).toEqual([
        "GET /matches?skip=0&limit=10",
        "GET /matches?skip=0&limit=10&radius_km=25",
      ]);
    });

    it("keeps the focus on the filter that was changed", async () => {
      routeFetch(fetchMock, routes());
      const user = userEvent.setup();
      renderPage();
      await screen.findByRole("article", { name: "Андрій" });
      const radius = screen.getByLabelText(text.filters.radius);

      await user.selectOptions(radius, "5");
      await screen.findByRole("article", { name: "Андрій" });

      expect(radius).toHaveFocus();
    });

    it("pages with Previous and Next, shows the total and moves focus to the results", async () => {
      routeFetch(fetchMock, routes({ "GET /matches": pagedFeed(25) }));
      const user = userEvent.setup();
      renderPage();

      await screen.findByRole("article", { name: "Партнер 1" });
      expect(screen.getByText(text.summary(1, 10, 25))).toBeInTheDocument();
      expect(screen.getByText(uk.pagination.pageOf(1, 3))).toBeInTheDocument();
      const previous = screen.getByRole("button", { name: uk.pagination.previous });
      expect(previous).toHaveAttribute("aria-disabled", "true");

      await user.click(screen.getByRole("button", { name: uk.pagination.next }));

      await screen.findByRole("article", { name: "Партнер 11" });
      expect(screen.getByText(text.summary(11, 20, 25))).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: text.resultsHeading })).toHaveFocus();
      expect(screen.getByRole("button", { name: uk.pagination.previous })).not.toHaveAttribute("aria-disabled");

      await user.click(screen.getByRole("button", { name: uk.pagination.next }));

      await screen.findByRole("article", { name: "Партнер 21" });
      expect(screen.getByText(text.summary(21, 25, 25))).toBeInTheDocument();
      expect(screen.getAllByRole("article")).toHaveLength(5);
      expect(screen.getByRole("button", { name: uk.pagination.next })).toHaveAttribute("aria-disabled", "true");

      await user.click(screen.getByRole("button", { name: uk.pagination.previous }));
      await screen.findByRole("article", { name: "Партнер 11" });
      // Going back to page 2 is served from the cache
      expect(feedCalls()).toEqual([
        "GET /matches?skip=0&limit=10",
        "GET /matches?skip=10&limit=10",
        "GET /matches?skip=20&limit=10",
      ]);
    });

    it("ignores a click on a disabled Previous or Next button", async () => {
      routeFetch(fetchMock, routes({ "GET /matches": pagedFeed(3) }));
      const user = userEvent.setup();
      renderPage();
      await screen.findByRole("article", { name: "Партнер 1" });

      await user.click(screen.getByRole("button", { name: uk.pagination.previous }));
      await user.click(screen.getByRole("button", { name: uk.pagination.next }));

      expect(feedCalls()).toHaveLength(1);
    });

    it("lets the keyboard reach the pagination buttons", async () => {
      routeFetch(fetchMock, routes({ "GET /matches": pagedFeed(25) }));
      const user = userEvent.setup();
      renderPage();
      await screen.findByRole("article", { name: "Партнер 1" });

      screen.getByRole("button", { name: uk.pagination.next }).focus();
      await user.keyboard("{Enter}");

      expect(await screen.findByRole("article", { name: "Партнер 11" })).toBeInTheDocument();
    });
  });

  describe("inviting", () => {
    const open = async (user: ReturnType<typeof userEvent.setup>) => {
      await screen.findByRole("article", { name: "Андрій" });
      await user.click(screen.getByRole("button", { name: text.invite.triggerFor("Андрій") }));
    };

    it("asks for confirmation first and sends nothing when the user cancels", async () => {
      routeFetch(fetchMock, routes());
      const user = userEvent.setup();
      renderPage();

      await open(user);

      expect(screen.getByRole("heading", { name: text.invite.title })).toHaveFocus();
      expect(feedCalls()).toHaveLength(1);
      await user.click(screen.getByRole("button", { name: uk.profile.manage.cancel }));
      expect(screen.getByRole("button", { name: text.invite.triggerFor("Андрій") })).toHaveFocus();
      expect(calls(fetchMock).filter((call) => call.startsWith("POST"))).toEqual([]);
    });

    it("posts only the recipient profile id, then shows a toast and the sent state", async () => {
      const match = makeMatch();
      routeFetch(fetchMock, routes({
        "POST /invitations": () => jsonResponse(201, makeInvitation("outgoing")),
      }));
      const user = userEvent.setup();
      renderPage();

      await open(user);
      await user.click(screen.getByRole("button", { name: text.invite.confirm }));

      const sent = await screen.findByRole("button", { name: text.invite.sent });
      expect(await bodiesSentTo(fetchMock, "POST /invitations")).toEqual([
        { recipient_profile_id: match.id },
      ]);
      expect(sent).toHaveAttribute("aria-disabled", "true");
      expect(sent).toHaveFocus();
      expect(await screen.findByText(text.invite.sentToast)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: text.invite.trigger })).toBeNull();

      await user.click(sent);
      expect(calls(fetchMock).filter((call) => call.startsWith("POST"))).toHaveLength(1);
    });

    it("remembers the sent state while paging back and forth", async () => {
      routeFetch(fetchMock, routes({
        "GET /matches": pagedFeed(25),
        "POST /invitations": () => jsonResponse(201, makeInvitation("outgoing")),
      }));
      const user = userEvent.setup();
      renderPage();
      await screen.findByRole("article", { name: "Партнер 1" });
      await user.click(screen.getByRole("button", { name: text.invite.triggerFor("Партнер 1") }));
      await user.click(screen.getByRole("button", { name: text.invite.confirm }));
      await screen.findByRole("button", { name: text.invite.sent });

      await user.click(screen.getByRole("button", { name: uk.pagination.next }));
      await screen.findByRole("article", { name: "Партнер 11" });
      await user.click(screen.getByRole("button", { name: uk.pagination.previous }));
      await screen.findByRole("article", { name: "Партнер 1" });

      expect(screen.getAllByRole("button", { name: text.invite.sent })).toHaveLength(1);
    });

    it.each([
      [409, text.invite.errorConflict],
      [404, text.invite.errorNotFound],
      [500, text.invite.errorGeneric],
    ])("reports a %i answer with a fixed message and keeps the button usable", async (status, message) => {
      routeFetch(fetchMock, routes({
        "POST /invitations": () => jsonResponse(status, { detail: "server wording" }),
      }));
      const user = userEvent.setup();
      renderPage();

      await open(user);
      await user.click(screen.getByRole("button", { name: text.invite.confirm }));

      expect(await screen.findByRole("alert")).toHaveTextContent(message);
      expect(screen.queryByText("server wording")).toBeNull();
      expect(screen.queryByRole("button", { name: text.invite.sent })).toBeNull();
      expect(screen.getByRole("button", { name: text.invite.confirm })).toBeInTheDocument();
    });

    it("answers a coded contact_required with a focused alert and a link to the profile", async () => {
      routeFetch(fetchMock, routes({
        "POST /invitations": () => jsonResponse(409, CONTACT_REQUIRED),
      }));
      const user = userEvent.setup();
      renderPage();

      await open(user);
      await user.click(screen.getByRole("button", { name: text.invite.confirm }));

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(uk.contactRequired.message);
      expect(alert).toHaveFocus();
      expect(within(alert).getByRole("link", { name: uk.contactRequired.link })).toHaveAttribute(
        "href",
        "/profile",
      );
      expect(screen.queryByText("server wording")).toBeNull();
      expect(screen.queryByText(text.invite.errorConflict)).toBeNull();
      expect(screen.queryByRole("button", { name: text.invite.confirm })).toBeNull();
      expect(screen.queryByRole("button", { name: text.invite.sent })).toBeNull();
    });

    it("replaces the invite button with a notice while the address is not confirmed", async () => {
      routeFetch(fetchMock, routes({
        "GET /auth/me": () => jsonResponse(200, makeAccount({ email_verified: false })),
      }));
      renderPage();

      await screen.findByRole("article", { name: "Андрій" });

      expect(await screen.findByText(uk.verification.inviteNotice)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: text.invite.triggerFor("Андрій") })).toBeNull();
    });

    it("turns the button into the notice when the server answers email_not_verified", async () => {
      routeFetch(fetchMock, routes({
        "POST /invitations": () =>
          jsonResponse(403, { detail: "server wording", code: "email_not_verified" }),
      }));
      const user = userEvent.setup();
      renderPage();

      await open(user);
      await user.click(screen.getByRole("button", { name: text.invite.confirm }));

      expect(await screen.findByText(uk.verification.inviteNotice)).toBeInTheDocument();
      expect(screen.queryByText("server wording")).toBeNull();
      expect(screen.queryByRole("button", { name: text.invite.confirm })).toBeNull();
    });

    it("keeps the usual conflict message for a 409 without the code", async () => {
      routeFetch(fetchMock, routes({
        "POST /invitations": () => jsonResponse(409, { detail: "server wording", code: "something_else" }),
      }));
      const user = userEvent.setup();
      renderPage();

      await open(user);
      await user.click(screen.getByRole("button", { name: text.invite.confirm }));

      expect(await screen.findByRole("alert")).toHaveTextContent(text.invite.errorConflict);
      expect(screen.queryByText(uk.contactRequired.message)).toBeNull();
    });

    it("follows the link to the profile page", async () => {
      routeFetch(fetchMock, routes({
        "POST /invitations": () => jsonResponse(409, CONTACT_REQUIRED),
        "GET /profiles/me": () => jsonResponse(404, {}),
      }));
      const user = userEvent.setup();
      renderPage();

      await open(user);
      await user.click(screen.getByRole("button", { name: text.invite.confirm }));
      await user.click(await screen.findByRole("link", { name: uk.contactRequired.link }));

      expect(await screen.findByRole("heading", { level: 1, name: uk.pages.profile.title })).toBeInTheDocument();
    });
  });

  describe("accessibility", () => {
    const states: [string, Routes][] = [
      ["baseline results", routes()],
      [
        "learned results",
        routes({
          "GET /matches": () =>
            jsonResponse(200, makeFeed([makeMatch({ rank_source: "learned", rank_influence: learnedInfluence })])),
        }),
      ],
      [
        "medium functional level with the hint",
        routes({
          "GET /matches": () =>
            jsonResponse(
              200,
              makeFeed([
                makeMatch({
                  breakdown: { sport: 15, distance: 20, intensity: 11.2, functional: "medium", total: 71.2 },
                }),
              ]),
            ),
        }),
      ],
      ["empty feed", routes({ "GET /matches": () => jsonResponse(200, makeFeed([])) })],
      ["no profile", routes({ "GET /matches": () => jsonResponse(404, {}) })],
      ["load error", routes({ "GET /matches": () => jsonResponse(500, {}) })],
    ];

    it.each(states)("has no axe violations: %s", async (_name, stateRoutes) => {
      routeFetch(fetchMock, stateRoutes);
      const { container } = renderPage();
      await waitFor(() => expect(feedCalls().length).toBeGreaterThan(0));
      await waitFor(() => expect(screen.queryByText(text.loading)).toBeNull());

      expect(await axe(container)).toHaveNoViolations();
    });

    it("has no axe violations while the invitation is being confirmed", async () => {
      routeFetch(fetchMock, routes());
      const user = userEvent.setup();
      const { container } = renderPage();
      await screen.findByRole("article", { name: "Андрій" });

      await user.click(screen.getByRole("button", { name: text.invite.triggerFor("Андрій") }));

      expect(await axe(container)).toHaveNoViolations();
    });

    it("has no axe violations with the contact notice shown", async () => {
      routeFetch(fetchMock, routes({ "POST /invitations": () => jsonResponse(409, CONTACT_REQUIRED) }));
      const user = userEvent.setup();
      const { container } = renderPage();
      await screen.findByRole("article", { name: "Андрій" });
      await user.click(screen.getByRole("button", { name: text.invite.triggerFor("Андрій") }));
      await user.click(screen.getByRole("button", { name: text.invite.confirm }));
      await screen.findByRole("alert");

      expect(await axe(container)).toHaveNoViolations();
    });

    it("has no axe violations after an invitation was sent", async () => {
      routeFetch(fetchMock, routes({ "POST /invitations": () => jsonResponse(201, makeInvitation("outgoing")) }));
      const user = userEvent.setup();
      const { container } = renderPage();
      await screen.findByRole("article", { name: "Андрій" });
      await user.click(screen.getByRole("button", { name: text.invite.triggerFor("Андрій") }));
      await user.click(screen.getByRole("button", { name: text.invite.confirm }));
      await screen.findByRole("button", { name: text.invite.sent });

      expect(await axe(container)).toHaveNoViolations();
    });

    it("has no axe violations on a page of a longer feed", async () => {
      routeFetch(fetchMock, routes({ "GET /matches": pagedFeed(25) }));
      const { container } = renderPage();
      await screen.findByRole("article", { name: "Партнер 1" });

      expect(await axe(container)).toHaveNoViolations();
    });
  });
});
