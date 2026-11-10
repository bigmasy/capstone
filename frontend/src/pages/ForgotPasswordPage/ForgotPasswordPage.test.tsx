import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import {
  bodiesSentTo,
  jsonResponse,
  noContent,
  routeFetch,
} from "../../test/api";
import { renderWithProviders } from "../../test/utils";
import ForgotPasswordPage from "./ForgotPasswordPage";

const text = uk.passwordReset.forgot;

describe("ForgotPasswordPage", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const open = () =>
    renderWithProviders(
      <Routes>
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      </Routes>,
      { route: "/forgot-password" },
    );

  const ask = async (address = "a@example.com") => {
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(new RegExp(uk.auth.email)), address);
    await user.click(screen.getByRole("button", { name: text.submit }));
    return user;
  };

  it("sends the trimmed address and says the same thing for any address", async () => {
    routeFetch(fetchMock, { "POST /auth/forgot-password": () => noContent() });
    open();

    await ask("  a@example.com ");

    expect(await screen.findByText(text.sent)).toBeInTheDocument();
    expect(await bodiesSentTo(fetchMock, "POST /auth/forgot-password")).toEqual(
      [{ email: "a@example.com" }],
    );
    expect(screen.queryByLabelText(new RegExp(uk.auth.email))).toBeNull();
  });

  it("lets the person try another address", async () => {
    routeFetch(fetchMock, { "POST /auth/forgot-password": () => noContent() });
    open();
    const user = await ask();
    await screen.findByText(text.sent);

    await user.click(screen.getByRole("button", { name: text.another }));

    expect(
      screen.getByLabelText(new RegExp(uk.auth.email)),
    ).toBeInTheDocument();
  });

  it("validates the address before asking the server", async () => {
    open();

    await ask("not-an-address");

    expect(
      await screen.findByText(uk.form.validation.email),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("explains a flood limit and a broken connection without the server's words", async () => {
    routeFetch(fetchMock, {
      "POST /auth/forgot-password": () =>
        jsonResponse(429, { detail: "slow down" }),
    });
    open();
    await ask();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      uk.auth.tooManyAttempts,
    );
    expect(screen.queryByText(/slow down/)).toBeNull();
  });

  it("reports a server error as a connection problem", async () => {
    routeFetch(fetchMock, {
      "POST /auth/forgot-password": () => jsonResponse(500, { detail: "boom" }),
    });
    open();
    await ask();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      uk.auth.connectionProblem,
    );
  });

  it("links back to the login page and has no axe violations", async () => {
    const { container } = open();

    expect(
      screen.getByRole("heading", { level: 1, name: text.title }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: text.backToLogin }),
    ).toHaveAttribute("href", "/login");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("announces the confirmation in a status region", async () => {
    routeFetch(fetchMock, { "POST /auth/forgot-password": () => noContent() });
    const { container } = open();
    await ask();

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(text.sent),
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
