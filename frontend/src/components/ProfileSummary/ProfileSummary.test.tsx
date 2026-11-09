import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import { jsonResponse, makeProfile, routeFetch, taxonomy } from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";
import ProfileSummary from "./ProfileSummary";

describe("ProfileSummary", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const renderSummary = () =>
    renderWithProviders(<ProfileSummary />, { preloadedState: loggedIn });

  it("summarises the profile with Ukrainian labels and links to editing", async () => {
    routeFetch(fetchMock, {
      "GET /taxonomy": () => jsonResponse(200, taxonomy),
      "GET /profiles/me": () =>
        jsonResponse(
          200,
          makeProfile({
            display_name: "Олена",
            district_code: "kyiv_podilskyi",
            intensity: 4,
            sports: [
              { sport: "swimming", skill: "advanced" },
              { sport: "archery", skill: "beginner" },
            ],
            is_visible: false,
            functional_data_consent: true,
          }),
        ),
    });
    const { container } = renderSummary();

    expect(await screen.findByRole("heading", { level: 2, name: uk.pages.home.summaryHeading })).toBeInTheDocument();
    expect(screen.getByText("Олена")).toBeInTheDocument();
    expect(screen.getByText("Київ, Подільський")).toBeInTheDocument();
    expect(screen.getByText("4: висока")).toBeInTheDocument();
    const sports = screen.getAllByRole("listitem").map((item) => item.textContent);
    expect(sports).toContain("Плавання (просунутий)");
    expect(sports).toContain("Стрільба з лука (початківець)");
    expect(screen.getByText(uk.profile.summary.hidden)).toBeInTheDocument();
    expect(screen.getByText(uk.profile.summary.consentGiven)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: uk.pages.home.editProfile })).toHaveAttribute(
      "href",
      "/profile",
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("does not show the contact or the functional answers", async () => {
    routeFetch(fetchMock, {
      "GET /taxonomy": () => jsonResponse(200, taxonomy),
      "GET /profiles/me": () =>
        jsonResponse(
          200,
          makeProfile({
            contact: "secret-contact@example.com",
            functional_data_consent: true,
            capabilities: [{ category: "vision", level: 1, equipment: "guide_support" }],
          }),
        ),
    });
    renderSummary();

    await screen.findByText("Олена");

    expect(document.body).not.toHaveTextContent("secret-contact");
    expect(document.body).not.toHaveTextContent("Зір і орієнтація");
    expect(document.body).not.toHaveTextContent("Супровідник");
  });

  it("invites the user to create a profile when there is none", async () => {
    routeFetch(fetchMock, {
      "GET /taxonomy": () => jsonResponse(200, taxonomy),
      "GET /profiles/me": () => jsonResponse(404, { detail: "none" }),
    });
    const { container } = renderSummary();

    expect(await screen.findByText(uk.pages.home.noProfile)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: uk.pages.home.createProfile })).toHaveAttribute(
      "href",
      "/profile",
    );
    expect(screen.queryByRole("alert")).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("reports a failure with a retry button", async () => {
    let healthy = false;
    routeFetch(fetchMock, {
      "GET /taxonomy": () => jsonResponse(200, taxonomy),
      "GET /profiles/me": () => (healthy ? jsonResponse(200, makeProfile()) : jsonResponse(500)),
    });
    const user = userEvent.setup();
    renderSummary();

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(uk.pages.home.summaryFailed)).toBeInTheDocument();
    healthy = true;
    await user.click(screen.getByRole("button", { name: uk.profile.retry }));

    expect(await screen.findByText("Олена")).toBeInTheDocument();
  });

  it("shows a loading status first", () => {
    fetchMock.mockReturnValue(new Promise<Response>(() => undefined));
    renderSummary();

    expect(screen.getByText(uk.profile.loading).closest('[role="status"]')).not.toBeNull();
  });
});
