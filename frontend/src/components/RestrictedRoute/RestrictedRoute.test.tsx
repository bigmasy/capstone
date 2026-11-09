import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { loggedIn, renderWithProviders } from "../../test/utils";
import RestrictedRoute from "./RestrictedRoute";

const routes = (
  <Routes>
    <Route path="/login" element={<RestrictedRoute component={<p>login page</p>} />} />
    <Route path="/profile" element={<p>profile page</p>} />
  </Routes>
);

describe("RestrictedRoute", () => {
  it("renders the page for an anonymous user", () => {
    renderWithProviders(routes, { route: "/login" });

    expect(screen.getByText("login page")).toBeInTheDocument();
  });

  it("redirects a logged-in user to the profile", () => {
    renderWithProviders(routes, { route: "/login", preloadedState: loggedIn });

    expect(screen.getByText("profile page")).toBeInTheDocument();
    expect(screen.queryByText("login page")).not.toBeInTheDocument();
  });
});
