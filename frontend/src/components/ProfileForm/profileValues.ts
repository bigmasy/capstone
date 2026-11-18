import { getIn, useFormikContext } from "formik";
import * as Yup from "yup";
import type {
  AreaPrecision,
  CapabilityItem,
  CategoryCode,
  DistrictCode,
  EquipmentCode,
  ProfileOwner,
  ProfilePut,
  SkillLevel,
  SportCode,
  SportItem,
  Taxonomy,
} from "../../api/types";
import { DEFAULT_PRECISION, isCoarser, snapToCell } from "../../geo/gridCell";
import { uk } from "../../i18n/uk";

// Limits follow the backend contract (display name 60, contact 120, at most 10 sports)
export const DISPLAY_NAME_MAX = 60;
export const CONTACT_MAX = 120;
export const MAX_SPORTS = 10;

export interface SportRow {
  sport: SportCode | "";
  skill: SkillLevel;
}

export interface CapabilityRow {
  category: CategoryCode | "";
  /** Level as text, because it comes from a select. */
  level: string;
  equipment: EquipmentCode | "";
}

/**
 * The chosen training area, held as the centre of its grid cell. The point the user clicked
 * is snapped the moment it is chosen and never kept, so the form state cannot leak it.
 */
export interface LocationValue {
  latitude: number;
  longitude: number;
}

/** Values of the profile form; numbers stay text until the payload is built. */
export interface ProfileFormValues {
  display_name: string;
  district_code: DistrictCode | "";
  intensity: string;
  is_visible: boolean;
  /** Null until an area is chosen; on an existing profile null keeps the stored area. */
  location: LocationValue | null;
  /** How coarse the stored area is; the owner's choice. */
  area_precision: AreaPrecision;
  sports: SportRow[];
  functional_data_consent: boolean;
  capabilities: CapabilityRow[];
  contact: string;
}

export const emptySportRow: SportRow = { sport: "", skill: "beginner" };
export const emptyCapabilityRow: CapabilityRow = { category: "", level: "", equipment: "" };

/**
 * Initial values of the form.
 *
 * The API never returns the location, so the area always starts unchosen and nothing that
 * looks like a position is ever shown back. Left unchosen on an existing profile, it keeps the
 * stored area.
 *
 * @param profile The stored profile, or undefined for a new one.
 */
export function buildInitialValues(profile?: ProfileOwner): ProfileFormValues {
  return {
    display_name: profile?.display_name ?? "",
    district_code: profile?.district_code ?? "",
    intensity: profile ? String(profile.intensity) : "",
    is_visible: profile?.is_visible ?? true,
    location: null,
    area_precision: profile?.area_precision ?? DEFAULT_PRECISION,
    sports: profile?.sports.length
      ? profile.sports.map(({ sport, skill }) => ({ sport, skill }))
      : [{ ...emptySportRow }],
    functional_data_consent: profile?.functional_data_consent ?? false,
    capabilities: (profile?.capabilities ?? []).map((item) => ({
      category: item.category,
      level: String(item.level),
      equipment: item.equipment ?? "",
    })),
    contact: profile?.contact ?? "",
  };
}

/** Equipment codes that may be attached to the category, according to the taxonomy. */
export function equipmentFor(taxonomy: Taxonomy, category: CategoryCode | ""): EquipmentCode[] {
  if (category === "") return [];
  return taxonomy.equipment.filter((rule) => rule.categories.includes(category)).map((r) => r.code);
}

/** The cell centre of an area, in the shape of the request body. */
function centreOf(
  { latitude, longitude }: LocationValue,
  precision: AreaPrecision,
): Pick<ProfilePut, "latitude" | "longitude"> {
  const cell = snapToCell(latitude, longitude, precision);
  return { latitude: cell.latitude, longitude: cell.longitude };
}

/**
 * Builds the request body from validated form values.
 *
 * The coordinates sent are the centre of the grid cell of the chosen area (snapped again here
 * as a last guard), never an exact point. When no area was chosen the two keys are left out
 * (they are not sent as null), which keeps the stored area of an existing profile.
 *
 * Without the consent the capabilities are not sent at all, whatever the form still holds.
 * Rows that are not filled in are skipped; validation prevents them from reaching here.
 */
export function toProfilePut(values: ProfileFormValues): ProfilePut {
  const consent = values.functional_data_consent;
  const sports: SportItem[] = values.sports.flatMap(({ sport, skill }) =>
    sport === "" ? [] : [{ sport, skill }],
  );
  const capabilities: CapabilityItem[] = consent
    ? values.capabilities.flatMap(({ category, level, equipment }) =>
        category === "" || level === ""
          ? []
          : [{ category, level: Number(level), equipment: equipment === "" ? null : equipment }],
      )
    : [];

  const location: Pick<ProfilePut, "latitude" | "longitude"> = values.location
    ? centreOf(values.location, values.area_precision)
    : {};

  return {
    display_name: values.display_name.trim(),
    district_code: values.district_code === "" ? null : values.district_code,
    intensity: Number(values.intensity),
    is_visible: values.is_visible,
    ...location,
    area_precision: values.area_precision,
    sports,
    capabilities,
    functional_data_consent: consent,
    contact: values.contact.trim() === "" ? null : values.contact.trim(),
  };
}

