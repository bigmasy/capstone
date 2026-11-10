import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { Route, Routes } from "react-router";
import { uk } from "../../i18n/uk";
import { bodiesSentTo, calls, jsonResponse, noContent, routeFetch } from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";
import VerifyEmailPage from "./VerifyEmailPage";

const text = uk.verification.page;
const TOKEN = "Abc_def-0123456789ABCDEFGHIJKLMNOPQRSTUVWXY";

describe("VerifyEmailPage", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState(null, "", "/verify-email#token=" + TOKEN);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
  });

  const open = (preloadedState = {}) =>
    renderWithProviders(
      <Routes>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
      </Routes>,
      { route: `/verify-email#token=${TOKEN}`, preloadedState },
    );

  it("sends the token from the fragment once, in the body, and confirms", async () => {
    routeFetch(fetchMock, { "POST /auth/verify-email": () => noContent() });
    open();

    expect(await screen.findByText(text.success)).toBeInTheDocument();

    expect(await bodiesSentTo(fetchMock, "POST /auth/verify-email")).toEqual([{ token: TOKEN }]);
    expect(calls(fetchMock)).toEqual(["POST /auth/verify-email"]);
  });

  it("removes the token from the address bar at once", async () => {
    routeFetch(fetchMock, { "POST /auth/verify-email": () => noContent() });
    open();

    await screen.findByText(text.success);

    expect(window.location.hash).toBe("");
    expect(window.location.href).not.toContain(TOKEN);
  });

  it("offers the partners page to a signed-in user and the login page to a visitor", async () => {
    routeFetch(fetchMock, { "POST /auth/verify-email": () => noContent() });
    const { unmount } = open(loggedIn);
    expect(await screen.findByRole("link", { name: text.toPartners })).toHaveAttribute(
      "href",
      "/matches",
    );
    unmount();

    window.history.replaceState(null, "", "/verify-email#token=" + TOKEN);
    open();
    expect(await screen.findByRole("link", { name: text.toLogin })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("explains a link that is invalid or has expired, without the server's wording", async () => {
    routeFetch(fetchMock, {
      "POST /auth/verify-email": () => jsonResponse(400, { detail: "The confirmation link is invalid" }),
    });
    open();

    expect(await screen.findByText(text.failure)).toBeInTheDocument();
    expect(screen.getByText(text.failureHelp)).toBeInTheDocument();
    expect(screen.queryByText(/confirmation link/)).toBeNull();
  });

  it("says so when the link carries no token and sends nothing", async () => {
    window.history.replaceState(null, "", "/verify-email");
    renderWithProviders(
      <Routes>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
      </Routes>,
      { route: "/verify-email" },
    );

    expect(await screen.findByText(text.missingToken)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("announces the progress and has no axe violations", async () => {
    routeFetch(fetchMock, { "POST /auth/verify-email": () => noContent() });
    const { container } = open();

    expect(screen.getByRole("heading", { level: 1, name: text.title })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
    await screen.findByText(text.success);

    expect(await axe(container)).toHaveNoViolations();
  });
});
