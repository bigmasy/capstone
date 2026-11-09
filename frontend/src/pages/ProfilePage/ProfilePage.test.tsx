import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import App from "../../components/App/App";
import { uk } from "../../i18n/uk";
import {
  bodiesSentTo,
  calls,
  jsonResponse,
  makeProfile,
  routeFetch,
  taxonomy,
  type Routes,
} from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";

// The real map is covered in LocationMap.test.tsx
vi.mock("../../components/LocationPicker/LocationMap", async () => import("../../test/LocationMapStub"));

const text = uk.profile;
const noProfile = () => jsonResponse(404, { detail: "Profile not found" });

describe("ProfilePage", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const baseRoutes = (overrides: Routes = {}): Routes => ({
    "GET /auth/me": () => jsonResponse(200, { id: "x", email: "a@example.com", created_at: "" }),
    "GET /taxonomy": () => jsonResponse(200, taxonomy),
    ...overrides,
  });

  const renderPage = () =>
    renderWithProviders(<App />, { route: "/profile", preloadedState: loggedIn });

  describe("onboarding", () => {
    it("shows the onboarding heading and an empty form when the account has no profile", async () => {
      routeFetch(fetchMock, baseRoutes({ "GET /profiles/me": noProfile }));
      renderPage();

      expect(
        await screen.findByRole("heading", { level: 2, name: text.onboarding.title }),
      ).toBeInTheDocument();
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(uk.pages.profile.title);
      expect(screen.getByRole("textbox", { name: /^Ім’я для інших користувачів/ })).toHaveValue("");
      expect(
        screen.getByRole("button", { name: text.manage.deleteAll.trigger }),
      ).toBeInTheDocument();
    });

    it("has no axe violations", async () => {
      routeFetch(fetchMock, baseRoutes({ "GET /profiles/me": noProfile }));
      const { container } = renderPage();
      await screen.findByRole("heading", { level: 2, name: text.onboarding.title });

      expect(await axe(container)).toHaveNoViolations();
    });

    it("saves, then switches to editing with the stored district and no onboarding", async () => {
      let stored = false;
      routeFetch(
        fetchMock,
        baseRoutes({
          "GET /profiles/me": () => (stored ? jsonResponse(200, makeProfile()) : noProfile()),
          "PUT /profiles/me": () => {
            stored = true;
            return jsonResponse(200, makeProfile({ district_code: "kyiv_podilskyi" }));
          },
        }),
      );
      const user = userEvent.setup();
      renderPage();
      await screen.findByRole("heading", { level: 2, name: text.onboarding.title });

      await user.type(screen.getByRole("textbox", { name: /^Ім’я для інших користувачів/ }), "Олена");
      await user.selectOptions(screen.getByRole("combobox", { name: /^Звична інтенсивність/ }), "3");
      await user.selectOptions(screen.getByRole("combobox", { name: /^Вид спорту/ }), "swimming");
      await user.selectOptions(screen.getByRole("combobox", { name: /^Місто або район/ }), "kyiv");
      await user.click(screen.getByRole("button", { name: text.submit }));

      expect((await screen.findByText(text.saved)).closest('[role="status"]')).not.toBeNull();
      await waitFor(() =>
        expect(screen.queryByRole("heading", { level: 2, name: text.onboarding.title })).toBeNull(),
      );
      expect(screen.getByText("Збережений район: Київ, Подільський.")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: text.manage.deleteAll.trigger }),
      ).toBeInTheDocument();
      expect(screen.getByRole("textbox", { name: /^Ім’я для інших користувачів/ })).toHaveValue("Олена");
      expect(screen.getByRole("combobox", { name: /^Місто або район/ })).toHaveValue("");
      const [sent] = (await bodiesSentTo(fetchMock, "PUT /profiles/me")) as Record<string, unknown>[];
      expect(sent).toMatchObject({ latitude: 50.46, longitude: 30.51, display_name: "Олена" });
    });
  });

  describe("editing", () => {
    it("shows the stored profile without the onboarding block", async () => {
      routeFetch(
        fetchMock,
        baseRoutes({ "GET /profiles/me": () => jsonResponse(200, makeProfile({ display_name: "Іван" })) }),
      );
      renderPage();

      expect(await screen.findByDisplayValue("Іван")).toBeInTheDocument();
      expect(screen.queryByRole("heading", { name: text.onboarding.title })).toBeNull();
      expect(
        screen.getByRole("button", { name: text.manage.deleteAll.trigger }),
      ).toBeInTheDocument();
    });

    it("has no axe violations for a stored profile with functional data", async () => {
      routeFetch(
        fetchMock,
        baseRoutes({
          "GET /profiles/me": () =>
            jsonResponse(
              200,
              makeProfile({
                functional_data_consent: true,
                capabilities: [{ category: "mobility_lower", level: 2, equipment: "crutches_or_cane" }],
              }),
            ),
        }),
      );
      const { container } = renderPage();
      await screen.findByRole("group", { name: text.functional.capabilitiesLegend });

      expect(await axe(container)).toHaveNoViolations();
    });

    it("prefills the capabilities of a profile that has the consent", async () => {
      routeFetch(
        fetchMock,
        baseRoutes({
          "GET /profiles/me": () =>
            jsonResponse(
              200,
              makeProfile({
                functional_data_consent: true,
                capabilities: [{ category: "vision", level: 3, equipment: "guide_support" }],
              }),
            ),
        }),
      );
      renderPage();

      const group = await screen.findByRole("group", { name: text.functional.capabilitiesLegend });
      expect(within(group).getByRole("combobox", { name: /^Категорія/ })).toHaveValue("vision");
      expect(within(group).getByRole("combobox", { name: /^Наскільки самостійно/ })).toHaveValue("3");
      expect(within(group).getByRole("combobox", { name: /^Обладнання/ })).toHaveValue("guide_support");
    });
  });

  describe("loading and failures", () => {
    it("shows a loader with a status role while the data is on its way", async () => {
      routeFetch(fetchMock, baseRoutes({ "GET /profiles/me": () => jsonResponse(200, makeProfile()) }));
      renderPage();

      expect(screen.getByText(text.loading).closest('[role="status"]')).not.toBeNull();
      expect(await screen.findByDisplayValue("Олена")).toBeInTheDocument();
    });

    it("offers a retry when the profile cannot be loaded", async () => {
      let healthy = false;
      routeFetch(
        fetchMock,
        baseRoutes({
          "GET /profiles/me": () => (healthy ? jsonResponse(200, makeProfile()) : jsonResponse(500)),
        }),
      );
      const user = userEvent.setup();
      renderPage();

      expect(await screen.findByRole("alert")).toHaveTextContent(text.loadFailed);
      healthy = true;
      await user.click(screen.getByRole("button", { name: text.retry }));

      expect(await screen.findByDisplayValue("Олена")).toBeInTheDocument();
      expect(screen.queryByRole("alert")).toBeNull();
    });

    it("offers a retry when the taxonomy cannot be loaded", async () => {
      let healthy = false;
      routeFetch(
        fetchMock,
        baseRoutes({
          "GET /taxonomy": () => (healthy ? jsonResponse(200, taxonomy) : jsonResponse(503)),
          "GET /profiles/me": noProfile,
        }),
      );
      const user = userEvent.setup();
      renderPage();

      expect(await screen.findByRole("alert")).toHaveTextContent(text.taxonomyFailed);
      healthy = true;
      await user.click(screen.getByRole("button", { name: text.retry }));

      expect(await screen.findByRole("heading", { level: 2, name: text.onboarding.title })).toBeInTheDocument();
    });

    it("has no axe violations in the failed state", async () => {
      routeFetch(fetchMock, baseRoutes({ "GET /profiles/me": () => jsonResponse(500) }));
      const { container } = renderPage();
      await screen.findByRole("alert");

      expect(await axe(container)).toHaveNoViolations();
    });
  });

  it("requests the taxonomy without needing the profile and caches it across visits", async () => {
    routeFetch(fetchMock, baseRoutes({ "GET /profiles/me": noProfile }));
    renderPage();
    await screen.findByRole("heading", { level: 2, name: text.onboarding.title });

    expect(calls(fetchMock).filter((call) => call === "GET /taxonomy")).toHaveLength(1);
  });
});
