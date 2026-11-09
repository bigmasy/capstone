import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Toaster } from "react-hot-toast";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { ProfileOwner } from "../../api/types";
import { uk } from "../../i18n/uk";
import {
  bodiesSentTo,
  calls,
  jsonResponse,
  makeProfile,
  routeFetch,
  taxonomy,
} from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";
import ProfileForm from "./ProfileForm";

// The real map is covered in LocationMap.test.tsx; here a stub that can report a click
vi.mock("../LocationPicker/LocationMap", async () => import("../../test/LocationMapStub"));

type User = ReturnType<typeof userEvent.setup>;

const text = uk.profile;

describe("ProfileForm", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    Reflect.deleteProperty(window.navigator, "geolocation");
  });

  const renderForm = (profile?: ProfileOwner) =>
    renderWithProviders(
      <>
        <Toaster />
        <ProfileForm taxonomy={taxonomy} profile={profile} />
      </>,
      { preloadedState: loggedIn },
    );

  const field = (role: "textbox" | "combobox", name: RegExp) => screen.getByRole(role, { name });
  const submitButton = () => screen.getByRole("button", { name: text.submit });

  const placeSelect = () => field("combobox", /^Місто або район/);
  /** Chooses Kyiv in the list; the stored cell is the one that contains its centre. */
  const choosePlace = (user: User, id = "kyiv") => user.selectOptions(placeSelect(), id);

  const fillBasics = async (user: User) => {
    await user.type(field("textbox", /^Ім’я для інших користувачів/), "Олена");
    await user.selectOptions(field("combobox", /^Звична інтенсивність/), "3");
    await user.selectOptions(field("combobox", /^Вид спорту/), "swimming");
    await choosePlace(user);
  };

  const givenConsent = async (user: User) => {
    await user.click(screen.getByRole("checkbox", { name: text.functional.consent }));
  };

  describe("accessibility", () => {
    it("has no axe violations as an empty onboarding form", async () => {
      const { container } = renderForm();

      expect(await axe(container)).toHaveNoViolations();
    });

    it("has no axe violations with the consent, a capability row and a stored profile", async () => {
      const user = userEvent.setup();
      const { container } = renderForm(makeProfile({ contact: "@olena" }));

      await givenConsent(user);
      await user.click(screen.getByRole("button", { name: text.functional.add }));
      await user.selectOptions(field("combobox", /^Категорія/), "vision");

      expect(await axe(container)).toHaveNoViolations();
    });

    it("has no axe violations while errors are shown", async () => {
      const user = userEvent.setup();
      const { container } = renderForm();

      await user.click(submitButton());
      await screen.findAllByText(uk.form.validation.required, { exact: false });

      expect(await axe(container)).toHaveNoViolations();
    });

    it("groups the fields in fieldsets with legends", () => {
      renderForm();

      for (const name of [
        text.about.legend,
        text.sports.legend,
        text.location.legend,
        text.contact.legend,
        text.functional.legend,
        text.visibility.legend,
      ]) {
        expect(screen.getByRole("group", { name })).toBeInTheDocument();
      }
      expect(screen.getByRole("group", { name: text.sports.row(1) })).toBeInTheDocument();
    });

    it("announces the visibility control as a switch", () => {
      renderForm();

      expect(screen.getByRole("switch", { name: text.visibility.isVisible })).toBeChecked();
    });

    it("can be completed and submitted with the keyboard only", async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, makeProfile()));
      const user = userEvent.setup();
      renderForm();

      // Every control is reached in reading order; option lists are set with the pointer-free API
      await user.tab();
      expect(field("textbox", /^Ім’я для інших користувачів/)).toHaveFocus();
      await user.keyboard("Олена");
      await user.tab();
      expect(field("combobox", /^Район/)).toHaveFocus();
      await user.tab();
      expect(field("combobox", /^Звична інтенсивність/)).toHaveFocus();
      await user.selectOptions(field("combobox", /^Звична інтенсивність/), "3");
      await user.tab();
      expect(field("combobox", /^Вид спорту/)).toHaveFocus();
      await user.selectOptions(field("combobox", /^Вид спорту/), "swimming");
      await user.tab();
      expect(field("combobox", /^Ваш рівень/)).toHaveFocus();
      await user.tab();
      expect(screen.getByRole("button", { name: text.sports.remove(1) })).toHaveFocus();
      await user.tab();
      expect(screen.getByRole("button", { name: text.sports.add })).toHaveFocus();
      await user.tab();
      expect(placeSelect()).toHaveFocus();
      await user.selectOptions(placeSelect(), "kyiv");
      // The map opened by the choice is passed through and left again: it is no keyboard trap
      await user.tab();
      expect(screen.getByRole("button", { name: text.location.hideMap })).toHaveFocus();
      await screen.findByRole("button", { name: "Клік по карті" });
      await user.tab();
      expect(screen.getByRole("button", { name: "Клік по карті" })).toHaveFocus();
      await user.tab();
      expect(screen.getByRole("link", { name: text.location.attribution })).toHaveFocus();
      for (const label of [
        text.location.north,
        text.location.west,
        text.location.east,
        text.location.south,
        text.location.clear,
      ]) {
        await user.tab();
        expect(screen.getByRole("button", { name: label })).toHaveFocus();
      }
      await user.tab();
      expect(field("textbox", /^Контакт для зв’язку/)).toHaveFocus();
      await user.keyboard("{Enter}");

      await waitFor(() => expect(calls(fetchMock)).toEqual(["PUT /profiles/me"]));
    });
  });

  describe("contact", () => {
    it("is labelled with the kinds of contact, states who sees it and the API limit", () => {
      renderForm();

      const contact = field("textbox", /^Контакт для зв’язку \(телефон, Telegram, email\)/);
      expect(contact).toHaveAccessibleDescription(new RegExp("лише людина, чиє запрошення ви приймаєте"));
      expect(contact).toHaveAccessibleDescription(/До 120 символів/);
      expect(contact).not.toBeRequired();
    });

    it("warns that invitations need a contact while the field is empty and stops when it is filled", async () => {
      const user = userEvent.setup();
      renderForm();

      expect(screen.getByText(text.contact.missing)).toBeInTheDocument();
      await user.type(field("textbox", /^Контакт для зв’язку/), "@olena");
      expect(screen.queryByText(text.contact.missing)).toBeNull();
      await user.clear(field("textbox", /^Контакт для зв’язку/));
      expect(screen.getByText(text.contact.missing)).toBeInTheDocument();
    });

    it("does not warn for a stored profile that has a contact", () => {
      renderForm(makeProfile({ contact: "@olena" }));

      expect(screen.queryByText(text.contact.missing)).toBeNull();
    });

    it("has no axe violations with the notice shown", async () => {
      const { container } = renderForm(makeProfile({ contact: null }));

      expect(screen.getByText(text.contact.missing)).toBeInTheDocument();
      expect(await axe(container)).toHaveNoViolations();
    });
  });

  describe("validation", () => {
    it("shows linked errors and focuses the first invalid field without calling the server", async () => {
      const user = userEvent.setup();
      renderForm();

      await user.click(submitButton());

      const name = await screen.findByRole("textbox", { name: /^Ім’я для інших користувачів/ });
      await waitFor(() => expect(name).toHaveFocus());
      expect(name).toHaveAttribute("aria-invalid", "true");
      expect(name).toHaveAccessibleDescription(new RegExp(uk.form.validation.required));
      expect(field("combobox", /^Звична інтенсивність/)).toHaveAttribute("aria-invalid", "true");
      expect(field("combobox", /^Вид спорту/)).toHaveAttribute("aria-invalid", "true");
      expect(placeSelect()).toHaveAttribute("aria-invalid", "true");
      expect(placeSelect()).toHaveAccessibleDescription(new RegExp(text.validation.locationRequired));
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("rejects a name over 60 characters and a contact over 120", async () => {
      const user = userEvent.setup();
      renderForm();

      await user.click(field("textbox", /^Ім’я для інших користувачів/));
      await user.paste("я".repeat(61));
      await user.click(field("textbox", /^Контакт для зв’язку/));
      await user.paste("x".repeat(121));
      await user.click(submitButton());

      expect(await screen.findByText(text.validation.displayNameMax)).toBeInTheDocument();
      expect(screen.getByText(text.validation.contactMax)).toBeInTheDocument();
    });

    it("requires a category and a level for every capability row once the consent is on", async () => {
      const user = userEvent.setup();
      renderForm();

      await fillBasics(user);
      await givenConsent(user);
      await user.click(screen.getByRole("button", { name: text.functional.add }));
      await user.click(submitButton());

      const category = await screen.findByRole("combobox", { name: /^Категорія/ });
      await waitFor(() => expect(category).toHaveFocus());
      expect(category).toHaveAttribute("aria-invalid", "true");
      expect(field("combobox", /^Наскільки самостійно/)).toHaveAttribute("aria-invalid", "true");
      expect(fetchMock).not.toHaveBeenCalled();
    });
  });

  describe("payload", () => {
    it("sends the whole profile in snake_case with numeric fields", async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, makeProfile()));
      const user = userEvent.setup();
      renderForm();

      await fillBasics(user);
      await user.selectOptions(field("combobox", /^Район/), "kyiv_podilskyi");
      await user.selectOptions(field("combobox", /^Ваш рівень/), "advanced");
      await user.type(field("textbox", /^Контакт для зв’язку/), "@olena");
      await user.click(screen.getByRole("switch", { name: text.visibility.isVisible }));
      await user.click(submitButton());

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
      expect(await bodiesSentTo(fetchMock, "PUT /profiles/me")).toEqual([
        {
          display_name: "Олена",
          district_code: "kyiv_podilskyi",
          intensity: 3,
          is_visible: false,
          latitude: 50.46,
          longitude: 30.51,
          sports: [{ sport: "swimming", skill: "advanced" }],
          capabilities: [],
          functional_data_consent: false,
          contact: "@olena",
        },
      ]);
    });

    it("sends the capabilities when the consent is on", async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, makeProfile()));
      const user = userEvent.setup();
      renderForm();

      await fillBasics(user);
      await givenConsent(user);
      await user.click(screen.getByRole("button", { name: text.functional.add }));
      await user.selectOptions(field("combobox", /^Категорія/), "vision");
      await user.selectOptions(field("combobox", /^Наскільки самостійно/), "2");
      await user.selectOptions(field("combobox", /^Обладнання/), "guide_support");
      await user.click(submitButton());

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
      const [body] = (await bodiesSentTo(fetchMock, "PUT /profiles/me")) as Record<string, unknown>[];
      expect(body).toMatchObject({
        functional_data_consent: true,
        capabilities: [{ category: "vision", level: 2, equipment: "guide_support" }],
      });
    });

    it("removes the capabilities from the payload when the consent is switched off again", async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, makeProfile()));
      const user = userEvent.setup();
      renderForm();

      await fillBasics(user);
      await givenConsent(user);
      await user.click(screen.getByRole("button", { name: text.functional.add }));
      await user.selectOptions(field("combobox", /^Категорія/), "endurance");
      await user.selectOptions(field("combobox", /^Наскільки самостійно/), "4");
      await givenConsent(user);
      expect(screen.queryByRole("group", { name: text.functional.capabilitiesLegend })).toBeNull();
      await user.click(submitButton());

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
      const [body] = (await bodiesSentTo(fetchMock, "PUT /profiles/me")) as Record<string, unknown>[];
      expect(body).toMatchObject({ functional_data_consent: false, capabilities: [] });
    });

    it("never sends capabilities without the consent, even for a stored profile that had them", async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, makeProfile()));
      const user = userEvent.setup();
      renderForm(
        makeProfile({
          functional_data_consent: true,
          capabilities: [{ category: "vision", level: 3, equipment: null }],
        }),
      );

      expect(screen.getByRole("checkbox", { name: text.functional.consent })).toBeChecked();
      await givenConsent(user);
      await choosePlace(user);
      await user.click(submitButton());

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
      const [body] = (await bodiesSentTo(fetchMock, "PUT /profiles/me")) as Record<string, unknown>[];
      expect(body).toMatchObject({ functional_data_consent: false, capabilities: [] });
    });
  });

  describe("consent and capabilities", () => {
    it("states what is collected and who sees what next to the checkbox", () => {
      renderForm();

      const group = screen.getByRole("group", { name: text.functional.legend });
      expect(within(group).getByText(text.functional.collected)).toBeInTheDocument();
      expect(within(group).getByText(text.functional.visibility)).toBeInTheDocument();
      expect(text.functional.visibility).toMatch(/низький, середній або високий/);
      expect(within(group).getByRole("checkbox", { name: text.functional.consent })).not.toBeChecked();
    });

    it("shows the capabilities editor only after the consent", async () => {
      const user = userEvent.setup();
      renderForm();
      const legend = { name: text.functional.capabilitiesLegend };

      expect(screen.queryByRole("group", legend)).toBeNull();
      await givenConsent(user);
      expect(screen.getByRole("group", legend)).toBeInTheDocument();
    });

    it("offers only the equipment of the chosen category and resets a choice that no longer fits", async () => {
      const user = userEvent.setup();
      renderForm();
      await givenConsent(user);
      await user.click(screen.getByRole("button", { name: text.functional.add }));
      const category = field("combobox", /^Категорія/);

      expect(screen.queryByRole("combobox", { name: /^Обладнання/ })).toBeNull();
      await user.selectOptions(category, "mobility_lower");
      const equipment = field("combobox", /^Обладнання/);
      const labels = () => within(equipment).getAllByRole("option").map((o) => o.textContent);
      expect(labels()).toEqual([
        text.functional.equipmentNone,
        "Активний (спортивний) візок",
        "Хендбайк",
        "Милиці або тростина",
        "Протез нижньої кінцівки",
        "Бігальний протез",
      ]);

      await user.selectOptions(equipment, "wheelchair_active");
      await user.selectOptions(category, "balance_posture");
      expect(labels()).toEqual([text.functional.equipmentNone, "Милиці або тростина"]);
      expect(field("combobox", /^Обладнання/)).toHaveValue("");

      await user.selectOptions(category, "endurance");
      expect(screen.queryByRole("combobox", { name: /^Обладнання/ })).toBeNull();
    });

    it("does not offer a category twice and stops adding rows when all are used", async () => {
      const user = userEvent.setup();
      renderForm();
      await givenConsent(user);
      const add = screen.getByRole("button", { name: text.functional.add });

      await user.click(add);
      await user.selectOptions(field("combobox", /^Категорія/), "vision");
      await user.click(add);
      const second = screen.getAllByRole("combobox", { name: /^Категорія/ })[1] as HTMLElement;
      expect(within(second).queryByRole("option", { name: "Зір і орієнтація" })).toBeNull();

      for (let i = 0; i < 5; i += 1) {
        await user.selectOptions(
          screen.getAllByRole("combobox", { name: /^Категорія/ }).at(-1) as HTMLElement,
          within(screen.getAllByRole("combobox", { name: /^Категорія/ }).at(-1) as HTMLElement)
            .getAllByRole("option")[1] as HTMLElement,
        );
        await user.click(add);
      }
      expect(screen.getAllByRole("combobox", { name: /^Категорія/ })).toHaveLength(7);
      expect(add).toHaveAttribute("aria-disabled", "true");
      expect(screen.getByText(text.functional.allCategoriesAdded)).toBeInTheDocument();
    });

    it("moves focus to the new row and, after a removal, to the add button", async () => {
      const user = userEvent.setup();
      renderForm();
      await givenConsent(user);
      const add = screen.getByRole("button", { name: text.functional.add });

      await user.click(add);
      expect(field("combobox", /^Категорія/)).toHaveFocus();
      await user.click(screen.getByRole("button", { name: text.functional.remove(1) }));

      expect(screen.queryByRole("combobox", { name: /^Категорія/ })).toBeNull();
      expect(add).toHaveFocus();
    });
  });

  describe("sports", () => {
    it("adds a row with focus on its sport and offers each sport once", async () => {
      const user = userEvent.setup();
      renderForm();

      await user.selectOptions(field("combobox", /^Вид спорту/), "swimming");
      await user.click(screen.getByRole("button", { name: text.sports.add }));

      const selects = screen.getAllByRole("combobox", { name: /^Вид спорту/ });
      expect(selects).toHaveLength(2);
      expect(selects[1]).toHaveFocus();
      expect(within(selects[1] as HTMLElement).queryByRole("option", { name: "Плавання" })).toBeNull();
      expect(within(selects[0] as HTMLElement).getByRole("option", { name: "Плавання" })).toBeInTheDocument();
    });

    it("removes a row, hands focus to the add button and keeps the last row", async () => {
      const user = userEvent.setup();
      renderForm();
      const add = screen.getByRole("button", { name: text.sports.add });
      await user.click(add);

      await user.click(screen.getByRole("button", { name: text.sports.remove(1) }));

      expect(screen.getAllByRole("combobox", { name: /^Вид спорту/ })).toHaveLength(1);
      expect(add).toHaveFocus();
      const last = screen.getByRole("button", { name: text.sports.remove(1) });
      expect(last).toHaveAttribute("aria-disabled", "true");
      expect(last).toHaveAccessibleDescription(text.sports.lastRow);
      await user.click(last);
      expect(screen.getAllByRole("combobox", { name: /^Вид спорту/ })).toHaveLength(1);
    });

    it("allows at most 10 sports", async () => {
      const user = userEvent.setup();
      renderForm();
      const add = screen.getByRole("button", { name: text.sports.add });

      for (let i = 0; i < 12; i += 1) await user.click(add);

      expect(screen.getAllByRole("combobox", { name: /^Вид спорту/ })).toHaveLength(10);
      expect(add).toHaveAttribute("aria-disabled", "true");
      expect(screen.getByText(text.sports.limitReached)).toBeInTheDocument();
    });
  });

  describe("location", () => {
    it("says that the location is rounded to an area before storage and never shown back", () => {
      renderForm();

      const group = screen.getByRole("group", { name: text.location.legend });
      expect(within(group).getByText(text.location.explanation)).toBeInTheDocument();
      expect(text.location.explanation).toMatch(/4 км × 4 км/);
      expect(text.location.explanation).toMatch(/Точні координати не зберігаються/);
    });

    it("has no coordinate inputs: the point is chosen from the list, the map or the browser", () => {
      renderForm();

      expect(screen.queryByRole("textbox", { name: /Широта|Довгота/ })).toBeNull();
      expect(placeSelect()).toBeRequired();
    });

    it("sends the centre of the cell of the chosen place, not the place itself", async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, makeProfile()));
      const user = userEvent.setup();
      renderForm();

      await fillBasics(user);
      await user.click(submitButton());

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
      const [body] = (await bodiesSentTo(fetchMock, "PUT /profiles/me")) as Record<string, unknown>[];
      // Kyiv is listed at 50.450, 30.524; the cell around it has its centre at 50.46, 30.51
      expect(body).toMatchObject({ latitude: 50.46, longitude: 30.51 });
    });

    it("sends the centre of the cell of a clicked point, never the clicked point", async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, makeProfile()));
      const user = userEvent.setup();
      renderForm();

      await fillBasics(user);
      await user.click(screen.getByRole("button", { name: "Клік по карті" }));
      await user.click(submitButton());

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
      const [raw] = await bodiesSentTo(fetchMock, "PUT /profiles/me");
      expect(raw).toMatchObject({ latitude: 50.46, longitude: 30.51 });
      const json = JSON.stringify(raw);
      expect(json).not.toContain("50.4517");
      expect(json).not.toContain("30.5249");
    });
  });

  describe("saving", () => {
    it("shows a success status, clears the coordinates and does not echo them", async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, makeProfile()));
      const user = userEvent.setup();
      renderForm();

      await fillBasics(user);
      await user.click(submitButton());

      const toastText = await screen.findByText(text.saved);
      expect(toastText.closest('[role="status"]')).not.toBeNull();
      await waitFor(() => expect(screen.getByText(text.location.areaNone)).toBeInTheDocument());
      expect(placeSelect()).toHaveValue("");
      expect(document.body).not.toHaveTextContent(/50\.4\d/);
    });

    it("maps a 422 to the fields, focuses the first one and never shows the server text", async () => {
      routeFetch(fetchMock, {
        "PUT /profiles/me": () =>
          jsonResponse(422, {
            detail: [
              { type: "value_error", loc: ["body", "display_name"], msg: "SERVER-TEXT Олена" },
              { type: "enum", loc: ["body", "sports", 0, "sport"], msg: "SERVER-TEXT" },
            ],
          }),
      });
      const user = userEvent.setup();
      renderForm();

      await fillBasics(user);
      await user.click(submitButton());

      const name = field("textbox", /^Ім’я для інших користувачів/);
      await waitFor(() => expect(name).toHaveAttribute("aria-invalid", "true"));
      expect(name).toHaveAccessibleDescription(new RegExp(text.server.noControlCharacters));
      await waitFor(() => expect(name).toHaveFocus());
      expect(field("combobox", /^Вид спорту/)).toHaveAccessibleDescription(
        new RegExp(text.server.notAllowed),
      );
      expect(await screen.findByRole("alert")).toHaveTextContent(text.saveFailed);
      expect(document.body).not.toHaveTextContent("SERVER-TEXT");
      expect(screen.queryByText(text.saved)).toBeNull();
    });

    it.each([
      { name: "500", response: () => jsonResponse(500), message: text.connectionProblem },
      { name: "429", response: () => jsonResponse(429), message: text.tooManyRequests },
      { name: "403", response: () => jsonResponse(403), message: text.saveFailed },
    ])("announces a failed save ($name) in an alert and keeps the values", async ({ response, message }) => {
      fetchMock.mockResolvedValue(response());
      const user = userEvent.setup();
      renderForm();

      await fillBasics(user);
      await user.click(submitButton());

      expect(await screen.findByRole("alert")).toHaveTextContent(message);
      expect(placeSelect()).toHaveValue("kyiv");
    });

    it("announces a network failure", async () => {
      fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
      const user = userEvent.setup();
      renderForm();

      await fillBasics(user);
      await user.click(submitButton());

      expect(await screen.findByRole("alert")).toHaveTextContent(text.connectionProblem);
    });

    it("uses aria-disabled while pending and ignores a second submit", async () => {
      let answer: (response: Response) => void = () => undefined;
      fetchMock.mockReturnValue(new Promise<Response>((resolve) => (answer = resolve)));
      const user = userEvent.setup();
      renderForm();

      await fillBasics(user);
      const button = submitButton();
      await user.click(button);

      await waitFor(() => expect(button).toHaveAttribute("aria-disabled", "true"));
      expect(button).not.toBeDisabled();
      expect(screen.getByText(text.saving).closest('[role="status"]')).not.toBeNull();
      await user.click(button);
      await user.type(field("textbox", /^Контакт для зв’язку/), "{Enter}");
      expect(fetchMock).toHaveBeenCalledTimes(1);

      answer(jsonResponse(200, makeProfile()));
      await waitFor(() => expect(button).not.toHaveAttribute("aria-disabled"));
    });
  });

  describe("stored profile", () => {
    it("is prefilled, shows the stored district and says the stored area is kept", () => {
      renderForm(
        makeProfile({
          display_name: "Іван",
          district_code: "kyiv_obolonskyi",
          intensity: 4,
          contact: "@ivan",
          sports: [
            { sport: "archery", skill: "advanced" },
            { sport: "rowing", skill: "beginner" },
          ],
        }),
      );

      expect(field("textbox", /^Ім’я для інших користувачів/)).toHaveValue("Іван");
      expect(field("combobox", /^Район/)).toHaveValue("kyiv_obolonskyi");
      expect(field("combobox", /^Звична інтенсивність/)).toHaveValue("4");
      expect(field("textbox", /^Контакт для зв’язку/)).toHaveValue("@ivan");
      expect(screen.getAllByRole("combobox", { name: /^Вид спорту/ })).toHaveLength(2);
      const group = screen.getByRole("group", { name: text.location.legend });
      expect(within(group).getByText("Збережений район: Київ, Оболонський.")).toBeInTheDocument();
      expect(within(group).getByText(text.location.keepStored, { exact: false })).toBeInTheDocument();
      expect(placeSelect()).toHaveValue("");
      expect(screen.getByText(text.location.areaNone)).toBeInTheDocument();
    });

    it("says so when the stored profile has no district", () => {
      renderForm(makeProfile({ district_code: null }));

      expect(screen.getByText(text.location.storedNoDistrict)).toBeInTheDocument();
    });

    describe("location", () => {
      const sentBodies = async () =>
        (await bodiesSentTo(fetchMock, "PUT /profiles/me")) as Record<string, unknown>[];

      it("makes choosing a place optional and explains that the stored area is kept", () => {
        renderForm(makeProfile());

        expect(placeSelect()).not.toBeRequired();
        expect(placeSelect()).toHaveAccessibleDescription(new RegExp(text.location.optionalHint));
        expect(text.location.keepStored).toMatch(/Збережена ділянка лишиться без змін/);
      });

      it("keeps the place required on the first save", () => {
        renderForm();

        expect(placeSelect()).toBeRequired();
        expect(screen.queryByText(text.location.keepStored, { exact: false })).toBeNull();
      });

      it("omits both coordinates from the payload when no place was chosen", async () => {
        fetchMock.mockResolvedValue(jsonResponse(200, makeProfile()));
        const user = userEvent.setup();
        renderForm(makeProfile());

        await user.click(submitButton());

        await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
        const [body] = await sentBodies();
        expect(body).toBeDefined();
        expect(body).not.toHaveProperty("latitude");
        expect(body).not.toHaveProperty("longitude");
        expect(body).toMatchObject({ display_name: "Олена", intensity: 3 });
      });

      it("omits the coordinates again after the choice was cancelled", async () => {
        fetchMock.mockResolvedValue(jsonResponse(200, makeProfile()));
        const user = userEvent.setup();
        renderForm(makeProfile());

        await choosePlace(user, "lviv");
        await user.click(screen.getByRole("button", { name: text.location.clear }));
        await user.click(submitButton());

        await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
        expect(JSON.stringify((await sentBodies())[0])).not.toMatch(/latitude|longitude/);
      });

      it("sends the cell centre when a place is chosen on an existing profile", async () => {
        fetchMock.mockResolvedValue(jsonResponse(200, makeProfile()));
        const user = userEvent.setup();
        renderForm(makeProfile());

        await choosePlace(user, "kyiv-pecherskyi");
        await user.click(submitButton());

        await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
        // Pecherskyi is listed at 50.429, 30.553: cell 50.42 / 30.57 in the grid of the server
        expect((await sentBodies())[0]).toMatchObject({ latitude: 50.42, longitude: 30.57 });
      });

      it("maps location_required to the list of places with a fixed text and focuses it", async () => {
        routeFetch(fetchMock, {
          "PUT /profiles/me": () =>
            jsonResponse(422, {
              detail: [
                { type: "location_required", loc: ["body", "latitude"], msg: "SERVER-TEXT 50.45" },
                { type: "location_required", loc: ["body", "longitude"], msg: "SERVER-TEXT 30.52" },
              ],
            }),
        });
        const user = userEvent.setup();
        renderForm(makeProfile());

        await user.click(submitButton());

        await waitFor(() => expect(placeSelect()).toHaveAttribute("aria-invalid", "true"));
        await waitFor(() => expect(placeSelect()).toHaveFocus());
        expect(placeSelect()).toHaveAccessibleDescription(new RegExp(text.server.locationRequired));
        expect(document.body).not.toHaveTextContent("SERVER-TEXT");
      });

      it("maps location_incomplete to the list of places and keeps the chosen area", async () => {
        routeFetch(fetchMock, {
          "PUT /profiles/me": () =>
            jsonResponse(422, {
              detail: [{ type: "location_incomplete", loc: ["body"], msg: "SERVER-TEXT" }],
            }),
        });
        const user = userEvent.setup();
        renderForm(makeProfile());

        await choosePlace(user);
        await user.click(submitButton());

        await waitFor(() => expect(placeSelect()).toHaveAttribute("aria-invalid", "true"));
        await waitFor(() => expect(placeSelect()).toHaveFocus());
        expect(placeSelect()).toHaveAccessibleDescription(new RegExp(text.server.locationIncomplete));
        expect(placeSelect()).toHaveValue("kyiv");
        expect(document.body).not.toHaveTextContent("SERVER-TEXT");
      });

      it("has no axe violations for an existing profile with the optional location", async () => {
        const { container } = renderForm(makeProfile());

        expect(await axe(container)).toHaveNoViolations();
      });

      it("has no axe violations with a place chosen, the map shown and an error", async () => {
        routeFetch(fetchMock, {
          "PUT /profiles/me": () =>
            jsonResponse(422, {
              detail: [{ type: "location_incomplete", loc: ["body"], msg: "x" }],
            }),
        });
        const user = userEvent.setup();
        const { container } = renderForm(makeProfile());

        await choosePlace(user);
        await screen.findByRole("group", { name: text.location.mapLabel });
        expect(await axe(container)).toHaveNoViolations();

        await user.click(submitButton());
        await screen.findAllByText(text.server.locationIncomplete);
        expect(await axe(container)).toHaveNoViolations();
      });
    });
  });
});
