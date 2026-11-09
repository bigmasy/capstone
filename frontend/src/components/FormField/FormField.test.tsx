import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import FormField from "./FormField";

describe("FormField", () => {
  it("associates the label with the input", () => {
    render(<FormField label="Email" name="email" />);

    expect(screen.getByLabelText("Email")).toHaveAttribute("name", "email");
  });

  it("is valid and has no description without a hint or an error", () => {
    render(<FormField label="Email" name="email" />);

    const input = screen.getByLabelText("Email");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(input).not.toHaveAttribute("aria-describedby");
  });

  it("links the error to the input and marks it invalid", async () => {
    const { container } = render(<FormField label="Email" name="email" error="Enter an email" />);

    const input = screen.getByLabelText("Email");
    const message = screen.getByText(/Enter an email/);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(/Enter an email/);
    expect(input.getAttribute("aria-describedby")).toBe(message.id);
    expect(message).toHaveAttribute("aria-live", "polite");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("links both the hint and the error", () => {
    render(<FormField label="Password" name="password" hint="At least 8" error="Too short" />);

    const description = screen.getByLabelText("Password").getAttribute("aria-describedby") ?? "";
    expect(description.split(" ")).toHaveLength(2);
    expect(screen.getByLabelText("Password")).toHaveAccessibleDescription(/At least 8.*Too short/);
  });

  it("announces a required field and keeps the error visible as text", () => {
    render(<FormField label="Email" name="email" required error="Required" />);

    const input = screen.getByLabelText(/Email/);
    expect(input).toHaveAttribute("aria-required", "true");
    expect(screen.getByText(/Required/).closest("p")).toHaveTextContent(/Помилка:.*Required/);
  });

  it("keeps an empty polite live region in the DOM so a later error is announced", () => {
    const { container } = render(<FormField label="Email" name="email" />);

    const region = container.querySelector("[aria-live='polite']");
    expect(region).toBeInTheDocument();
    expect(region).toBeEmptyDOMElement();
    expect(screen.getByLabelText("Email")).not.toHaveAttribute("aria-describedby");
  });

  it("forwards autoCapitalize and spellCheck", () => {
    render(<FormField label="Email" name="email" autoCapitalize="none" spellCheck={false} />);

    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("autocapitalize", "none");
    expect(input).toHaveAttribute("spellcheck", "false");
  });

  it("forwards native input attributes", () => {
    render(<FormField label="Email" name="email" type="email" autoComplete="email" />);

    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("type", "email");
    expect(input).toHaveAttribute("autocomplete", "email");
  });
});
