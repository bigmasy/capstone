import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import SelectField from "./SelectField";

const options = [
  { value: "a", label: "Alpha" },
  { value: "b", label: "Beta" },
];

describe("SelectField", () => {
  it("associates the label with the select and lists the options", () => {
    render(<SelectField label="Letter" name="letter" options={options} defaultValue="b" />);

    const select = screen.getByRole("combobox", { name: "Letter" });
    expect(select).toHaveAttribute("name", "letter");
    expect(select).toHaveValue("b");
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual(["Alpha", "Beta"]);
  });

  it("adds an empty first option only when a placeholder is given", () => {
    render(<SelectField label="Letter" name="letter" options={options} placeholder="Choose" />);

    expect(screen.getAllByRole("option")[0]).toHaveTextContent("Choose");
    expect(screen.getAllByRole("option")[0]).toHaveValue("");
  });

  it("links the hint and the error to the select and marks it invalid", async () => {
    const { container } = render(
      <SelectField label="Letter" name="letter" options={options} hint="Pick one" error="Required" required />,
    );

    const select = screen.getByRole("combobox", { name: /Letter/ });
    expect(select).toHaveAttribute("aria-invalid", "true");
    expect(select).toHaveAttribute("aria-required", "true");
    expect(select).toHaveAccessibleDescription(/Pick one.*Required/);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("has no description or invalid state without a hint or an error", () => {
    render(<SelectField label="Letter" name="letter" options={options} />);

    const select = screen.getByRole("combobox");
    expect(select).not.toHaveAttribute("aria-invalid");
    expect(select).not.toHaveAttribute("aria-describedby");
  });
});
