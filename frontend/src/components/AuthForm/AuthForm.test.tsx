import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import { renderWithProviders } from "../../test/utils";
import AuthForm from "./AuthForm";

const EMAIL = "a@example.com";
const PASSWORD = "long-enough-pass";

function jsonResponse(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("AuthForm", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const fill = async (user: ReturnType<typeof userEvent.setup>, password = PASSWORD) => {
    await user.type(screen.getByLabelText(new RegExp(uk.auth.email)), EMAIL);
    await user.type(screen.getByLabelText(new RegExp(uk.auth.password)), password);
  };

  it("labels the fields and has no axe violations", async () => {
    const { container } = renderWithProviders(<AuthForm mode="login" />);

    const email = screen.getByLabelText(new RegExp(uk.auth.email));
    expect(email).toHaveAttribute("type", "email");
    expect(email).toHaveAttribute("autocapitalize", "none");
    expect(email).toHaveAttribute("spellcheck", "false");
    expect(screen.getByLabelText(new RegExp(uk.auth.password))).toHaveAttribute("type", "password");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("shows linked errors and focuses the first invalid field after a failed submit", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuthForm mode="login" />);

    await user.click(screen.getByRole("button", { name: uk.auth.submitLogin }));

    const email = await screen.findByLabelText(new RegExp(uk.auth.email));
    await waitFor(() => expect(email).toHaveFocus());
    expect(email).toHaveAttribute("aria-invalid", "true");
    expect(email).toHaveAccessibleDescription(new RegExp(uk.form.validation.required));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("reports a malformed email and a short password", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuthForm mode="register" />);

    await user.type(screen.getByLabelText(new RegExp(uk.auth.email)), "not-an-email");
    await user.type(screen.getByLabelText(new RegExp(uk.auth.password)), "123456789");
    await user.click(screen.getByRole("button", { name: uk.auth.submitRegister }));

    expect(await screen.findByText(uk.form.validation.email)).toBeInTheDocument();
    expect(screen.getByText(uk.form.validation.passwordMin)).toBeInTheDocument();
  });

  it("accepts a password of exactly 10 characters", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { access_token: "tok", token_type: "bearer" }));
    const user = userEvent.setup();
    renderWithProviders(<AuthForm mode="login" />);

    await fill(user, "1234567890");
    await user.click(screen.getByRole("button", { name: uk.auth.submitLogin }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  });

  it("rejects an e-mail over 254 characters and a password over 128", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuthForm mode="register" />);

    await user.click(screen.getByLabelText(new RegExp(uk.auth.email)));
    await user.paste(`${"a".repeat(64)}@${"b".repeat(63)}.${"c".repeat(63)}.${"d".repeat(63)}.com`);
    await user.click(screen.getByLabelText(new RegExp(uk.auth.password)));
    await user.paste("p".repeat(129));
    await user.click(screen.getByRole("button", { name: uk.auth.submitRegister }));

    expect(await screen.findByText(uk.form.validation.emailMax)).toBeInTheDocument();
    expect(screen.getByText(uk.form.validation.passwordMax)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("stores the token after a successful login", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { access_token: "tok", token_type: "bearer" }));
    const user = userEvent.setup();
    const { store } = renderWithProviders(<AuthForm mode="login" />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: uk.auth.submitLogin }));

    await waitFor(() => expect(store.getState().auth.token).toBe("tok"));
    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.url).toBe("http://localhost/api/v1/auth/login");
    expect(window.localStorage.length).toBe(0);
  });

  it("registers and then logs in", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(201));
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { access_token: "tok", token_type: "bearer" }));
    const user = userEvent.setup();
    const { store } = renderWithProviders(<AuthForm mode="register" />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: uk.auth.submitRegister }));

    await waitFor(() => expect(store.getState().auth.token).toBe("tok"));
    const urls = fetchMock.mock.calls.map(([request]) => (request as Request).url);
    expect(urls).toEqual(["http://localhost/api/v1/auth/register", "http://localhost/api/v1/auth/login"]);
  });

  it("sends the page to the login screen when the account was created but the login failed", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(201));
    fetchMock.mockResolvedValueOnce(jsonResponse(500));
    const user = userEvent.setup();
    const { store } = renderWithProviders(
      <Routes>
        <Route path="/register" element={<AuthForm mode="register" />} />
        <Route path="/login" element={<p>login page</p>} />
      </Routes>,
      { route: "/register" },
    );

    await fill(user);
    await user.click(screen.getByRole("button", { name: uk.auth.submitRegister }));

    expect(await screen.findByText("login page")).toBeInTheDocument();
    expect(store.getState().auth.token).toBeNull();
  });

  it.each([
    { name: "401", response: () => jsonResponse(401, { detail: "bad" }), text: uk.auth.invalidCredentials },
    { name: "429", response: () => jsonResponse(429), text: uk.auth.tooManyAttempts },
    { name: "500", response: () => jsonResponse(500), text: uk.auth.connectionProblem },
    { name: "502", response: () => jsonResponse(502), text: uk.auth.connectionProblem },
    { name: "non-JSON body", response: () => new Response("<html>", { status: 200 }), text: uk.auth.connectionProblem },
  ])("announces a failed login ($name) with its own message", async ({ response, text }) => {
    fetchMock.mockResolvedValue(response());
    const user = userEvent.setup();
    const { store } = renderWithProviders(<AuthForm mode="login" />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: uk.auth.submitLogin }));

    expect(await screen.findByRole("alert")).toHaveTextContent(text);
    expect(store.getState().auth.token).toBeNull();
  });

  it("announces a network failure as a connection problem", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const user = userEvent.setup();
    renderWithProviders(<AuthForm mode="login" />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: uk.auth.submitLogin }));

    expect(await screen.findByRole("alert")).toHaveTextContent(uk.auth.connectionProblem);
  });

  it("explains that the account exists and links to the login page on 409", async () => {
    fetchMock.mockResolvedValue(jsonResponse(409, { detail: "exists" }));
    const user = userEvent.setup();
    renderWithProviders(<AuthForm mode="register" />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: uk.auth.submitRegister }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(uk.auth.accountExists);
    expect(screen.getByRole("link", { name: uk.auth.accountExistsLink })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("maps a server 422 to the field and never shows the server text", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(422, [
        { type: "string_too_short", loc: ["body", "password"], msg: "SERVER-TEXT with " + PASSWORD },
      ]),
    );
    const user = userEvent.setup();
    renderWithProviders(<AuthForm mode="register" />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: uk.auth.submitRegister }));

    const password = screen.getByLabelText(new RegExp(uk.auth.password));
    await waitFor(() => expect(password).toHaveAttribute("aria-invalid", "true"));
    expect(password).toHaveAccessibleDescription(new RegExp(uk.auth.serverRejectedPassword));
    await waitFor(() => expect(password).toHaveFocus());
    expect(screen.getByLabelText(new RegExp(uk.auth.email))).not.toHaveAttribute("aria-invalid");
    expect(document.body).not.toHaveTextContent("SERVER-TEXT");
  });

  it("uses aria-disabled instead of disabled while pending and ignores a second submit", async () => {
    let answer: (response: Response) => void = () => undefined;
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => (answer = resolve)));
    const user = userEvent.setup();
    renderWithProviders(<AuthForm mode="login" />);

    await fill(user);
    const button = screen.getByRole("button", { name: uk.auth.submitLogin });
    await user.click(button);

    await waitFor(() => expect(button).toHaveAttribute("aria-disabled", "true"));
    expect(button).not.toBeDisabled();
    await user.click(button);
    await user.type(screen.getByLabelText(new RegExp(uk.auth.password)), "{Enter}");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    answer(jsonResponse(200, { access_token: "tok", token_type: "bearer" }));
    await waitFor(() => expect(button).not.toHaveAttribute("aria-disabled"));
  });
});
