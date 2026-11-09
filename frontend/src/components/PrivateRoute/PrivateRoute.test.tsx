import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { loggedIn, renderWithProviders } from "../../test/utils";
import PrivateRoute from "./PrivateRoute";

const routes = (
  <Routes>
    <Route path="/secret" element={<PrivateRoute component={<p>secret page</p>} />} />
    <Route path="/login" element={<p>login page</p>} />
  </Routes>
);

describe("PrivateRoute", () => {
  it("renders the page for a logged-in user", () => {
    renderWithProviders(routes, { route: "/secret", preloadedState: loggedIn });

    expect(screen.getByText("secret page")).toBeInTheDocument();
  });

  it("redirects an anonymous user to the login page", () => {
    renderWithProviders(routes, { route: "/secret" });

    expect(screen.getByText("login page")).toBeInTheDocument();
    expect(screen.queryByText("secret page")).not.toBeInTheDocument();
  });
});
