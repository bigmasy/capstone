import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { uk } from "../../i18n/uk";
import { renderWithProviders } from "../../test/utils";
import LoginPage from "./LoginPage";

describe("LoginPage", () => {
  it("offers password recovery next to the form", () => {
    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
      </Routes>,
      { route: "/login" },
    );

    expect(
      screen.getByRole("link", { name: uk.passwordReset.forgotLink }),
    ).toHaveAttribute("href", "/forgot-password");
  });
});
