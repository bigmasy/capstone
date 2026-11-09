import { describe, expect, it } from "vitest";
import { uk } from "../../i18n/uk";
import { makeProfile, taxonomy } from "../../test/api";
import {
  buildInitialValues,
  buildProfileSchema,
  equipmentFor,
  toProfilePut,
  type ProfileFormValues,
} from "./profileValues";

function makeValues(overrides: Partial<ProfileFormValues> = {}): ProfileFormValues {
  return {
    display_name: "  Олена ",
    district_code: "",
    intensity: "3",
    is_visible: true,
    location: { latitude: 50.46, longitude: 30.51 },
    sports: [{ sport: "swimming", skill: "beginner" }],
    functional_data_consent: false,
    capabilities: [],
    contact: "   ",
    ...overrides,
  };
}

describe("equipmentFor", () => {
  it("offers only equipment that fits the category", () => {
    expect(equipmentFor(taxonomy, "vision")).toEqual(["guide_support"]);
    expect(equipmentFor(taxonomy, "balance_posture")).toEqual(["crutches_or_cane"]);
    expect(equipmentFor(taxonomy, "endurance")).toEqual([]);
    expect(equipmentFor(taxonomy, "")).toEqual([]);
  });
});

describe("toProfilePut", () => {
  it("builds a snake_case body with numbers and nulls for empty optional fields", () => {
    expect(toProfilePut(makeValues())).toEqual({
      display_name: "Олена",
      district_code: null,
      intensity: 3,
      is_visible: true,
      latitude: 50.46,
      longitude: 30.51,
      sports: [{ sport: "swimming", skill: "beginner" }],
      capabilities: [],
      functional_data_consent: false,
      contact: null,
    });
  });

  it("leaves both coordinate keys out when no area was chosen", () => {
    const body = toProfilePut(makeValues({ location: null }));

    expect(body).not.toHaveProperty("latitude");
    expect(body).not.toHaveProperty("longitude");
    expect(JSON.stringify(body)).not.toMatch(/latitude|longitude/);
  });

  it.each([
    { name: "a point inside a cell", point: { latitude: 50.4501, longitude: 30.5236 }, centre: [50.46, 30.51] },
    { name: "a point on a cell edge", point: { latitude: 50.44, longitude: 30.48 }, centre: [50.46, 30.51] },
    { name: "negative coordinates", point: { latitude: -33.8688, longitude: -70.6693 }, centre: [-33.86, -70.65] },
  ])("sends the cell centre, never the exact point ($name)", ({ point, centre }) => {
    const body = toProfilePut(makeValues({ location: point }));

    expect([body.latitude, body.longitude]).toEqual(centre);
    expect(JSON.stringify(body)).not.toContain(String(point.latitude));
    expect(JSON.stringify(body)).not.toContain(String(point.longitude));
  });

  it("leaves the capabilities out when the consent is off, whatever the form holds", () => {
    const body = toProfilePut(
      makeValues({
        functional_data_consent: false,
        capabilities: [{ category: "vision", level: "2", equipment: "guide_support" }],
      }),
    );

    expect(body.capabilities).toEqual([]);
    expect(body.functional_data_consent).toBe(false);
  });

  it("sends the capabilities with numeric levels when the consent is on", () => {
    const body = toProfilePut(
      makeValues({
        functional_data_consent: true,
        capabilities: [
          { category: "vision", level: "2", equipment: "guide_support" },
          { category: "endurance", level: "0", equipment: "" },
        ],
      }),
    );

    expect(body.capabilities).toEqual([
      { category: "vision", level: 2, equipment: "guide_support" },
      { category: "endurance", level: 0, equipment: null },
    ]);
  });

  it("sends the chosen district and a trimmed contact", () => {
    const body = toProfilePut(makeValues({ district_code: "kyiv_podilskyi", contact: " @olena " }));

    expect(body.district_code).toBe("kyiv_podilskyi");
    expect(body.contact).toBe("@olena");
  });
});

