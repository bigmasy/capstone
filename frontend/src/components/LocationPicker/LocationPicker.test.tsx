import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { AreaPrecision } from "../../api/types";
import { uk } from "../../i18n/uk";
import type { LocationValue } from "../ProfileForm/profileValues";
import LocationPicker from "./LocationPicker";

const loads = vi.hoisted(() => ({ count: 0 }));

// The real map is covered in LocationMap.test.tsx; the stub also counts how often the lazy
// module is loaded, which is how "no map before it is asked for" is checked.
vi.mock("./LocationMap", async () => {
  loads.count += 1;
  return import("../../test/LocationMapStub");
});

const text = uk.profile.location;

interface HarnessProps {
  initial?: LocationValue | null;
  initialPrecision?: AreaPrecision;
  optional?: boolean;
  error?: string;
}

/** Holds the value the way the form does and shows it, so a test can read what was chosen. */
const Harness = ({
  initial = null,
  initialPrecision = "4km",
  optional = false,
  error,
}: HarnessProps) => {
  const [value, setValue] = useState<LocationValue | null>(initial);
  const [precision, setPrecision] = useState<AreaPrecision>(initialPrecision);
  return (
    <>
      <LocationPicker
        value={value}
        onChange={setValue}
        precision={precision}
        onPrecisionChange={setPrecision}
        optional={optional}
        error={error}
      />
      <span data-testid="value">{value ? `${value.latitude};${value.longitude}` : "none"}</span>
      <span data-testid="precision">{precision}</span>
    </>
  );
};

const chosen = () => screen.getByTestId("value").textContent;
const placeSelect = () => screen.getByRole("combobox", { name: /^Місто або район/ });
const size = (precision: AreaPrecision) =>
  screen.getByRole("radio", { name: new RegExp(`^${text.precision[precision].name}`) });

function stubGeolocation(
  behaviour: (ok: PositionCallback, fail: PositionErrorCallback) => void,
) {
  Object.defineProperty(window.navigator, "geolocation", {
    configurable: true,
    value: { getCurrentPosition: behaviour },
  });
}

