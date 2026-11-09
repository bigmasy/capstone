import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import Accordion from "./Accordion";

const items = [
  { heading: "First question", content: <p>First answer</p> },
  { heading: "Second question", content: <p>Second answer</p> },
];

describe("Accordion", () => {
  it("renders each heading with one button that starts collapsed", () => {
    render(<Accordion items={items} />);

    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(2);
    const first = screen.getByRole("button", { name: "First question" });
    expect(first).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("First answer")).not.toBeVisible();
  });

  it("links the button to its panel with aria-controls", () => {
    render(<Accordion items={items} />);

    const button = screen.getByRole("button", { name: "First question" });
    const panel = document.getElementById(button.getAttribute("aria-controls") as string);
    expect(panel).not.toBeNull();
    expect(panel).toContainHTML("First answer");
  });

  it("expands and collapses with Enter and Space", async () => {
    const user = userEvent.setup();
    render(<Accordion items={items} />);
    const button = screen.getByRole("button", { name: "First question" });

    button.focus();
    await user.keyboard("{Enter}");
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("First answer")).toBeVisible();

    await user.keyboard(" ");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("First answer")).not.toBeVisible();
  });

  it("lets several panels stay open and keeps the buttons in the tab order", async () => {
    const user = userEvent.setup();
    render(<Accordion items={items} />);

    await user.click(screen.getByRole("button", { name: "First question" }));
    await user.click(screen.getByRole("button", { name: "Second question" }));

    expect(screen.getByText("First answer")).toBeVisible();
    expect(screen.getByText("Second answer")).toBeVisible();
  });

  it("puts the buttons in the tab order, one stop per question", async () => {
    const user = userEvent.setup();
    render(<Accordion items={items} />);

    await user.tab();
    expect(screen.getByRole("button", { name: "First question" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Second question" })).toHaveFocus();
  });

  it("uses the requested heading level", () => {
    render(<Accordion items={items} headingLevel={4} />);

    expect(screen.getAllByRole("heading", { level: 4 })).toHaveLength(2);
  });

  it("has no axe violations collapsed or expanded", async () => {
    const user = userEvent.setup();
    const { container } = render(<Accordion items={items} />);

    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "First question" }));
    expect(await axe(container)).toHaveNoViolations();
  });
});
