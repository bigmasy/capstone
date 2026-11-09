import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Form, Formik } from "formik";
import { useRef } from "react";
import { describe, expect, it } from "vitest";
import FocusFirstError from "./FocusFirstError";

const Harness = () => {
  const formRef = useRef<HTMLFormElement>(null);
  return (
    <>
      {/* An invalid field outside the form must never receive focus */}
      <input aria-label="outside" aria-invalid="true" />
      <Formik
        initialValues={{ a: "", b: "" }}
        validate={() => ({ a: "required", b: "required" })}
        onSubmit={() => undefined}
      >
        <Form ref={formRef}>
          <FocusFirstError formRef={formRef} />
          <input aria-label="first" aria-invalid="true" />
          <input aria-label="second" aria-invalid="true" />
          <button type="submit">go</button>
        </Form>
      </Formik>
    </>
  );
};

describe("FocusFirstError", () => {
  it("focuses the first invalid field inside its own form after a failed submit", async () => {
    render(<Harness />);

    await userEvent.setup().click(screen.getByRole("button", { name: "go" }));

    await waitFor(() => expect(screen.getByLabelText("first")).toHaveFocus());
    expect(screen.getByLabelText("outside")).not.toHaveFocus();
  });
});
