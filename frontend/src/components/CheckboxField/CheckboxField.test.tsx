import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import CheckboxField from "./CheckboxField";

describe("CheckboxField", () => {
  it("is a checkbox named by its label and toggles with the keyboard", async () => {
    const user = userEvent.setup();
    render(<CheckboxField label="Agree" name="agree" />);

    const box = screen.getByRole("checkbox", { name: "Agree" });
    await user.tab();
    expect(box).toHaveFocus();
    await user.keyboard(" ");
    expect(box).toBeChecked();
  });

  it("is announced as a switch in the switch variant", () => {
    render(<CheckboxField label="Visible" name="visible" variant="switch" defaultChecked />);

    expect(screen.getByRole("switch", { name: "Visible" })).toBeChecked();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("links the description and the error and passes axe", async () => {
    const { container } = render(
      <CheckboxField label="Agree" name="agree" description="What this means" error="Required" />,
    );

    const box = screen.getByRole("checkbox", { name: "Agree" });
    expect(box).toHaveAttribute("aria-invalid", "true");
    expect(box).toHaveAccessibleDescription(/What this means.*Required/);
    expect(await axe(container)).toHaveNoViolations();
  });
});
