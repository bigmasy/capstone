import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { uk } from "../../i18n/uk";
import type { LocationValue } from "../ProfileForm/profileValues";
import LocationPicker from "./LocationPicker";

// A map chunk that cannot be loaded (offline, blocked, or a browser the library does not support)
vi.mock("./LocationMap", () => {
  throw new Error("chunk failed");
});

const text = uk.profile.location;

const Picker = () => {
  const [value, setValue] = useState<LocationValue | null>(null);
  return (
    <>
      <LocationPicker value={value} onChange={setValue} />
      <span data-testid="value">{value ? `${value.latitude};${value.longitude}` : "none"}</span>
    </>
  );
};

describe("LocationPicker when the map cannot be loaded", () => {
  beforeEach(() => {
    // React reports the caught error to the console; the test expects it
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("tells the user in an alert and leaves the list and the direction buttons working", async () => {
    const user = userEvent.setup();
    render(<Picker />);

    await user.click(screen.getByRole("button", { name: text.showMap }));

    expect(await screen.findByRole("alert")).toHaveTextContent(text.mapFailed);
    await user.selectOptions(screen.getByRole("combobox", { name: /^Місто або район/ }), "kyiv");
    await user.click(screen.getByRole("button", { name: text.north }));
    expect(screen.getByTestId("value")).toHaveTextContent("50.5;30.51");
  });
});
