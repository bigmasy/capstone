import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { calls, jsonResponse, makeProfile, routeFetch, type Handler } from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";
import PostLoginRedirect from "./PostLoginRedirect";

const routes = (
  <Routes>
    <Route path="/start" element={<PostLoginRedirect />} />
    <Route path="/profile" element={<p>profile page</p>} />
    <Route path="/" element={<p>home page</p>} />
  </Routes>
);

describe("PostLoginRedirect", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const visit = (handler: Handler) => {
    routeFetch(fetchMock, { "GET /profiles/me": handler });
    return renderWithProviders(routes, { route: "/start", preloadedState: loggedIn });
  };

  it("sends an account without a profile (404) to the profile page", async () => {
    visit(() => jsonResponse(404, { detail: "none" }));

    expect(await screen.findByText("profile page")).toBeInTheDocument();
    expect(calls(fetchMock)).toEqual(["GET /profiles/me"]);
  });

  it("sends an account with a profile to the home page", async () => {
    visit(() => jsonResponse(200, makeProfile()));

    expect(await screen.findByText("home page")).toBeInTheDocument();
  });

  it.each([500, 503, 403])("sends the user home when the profile cannot be read (%i)", async (status) => {
    visit(() => jsonResponse(status));

    expect(await screen.findByText("home page")).toBeInTheDocument();
  });

  it("sends the user home on a network failure", async () => {
    routeFetch(fetchMock, {});
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    renderWithProviders(routes, { route: "/start", preloadedState: loggedIn });

    expect(await screen.findByText("home page")).toBeInTheDocument();
  });

  it("shows a loading status until the answer arrives", async () => {
    let answer: (response: Response) => void = () => undefined;
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => (answer = resolve)));
    renderWithProviders(routes, { route: "/start", preloadedState: loggedIn });

    expect(screen.getByRole("status")).toBeInTheDocument();
    answer(jsonResponse(404, { detail: "none" }));
    expect(await screen.findByText("profile page")).toBeInTheDocument();
  });
});
