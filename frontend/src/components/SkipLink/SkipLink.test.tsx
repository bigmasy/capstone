import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { uk } from "../../i18n/uk";
import SkipLink from "./SkipLink";

function renderPage() {
  render(
    <>
      <SkipLink targetId="content" />
      <button type="button">other control</button>
      <main id="content" tabIndex={-1}>
        <h1>Heading</h1>
      </main>
    </>,
  );
}

describe("SkipLink", () => {
  it("is the first element reached with the Tab key", async () => {
    renderPage();

    await userEvent.tab();

    expect(screen.getByRole("link", { name: uk.a11y.skipToContent })).toHaveFocus();
  });

  it("moves focus to the target when activated from the keyboard", async () => {
    renderPage();

    await userEvent.tab();
    await userEvent.keyboard("{Enter}");

    expect(screen.getByRole("main")).toHaveFocus();
  });

  it("does nothing when the target is missing", async () => {
    render(<SkipLink targetId="missing" />);

    await userEvent.tab();
    await userEvent.keyboard("{Enter}");

    expect(screen.getByRole("link")).toHaveFocus();
  });
});
