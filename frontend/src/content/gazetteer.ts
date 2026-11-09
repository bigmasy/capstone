/**
 * A static gazetteer of Ukrainian places for the quick select of the location picker.
 *
 * Source: Wikidata (public domain, CC0), the coordinate property P625, read in November 2026.
 * The cities are all oblast centres plus the other cities that Wikidata lists with a population
 * above 100 000; the district rows are the current city districts of Kyiv (10), Kharkiv (9),
 * Odesa (4), Dnipro (8) and Lviv (6), as listed by Wikidata for the city. The `wikidata` field
 * holds the item id, so every row can be checked against the source.
 *
 * A row is a representative point (the city centre as Wikidata gives it, or the point Wikidata
 * stores for the district), rounded to three decimals, about 100 m. It is where the map is
 * centred and where the point starts; the location that is stored is the rounded grid cell
 * around it, never this point, and the user can move it. Population is not kept, because it
 * changes and has no use here.
 *
 * Nothing here is looked up at run time: choosing a place never contacts a third party, so what
 * the user picks is not leaked to a geocoding service.
 */

import { distanceKm } from "../geo/gridCell";

export interface Place {
  /** Stable key, lower-case ASCII with hyphens. */
  id: string;
  kind: "city" | "district";
  /** Name for display in Ukrainian; a district is written as "City, District район". */
  name: string;
  /** For a district: the id of its city. */
  cityId?: string;
  /** Wikidata item the coordinates were taken from. */
  wikidata: string;
  latitude: number;
  longitude: number;
}

