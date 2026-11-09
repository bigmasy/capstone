import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, Route, Routes } from "react-router";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { uk } from "../../i18n/uk";
import { loggedIn, renderWithProviders } from "../../test/utils";
import Layout from "./Layout";

const PageA = () => (
  <>
    <h1>Page A</h1>
    <Link to="/b">Go to B</Link>
  </>
);
const PageB = () => <h1>Page B</h1>;

const routes = (
  <Routes>
    <Route path="/" element={<Layout />}>
      <Route index element={<PageA />} />
      <Route path="b" element={<PageB />} />
    </Route>
  </Routes>
);

describe("Layout", () => {
  it("provides the landmarks and a single h1", async () => {
    const { container } = renderWithProviders(routes);

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getAllByRole("navigation").length).toBeGreaterThan(0);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("has no axe violations for a logged-in user", async () => {
    const { container } = renderWithProviders(routes, { preloadedState: loggedIn });

    expect(await axe(container)).toHaveNoViolations();
  });

  it("uses the implicit polite semantics of role=status without a redundant aria-live", () => {
    renderWithProviders(routes);

    expect(screen.getByRole("status")).not.toHaveAttribute("aria-live");
  });

  it("sets the document title from the heading", () => {
    renderWithProviders(routes);

    expect(document.title).toBe(`Page A${uk.app.titleSeparator}${uk.app.name}`);
  });

  it("does not steal focus on the first page load", () => {
    renderWithProviders(routes);

    expect(document.body).toHaveFocus();
  });

  it("moves focus to the h1, announces the page and updates the title on route change", async () => {
    renderWithProviders(routes);
    const user = userEvent.setup();

    await user.click(screen.getByRole("link", { name: "Go to B" }));

    const heading = screen.getByRole("heading", { level: 1, name: "Page B" });
    expect(heading).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent("Page B");
    expect(document.title).toBe(`Page B${uk.app.titleSeparator}${uk.app.name}`);
  });
});
