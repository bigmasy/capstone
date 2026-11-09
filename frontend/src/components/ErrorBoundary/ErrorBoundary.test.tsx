import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import { renderWithProviders } from "../../test/utils";
import Layout from "../Layout/Layout";
import ErrorBoundary from "./ErrorBoundary";
import { Route, Routes } from "react-router";

let shouldThrow = true;

const Broken = (): never => {
  throw new Error("secret details");
};

const Flaky = () => {
  if (shouldThrow) throw new Error("secret details");
  return <h1>Recovered page</h1>;
};

describe("ErrorBoundary", () => {
  let consoleError: MockInstance;

  beforeEach(() => {
    shouldThrow = true;
    // React reports caught render errors to the console; keep the test output clean
    consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    consoleError.mockRestore();
  });

  it("renders its children when nothing fails", () => {
    render(
      <ErrorBoundary>
        <p>fine</p>
      </ErrorBoundary>,
    );

    expect(screen.getByText("fine")).toBeInTheDocument();
  });

  it("shows an accessible fallback without the error message", async () => {
    const { container } = render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("heading", { level: 1, name: uk.errors.title })).toBeInTheDocument();
    expect(screen.queryByText(/secret details/)).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("focuses the heading and sets the document title when the fallback appears", () => {
    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveAttribute("tabindex", "-1");
    expect(heading).toHaveFocus();
    expect(document.title).toBe(`${uk.errors.title}${uk.app.titleSeparator}${uk.app.name}`);
  });

  it("offers a real link to the home page", () => {
    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("link", { name: uk.errors.home })).toHaveAttribute("href", "/");
  });

  it("moves focus to the heading again when a retry fails", async () => {
    const user = userEvent.setup();
    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );

    await user.click(screen.getByRole("button", { name: uk.errors.retry }));

    expect(screen.getByRole("heading", { level: 1, name: uk.errors.title })).toHaveFocus();
  });

  it("moves focus to the page heading when a retry succeeds", async () => {
    const user = userEvent.setup();
    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    );
    shouldThrow = false;

    await user.click(screen.getByRole("button", { name: uk.errors.retry }));

    expect(screen.getByRole("heading", { level: 1, name: "Recovered page" })).toHaveFocus();
  });

  it("brings its own main landmark when used standalone at the root", async () => {
    const { container } = render(
      <ErrorBoundary standalone>
        <Broken />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("main")).toContainElement(screen.getByRole("heading", { level: 1 }));
    expect(screen.getByRole("link", { name: uk.errors.home })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("does not add a main landmark by default, because the layout provides one", () => {
    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );

    expect(screen.queryByRole("main")).not.toBeInTheDocument();
  });

  it("keeps the layout around a failing page", () => {
    renderWithProviders(
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Broken />} />
        </Route>
      </Routes>,
    );

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toContainElement(
      screen.getByRole("heading", { level: 1, name: uk.errors.title }),
    );
  });
});