export const PLACES: readonly Place[] = [
  { id: "kyiv", kind: "city", name: "Київ", wikidata: "Q1899", latitude: 50.450, longitude: 30.524 },
  { id: "kyiv-holosiivskyi", kind: "district", name: "Київ, Голосіївський район", cityId: "kyiv", wikidata: "Q2248375", latitude: 50.328, longitude: 30.551 },
  { id: "kyiv-darnytskyi", kind: "district", name: "Київ, Дарницький район", cityId: "kyiv", wikidata: "Q1970473", latitude: 50.404, longitude: 30.705 },
  { id: "kyiv-desnianskyi", kind: "district", name: "Київ, Деснянський район", cityId: "kyiv", wikidata: "Q1577772", latitude: 50.519, longitude: 30.674 },
  { id: "kyiv-dniprovskyi", kind: "district", name: "Київ, Дніпровський район", cityId: "kyiv", wikidata: "Q606937", latitude: 50.456, longitude: 30.644 },
  { id: "kyiv-obolonskyi", kind: "district", name: "Київ, Оболонський район", cityId: "kyiv", wikidata: "Q2367180", latitude: 50.532, longitude: 30.421 },
  { id: "kyiv-pecherskyi", kind: "district", name: "Київ, Печерський район", cityId: "kyiv", wikidata: "Q1585799", latitude: 50.429, longitude: 30.553 },
  { id: "kyiv-podilskyi", kind: "district", name: "Київ, Подільський район", cityId: "kyiv", wikidata: "Q892548", latitude: 50.489, longitude: 30.452 },
  { id: "kyiv-sviatoshynskyi", kind: "district", name: "Київ, Святошинський район", cityId: "kyiv", wikidata: "Q2381039", latitude: 50.469, longitude: 30.335 },
  { id: "kyiv-solomianskyi", kind: "district", name: "Київ, Солом’янський район", cityId: "kyiv", wikidata: "Q528868", latitude: 50.421, longitude: 30.458 },
  { id: "kyiv-shevchenkivskyi", kind: "district", name: "Київ, Шевченківський район", cityId: "kyiv", wikidata: "Q1817299", latitude: 50.463, longitude: 30.462 },
  { id: "kharkiv", kind: "city", name: "Харків", wikidata: "Q42308", latitude: 49.993, longitude: 36.231 },
  { id: "kharkiv-industrialnyi", kind: "district", name: "Харків, Індустріальний район", cityId: "kharkiv", wikidata: "Q2112093", latitude: 49.950, longitude: 36.367 },
  { id: "kharkiv-kholodnohirskyi", kind: "district", name: "Харків, Холодногірський район", cityId: "kharkiv", wikidata: "Q7242862", latitude: 49.995, longitude: 36.177 },
  { id: "kharkiv-kyivskyi", kind: "district", name: "Харків, Київський район", cityId: "kharkiv", wikidata: "Q4220235", latitude: 50.041, longitude: 36.300 },
  { id: "kharkiv-nemyshlianskyi", kind: "district", name: "Харків, Немишлянський район", cityId: "kharkiv", wikidata: "Q4493135", latitude: 49.967, longitude: 36.336 },
  { id: "kharkiv-novobavarskyi", kind: "district", name: "Харків, Новобаварський район", cityId: "kharkiv", wikidata: "Q4333164", latitude: 49.967, longitude: 36.200 },
  { id: "kharkiv-osnovianskyi", kind: "district", name: "Харків, Основ’янський район", cityId: "kharkiv", wikidata: "Q4512330", latitude: 49.983, longitude: 36.233 },
  { id: "kharkiv-saltivskyi", kind: "district", name: "Харків, Салтівський район", cityId: "kharkiv", wikidata: "Q4304270", latitude: 50.004, longitude: 36.334 },
  { id: "kharkiv-shevchenkivskyi", kind: "district", name: "Харків, Шевченківський район", cityId: "kharkiv", wikidata: "Q4160816", latitude: 50.017, longitude: 36.217 },
  { id: "kharkiv-slobidskyi", kind: "district", name: "Харків, Слобідський район", cityId: "kharkiv", wikidata: "Q4229581", latitude: 49.933, longitude: 36.267 },
  { id: "odesa", kind: "city", name: "Одеса", wikidata: "Q1874", latitude: 46.484, longitude: 30.733 },
  { id: "odesa-khadzhybeiskyi", kind: "district", name: "Одеса, Хаджибейський район", cityId: "odesa", wikidata: "Q4277948", latitude: 46.458, longitude: 30.683 },
  { id: "odesa-kyivskyi", kind: "district", name: "Одеса, Київський район", cityId: "odesa", wikidata: "Q4220231", latitude: 46.398, longitude: 30.727 },
  { id: "odesa-peresypskyi", kind: "district", name: "Одеса, Пересипський район", cityId: "odesa", wikidata: "Q4445200", latitude: 46.526, longitude: 30.729 },
  { id: "odesa-prymorskyi", kind: "district", name: "Одеса, Приморський район", cityId: "odesa", wikidata: "Q4378731", latitude: 46.467, longitude: 30.750 },
  { id: "dnipro", kind: "city", name: "Дніпро", wikidata: "Q48256", latitude: 48.468, longitude: 35.040 },
  { id: "dnipro-nyzhnodniprovskyi", kind: "district", name: "Дніпро, Нижньодніпровський район", cityId: "dnipro", wikidata: "Q4064555", latitude: 48.521, longitude: 34.978 },
  { id: "dnipro-industrialnyi", kind: "district", name: "Дніпро, Індустріальний район", cityId: "dnipro", wikidata: "Q4200940", latitude: 48.517, longitude: 35.083 },
  { id: "dnipro-novokodatskyi", kind: "district", name: "Дніпро, Новокодацький район", cityId: "dnipro", wikidata: "Q4258367", latitude: 48.475, longitude: 34.945 },
  { id: "dnipro-samarskyi", kind: "district", name: "Дніпро, Самарський район", cityId: "dnipro", wikidata: "Q9066043", latitude: 48.417, longitude: 35.118 },
  { id: "dnipro-sobornyi", kind: "district", name: "Дніпро, Соборний район", cityId: "dnipro", wikidata: "Q2841378", latitude: 48.450, longitude: 35.067 },
  { id: "dnipro-tsentralnyi", kind: "district", name: "Дніпро, Центральний район", cityId: "dnipro", wikidata: "Q4221675", latitude: 48.467, longitude: 35.033 },
  { id: "dnipro-shevchenkivskyi", kind: "district", name: "Дніпро, Шевченківський район", cityId: "dnipro", wikidata: "Q2070309", latitude: 48.409, longitude: 35.013 },
  { id: "dnipro-chechelivskyi", kind: "district", name: "Дніпро, Чечелівський район", cityId: "dnipro", wikidata: "Q9066039", latitude: 48.421, longitude: 34.967 },
  { id: "donetsk", kind: "city", name: "Донецьк", wikidata: "Q43070", latitude: 48.016, longitude: 37.803 },
  { id: "lviv", kind: "city", name: "Львів", wikidata: "Q36036", latitude: 49.842, longitude: 24.032 },
  { id: "lviv-halytskyi", kind: "district", name: "Львів, Галицький район", cityId: "lviv", wikidata: "Q4132542", latitude: 49.838, longitude: 24.029 },
  { id: "lviv-zaliznychnyi", kind: "district", name: "Львів, Залізничний район", cityId: "lviv", wikidata: "Q4178968", latitude: 49.831, longitude: 23.958 },
  { id: "lviv-lychakivskyi", kind: "district", name: "Львів, Личаківський район", cityId: "lviv", wikidata: "Q4270859", latitude: 49.833, longitude: 24.083 },
  { id: "lviv-sykhivskyi", kind: "district", name: "Львів, Сихівський район", cityId: "lviv", wikidata: "Q4421225", latitude: 49.795, longitude: 24.050 },
  { id: "lviv-frankivskyi", kind: "district", name: "Львів, Франківський район", cityId: "lviv", wikidata: "Q4492396", latitude: 49.811, longitude: 23.997 },
  { id: "lviv-shevchenkivskyi", kind: "district", name: "Львів, Шевченківський район", cityId: "lviv", wikidata: "Q4522272", latitude: 49.870, longitude: 23.984 },
  { id: "zaporizhzhia", kind: "city", name: "Запоріжжя", wikidata: "Q157835", latitude: 47.850, longitude: 35.118 },
  { id: "kryvyi-rih", kind: "city", name: "Кривий Ріг", wikidata: "Q157137", latitude: 47.910, longitude: 33.390 },
  { id: "sevastopol", kind: "city", name: "Севастополь", wikidata: "Q7525", latitude: 44.605, longitude: 33.523 },
  { id: "mykolaiv", kind: "city", name: "Миколаїв", wikidata: "Q41572", latitude: 46.975, longitude: 31.995 },
  { id: "luhansk", kind: "city", name: "Луганськ", wikidata: "Q134279", latitude: 48.572, longitude: 39.297 },
  { id: "vinnytsia", kind: "city", name: "Вінниця", wikidata: "Q157144", latitude: 49.237, longitude: 28.467 },
  { id: "makiivka", kind: "city", name: "Макіївка", wikidata: "Q157134", latitude: 48.056, longitude: 37.961 },
  { id: "simferopol", kind: "city", name: "Сімферополь", wikidata: "Q19566", latitude: 44.948, longitude: 34.100 },
  { id: "chernihiv", kind: "city", name: "Чернігів", wikidata: "Q157053", latitude: 51.494, longitude: 31.295 },
  { id: "poltava", kind: "city", name: "Полтава", wikidata: "Q156747", latitude: 49.589, longitude: 34.551 },
  { id: "kherson", kind: "city", name: "Херсон", wikidata: "Q156732", latitude: 46.643, longitude: 32.625 },
  { id: "khmelnytskyi", kind: "city", name: "Хмельницький", wikidata: "Q156717", latitude: 49.420, longitude: 27.000 },
  { id: "cherkasy", kind: "city", name: "Черкаси", wikidata: "Q157055", latitude: 49.444, longitude: 32.060 },
  { id: "sumy", kind: "city", name: "Суми", wikidata: "Q156752", latitude: 50.907, longitude: 34.799 },
  { id: "chernivtsi", kind: "city", name: "Чернівці", wikidata: "Q157725", latitude: 48.291, longitude: 25.934 },
  { id: "zhytomyr", kind: "city", name: "Житомир", wikidata: "Q156713", latitude: 50.254, longitude: 28.658 },
  { id: "horlivka", kind: "city", name: "Горлівка", wikidata: "Q157260", latitude: 48.334, longitude: 38.093 },
  { id: "mariupol", kind: "city", name: "Маріуполь", wikidata: "Q37133", latitude: 47.131, longitude: 37.564 },
  { id: "rivne", kind: "city", name: "Рівне", wikidata: "Q156739", latitude: 50.620, longitude: 26.251 },
  { id: "ivano-frankivsk", kind: "city", name: "Івано-Франківськ", wikidata: "Q156726", latitude: 48.923, longitude: 24.711 },
  { id: "kamianske", kind: "city", name: "Кам’янське", wikidata: "Q156719", latitude: 48.517, longitude: 34.613 },
  { id: "ternopil", kind: "city", name: "Тернопіль", wikidata: "Q156743", latitude: 49.567, longitude: 25.600 },
  { id: "kropyvnytskyi", kind: "city", name: "Кропивницький", wikidata: "Q158292", latitude: 48.510, longitude: 32.267 },
  { id: "lutsk", kind: "city", name: "Луцьк", wikidata: "Q7550", latitude: 50.748, longitude: 25.324 },
  { id: "kremenchuk", kind: "city", name: "Кременчук", wikidata: "Q156724", latitude: 49.063, longitude: 33.404 },
  { id: "bila-tserkva", kind: "city", name: "Біла Церква", wikidata: "Q33342", latitude: 49.796, longitude: 30.117 },
  { id: "kerch", kind: "city", name: "Керч", wikidata: "Q157065", latitude: 45.339, longitude: 36.468 },
  { id: "melitopol", kind: "city", name: "Мелітополь", wikidata: "Q33349", latitude: 46.849, longitude: 35.368 },
  { id: "kramatorsk", kind: "city", name: "Краматорськ", wikidata: "Q33613", latitude: 48.739, longitude: 37.584 },
  { id: "uzhhorod", kind: "city", name: "Ужгород", wikidata: "Q156711", latitude: 48.624, longitude: 22.295 },
  { id: "brovary", kind: "city", name: "Бровари", wikidata: "Q841026", latitude: 50.511, longitude: 30.790 },
  { id: "berdiansk", kind: "city", name: "Бердянськ", wikidata: "Q33292", latitude: 46.756, longitude: 36.789 },
  { id: "alchevsk", kind: "city", name: "Алчевськ", wikidata: "Q161144", latitude: 48.467, longitude: 38.798 },
  { id: "yevpatoriia", kind: "city", name: "Євпаторія", wikidata: "Q33345", latitude: 45.200, longitude: 33.358 },
  { id: "nikopol", kind: "city", name: "Нікополь", wikidata: "Q156760", latitude: 47.567, longitude: 34.400 },
  { id: "sloviansk", kind: "city", name: "Слов’янськ", wikidata: "Q33581", latitude: 48.853, longitude: 37.606 },
  { id: "pavlohrad", kind: "city", name: "Павлоград", wikidata: "Q237206", latitude: 48.520, longitude: 35.870 },
];

