import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import { loggedIn, renderWithProviders } from "../../test/utils";
import Footer from "./Footer";

describe("Footer", () => {
  it("is the contentinfo landmark with a privacy note", () => {
    renderWithProviders(<Footer />);

    const footer = screen.getByRole("contentinfo");
    expect(within(footer).getByText(uk.footer.note)).toBeInTheDocument();
  });

  it("links a visitor to the public pages", () => {
    renderWithProviders(<Footer />);

    const nav = screen.getByRole("navigation", { name: uk.a11y.footerNavigation });
    expect(within(nav).getByRole("link", { name: uk.nav.about })).toHaveAttribute("href", "/about");
    expect(within(nav).getByRole("link", { name: uk.nav.login })).toHaveAttribute("href", "/login");
    expect(within(nav).queryByRole("link", { name: uk.nav.matches })).toBeNull();
  });

  it("links a logged-in user to the member pages", () => {
    renderWithProviders(<Footer />, { preloadedState: loggedIn });

    const nav = screen.getByRole("navigation", { name: uk.a11y.footerNavigation });
    expect(within(nav).getByRole("link", { name: uk.nav.matches })).toHaveAttribute("href", "/matches");
    expect(within(nav).queryByRole("link", { name: uk.nav.register })).toBeNull();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<Footer />);

    expect(await axe(container)).toHaveNoViolations();
  });
});
