import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import { loggedIn, renderWithProviders } from "../../test/utils";
import Navigation from "./Navigation";

describe("Navigation", () => {
  it("links a logged-in user to the profile, the matches and the invitations", () => {
    renderWithProviders(<Navigation />, { preloadedState: loggedIn });

    const nav = screen.getByRole("navigation", { name: uk.a11y.mainNavigation });

    expect(within(nav).getByRole("link", { name: uk.nav.profile })).toHaveAttribute("href", "/profile");
    expect(within(nav).getByRole("link", { name: uk.nav.matches })).toHaveAttribute("href", "/matches");
    expect(within(nav).getByRole("link", { name: uk.nav.invitations })).toHaveAttribute("href", "/invitations");
    expect(within(nav).queryByRole("link", { name: uk.nav.login })).toBeNull();
  });

  it("marks only the current page with aria-current", () => {
    renderWithProviders(<Navigation />, { route: "/matches", preloadedState: loggedIn });

    expect(screen.getByRole("link", { name: uk.nav.matches })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: uk.nav.invitations })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: uk.nav.profile })).not.toHaveAttribute("aria-current");
  });

  it("is reachable and operable with the keyboard in reading order", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Navigation />, { preloadedState: loggedIn });

    await user.tab();
    expect(screen.getByRole("link", { name: uk.nav.matches })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: uk.nav.invitations })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: uk.nav.profile })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: uk.nav.logout })).toHaveFocus();
  });

  it("lists the public pages for a visitor in order, with registration last", () => {
    renderWithProviders(<Navigation />);

    const nav = screen.getByRole("navigation", { name: uk.a11y.mainNavigation });
    const labels = within(nav)
      .getAllByRole("link")
      .map((link) => link.textContent);

    expect(labels).toEqual([uk.nav.home, uk.nav.about, uk.nav.login, uk.nav.register]);
    expect(within(nav).getByRole("link", { name: uk.nav.about })).toHaveAttribute("href", "/about");
    expect(within(nav).queryByRole("button", { name: uk.nav.logout })).toBeNull();
  });

  it("offers sign out instead of the public links to a logged-in user", () => {
    renderWithProviders(<Navigation />, { preloadedState: loggedIn });

    const nav = screen.getByRole("navigation", { name: uk.a11y.mainNavigation });

    expect(within(nav).getByRole("button", { name: uk.nav.logout })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: uk.nav.register })).toBeNull();
    expect(within(nav).queryByRole("link", { name: uk.nav.about })).toBeNull();
  });

  it("signs the user out and calls onNavigate", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const { store } = renderWithProviders(<Navigation onNavigate={onNavigate} />, {
      preloadedState: loggedIn,
    });

    await user.click(screen.getByRole("button", { name: uk.nav.logout }));

    expect(store.getState().auth.token).toBeNull();
    expect(onNavigate).toHaveBeenCalledTimes(1);
  });

  it("offers the login and registration links to a visitor and no member pages", () => {
    renderWithProviders(<Navigation />);

    expect(screen.getByRole("link", { name: uk.nav.login })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: uk.nav.matches })).toBeNull();
    expect(screen.queryByRole("link", { name: uk.nav.invitations })).toBeNull();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<Navigation />, { route: "/invitations", preloadedState: loggedIn });

    expect(await axe(container)).toHaveNoViolations();
  });
});