describe("LocationPicker", () => {
  afterEach(() => {
    Reflect.deleteProperty(window.navigator, "geolocation");
  });

  describe("before anything is chosen", () => {
    it("loads no map and offers the list, the toggle and the privacy note", () => {
      render(<Harness />);

      expect(loads.count).toBe(0);
      expect(screen.queryByRole("group", { name: text.mapLabel })).toBeNull();
      expect(screen.getByRole("button", { name: text.showMap })).toHaveAttribute("aria-expanded", "false");
      expect(screen.getByText(text.mapNote)).toBeInTheDocument();
      expect(text.mapNote).toContain("сервер карт бачить лише ділянку карти, яку ви переглядаєте");
      expect(chosen()).toBe("none");
    });

    it("lists the cities alphabetically, each followed by its districts", () => {
      render(<Harness />);

      const options = within(placeSelect())
        .getAllByRole("option")
        .map((option) => option.textContent);
      expect(options[0]).toBe(text.placePlaceholder);
      expect(options).toContain("Київ");
      expect(options.indexOf("Київ, Печерський район")).toBeGreaterThan(options.indexOf("Київ"));
      expect(options.indexOf("Київ, Печерський район")).toBe(options.indexOf("Київ, Оболонський район") + 1);
      expect(options.indexOf("Житомир")).toBeLessThan(options.indexOf("Київ"));
    });

    it("offers no cancel button, no coordinates and no direction buttons", () => {
      render(<Harness />);

      expect(screen.queryByRole("button", { name: text.clear })).toBeNull();
      for (const name of ["Північ", "Південь", "Схід", "Захід"]) {
        expect(screen.queryByRole("button", { name })).toBeNull();
      }
      expect(document.body).not.toHaveTextContent(/пн\. ш\.|сх\. д\./);
    });

    it("has no axe violations", async () => {
      const { container } = render(<Harness />);

      expect(await axe(container)).toHaveNoViolations();
    });
  });

  describe("the map", () => {
    it("loads only when the button is pressed, can be hidden again and does not choose anything", async () => {
      const user = userEvent.setup();
      render(<Harness />);

      await user.click(screen.getByRole("button", { name: text.showMap }));

      expect(await screen.findByRole("group", { name: text.mapLabel })).toBeInTheDocument();
      expect(loads.count).toBeGreaterThanOrEqual(1);
      const toggle = screen.getByRole("button", { name: text.hideMap });
      expect(toggle).toHaveAttribute("aria-expanded", "true");
      expect(chosen()).toBe("none");

      await user.click(toggle);

      expect(screen.queryByRole("group", { name: text.mapLabel })).toBeNull();
      expect(screen.getByRole("button", { name: text.showMap })).toHaveFocus();
    });

    it("shows the attribution link and the pointer help", async () => {
      const user = userEvent.setup();
      render(<Harness />);

      await user.click(screen.getByRole("button", { name: text.showMap }));
      await screen.findByRole("group", { name: text.mapLabel });

      const link = screen.getByRole("link", { name: "© OpenStreetMap contributors" });
      expect(link).toHaveAttribute("href", "https://www.openstreetmap.org/copyright");
      expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
      expect(screen.getByText(text.mapPointerHint)).toBeInTheDocument();
    });

    it("snaps a clicked point to its cell and keeps only the cell centre", async () => {
      const user = userEvent.setup();
      render(<Harness />);
      await user.click(screen.getByRole("button", { name: text.showMap }));

      await user.click(await screen.findByRole("button", { name: "Клік по карті" }));

      expect(chosen()).toBe("50.46;30.51");
      // The map is given the centre of the cell, never the clicked point
      expect(screen.getByTestId("stub-value")).toHaveTextContent("50.46;30.51");
      expect(document.body).not.toHaveTextContent("50.4517");
      expect(placeSelect()).toHaveValue("");
    });

    it("is not asked to recentre on its own click, so the view stays where the user put it", async () => {
      const user = userEvent.setup();
      render(<Harness />);
      await user.click(screen.getByRole("button", { name: text.showMap }));

      await user.click(await screen.findByRole("button", { name: "Клік по карті" }));

      expect(screen.getByTestId("stub-recenter")).toHaveTextContent("0");
    });
  });

  describe("choosing a place", () => {
    it("sets the cell of the place, opens the map and asks it to recentre", async () => {
      const user = userEvent.setup();
      render(<Harness />);

      await user.selectOptions(placeSelect(), "lviv");

      // Lviv is listed at 49.842, 24.032; the grid of the server puts it in the cell 49.86 / 24.03
      expect(chosen()).toBe("49.86;24.03");
      expect(await screen.findByRole("group", { name: text.mapLabel })).toBeInTheDocument();
      expect(screen.getByTestId("stub-recenter")).toHaveTextContent("1");
      expect(placeSelect()).toHaveValue("lviv");
    });

    it("resets the list when the point is changed afterwards", async () => {
      const user = userEvent.setup();
      render(<Harness />);
      await user.selectOptions(placeSelect(), "lviv");

      await user.click(await screen.findByRole("button", { name: "Клік по карті" }));

      expect(placeSelect()).toHaveValue("");
    });

    it("confirms the choice in one short status line, without coordinates", async () => {
      const user = userEvent.setup();
      render(<Harness />);

      await user.selectOptions(placeSelect(), "kyiv");

      const status = screen.getByText(text.chosen["4km"]);
      expect(status).toHaveAttribute("role", "status");
      expect(document.body).not.toHaveTextContent("пн. ш.");
      expect(document.body).not.toHaveTextContent("Найближче місто");
    });

    it("clears the area with the cancel button", async () => {
      const user = userEvent.setup();
      render(<Harness />);
      await user.selectOptions(placeSelect(), "kyiv");

      await user.click(screen.getByRole("button", { name: text.clear }));

      expect(chosen()).toBe("none");
      expect(screen.queryByText(text.chosen["4km"])).toBeNull();
      expect(placeSelect()).toHaveValue("");
    });

    it("clears the area when the empty choice of the list is selected", async () => {
      const user = userEvent.setup();
      render(<Harness initial={{ latitude: 50.46, longitude: 30.51 }} />);

      await user.selectOptions(placeSelect(), "");

      expect(chosen()).toBe("none");
    });
  });

  describe("the size of the area", () => {
    it("offers four sizes from a city or district down to about one kilometre, 4 km chosen", () => {
      render(<Harness />);

      const group = screen.getByRole("group", { name: text.precisionLegend });
      const values = within(group)
        .getAllByRole("radio")
        .map((radio) => (radio as HTMLInputElement).value);
      expect(values).toEqual(["place", "4km", "2km", "1km"]);
      expect(size("4km")).toBeChecked();
    });

    it.each([
      { precision: "1km", cell: "50.455;30.5175" },
      { precision: "2km", cell: "50.45;30.525" },
      { precision: "4km", cell: "50.46;30.51" },
    ] as const)("snaps a clicked point to the $precision grid", async ({ precision, cell }) => {
      const user = userEvent.setup();
      render(<Harness initialPrecision={precision} />);
      await user.click(screen.getByRole("button", { name: text.showMap }));

      await user.click(await screen.findByRole("button", { name: "Клік по карті" }));

      expect(chosen()).toBe(cell);
      expect(screen.getByTestId("stub-precision")).toHaveTextContent(precision);
      expect(screen.getByText(text.chosen[precision])).toBeInTheDocument();
    });

    it("leaves only the list for a city or district: no map, no geolocation", async () => {
      stubGeolocation(vi.fn());
      const user = userEvent.setup();
      render(<Harness />);

      await user.click(size("place"));

      expect(screen.getByTestId("precision")).toHaveTextContent("place");
      expect(screen.queryByRole("button", { name: text.showMap })).toBeNull();
      expect(screen.queryByRole("button", { name: text.useMyLocation })).toBeNull();
      expect(placeSelect()).toHaveAccessibleDescription(new RegExp(text.placeOnlyHint));

      await user.selectOptions(placeSelect(), "kyiv");

      // Kyiv is listed at 50.450, 30.524; the coarsest grid puts it in the cell 50.44 / 30.54
      expect(chosen()).toBe("50.44;30.54");
      expect(screen.queryByRole("group", { name: text.mapLabel })).toBeNull();
    });

    it("snaps a place from the list again when the size changes, in either direction", async () => {
      const user = userEvent.setup();
      render(<Harness />);
      await user.selectOptions(placeSelect(), "kyiv");
      expect(chosen()).toBe("50.46;30.51");

      await user.click(size("1km"));
      expect(chosen()).toBe("50.455;30.5175");
      expect(placeSelect()).toHaveValue("kyiv");

      await user.click(size("place"));
      expect(chosen()).toBe("50.44;30.54");
      expect(placeSelect()).toHaveValue("kyiv");
    });

    it("makes a point from the map coarser in place and asks for it again when made finer", async () => {
      const user = userEvent.setup();
      render(<Harness initialPrecision="2km" />);
      await user.click(screen.getByRole("button", { name: text.showMap }));
      await user.click(await screen.findByRole("button", { name: "Клік по карті" }));
      expect(chosen()).toBe("50.45;30.525");

      await user.click(size("4km"));
      expect(chosen()).toBe("50.46;30.51");

      await user.click(size("1km"));
      expect(chosen()).toBe("none");
    });
  });

  describe("the browser's position", () => {
    it("is not offered when the browser has no geolocation", () => {
      render(<Harness />);

      expect(screen.queryByRole("button", { name: text.useMyLocation })).toBeNull();
    });

    it("sets the cell only, shows no exact value and does not open the map", async () => {
      stubGeolocation((ok) =>
        ok({ coords: { latitude: 50.450123, longitude: 30.523987 } } as GeolocationPosition),
      );
      const user = userEvent.setup();
      render(<Harness />);

      await user.click(screen.getByRole("button", { name: text.useMyLocation }));

      expect(chosen()).toBe("50.46;30.51");
      expect(screen.getByText(text.located).closest('[role="status"]')).not.toBeNull();
      expect(document.body).not.toHaveTextContent("50.450123");
      expect(document.body).not.toHaveTextContent("30.523987");
      expect(screen.queryByRole("group", { name: text.mapLabel })).toBeNull();
    });

    it.each([
      { name: "denied", code: 1, message: text.denied },
      { name: "unavailable", code: 2, message: text.unavailable },
    ])("explains a $name geolocation and leaves the choice open", async ({ code, message }) => {
      stubGeolocation((_ok, fail) => fail({ code, PERMISSION_DENIED: 1 } as GeolocationPositionError));
      const user = userEvent.setup();
      render(<Harness />);

      await user.click(screen.getByRole("button", { name: text.useMyLocation }));

      expect(screen.getByText(message).closest('[role="status"]')).not.toBeNull();
      expect(chosen()).toBe("none");
    });

    it("ignores a second press while waiting", async () => {
      const getCurrentPosition = vi.fn();
      stubGeolocation(getCurrentPosition);
      const user = userEvent.setup();
      render(<Harness />);
      const button = screen.getByRole("button", { name: text.useMyLocation });

      await user.click(button);
      await user.click(button);

      expect(getCurrentPosition).toHaveBeenCalledTimes(1);
      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(screen.getByText(text.locating)).toBeInTheDocument();
    });
  });

  describe("optional and error states", () => {
    it("marks the list required for a new profile and optional for an existing one", () => {
      const { unmount } = render(<Harness />);
      expect(placeSelect()).toBeRequired();
      unmount();

      render(<Harness optional />);
      expect(placeSelect()).not.toBeRequired();
      expect(placeSelect()).toHaveAccessibleDescription(new RegExp(text.optionalHint));
    });

    it("links an error to the list", () => {
      render(<Harness error={uk.profile.validation.locationRequired} />);

      expect(placeSelect()).toHaveAttribute("aria-invalid", "true");
      expect(placeSelect()).toHaveAccessibleDescription(
        new RegExp(uk.profile.validation.locationRequired),
      );
    });

    it("has no axe violations with a place chosen, the map shown, geolocation text and an error", async () => {
      stubGeolocation((ok) =>
        ok({ coords: { latitude: 50.45, longitude: 30.52 } } as GeolocationPosition),
      );
      const user = userEvent.setup();
      const { container } = render(<Harness error={uk.profile.validation.locationRequired} />);

      await user.click(screen.getByRole("button", { name: text.useMyLocation }));
      await user.selectOptions(placeSelect(), "kyiv-pecherskyi");
      await screen.findByRole("group", { name: text.mapLabel });

      expect(await axe(container)).toHaveNoViolations();
    });
  });
});
