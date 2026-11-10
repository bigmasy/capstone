import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import { calls, jsonResponse, makeAccount, noContent, routeFetch } from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";
import VerificationBanner from "./VerificationBanner";

const text = uk.verification;

describe("VerificationBanner", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const unconfirmed = () =>
    routeFetch(fetchMock, {
      "GET /auth/me": () => jsonResponse(200, makeAccount({ email_verified: false })),
      "POST /auth/resend-verification": () => noContent(),
    });

  it("asks an unconfirmed account to confirm the address, in a labelled region", async () => {
    unconfirmed();
    renderWithProviders(<VerificationBanner />, { preloadedState: loggedIn });

    const region = await screen.findByRole("region", { name: text.bannerLabel });

    expect(region).toHaveTextContent(text.bannerTitle);
    expect(region).toHaveTextContent(text.bannerText);
    expect(screen.getByRole("button", { name: text.resend })).toBeInTheDocument();
  });

  it("shows nothing for a confirmed account", async () => {
    routeFetch(fetchMock, { "GET /auth/me": () => jsonResponse(200, makeAccount()) });
    renderWithProviders(<VerificationBanner />, { preloadedState: loggedIn });

    await waitFor(() => expect(calls(fetchMock)).toContain("GET /auth/me"));

    expect(screen.queryByRole("region", { name: text.bannerLabel })).toBeNull();
  });

  it("shows nothing and asks nothing when nobody is signed in", () => {
    renderWithProviders(<VerificationBanner />);

    expect(screen.queryByRole("region")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("stays out of the way on the confirmation page itself", async () => {
    unconfirmed();
    renderWithProviders(<VerificationBanner />, {
      preloadedState: loggedIn,
      route: "/verify-email",
    });

    await waitFor(() => expect(calls(fetchMock)).toContain("GET /auth/me"));

    expect(screen.queryByRole("region", { name: text.bannerLabel })).toBeNull();
  });

  it("asks for a new message and says so in a status line", async () => {
    const user = userEvent.setup();
    unconfirmed();
    renderWithProviders(<VerificationBanner />, { preloadedState: loggedIn });

    await user.click(await screen.findByRole("button", { name: text.resend }));

    expect(await screen.findByText(text.resent)).toBeInTheDocument();
    expect(calls(fetchMock)).toContain("POST /auth/resend-verification");
    expect(screen.getByRole("status")).toHaveTextContent(text.resent);
  });

  it("reports a failed request with a fixed message", async () => {
    const user = userEvent.setup();
    routeFetch(fetchMock, {
      "GET /auth/me": () => jsonResponse(200, makeAccount({ email_verified: false })),
      "POST /auth/resend-verification": () => jsonResponse(500, { detail: "boom" }),
    });
    renderWithProviders(<VerificationBanner />, { preloadedState: loggedIn });

    await user.click(await screen.findByRole("button", { name: text.resend }));

    expect(await screen.findByText(text.resendFailed)).toBeInTheDocument();
    expect(screen.queryByText("boom")).toBeNull();
  });

  it("has no axe violations", async () => {
    unconfirmed();
    const { container } = renderWithProviders(<VerificationBanner />, {
      preloadedState: loggedIn,
    });
    await screen.findByRole("region", { name: text.bannerLabel });

    expect(await axe(container)).toHaveNoViolations();
  });
});
