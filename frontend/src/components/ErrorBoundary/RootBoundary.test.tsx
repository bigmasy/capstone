import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import { renderWithProviders } from "../../test/utils";
import Layout from "../Layout/Layout";
import ErrorBoundary from "./ErrorBoundary";

// The page-level boundary sits inside Layout, so a failing app bar can only be caught above it
vi.mock("../AppBar/AppBar", () => ({
  default: (): never => {
    throw new Error("app bar failed");
  },
}));

describe("root-level ErrorBoundary", () => {
  let consoleError: MockInstance;

  beforeEach(() => {
    consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    consoleError.mockRestore();
  });

  it("still shows an h1, a main landmark and a way out when the app bar fails", async () => {
    const { container } = renderWithProviders(
      <ErrorBoundary standalone>
        <Routes>
          <Route path="/" element={<Layout />} />
        </Routes>
      </ErrorBoundary>,
    );

    const heading = screen.getByRole("heading", { level: 1, name: uk.errors.title });
    expect(screen.getByRole("main")).toContainElement(heading);
    expect(heading).toHaveFocus();
    expect(screen.getByRole("link", { name: uk.errors.home })).toHaveAttribute("href", "/");
    expect(await axe(container)).toHaveNoViolations();
  });
});
