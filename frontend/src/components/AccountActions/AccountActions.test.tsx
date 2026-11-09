import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import { calls, jsonResponse, makeProfile, noContent, routeFetch, taxonomy, type Routes } from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";
import App from "../App/App";

const text = uk.profile.manage;

describe("AccountActions on the profile page", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const routes = (overrides: Routes = {}): Routes => ({
    "GET /auth/me": () => jsonResponse(200, { id: "x", email: "a@example.com", created_at: "" }),
    "GET /taxonomy": () => jsonResponse(200, taxonomy),
    "GET /profiles/me": () => jsonResponse(200, makeProfile()),
    ...overrides,
  });

  const renderPage = async () => {
    const result = renderWithProviders(<App />, { route: "/profile", preloadedState: loggedIn });
    await screen.findByDisplayValue("Олена");
    return result;
  };

  describe("deleting the profile and the account", () => {
    it("asks for confirmation first and sends nothing when the user cancels", async () => {
      routeFetch(fetchMock, routes());
      const user = userEvent.setup();
      await renderPage();
      const before = calls(fetchMock).length;

      const trigger = screen.getByRole("button", { name: text.deleteAll.trigger });
      await user.click(trigger);

      const heading = screen.getByRole("heading", { level: 3, name: text.deleteAll.title });
      expect(heading).toHaveFocus();
      expect(screen.getByText(text.deleteAll.description)).toBeInTheDocument();
      expect(calls(fetchMock)).toHaveLength(before);

      await user.click(screen.getByRole("button", { name: text.cancel }));

      expect(screen.queryByRole("heading", { name: text.deleteAll.title })).toBeNull();
      expect(screen.getByRole("button", { name: text.deleteAll.trigger })).toHaveFocus();
      expect(calls(fetchMock)).toHaveLength(before);
    });

    it("is the only destructive action and the confirmation names what is lost", async () => {
      routeFetch(fetchMock, routes());
      const user = userEvent.setup();
      await renderPage();

      expect(screen.getAllByRole("button", { name: /^Видалити (профіль|обліковий)/ })).toHaveLength(1);
      await user.click(screen.getByRole("button", { name: text.deleteAll.trigger }));

      const panel = screen.getByRole("group", { name: text.deleteAll.title });
      expect(panel).toHaveTextContent(/безповоротно видалено все/);
      for (const word of ["профіль", "контакт", "запрошення"]) {
        expect(panel).toHaveTextContent(word);
      }
      // The softer way out is named, and it exists on the page
      expect(panel).toHaveTextContent(uk.profile.visibility.isVisible);
      expect(screen.getByRole("switch", { name: uk.profile.visibility.isVisible })).toBeInTheDocument();
    });

    it("has no axe violations while the confirmation is open", async () => {
      routeFetch(fetchMock, routes());
      const user = userEvent.setup();
      const { container } = await renderPage();

      await user.click(screen.getByRole("button", { name: text.deleteAll.trigger }));

      expect(await axe(container)).toHaveNoViolations();
    });

    it("deletes everything, ends the session and leaves for the landing page", async () => {
      routeFetch(fetchMock, routes({ "DELETE /auth/me": () => noContent() }));
      const user = userEvent.setup();
      const { store } = await renderPage();

      await user.click(screen.getByRole("button", { name: text.deleteAll.trigger }));
      await user.click(screen.getByRole("button", { name: text.deleteAll.confirm }));

      expect(
        await screen.findByRole("heading", { level: 1, name: uk.pages.home.title }),
      ).toBeInTheDocument();
      expect(screen.getAllByRole("link", { name: uk.nav.login }).length).toBeGreaterThan(0);
      expect(screen.queryByRole("heading", { level: 1, name: uk.pages.login.title })).toBeNull();
      expect(store.getState().auth.token).toBeNull();
      expect(window.sessionStorage.getItem("auth.token")).toBeNull();
      expect(calls(fetchMock)).toContain("DELETE /auth/me");
      expect((await screen.findByText(text.deleteAll.done)).closest('[role="status"]')).not.toBeNull();
      // Nothing of the deleted account stays in the cache
      expect(JSON.stringify(store.getState().api)).not.toContain("Олена");
      expect(screen.queryByText(uk.auth.sessionEnded)).toBeNull();
    });

    it("keeps the session and shows an alert when the server refuses", async () => {
      routeFetch(fetchMock, routes({ "DELETE /auth/me": () => jsonResponse(500) }));
      const user = userEvent.setup();
      const { store } = await renderPage();

      await user.click(screen.getByRole("button", { name: text.deleteAll.trigger }));
      await user.click(screen.getByRole("button", { name: text.deleteAll.confirm }));

      expect(await screen.findByRole("alert")).toHaveTextContent(text.deleteAll.failed);
      expect(store.getState().auth.token).toBe("test-token");
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(uk.pages.profile.title);
    });

    it("uses aria-disabled while pending and sends the request once", async () => {
      let answer: (response: Response) => void = () => undefined;
      routeFetch(fetchMock, routes());
      const user = userEvent.setup();
      await renderPage();
      fetchMock.mockImplementation((input) => {
        if ((input as Request).method === "DELETE") {
          return new Promise<Response>((resolve) => (answer = resolve));
        }
        return Promise.resolve(jsonResponse(200, makeProfile()));
      });

      await user.click(screen.getByRole("button", { name: text.deleteAll.trigger }));
      const confirm = screen.getByRole("button", { name: text.deleteAll.confirm });
      await user.click(confirm);

      await waitFor(() => expect(confirm).toHaveAttribute("aria-disabled", "true"));
      await user.click(confirm);
      await user.click(screen.getByRole("button", { name: text.cancel }));
      expect(calls(fetchMock).filter((call) => call === "DELETE /auth/me")).toHaveLength(1);
      expect(screen.getByRole("heading", { level: 3, name: text.deleteAll.title })).toBeInTheDocument();

      answer(noContent());
      expect(
        await screen.findByRole("heading", { level: 1, name: uk.pages.home.title }),
      ).toBeInTheDocument();
    });
  });
});