const collator = new Intl.Collator("uk");

/**
 * The places in reading order for a select: cities alphabetically, each followed by its own
 * districts. A copy, so the caller cannot reorder the data.
 */
export function placesInOrder(): Place[] {
  const cities = PLACES.filter((place) => place.kind === "city").sort((a, b) =>
    collator.compare(a.name, b.name),
  );
  return cities.flatMap((city) => [
    city,
    ...PLACES.filter((place) => place.cityId === city.id).sort((a, b) =>
      collator.compare(a.name, b.name),
    ),
  ]);
}

/** The place with an id, or undefined. */
export function findPlace(id: string): Place | undefined {
  return PLACES.find((place) => place.id === id);
}

export interface NearestPlace {
  place: Place;
  distanceKm: number;
}

/**
 * The listed city nearest to a point, for the text alternative of the map. Districts are not
 * considered, so the answer is always a city name that a reader recognises.
 *
 * @param point Any point; the caller passes the centre of the stored cell, not the exact point.
 */
export function nearestCity(point: { latitude: number; longitude: number }): NearestPlace {
  let best: NearestPlace | undefined;
  for (const place of PLACES) {
    if (place.kind !== "city") continue;
    const distance = distanceKm(point, place);
    if (best === undefined || distance < best.distanceKm) best = { place, distanceKm: distance };
  }
  // PLACES always holds cities, so there is a result
  return best as NearestPlace;
}
