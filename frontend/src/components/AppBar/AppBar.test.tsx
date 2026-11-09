import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import { loggedIn, renderWithProviders } from "../../test/utils";
import AppBar from "./AppBar";

const routes = (
  <Routes>
    <Route path="*" element={<AppBar />} />
  </Routes>
);

const menuButton = () => screen.getByRole("button", { name: uk.nav.menu });

describe("AppBar mobile menu", () => {
  it("starts collapsed and is controlled by a button that points at the navigation", () => {
    renderWithProviders(routes);

    const nav = screen.getByRole("navigation", { name: uk.a11y.mainNavigation });
    expect(menuButton()).toHaveAttribute("aria-expanded", "false");
    expect(menuButton()).toHaveAttribute("aria-controls", nav.id);
    expect(nav.id).not.toBe("");
  });

  it("toggles aria-expanded with the keyboard (Enter and Space)", async () => {
    const user = userEvent.setup();
    renderWithProviders(routes);

    menuButton().focus();
    await user.keyboard("{Enter}");
    expect(menuButton()).toHaveAttribute("aria-expanded", "true");
    await user.keyboard(" ");
    expect(menuButton()).toHaveAttribute("aria-expanded", "false");
  });

  it("closes on Escape and returns focus to the button", async () => {
    const user = userEvent.setup();
    renderWithProviders(routes);

    await user.click(menuButton());
    expect(menuButton()).toHaveAttribute("aria-expanded", "true");
    screen.getByRole("link", { name: uk.nav.login }).focus();
    await user.keyboard("{Escape}");

    expect(menuButton()).toHaveAttribute("aria-expanded", "false");
    expect(menuButton()).toHaveFocus();
  });

  it("collapses after a link was followed", async () => {
    const user = userEvent.setup();
    renderWithProviders(routes);

    await user.click(menuButton());
    expect(menuButton()).toHaveAttribute("aria-expanded", "true");
    await user.click(screen.getByRole("link", { name: uk.nav.login }));

    expect(menuButton()).toHaveAttribute("aria-expanded", "false");
  });

  it("keeps the brand link to the landing page and shows the sign out button after login", () => {
    renderWithProviders(routes, { preloadedState: loggedIn });

    expect(screen.getByRole("link", { name: uk.app.name })).toHaveAttribute("href", "/");
    const nav = screen.getByRole("navigation", { name: uk.a11y.mainNavigation });
    expect(within(nav).getByRole("button", { name: uk.nav.logout })).toBeInTheDocument();
  });

  it("has no axe violations when collapsed and when expanded", async () => {
    const user = userEvent.setup();
    const { container } = renderWithProviders(routes);

    expect(await axe(container)).toHaveNoViolations();
    await user.click(menuButton());
    expect(await axe(container)).toHaveNoViolations();
  });
});
