import { describe, expect, it } from "vitest";
import { distanceKm } from "../geo/gridCell";
import { PLACES, findPlace, nearestCity, placesInOrder } from "./gazetteer";

const cities = PLACES.filter((place) => place.kind === "city");
const districts = PLACES.filter((place) => place.kind === "district");

/** The oblast centres of Ukraine (the city of Kyiv counts for its own region). */
const OBLAST_CENTRES = [
  "vinnytsia",
  "lutsk",
  "dnipro",
  "donetsk",
  "zhytomyr",
  "uzhhorod",
  "zaporizhzhia",
  "ivano-frankivsk",
  "kyiv",
  "kropyvnytskyi",
  "luhansk",
  "lviv",
  "mykolaiv",
  "odesa",
  "poltava",
  "rivne",
  "sumy",
  "ternopil",
  "kharkiv",
  "kherson",
  "khmelnytskyi",
  "cherkasy",
  "chernivtsi",
  "chernihiv",
  "simferopol",
  "sevastopol",
];

describe("gazetteer data", () => {
  it("has unique ids made of lower-case ASCII letters and hyphens", () => {
    const ids = PLACES.map((place) => place.id);

    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) expect(id).toMatch(/^[a-z]+(-[a-z]+)*$/);
  });

  it("has unique display names", () => {
    const names = PLACES.map((place) => place.name);

    expect(new Set(names).size).toBe(names.length);
  });

  it("keeps every point inside the bounding box of Ukraine (44 to 53 N, 22 to 41 E)", () => {
    for (const { id, latitude, longitude } of PLACES) {
      expect(latitude, id).toBeGreaterThanOrEqual(44);
      expect(latitude, id).toBeLessThanOrEqual(53);
      expect(longitude, id).toBeGreaterThanOrEqual(22);
      expect(longitude, id).toBeLessThanOrEqual(41);
    }
  });

  it("rounds coordinates to three decimals", () => {
    for (const { id, latitude, longitude } of PLACES) {
      expect(Number(latitude.toFixed(3)), id).toBe(latitude);
      expect(Number(longitude.toFixed(3)), id).toBe(longitude);
    }
  });

  it("names a Wikidata item for every row and uses each item once", () => {
    const items = PLACES.map((place) => place.wikidata);

    for (const item of items) expect(item).toMatch(/^Q\d+$/);
    expect(new Set(items).size).toBe(items.length);
  });

  it("contains every oblast centre", () => {
    const ids = new Set(cities.map((city) => city.id));

    for (const id of OBLAST_CENTRES) expect(ids.has(id), id).toBe(true);
  });

  it("has the districts of the five big cities, each pointing at an existing city", () => {
    const perCity = new Map<string, number>();
    for (const district of districts) {
      expect(district.cityId, district.id).toBeDefined();
      expect(findPlace(district.cityId ?? "")?.kind, district.id).toBe("city");
      expect(district.id.startsWith(`${district.cityId}-`), district.id).toBe(true);
      perCity.set(district.cityId ?? "", (perCity.get(district.cityId ?? "") ?? 0) + 1);
    }

    expect(Object.fromEntries(perCity)).toEqual({ kyiv: 10, kharkiv: 9, odesa: 4, dnipro: 8, lviv: 6 });
  });

  it("keeps a district within 20 km of the centre of its city", () => {
    for (const district of districts) {
      const city = findPlace(district.cityId ?? "");
      expect(city).toBeDefined();
      if (city) expect(distanceKm(district, city), district.id).toBeLessThan(20);
    }
  });

  it("has no city without a district entry written as a district and no district on a city", () => {
    for (const city of cities) expect(city.cityId).toBeUndefined();
    for (const district of districts) expect(district.name).toMatch(/ район$/);
  });
});

describe("placesInOrder", () => {
  it("lists every place once, each city followed by its districts", () => {
    const ordered = placesInOrder();

    expect(ordered).toHaveLength(PLACES.length);
    expect(new Set(ordered.map((place) => place.id)).size).toBe(PLACES.length);
    ordered.forEach((place, index) => {
      if (place.kind === "district") {
        const previous = ordered[index - 1];
        expect(previous?.id === place.cityId || previous?.cityId === place.cityId).toBe(true);
      }
    });
  });

  it("sorts the cities by the Ukrainian alphabet", () => {
    const names = placesInOrder()
      .filter((place) => place.kind === "city")
      .map((place) => place.name);

    expect(names).toEqual([...names].sort(new Intl.Collator("uk").compare));
    expect(names[0]).toBe("Алчевськ");
  });
});

describe("findPlace", () => {
  it("finds a place by id and returns undefined for an unknown id", () => {
    expect(findPlace("kyiv-pecherskyi")?.name).toBe("Київ, Печерський район");
    expect(findPlace("atlantis")).toBeUndefined();
  });
});

describe("nearestCity", () => {
  it("finds the city for a point in it", () => {
    const result = nearestCity({ latitude: 49.85, longitude: 24.03 });

    expect(result.place.id).toBe("lviv");
    expect(result.distanceKm).toBeLessThan(2);
  });

  it("reports a distance for a point far from every city", () => {
    const result = nearestCity({ latitude: 0, longitude: 0 });

    expect(result.distanceKm).toBeGreaterThan(1000);
  });
});
