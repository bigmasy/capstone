import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { InvitationOut } from "../../api/types";
import App from "../../components/App/App";
import { formatDateTime } from "../../i18n/format";
import { uk } from "../../i18n/uk";
import {
  calls,
  jsonResponse,
  makeAccount,
  makeInvitation,
  makePartner,
  routeFetch,
  taxonomy,
  type Routes,
} from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";

const text = uk.invitations;
const ID = "6f1c1c0e-0000-4000-8000-0000000000c1";
const CONTACT_REQUIRED = { detail: "server wording", code: "contact_required" };

type User = ReturnType<typeof userEvent.setup>;

describe("InvitationsPage", () => {
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
    "GET /invitations": () => jsonResponse(200, [makeInvitation("incoming")]),
    ...overrides,
  });

  const renderPage = () =>
    renderWithProviders(<App />, { route: "/invitations", preloadedState: loggedIn });
  const listCalls = () => calls(fetchMock).filter((call) => call.startsWith("GET /invitations"));
  const posts = () => calls(fetchMock).filter((call) => call.startsWith("POST"));

  /** Answers the list with `lists[n]` on the n-th request, repeating the last one. */
  const sequence = (...lists: InvitationOut[][]) => {
    let index = 0;
    return () => jsonResponse(200, lists[Math.min(index++, lists.length - 1)]);
  };

  /** Finds text inside the cards only, so the same word in the status filter does not match. */
  const inArticle = (name: string) =>
    waitFor(() => within(screen.getByRole("article")).getByText(name));

  const openAction = async (user: User, trigger: string) => {
    await user.click(await screen.findByRole("button", { name: trigger }));
  };

  describe("list", () => {
    it("shows the sender, the status, the dates and the public fields of an incoming invitation", async () => {
      routeFetch(fetchMock, routes());
      renderPage();

      const article = await screen.findByRole("article", { name: "Марія" });

      expect(within(article).getByText(text.card.from)).toBeInTheDocument();
      expect(within(article).getByText(text.status.pending)).toBeInTheDocument();
      expect(within(article).getByText(text.card.received(formatDateTime("2026-11-01T10:00:00Z")))).toBeInTheDocument();
      expect(within(article).getByText(text.card.pendingUntil(formatDateTime("2026-11-15T10:00:00Z")))).toBeInTheDocument();
      expect(within(article).getByText("Київ, Печерський")).toBeInTheDocument();
      expect(within(article).getByText("2: легка")).toBeInTheDocument();
      expect(within(article).getByText("Йога і розтяжка (середній рівень)")).toBeInTheDocument();
      expect(listCalls()).toEqual(["GET /invitations?direction=incoming&skip=0&limit=11"]);
    });

    it("announces how many invitations the page holds", async () => {
      routeFetch(fetchMock, routes());
      renderPage();

      const summary = await screen.findByText(text.summary(1));

      expect(summary).toHaveAttribute("role", "status");
    });

    it("shows the status expired as the API returns it, with no actions", async () => {
      routeFetch(fetchMock, routes({
        "GET /invitations": () => jsonResponse(200, [makeInvitation("incoming", { status: "expired" })]),
      }));
      renderPage();

      const article = await screen.findByRole("article", { name: "Марія" });

      expect(within(article).getByText(text.status.expired)).toBeInTheDocument();
      expect(within(article).getByText(text.card.expiredOn(formatDateTime("2026-11-15T10:00:00Z")))).toBeInTheDocument();
      expect(within(article).queryByRole("button")).toBeNull();
    });

    it("says when the other profile is no longer available", async () => {
      routeFetch(fetchMock, routes({
        "GET /invitations": () => jsonResponse(200, [makeInvitation("incoming", { partner: null })]),
      }));
      renderPage();

      expect(await screen.findByRole("article", { name: text.card.partnerUnavailable })).toBeInTheDocument();
    });

    it.each([
      ["incoming", text.emptyIncoming],
      ["outgoing", text.emptyOutgoing],
    ] as const)("explains an empty %s list", async (direction, message) => {
      routeFetch(fetchMock, routes({ "GET /invitations": () => jsonResponse(200, []) }));
      const user = userEvent.setup();
      renderPage();
      if (direction === "outgoing") await user.click(await screen.findByRole("tab", { name: text.outgoing }));

      expect(await screen.findByText(message)).toBeInTheDocument();
    });

    it("links from an empty outgoing list to the recommendations", async () => {
      routeFetch(fetchMock, routes({ "GET /invitations": () => jsonResponse(200, []) }));
      const user = userEvent.setup();
      renderPage();
      await user.click(await screen.findByRole("tab", { name: text.outgoing }));

      expect(await screen.findByRole("link", { name: text.toMatches })).toHaveAttribute("href", "/matches");
    });

    it("shows an alert and retries when the list cannot be loaded", async () => {
      routeFetch(fetchMock, routes({ "GET /invitations": () => jsonResponse(500, { detail: "boom" }) }));
      const user = userEvent.setup();
      renderPage();

      expect(await screen.findByRole("alert")).toHaveTextContent(text.loadFailed);
      expect(screen.queryByText("boom")).toBeNull();

      routeFetch(fetchMock, routes());
      await user.click(screen.getByRole("button", { name: text.retry }));
      expect(await screen.findByRole("article", { name: "Марія" })).toBeInTheDocument();
    });

    it("renders no coordinates or capability data even if the response carried them", async () => {
      const leaky = makePartner({ display_name: "Марія" }) as ReturnType<typeof makePartner> & Record<string, unknown>;
      leaky.latitude = 50.4501;
      leaky.capabilities = [{ category: "vision", level: 1 }];
      routeFetch(fetchMock, routes({
        "GET /invitations": () => jsonResponse(200, [makeInvitation("incoming", { partner: leaky })]),
      }));
      const { container } = renderPage();

      await screen.findByRole("article", { name: "Марія" });

      expect(container.textContent).not.toContain("50.45");
      expect(container.textContent).not.toContain("Зір і орієнтація");
    });
  });

  it("ends the session and explains it on the login page when the list answers 401", async () => {
    routeFetch(fetchMock, routes({ "GET /invitations": () => jsonResponse(401, { detail: "expired" }) }));

    const { store } = renderPage();

    expect(await screen.findByRole("heading", { level: 1, name: uk.pages.login.title })).toBeInTheDocument();
    expect(screen.getByText(uk.auth.sessionEnded)).toBeInTheDocument();
    expect(store.getState().auth.token).toBeNull();
  });

  describe("tabs and filter", () => {
    it("has tab semantics with the incoming tab selected first", async () => {
      routeFetch(fetchMock, routes());
      renderPage();
      await screen.findByRole("article", { name: "Марія" });

      const list = screen.getByRole("tablist", { name: text.directionLabel });
      const incoming = within(list).getByRole("tab", { name: text.incoming });
      const outgoing = within(list).getByRole("tab", { name: text.outgoing });

      expect(incoming).toHaveAttribute("aria-selected", "true");
      expect(outgoing).toHaveAttribute("aria-selected", "false");
      expect(incoming).toHaveAttribute("tabindex", "0");
      expect(outgoing).toHaveAttribute("tabindex", "-1");
      const panel = screen.getByRole("tabpanel", { name: text.incoming });
      expect(incoming).toHaveAttribute("aria-controls", panel.id);
    });

    it("loads the outgoing invitations and shows the recipient when that tab is chosen", async () => {
      routeFetch(fetchMock, routes({
        "GET /invitations": (request) =>
          jsonResponse(200, [
            new URL(request.url).searchParams.get("direction") === "outgoing"
              ? makeInvitation("outgoing", { partner: makePartner({ display_name: "Петро" }) })
              : makeInvitation("incoming"),
          ]),
      }));
      const user = userEvent.setup();
      renderPage();
      await screen.findByRole("article", { name: "Марія" });

      await user.click(screen.getByRole("tab", { name: text.outgoing }));

      const article = await screen.findByRole("article", { name: "Петро" });
      expect(within(article).getByText(text.card.to)).toBeInTheDocument();
      expect(within(article).getByText(text.card.sent(formatDateTime("2026-11-01T10:00:00Z")))).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: text.outgoing })).toHaveAttribute("aria-selected", "true");
      expect(listCalls()[1]).toBe("GET /invitations?direction=outgoing&skip=0&limit=11");
    });

    it("moves between the tabs with the arrow keys, Home and End", async () => {
      routeFetch(fetchMock, routes());
      const user = userEvent.setup();
      renderPage();
      const incoming = await screen.findByRole("tab", { name: text.incoming });
      incoming.focus();

      await user.keyboard("{ArrowRight}");
      const outgoing = screen.getByRole("tab", { name: text.outgoing });
      expect(outgoing).toHaveFocus();
      expect(outgoing).toHaveAttribute("aria-selected", "true");

      await user.keyboard("{ArrowRight}");
      expect(screen.getByRole("tab", { name: text.incoming })).toHaveFocus();

      await user.keyboard("{ArrowLeft}");
      expect(screen.getByRole("tab", { name: text.outgoing })).toHaveFocus();

      await user.keyboard("{Home}");
      expect(screen.getByRole("tab", { name: text.incoming })).toHaveFocus();

      await user.keyboard("{End}");
      expect(screen.getByRole("tab", { name: text.outgoing })).toHaveFocus();
    });

    it("sends the chosen status and keeps it when the tab changes", async () => {
      routeFetch(fetchMock, routes());
      const user = userEvent.setup();
      renderPage();
      await screen.findByRole("article", { name: "Марія" });

      await user.selectOptions(screen.getByLabelText(text.statusFilter), "pending");
      await waitFor(() => expect(listCalls()).toHaveLength(2));
      await user.click(screen.getByRole("tab", { name: text.outgoing }));
      await waitFor(() => expect(listCalls()).toHaveLength(3));

      expect(listCalls()).toEqual([
        "GET /invitations?direction=incoming&skip=0&limit=11",
        "GET /invitations?direction=incoming&status=pending&skip=0&limit=11",
        "GET /invitations?direction=outgoing&status=pending&skip=0&limit=11",
      ]);
      expect(screen.getByLabelText(text.statusFilter)).toHaveValue("pending");
    });

    it("offers every status and explains an empty filtered list", async () => {
      routeFetch(fetchMock, routes({ "GET /invitations": () => jsonResponse(200, []) }));
      const user = userEvent.setup();
      renderPage();
      const filter = await screen.findByLabelText(text.statusFilter);

      expect(within(filter).getAllByRole("option").map((option) => option.textContent)).toEqual([
        text.statusAll,
        text.status.pending,
        text.status.accepted,
        text.status.declined,
        text.status.cancelled,
        text.status.expired,
      ]);
      await user.selectOptions(filter, "declined");

      expect(await screen.findByText(text.emptyFiltered)).toBeInTheDocument();
    });
  });

  describe("pagination", () => {
    const many = (count: number, offset = 0) =>
      Array.from({ length: count }, (_, index) =>
        makeInvitation("incoming", {
          id: `inv-${offset + index}`,
          partner: makePartner({ display_name: `Особа ${offset + index + 1}` }),
        }),
      );

    it("shows ten, detects the next page by the extra invitation and moves focus on paging", async () => {
      routeFetch(fetchMock, routes({
        "GET /invitations": (request) => {
          const skip = Number(new URL(request.url).searchParams.get("skip"));
          return jsonResponse(200, skip === 0 ? many(11) : many(3, 10));
        },
      }));
      const user = userEvent.setup();
      renderPage();

      await screen.findByRole("article", { name: "Особа 1" });
      expect(screen.getAllByRole("article")).toHaveLength(10);
      expect(screen.queryByRole("article", { name: "Особа 11" })).toBeNull();
      expect(screen.getByText(uk.pagination.page(1))).toBeInTheDocument();
      expect(screen.getByRole("button", { name: uk.pagination.previous })).toHaveAttribute("aria-disabled", "true");

      await user.click(screen.getByRole("button", { name: uk.pagination.next }));

      await screen.findByRole("article", { name: "Особа 11" });
      expect(screen.getAllByRole("article")).toHaveLength(3);
      expect(screen.getByRole("heading", { name: text.listHeading })).toHaveFocus();
      expect(screen.getByRole("button", { name: uk.pagination.next })).toHaveAttribute("aria-disabled", "true");
      expect(listCalls()[1]).toBe("GET /invitations?direction=incoming&skip=10&limit=11");

      await user.click(screen.getByRole("button", { name: uk.pagination.previous }));
      expect(await screen.findByRole("article", { name: "Особа 1" })).toBeInTheDocument();
    });

    it("has no pagination while everything fits on one page", async () => {
      routeFetch(fetchMock, routes());
      renderPage();
      await screen.findByRole("article", { name: "Марія" });

      expect(screen.queryByRole("navigation", { name: uk.pagination.label })).toBeNull();
    });
  });

  describe("contact", () => {
    it("shows the contact of an accepted invitation with the reason it is shared", async () => {
      routeFetch(fetchMock, routes({
        "GET /invitations": () =>
          jsonResponse(200, [
            makeInvitation("incoming", {
              status: "accepted",
              responded_at: "2026-11-02T09:00:00Z",
              partner: makePartner({ contact: "@maria_runs" }),
            }),
          ]),
      }));
      renderPage();

      const article = await screen.findByRole("article", { name: "Марія" });

      expect(within(article).getByText("@maria_runs")).toBeInTheDocument();
      expect(within(article).getByText(text.card.contactNote)).toBeInTheDocument();
      expect(within(article).getByText(text.status.accepted)).toBeInTheDocument();
      expect(within(article).getByText(text.card.answeredOn(formatDateTime("2026-11-02T09:00:00Z")))).toBeInTheDocument();
    });

    it("says so when an accepted partner left no contact", async () => {
      routeFetch(fetchMock, routes({
        "GET /invitations": () =>
          jsonResponse(200, [makeInvitation("outgoing", { status: "accepted", partner: makePartner({ contact: null }) })]),
      }));
      const user = userEvent.setup();
      renderPage();
      await user.click(await screen.findByRole("tab", { name: text.outgoing }));

      expect(await screen.findByText(text.card.contactNone)).toBeInTheDocument();
      expect(screen.queryByText(text.card.contactNote)).toBeNull();
    });

    it.each(["pending", "declined", "cancelled", "expired"] as const)(
      "never shows a contact on a %s invitation, even if the response carried one",
      async (status) => {
        routeFetch(fetchMock, routes({
          "GET /invitations": () =>
            jsonResponse(200, [makeInvitation("incoming", { status, partner: makePartner({ contact: "secret-contact" }) })]),
        }));
        const { container } = renderPage();

        await screen.findByRole("article", { name: "Марія" });

        expect(container.textContent).not.toContain("secret-contact");
        expect(screen.queryByText(text.card.contactHeading)).toBeNull();
      },
    );
  });

  describe("answering", () => {
    const accepted = makeInvitation("incoming", {
      status: "accepted",
      responded_at: "2026-11-02T09:00:00Z",
      partner: makePartner({ contact: "@maria_runs" }),
    });

    it("accepts after a confirmation, refreshes the list and then shows the contact", async () => {
      routeFetch(fetchMock, routes({
        "GET /invitations": sequence([makeInvitation("incoming")], [accepted]),
        [`POST /invitations/${ID}/accept`]: () => jsonResponse(200, accepted),
      }));
      const user = userEvent.setup();
      renderPage();

      await openAction(user, text.actions.accept.triggerFor("Марія"));
      expect(screen.getByRole("heading", { name: text.actions.accept.title })).toHaveFocus();
      expect(posts()).toEqual([]);
      await user.click(screen.getByRole("button", { name: text.actions.accept.confirm }));

      expect(await screen.findByText("@maria_runs")).toBeInTheDocument();
      const feedback = screen.getByText(text.actions.accept.done);
      expect(feedback).toHaveAttribute("role", "status");
      expect(feedback).toHaveFocus();
      expect(posts()).toEqual([`POST /invitations/${ID}/accept`]);
      expect(listCalls()).toHaveLength(2);
      expect(screen.queryByRole("button", { name: text.actions.accept.trigger })).toBeNull();
    });

    it("declines after a confirmation and refreshes the list", async () => {
      const declined = makeInvitation("incoming", { status: "declined", responded_at: "2026-11-02T09:00:00Z" });
      routeFetch(fetchMock, routes({
        "GET /invitations": sequence([makeInvitation("incoming")], [declined]),
        [`POST /invitations/${ID}/decline`]: () => jsonResponse(200, declined),
      }));
      const user = userEvent.setup();
      renderPage();

      await openAction(user, text.actions.decline.triggerFor("Марія"));
      await user.click(screen.getByRole("button", { name: text.actions.decline.confirm }));

      expect(await inArticle(text.status.declined)).toBeInTheDocument();
      expect(screen.getByText(text.actions.decline.done)).toHaveFocus();
      expect(posts()).toEqual([`POST /invitations/${ID}/decline`]);
      expect(screen.queryByText(text.card.contactHeading)).toBeNull();
    });

    it("cancels an outgoing invitation after a confirmation", async () => {
      const cancelled = makeInvitation("outgoing", { status: "cancelled", responded_at: "2026-11-02T09:00:00Z" });
      routeFetch(fetchMock, routes({
        "GET /invitations": sequence([], [makeInvitation("outgoing")], [cancelled]),
        [`POST /invitations/${ID}/cancel`]: () => jsonResponse(200, cancelled),
      }));
      const user = userEvent.setup();
      renderPage();
      await user.click(await screen.findByRole("tab", { name: text.outgoing }));

      await openAction(user, text.actions.cancel.triggerFor("Марія"));
      expect(screen.queryByRole("button", { name: text.actions.accept.trigger })).toBeNull();
      await user.click(screen.getByRole("button", { name: text.actions.cancel.confirm }));

      expect(await inArticle(text.status.cancelled)).toBeInTheDocument();
      expect(screen.getByText(text.actions.cancel.done)).toHaveFocus();
    });

    it("sends nothing when the confirmation is cancelled", async () => {
      routeFetch(fetchMock, routes());
      const user = userEvent.setup();
      renderPage();

      await openAction(user, text.actions.decline.triggerFor("Марія"));
      await user.click(screen.getByRole("button", { name: uk.profile.manage.cancel }));

      expect(posts()).toEqual([]);
      expect(screen.getByRole("button", { name: text.actions.decline.triggerFor("Марія") })).toHaveFocus();
    });

    it("offers accept and decline only on incoming pending invitations", async () => {
      routeFetch(fetchMock, routes());
      renderPage();
      const article = await screen.findByRole("article", { name: "Марія" });

      expect(within(article).getAllByRole("button").map((button) => button.textContent)).toEqual([
        text.actions.accept.trigger,
        text.actions.decline.trigger,
      ]);
    });

    it.each([
      [409, text.errors.conflict],
      [404, text.errors.notFound],
    ])("reports %i with a fixed message above the list and refreshes the list", async (status, message) => {
      const answered = makeInvitation("incoming", { status: "declined", responded_at: "2026-11-02T09:00:00Z" });
      routeFetch(fetchMock, routes({
        "GET /invitations": sequence([makeInvitation("incoming")], [answered]),
        [`POST /invitations/${ID}/accept`]: () => jsonResponse(status, { detail: "server wording" }),
      }));
      const user = userEvent.setup();
      renderPage();

      await openAction(user, text.actions.accept.triggerFor("Марія"));
      await user.click(screen.getByRole("button", { name: text.actions.accept.confirm }));

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(message);
      expect(alert).toHaveFocus();
      expect(screen.queryByText("server wording")).toBeNull();
      expect(await inArticle(text.status.declined)).toBeInTheDocument();
      expect(listCalls()).toHaveLength(2);
    });

    it("reports 403 inside the confirmation and leaves the invitation as it was", async () => {
      routeFetch(fetchMock, routes({
        [`POST /invitations/${ID}/accept`]: () => jsonResponse(403, { detail: "server wording" }),
      }));
      const user = userEvent.setup();
      renderPage();

      await openAction(user, text.actions.accept.triggerFor("Марія"));
      await user.click(screen.getByRole("button", { name: text.actions.accept.confirm }));

      const group = screen.getByRole("group", { name: text.actions.accept.title });
      expect(await within(group).findByRole("alert")).toHaveTextContent(text.errors.forbidden);
      expect(within(screen.getByRole("article")).getByText(text.status.pending)).toBeInTheDocument();
    });

    it("answers a coded contact_required with a focused alert and a link to the profile", async () => {
      routeFetch(fetchMock, routes({
        [`POST /invitations/${ID}/accept`]: () => jsonResponse(409, CONTACT_REQUIRED),
      }));
      const user = userEvent.setup();
      renderPage();

      await openAction(user, text.actions.accept.triggerFor("Марія"));
      await user.click(screen.getByRole("button", { name: text.actions.accept.confirm }));

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(uk.contactRequired.message);
      expect(alert).toHaveFocus();
      expect(within(alert).getByRole("link", { name: uk.contactRequired.link })).toHaveAttribute(
        "href",
        "/profile",
      );
      expect(screen.queryByText("server wording")).toBeNull();
      expect(screen.queryByText(text.errors.conflict)).toBeNull();
      // The invitation is still pending, the confirmation is gone and declining stays possible
      expect(within(screen.getByRole("article")).getByText(text.status.pending)).toBeInTheDocument();
      expect(screen.queryByRole("group", { name: text.actions.accept.title })).toBeNull();
      expect(screen.getByRole("button", { name: text.actions.decline.triggerFor("Марія") })).toBeInTheDocument();
      expect(posts()).toEqual([`POST /invitations/${ID}/accept`]);
    });

    it("replaces accept with a notice while the address is not confirmed and keeps decline", async () => {
      routeFetch(fetchMock, routes({
        "GET /auth/me": () => jsonResponse(200, makeAccount({ email_verified: false })),
      }));
      renderPage();

      await screen.findByRole("article");

      expect(await screen.findByText(uk.verification.acceptNotice)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: text.actions.accept.triggerFor("Марія") })).toBeNull();
      expect(screen.getByRole("button", { name: text.actions.decline.triggerFor("Марія") })).toBeInTheDocument();
    });

    it("turns accept into the notice when the server answers email_not_verified", async () => {
      routeFetch(fetchMock, routes({
        [`POST /invitations/${ID}/accept`]: () =>
          jsonResponse(403, { detail: "server wording", code: "email_not_verified" }),
      }));
      const user = userEvent.setup();
      renderPage();

      await openAction(user, text.actions.accept.triggerFor("Марія"));
      await user.click(screen.getByRole("button", { name: text.actions.accept.confirm }));

      expect(await screen.findByText(uk.verification.acceptNotice)).toBeInTheDocument();
      expect(screen.queryByText("server wording")).toBeNull();
      // A plain 403 (answering one's own invitation) keeps its own message, see above
      expect(within(screen.getByRole("article")).getByText(text.status.pending)).toBeInTheDocument();
    });

    it("still declines after the contact notice was shown", async () => {
      const declined = makeInvitation("incoming", { status: "declined" });
      routeFetch(fetchMock, routes({
        "GET /invitations": sequence([makeInvitation("incoming")], [makeInvitation("incoming")], [declined]),
        [`POST /invitations/${ID}/accept`]: () => jsonResponse(409, CONTACT_REQUIRED),
        [`POST /invitations/${ID}/decline`]: () => jsonResponse(200, declined),
      }));
      const user = userEvent.setup();
      renderPage();

      await openAction(user, text.actions.accept.triggerFor("Марія"));
      await user.click(screen.getByRole("button", { name: text.actions.accept.confirm }));
      await screen.findByRole("alert");
      await user.click(screen.getByRole("button", { name: text.actions.decline.triggerFor("Марія") }));
      await user.click(screen.getByRole("button", { name: text.actions.decline.confirm }));

      expect(await screen.findByText(text.actions.decline.done)).toBeInTheDocument();
    });

    it("reports a server error inside the confirmation so that the user can try again", async () => {
      routeFetch(fetchMock, routes({
        [`POST /invitations/${ID}/decline`]: () => jsonResponse(500, {}),
      }));
      const user = userEvent.setup();
      renderPage();

      await openAction(user, text.actions.decline.triggerFor("Марія"));
      await user.click(screen.getByRole("button", { name: text.actions.decline.confirm }));

      expect(await screen.findByRole("alert")).toHaveTextContent(text.errors.generic);
      expect(screen.getByRole("button", { name: text.actions.decline.confirm })).toBeInTheDocument();
    });
  });

  describe("accessibility", () => {
    const accepted = makeInvitation("incoming", {
      status: "accepted",
      partner: makePartner({ contact: "@maria_runs" }),
    });
    const states: [string, Routes][] = [
      ["pending incoming", routes()],
      ["accepted with contact", routes({ "GET /invitations": () => jsonResponse(200, [accepted]) })],
      ["expired", routes({ "GET /invitations": () => jsonResponse(200, [makeInvitation("incoming", { status: "expired" })]) })],
      ["empty", routes({ "GET /invitations": () => jsonResponse(200, []) })],
      ["load error", routes({ "GET /invitations": () => jsonResponse(500, {}) })],
    ];

    it.each(states)("has no axe violations: %s", async (_name, stateRoutes) => {
      routeFetch(fetchMock, stateRoutes);
      const { container } = renderPage();
      await waitFor(() => expect(listCalls().length).toBeGreaterThan(0));
      await waitFor(() => expect(screen.queryByText(text.loading)).toBeNull());

      expect(await axe(container)).toHaveNoViolations();
    });

    it("has no axe violations on the outgoing tab or while an action is confirmed", async () => {
      routeFetch(fetchMock, routes());
      const user = userEvent.setup();
      const { container } = renderPage();
      await openAction(user, text.actions.accept.triggerFor("Марія"));

      expect(await axe(container)).toHaveNoViolations();

      await user.click(screen.getByRole("tab", { name: text.outgoing }));
      await screen.findByRole("article");
      expect(await axe(container)).toHaveNoViolations();
    });

    it("has no axe violations with the contact notice shown", async () => {
      routeFetch(fetchMock, routes({
        [`POST /invitations/${ID}/accept`]: () => jsonResponse(409, CONTACT_REQUIRED),
      }));
      const user = userEvent.setup();
      const { container } = renderPage();
      await openAction(user, text.actions.accept.triggerFor("Марія"));
      await user.click(screen.getByRole("button", { name: text.actions.accept.confirm }));
      await screen.findByRole("alert");

      expect(await axe(container)).toHaveNoViolations();
    });

    it("has no axe violations with a feedback message and a long list", async () => {
      const declined = makeInvitation("incoming", { status: "declined" });
      routeFetch(fetchMock, routes({
        "GET /invitations": sequence(
          Array.from({ length: 11 }, (_, index) =>
            makeInvitation("incoming", { id: index === 0 ? ID : `inv-${index}`, partner: makePartner({ display_name: `Особа ${index + 1}` }) }),
          ),
          [declined],
        ),
        [`POST /invitations/${ID}/decline`]: () => jsonResponse(200, declined),
      }));
      const user = userEvent.setup();
      const { container } = renderPage();
      await openAction(user, text.actions.decline.triggerFor("Особа 1"));
      await user.click(screen.getByRole("button", { name: text.actions.decline.confirm }));
      await screen.findByText(text.actions.decline.done);

      expect(await axe(container)).toHaveNoViolations();
    });
  });
});
