import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
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
  optional?: boolean;
  error?: string;
}

/** Holds the value the way the form does and shows it, so a test can read what was chosen. */
const Harness = ({ initial = null, optional = false, error }: HarnessProps) => {
  const [value, setValue] = useState<LocationValue | null>(initial);
  return (
    <>
      <LocationPicker value={value} onChange={setValue} optional={optional} error={error} />
      <span data-testid="value">{value ? `${value.latitude};${value.longitude}` : "none"}</span>
    </>
  );
};

const chosen = () => screen.getByTestId("value").textContent;
const placeSelect = () => screen.getByRole("combobox", { name: /^Місто або район/ });

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
      expect(text.mapNote).toBe(
        "Карта завантажується з OpenStreetMap; сервер карт бачить лише ділянку карти, яку ви переглядаєте.",
      );
      expect(screen.getByText(text.areaNone)).toBeInTheDocument();
      expect(screen.getByText(text.previewNote)).toBeInTheDocument();
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

    it("offers no direction buttons and no cancel button", () => {
      render(<Harness />);

      expect(screen.queryByRole("group", { name: text.nudgeLegend })).toBeNull();
      expect(screen.queryByRole("button", { name: text.clear })).toBeNull();
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

    it("shows the attribution link, the keyboard help and the pointer help", async () => {
      const user = userEvent.setup();
      render(<Harness />);

      await user.click(screen.getByRole("button", { name: text.showMap }));
      await screen.findByRole("group", { name: text.mapLabel });

      const link = screen.getByRole("link", { name: "© OpenStreetMap contributors" });
      expect(link).toHaveAttribute("href", "https://www.openstreetmap.org/copyright");
      expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
      expect(screen.getByText(text.mapKeyboardHint)).toBeInTheDocument();
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
      await user.selectOptions(placeSelect(), "kyiv");

      await user.click(await screen.findByRole("button", { name: text.north }));

      expect(placeSelect()).toHaveValue("");
    });

    it("describes the area in words, with the nearest listed city", async () => {
      const user = userEvent.setup();
      render(<Harness />);

      await user.selectOptions(placeSelect(), "kyiv");

      const status = screen.getByText(/^Обрана ділянка/);
      expect(status).toHaveAttribute("role", "status");
      expect(status).toHaveTextContent(
        "Обрана ділянка: від 50.44° пн. ш. до 50.48° пн. ш. і від 30.48° сх. д. до 30.54° сх. д., приблизно 4 км × 4 км.",
      );
      expect(status).toHaveTextContent("Найближче місто зі списку: Київ, близько 1 км від центру ділянки.");
      expect(screen.getByText(text.previewNote)).toBeInTheDocument();
    });

    it("words a centre that lies within a kilometre of a city centre differently", () => {
      expect(text.nearest("Київ", 0)).toBe("Центр ділянки в межах 1 км від центру міста Київ.");
      expect(text.nearest("Київ", 4)).toBe("Найближче місто зі списку: Київ, близько 4 км від центру ділянки.");
    });

    it("writes southern and western edges with their own suffix", () => {
      render(<Harness initial={{ latitude: -33.86, longitude: -70.65 }} />);

      expect(screen.getByText(/^Обрана ділянка/)).toHaveTextContent(
        "від 33.88° пд. ш. до 33.84° пд. ш. і від 70.68° зх. д. до 70.62° зх. д.",
      );
    });

    it("clears the area with the cancel button", async () => {
      const user = userEvent.setup();
      render(<Harness />);
      await user.selectOptions(placeSelect(), "kyiv");

      await user.click(screen.getByRole("button", { name: text.clear }));

      expect(chosen()).toBe("none");
      expect(screen.getByText(text.areaNone)).toBeInTheDocument();
      expect(placeSelect()).toHaveValue("");
    });

    it("clears the area when the empty choice of the list is selected", async () => {
      const user = userEvent.setup();
      render(<Harness initial={{ latitude: 50.46, longitude: 30.51 }} />);

      await user.selectOptions(placeSelect(), "");

      expect(chosen()).toBe("none");
    });
  });

  describe("the direction buttons", () => {
    it("move the area by exactly one cell", async () => {
      const user = userEvent.setup();
      render(<Harness initial={{ latitude: 50.46, longitude: 30.51 }} />);

      const group = screen.getByRole("group", { name: text.nudgeLegend });
      await user.click(within(group).getByRole("button", { name: text.north }));
      expect(chosen()).toBe("50.5;30.51");
      await user.click(within(group).getByRole("button", { name: text.east }));
      expect(chosen()).toBe("50.5;30.57");
      await user.click(within(group).getByRole("button", { name: text.south }));
      await user.click(within(group).getByRole("button", { name: text.south }));
      expect(chosen()).toBe("50.42;30.57");
      await user.click(within(group).getByRole("button", { name: text.west }));
      expect(chosen()).toBe("50.42;30.51");
    });

    it("also react to the arrow keys while a direction button has the focus", async () => {
      const user = userEvent.setup();
      render(<Harness initial={{ latitude: 50.46, longitude: 30.51 }} />);

      screen.getByRole("button", { name: text.north }).focus();
      await user.keyboard("{ArrowRight}");
      expect(chosen()).toBe("50.46;30.57");
      await user.keyboard("{ArrowUp}");
      expect(chosen()).toBe("50.5;30.57");
      await user.keyboard("{ArrowLeft}{ArrowLeft}");
      expect(chosen()).toBe("50.5;30.45");
      await user.keyboard("{ArrowDown}");
      expect(chosen()).toBe("50.46;30.45");
    });

    it("keep the area on the grid and ask the open map to follow", async () => {
      const user = userEvent.setup();
      render(<Harness initial={{ latitude: 50.46, longitude: 30.51 }} />);
      await user.click(screen.getByRole("button", { name: text.showMap }));
      await screen.findByRole("group", { name: text.mapLabel });

      await user.click(screen.getByRole("button", { name: text.east }));

      expect(screen.getByTestId("stub-value")).toHaveTextContent("50.46;30.57");
      expect(screen.getByTestId("stub-recenter")).toHaveTextContent("1");
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
