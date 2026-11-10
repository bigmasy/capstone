import { screen } from "@testing-library/react";
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
import ResetPasswordPage from "./ResetPasswordPage";

const text = uk.passwordReset.reset;
const TOKEN = "Abc_def-0123456789ABCDEFGHIJKLMNOPQRSTUVWXY";
const NEW_PASSWORD = "a brand new passphrase";

describe("ResetPasswordPage", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState(null, "", "/reset-password#token=" + TOKEN);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
  });

  const open = (hash = `#token=${TOKEN}`) =>
    renderWithProviders(
      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
      </Routes>,
      { route: `/reset-password${hash}` },
    );

  const fill = async (password = NEW_PASSWORD, confirmation = password) => {
    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText(new RegExp(`^${text.newPassword}`)),
      password,
    );
    await user.type(
      screen.getByLabelText(new RegExp(text.confirmPassword)),
      confirmation,
    );
    await user.click(screen.getByRole("button", { name: text.submit }));
  };

  it("removes the token from the address bar at once and sends nothing yet", () => {
    open();

    expect(window.location.hash).toBe("");
    expect(window.location.href).not.toContain(TOKEN);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends the token and the new password in one body and offers the login", async () => {
    routeFetch(fetchMock, { "POST /auth/reset-password": () => noContent() });
    open();

    await fill();

    expect(await screen.findByText(text.saved)).toBeInTheDocument();
    expect(await bodiesSentTo(fetchMock, "POST /auth/reset-password")).toEqual([
      { token: TOKEN, password: NEW_PASSWORD },
    ]);
    expect(screen.getByRole("link", { name: text.toLogin })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("does not send when the two passwords differ", async () => {
    open();

    await fill(NEW_PASSWORD, "something else entirely");

    expect(
      await screen.findByText(uk.form.validation.passwordMismatch),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not send a password that is too short", async () => {
    open();

    await fill("short");

    expect(
      await screen.findByText(uk.form.validation.passwordMin),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("explains a refused link and offers a new one, in our words", async () => {
    routeFetch(fetchMock, {
      "POST /auth/reset-password": () =>
        jsonResponse(400, { detail: "The reset link is invalid" }),
    });
    open();

    await fill();

    expect(await screen.findByText(text.invalidLink)).toBeInTheDocument();
    expect(screen.queryByText(/reset link/)).toBeNull();
    expect(screen.getByRole("link", { name: text.requestNew })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
  });

  it("keeps the form when the server only rejects the password", async () => {
    routeFetch(fetchMock, {
      "POST /auth/reset-password": () => jsonResponse(422, { detail: [] }),
    });
    open();

    await fill();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      uk.auth.serverRejectedPassword,
    );
    expect(
      screen.getByLabelText(new RegExp(`^${text.newPassword}`)),
    ).toBeInTheDocument();
  });

  it("says so when the link carries no token and sends nothing", () => {
    window.history.replaceState(null, "", "/reset-password");
    open("");

    expect(screen.getByText(text.missingToken)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: text.requestNew }),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("has no axe violations in the form and after saving", async () => {
    routeFetch(fetchMock, { "POST /auth/reset-password": () => noContent() });
    const { container } = open();
    expect(
      screen.getByRole("heading", { level: 1, name: text.title }),
    ).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    await fill();
    await screen.findByText(text.saved);

    expect(await axe(container)).toHaveNoViolations();
  });
});
