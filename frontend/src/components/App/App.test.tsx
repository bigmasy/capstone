import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import toast from "react-hot-toast";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { uk } from "../../i18n/uk";
import { loggedIn, renderWithProviders } from "../../test/utils";
import App from "./App";

function jsonResponse(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("App", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const urls = () => fetchMock.mock.calls.map(([request]) => (request as Request).url);

  describe("status messages", () => {
    it("renders a success toast inside an element with role=status", async () => {
      renderWithProviders(<App />);

      act(() => {
        toast.success(uk.auth.loggedIn);
      });

      const message = await screen.findByText(uk.auth.loggedIn);
      expect(message.closest('[role="status"]')).not.toBeNull();
    });
  });

  describe("session", () => {
    it("checks a restored token once with GET /auth/me", async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, {}));

      const { store } = renderWithProviders(<App />, { route: "/profile", preloadedState: loggedIn });

      // The profile page asks for its own data too; /auth/me must be requested exactly once
      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
      expect(urls().filter((url) => url.endsWith("/auth/me"))).toHaveLength(1);
      expect(store.getState().auth.token).toBe("test-token");
    });

    it("does not call the server when there is no token", () => {
      renderWithProviders(<App />);

      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("clears the session on 401 and explains it on the login page", async () => {
      fetchMock.mockResolvedValue(jsonResponse(401, { detail: "expired" }));

      const { store } = renderWithProviders(<App />, { route: "/profile", preloadedState: loggedIn });

      const heading = await screen.findByRole("heading", { level: 1, name: uk.pages.login.title });
      expect(heading).toBeInTheDocument();
      expect(store.getState().auth.token).toBeNull();
      expect(window.sessionStorage.getItem("auth.token")).toBeNull();
      const message = screen.getByText(uk.auth.sessionEnded);
      expect(message.closest('[role="status"]')).not.toBeNull();
      expect(store.getState().auth.endedBy).toBeUndefined();
    });

    it("redirects from a public page too when the server ends the session", async () => {
      fetchMock.mockResolvedValue(jsonResponse(401));

      renderWithProviders(<App />, { route: "/", preloadedState: loggedIn });

      expect(
        await screen.findByRole("heading", { level: 1, name: uk.pages.login.title }),
      ).toBeInTheDocument();
      expect(screen.getByText(uk.auth.sessionEnded)).toBeInTheDocument();
    });

    it("keeps the user logged in when the server is unreachable", async () => {
      fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

      const { store } = renderWithProviders(<App />, { route: "/profile", preloadedState: loggedIn });

      await waitFor(() => expect(fetchMock).toHaveBeenCalled());
      expect(store.getState().auth.token).toBe("test-token");
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(uk.pages.profile.title);
    });

    it("lands on the landing page, not on the login page, after signing out of a private page", async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, {}));
      const user = userEvent.setup();
      const { store } = renderWithProviders(<App />, { route: "/profile", preloadedState: loggedIn });

      const nav = await screen.findByRole("navigation", { name: uk.a11y.mainNavigation });
      await user.click(within(nav).getByRole("button", { name: uk.nav.logout }));

      expect(
        await screen.findByRole("heading", { level: 1, name: uk.pages.home.title }),
      ).toBeInTheDocument();
      expect(store.getState().auth.token).toBeNull();
      expect(screen.queryByText(uk.auth.sessionEnded)).not.toBeInTheDocument();
    });

    it("shows the expiry message only when the router state asks for it", () => {
      renderWithProviders(<App />, { route: "/login" });
      expect(screen.queryByText(uk.auth.sessionEnded)).not.toBeInTheDocument();
    });
  });
});