describe("buildInitialValues", () => {
  it("starts a new profile with one empty sport and no location", () => {
    const values = buildInitialValues();

    expect(values.sports).toHaveLength(1);
    expect(values.sports[0]?.sport).toBe("");
    expect(values.location).toBeNull();
    expect(values.is_visible).toBe(true);
    expect(values.functional_data_consent).toBe(false);
  });

  it("fills the stored values but never a location", () => {
    const values = buildInitialValues(
      makeProfile({
        contact: "@olena",
        functional_data_consent: true,
        capabilities: [{ category: "vision", level: 3, equipment: null }],
      }),
    );

    expect(values.display_name).toBe("Олена");
    expect(values.intensity).toBe("3");
    expect(values.capabilities).toEqual([{ category: "vision", level: "3", equipment: "" }]);
    expect(values.contact).toBe("@olena");
    expect(values.location).toBeNull();
  });
});

describe("buildProfileSchema", () => {
  const schema = buildProfileSchema(taxonomy);
  const errorsOf = async (values: ProfileFormValues) => {
    try {
      await schema.validate(values, { abortEarly: false });
      return [];
    } catch (error) {
      return (error as { inner: { path: string }[] }).inner.map((item) => item.path);
    }
  };

  it("accepts a valid form", async () => {
    expect(await errorsOf(makeValues())).toEqual([]);
  });

  it("requires the name, intensity, sport and an area", async () => {
    const paths = await errorsOf(
      makeValues({
        display_name: "  ",
        intensity: "",
        location: null,
        sports: [{ sport: "", skill: "beginner" }],
      }),
    );

    expect(paths).toEqual(
      expect.arrayContaining(["display_name", "intensity", "location", "sports[0].sport"]),
    );
  });

  it("gives the missing area the fixed message", async () => {
    await expect(schema.validate(makeValues({ location: null }))).rejects.toThrow(
      uk.profile.validation.locationRequired,
    );
  });

  it("limits the lengths of the name and the contact", async () => {
    expect(await errorsOf(makeValues({ display_name: "я".repeat(61) }))).toContain("display_name");
    expect(await errorsOf(makeValues({ display_name: "я".repeat(60) }))).toEqual([]);
    expect(await errorsOf(makeValues({ contact: "x".repeat(121) }))).toContain("contact");
  });

  describe("with an existing profile", () => {
    const optional = buildProfileSchema(taxonomy, true);
    const optionalErrors = async (values: ProfileFormValues) => {
      try {
        await optional.validate(values, { abortEarly: false });
        return [];
      } catch (error) {
        return (error as { inner: { path: string; message: string }[] }).inner.map(
          (item) => `${item.path}:${item.message}`,
        );
      }
    };

    it("accepts an unchosen area, which keeps the stored one", async () => {
      expect(await optionalErrors(makeValues({ location: null }))).toEqual([]);
    });

    it("accepts a chosen area", async () => {
      expect(await optionalErrors(makeValues())).toEqual([]);
    });

    it("keeps the other rules", async () => {
      expect(await optionalErrors(makeValues({ location: null, intensity: "" }))).toEqual([
        expect.stringMatching(/^intensity:/),
      ]);
    });
  });

  it("rejects control characters in text", async () => {
    expect(await errorsOf(makeValues({ display_name: "a\nb" }))).toContain("display_name");
    expect(await errorsOf(makeValues({ contact: "a\u0000b" }))).toContain("contact");
  });

  it("rejects a sport that is listed twice, on the later row", async () => {
    const paths = await errorsOf(
      makeValues({
        sports: [
          { sport: "swimming", skill: "beginner" },
          { sport: "swimming", skill: "advanced" },
        ],
      }),
    );

    expect(paths).toEqual(["sports[1].sport"]);
  });

  it("validates capabilities only while the consent is on", async () => {
    const incomplete = [{ category: "", level: "", equipment: "" } as const];

    expect(
      await errorsOf(makeValues({ functional_data_consent: false, capabilities: [...incomplete] })),
    ).toEqual([]);
    expect(
      await errorsOf(makeValues({ functional_data_consent: true, capabilities: [...incomplete] })),
    ).toEqual(expect.arrayContaining(["capabilities[0].category", "capabilities[0].level"]));
  });

  it("rejects equipment that does not fit the category and a repeated category", async () => {
    const paths = await errorsOf(
      makeValues({
        functional_data_consent: true,
        capabilities: [
          { category: "vision", level: "2", equipment: "hearing_aid" },
          { category: "vision", level: "1", equipment: "" },
        ],
      }),
    );

    expect(paths).toEqual(
      expect.arrayContaining(["capabilities[0].equipment", "capabilities[1].category"]),
    );
  });
});
