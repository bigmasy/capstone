/** Labels of taxonomy codes, grouped by the kind of dictionary the backend serves. */
export interface TaxonomyLabels {
  sports: Readonly<Record<string, string>>;
  categories: Readonly<Record<string, string>>;
  equipment: Readonly<Record<string, string>>;
  districts: Readonly<Record<string, string>>;
  skills: Readonly<Record<string, string>>;
  /** Wording of the capability levels 0 to 4, keyed by the level as text. */
  capabilityLevels: Readonly<Record<string, string>>;
  /** Wording of the training intensities 1 to 5, keyed by the intensity as text. */
  intensities: Readonly<Record<string, string>>;
  /** Short neutral description of what a capability category covers. */
  categoryHints: Readonly<Record<string, string>>;
}

export type TaxonomyKind = keyof TaxonomyLabels;

/**
 * Labels per taxonomy version. A major version may remove or rename codes, so
 * each published version keeps its own table instead of overwriting the previous one.
 */
const taxonomyLabelsByVersion: Readonly<Record<string, TaxonomyLabels>> = {
  "1.0.0": {
    sports: {
      swimming: "Плавання",
      archery: "Стрільба з лука",
      table_tennis: "Настільний теніс",
      sitting_volleyball: "Волейбол сидячи",
      wheelchair_basketball: "Баскетбол на візках",
      cycling: "Велоспорт",
      handcycling: "Хендбайк",
      rowing: "Веслування",
      athletics: "Легка атлетика",
      gym_fitness: "Тренажерний зал і фітнес",
      powerlifting: "Пауерліфтинг",
      yoga_stretching: "Йога і розтяжка",
      badminton: "Бадмінтон",
      nordic_walking: "Скандинавська ходьба",
    },
    categories: {
      mobility_lower: "Пересування на ногах",
      mobility_upper: "Використання рук для руху й навантаження",
      balance_posture: "Рівновага і постава",
      endurance: "Підтримання фізичного зусилля",
      dexterity: "Дрібні рухи рук",
      vision: "Зір і орієнтація",
      hearing: "Сприйняття вказівок на слух",
    },
    equipment: {
      wheelchair_active: "Активний (спортивний) візок",
      handcycle: "Хендбайк",
      crutches_or_cane: "Милиці або тростина",
      prosthesis_lower_limb: "Протез нижньої кінцівки",
      running_blade: "Бігальний протез",
      prosthesis_upper_limb: "Протез верхньої кінцівки",
      guide_support: "Супровідник або прив’язь",
      hearing_aid: "Слуховий апарат",
    },
    districts: {
      kyiv_holosiivskyi: "Київ, Голосіївський",
      kyiv_darnytskyi: "Київ, Дарницький",
      kyiv_desnianskyi: "Київ, Деснянський",
      kyiv_dniprovskyi: "Київ, Дніпровський",
      kyiv_obolonskyi: "Київ, Оболонський",
      kyiv_pecherskyi: "Київ, Печерський",
      kyiv_podilskyi: "Київ, Подільський",
      kyiv_sviatoshynskyi: "Київ, Святошинський",
      kyiv_solomianskyi: "Київ, Солом’янський",
      kyiv_shevchenkivskyi: "Київ, Шевченківський",
    },
    skills: {
      beginner: "Початківець",
      intermediate: "Середній рівень",
      advanced: "Просунутий",
    },
    capabilityLevels: {
      "0": "неможливо",
      "1": "лише зі значною допомогою або адаптацією",
      "2": "з адаптацією або обладнанням",
      "3": "здебільшого самостійно",
      "4": "повністю самостійно",
    },
    intensities: {
      "1": "дуже легка",
      "2": "легка",
      "3": "помірна",
      "4": "висока",
      "5": "дуже висока",
    },
    categoryHints: {
      mobility_lower: "стояння, ходьба, підйом сходами, біг",
      mobility_upper: "діставання, штовхання, тягнення, перенесення",
      balance_posture: "збереження рівноваги й стійкого положення сидячи або стоячи",
      endurance: "підтримання фізичного зусилля протягом часу",
      dexterity: "хапання, кидання, робота з дрібним спорядженням",
      vision: "орієнтація на трасі, бачення спорядження й розмітки",
      hearing: "сприйняття усних вказівок і сигналів на тренуванні",
    },
  },
};

/**
 * Returns the Ukrainian label of a taxonomy code for the given taxonomy version.
 *
 * Falls back to the raw code when the version or the code is unknown, so a newer
 * backend never breaks rendering; the code itself is a stable, non-sensitive identifier.
 */
export function taxonomyLabel(version: string, kind: TaxonomyKind, code: string): string {
  return taxonomyLabelsByVersion[version]?.[kind][code] ?? code;
}