const messages = uk.profile.validation;
// Control characters are rejected by the server as well (NUL, newlines, escapes)
// eslint-disable-next-line no-control-regex
const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/;

/** Index of a row in a Yup path such as `sports[2].sport`. */
function rowIndex(path: string): number {
  const match = /\[(\d+)\]/.exec(path);
  return match ? Number(match[1]) : -1;
}

/** Marks a value that repeats an earlier row of the same list. */
function repeatsEarlierRow(listName: "sports" | "capabilities", key: string) {
  return function (this: Yup.TestContext, value: unknown): boolean {
    if (typeof value !== "string" || value === "") return true;
    const root = this.from?.at(-1)?.value as ProfileFormValues | undefined;
    const rows = (root?.[listName] ?? []) as unknown as Record<string, unknown>[];
    const index = rowIndex(this.path);
    return !rows.slice(0, Math.max(index, 0)).some((row) => row[key] === value);
  };
}

/**
 * Builds the validation schema of the form.
 *
 * Allowed values come from the taxonomy that the API served, so a code the server would
 * reject is caught on the client. Capabilities are validated only while the consent is on.
 *
 * @param taxonomy The vocabulary served by the API.
 * @param locationOptional True when a profile already exists: no area needs to be chosen then
 *   (the stored area is kept).
 * @param storedPrecision Size of the stored area of an existing profile. A smaller size cannot
 *   be derived from it, so choosing one asks for the place again.
 */
export function buildProfileSchema(
  taxonomy: Taxonomy,
  locationOptional = false,
  storedPrecision?: AreaPrecision,
) {
  const choose = (allowed: readonly string[]) =>
    Yup.string().required(uk.form.validation.required).oneOf(allowed, messages.choose);

  const sportRow = Yup.object({
    sport: choose(taxonomy.sports).test(
      "unique",
      messages.duplicateSport,
      repeatsEarlierRow("sports", "sport"),
    ),
    skill: choose(taxonomy.skills),
  });

  const capabilityRow = Yup.object({
    category: choose(taxonomy.categories).test(
      "unique",
      messages.duplicateCategory,
      repeatsEarlierRow("capabilities", "category"),
    ),
    level: choose(taxonomy.capability_levels.map(String)),
    equipment: Yup.string()
      .oneOf(["", ...taxonomy.equipment.map((rule) => rule.code)], messages.choose)
      .test("fits", messages.equipmentMismatch, function (value) {
        if (!value) return true;
        const row = this.parent as CapabilityRow;
        return equipmentFor(taxonomy, row.category).includes(value);
      }),
  });

  return Yup.object({
    display_name: Yup.string()
      .trim()
      .required(uk.form.validation.required)
      .max(DISPLAY_NAME_MAX, messages.displayNameMax)
      .test("text", messages.noControlCharacters, (value) => !CONTROL_CHARACTERS.test(value)),
    district_code: Yup.string().oneOf(["", ...taxonomy.districts], messages.choose),
    intensity: choose(taxonomy.intensities.map(String)),
    location: Yup.mixed<LocationValue>()
      .nullable()
      .test("chosen", messages.locationRequired, (value) => locationOptional || value != null)
      .test("finer", uk.profile.location.finerNeedsPlace, function (value) {
        if (value != null || storedPrecision === undefined) return true;
        const chosen = (this.parent as ProfileFormValues).area_precision;
        return !isCoarser(storedPrecision, chosen);
      }),
    sports: Yup.array().of(sportRow).min(1, uk.profile.sports.lastRow).max(MAX_SPORTS),
    functional_data_consent: Yup.boolean(),
    capabilities: Yup.array().when("functional_data_consent", {
      is: true,
      then: (schema) => schema.of(capabilityRow),
    }),
    contact: Yup.string()
      .trim()
      .max(CONTACT_MAX, messages.contactMax)
      .test("text", messages.noControlCharacters, (value) => !CONTROL_CHARACTERS.test(value ?? "")),
  });
}

/**
 * Error text of one field, shown only after the field was touched or a submit was tried.
 * Must be used inside a Formik form.
 *
 * @param path Formik path such as `sports.0.sport`.
 */
export function useFieldError(path: string): string | undefined {
  const { errors, touched } = useFormikContext<ProfileFormValues>();
  const error: unknown = getIn(errors, path);
  return getIn(touched, path) && typeof error === "string" ? error : undefined;
}
