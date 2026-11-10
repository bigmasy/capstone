import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { uk } from "../../i18n/uk";
import {
  calls,
  jsonResponse,
  makeAccount,
  makeNews,
  makeProfile,
  routeFetch,
  taxonomy,
  type Routes,
} from "../../test/api";
import { renderWithProviders } from "../../test/utils";
import App from "./App";

const TOKEN = { access_token: "tok", token_type: "bearer" };

describe("first login flow", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const routes = (profile: () => Response): Routes => ({
    "POST /auth/register": () => jsonResponse(201, {}),
    "POST /auth/login": () => jsonResponse(200, TOKEN),
    "GET /auth/me": () => jsonResponse(200, makeAccount()),
    "GET /news": () => jsonResponse(200, makeNews()),
    "GET /taxonomy": () => jsonResponse(200, taxonomy),
    "GET /profiles/me": profile,
  });

  const logIn = async (route: "/login" | "/register") => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { route });
    await user.type(
      screen.getByLabelText(new RegExp(uk.auth.email)),
      "a@example.com",
    );
    await user.type(
      screen.getByLabelText(new RegExp(uk.auth.password)),
      "long-enough-pass",
    );
    if (route === "/register") {
      await user.type(
        screen.getByLabelText(new RegExp(uk.auth.confirmPassword)),
        "long-enough-pass",
      );
    }
    await user.click(
      screen.getByRole("button", {
        name: route === "/login" ? uk.auth.submitLogin : uk.auth.submitRegister,
      }),
    );
  };

  it("sends a new account to the profile page with the onboarding heading after registration", async () => {
    routeFetch(
      fetchMock,
      routes(() => jsonResponse(404, { detail: "none" })),
    );

    await logIn("/register");

    expect(
      await screen.findByRole("heading", {
        level: 2,
        name: uk.profile.onboarding.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      uk.pages.profile.title,
    );
    // The account is read in between, to know whether the address is confirmed
    expect(
      calls(fetchMock)
        .filter((call) => call !== "GET /auth/me")
        .slice(0, 3),
    ).toEqual(["POST /auth/register", "POST /auth/login", "GET /profiles/me"]);
  });

  it("sends an account without a profile to the onboarding after login", async () => {
    routeFetch(
      fetchMock,
      routes(() => jsonResponse(404, { detail: "none" })),
    );

    await logIn("/login");

    expect(
      await screen.findByRole("heading", {
        level: 2,
        name: uk.profile.onboarding.title,
      }),
    ).toBeInTheDocument();
  });

  it("sends an account with a profile to the home page with its summary after login", async () => {
    routeFetch(
      fetchMock,
      routes(() => jsonResponse(200, makeProfile())),
    );

    await logIn("/login");

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: uk.pages.home.title,
      }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Олена")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: uk.profile.onboarding.title }),
    ).toBeNull();
    // The summary reuses the answer that decided the redirect
    expect(
      calls(fetchMock).filter((call) => call === "GET /profiles/me"),
    ).toHaveLength(1);
  });

  it("moves focus to the page heading after the redirect", async () => {
    routeFetch(
      fetchMock,
      routes(() => jsonResponse(404, { detail: "none" })),
    );

    await logIn("/login");

    const heading = await screen.findByRole("heading", {
      level: 1,
      name: uk.pages.profile.title,
    });
    expect(heading).toHaveFocus();
  });

  it("goes home when the profile cannot be read", async () => {
    routeFetch(
      fetchMock,
      routes(() => jsonResponse(500)),
    );

    await logIn("/login");

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: uk.pages.home.title,
      }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      uk.pages.home.summaryFailed,
    );
  });
});
