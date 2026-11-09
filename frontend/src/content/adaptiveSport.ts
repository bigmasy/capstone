/**
 * Reading list about adaptive sport for the landing page.
 *
 * Every entry points to a page that was opened and read on `verifiedOn`. Descriptions say only
 * what the page itself states; where no specific article was checked, the entry links to the
 * home page or the section of the source. Dates are those given by the source.
 */

/** Day (ISO 8601) on which every link below was opened and checked. */
export const verifiedOn = "2026-11-06";

export interface InfoItem {
  id: string;
  /** What the link leads to. */
  title: string;
  /** Name of the publisher or organisation. */
  source: string;
  /** One neutral sentence about the page. */
  description: string;
  href: string;
}

export interface InfoColumn {
  id: "games" | "news" | "organisations";
  heading: string;
  items: readonly InfoItem[];
}

export const adaptiveSportColumns: readonly InfoColumn[] = [
  {
    id: "games",
    heading: "Ігри нескорених та змагання",
    items: [
      {
        id: "invictus-games-foundation",
        title: "Invictus Games Foundation",
        source: "Invictus Games Foundation",
        description:
          "Благодійна організація, що стоїть за Іграми нескорених: використовує спорт для підтримки відновлення поранених, травмованих і хворих військовослужбовців та ветеранів.",
        href: "https://www.invictusgamesfoundation.org/",
      },
      {
        id: "invictus-games-ukraine",
        title: "Ігри нескорених Україна",
        source: "Invictus Games Team Ukraine",
        description:
          "Український проєкт Ігор нескорених: адаптивний спорт і спільнота для військових та ветеранів, відбір національної збірної.",
        href: "https://invictusgames.in.ua/",
      },
      {
        id: "birmingham-2027",
        title: "Ігри нескорених, Бірмінгем: 10–17 липня 2027",
        source: "Invictus Games Foundation, 10 червня 2025",
        description:
          "Оголошення про підтверджені дати наступних Ігор: змагання відбудуться в Національному виставковому центрі (NEC), плавання — в Aquatics Centre у Сандвеллі.",
        href: "https://www.invictusgamesfoundation.org/news/invictus-games-birmingham-2027-dates-confirmed",
      },
      {
        id: "all-ukrainian-games-2026",
        title: "Відкрито реєстрацію на Всеукраїнські Ігри Нескорених — відбір на Invictus Games Birmingham 2027",
        source: "Invictus Games Team Ukraine, 1 жовтня 2026",
        description:
          "Національний відбір до збірної України на Бірмінгем 2027: змагання у Львові в листопаді 2026 року; умови участі й строки викладено в оголошенні.",
        href: "https://invictusgames.in.ua/vin/",
      },
      {
        id: "milano-cortina-2026",
        title: "Паралімпійські зимові ігри Milano Cortina 2026: 6–15 березня 2026",
        source: "Міжнародний паралімпійський комітет",
        description:
          "Сторінка Ігор на сайті МПК: шість видів спорту та 79 комплектів медалей.",
        href: "https://www.paralympic.org/milano-cortina-2026",
      },
      {
        id: "la-2028",
        title: "Літні Паралімпійські ігри, Лос-Анджелес: 15–27 серпня 2028",
        source: "Міжнародний паралімпійський комітет",
        description:
          "Дати наступних літніх Паралімпійських ігор вказано на головній сторінці МПК; ті самі дати є на сайті Національного комітету спорту інвалідів України.",
        href: "https://www.paralympic.org/",
      },
    ],
  },
  {
    id: "news",
    heading: "Видання та новини",
    items: [
      {
        id: "ipc-news",
        title: "Paralympic.org: новини",
        source: "Міжнародний паралімпійський комітет",
        description:
          "Новини паралімпійського руху англійською мовою: Ігри, види спорту, історії спортсменів і спортсменок, робота МПК.",
        href: "https://www.paralympic.org/news",
      },
      {
        id: "invictus-foundation-news",
        title: "Новини й медіа Invictus Games Foundation",
        source: "Invictus Games Foundation",
        description:
          "Статті англійською мовою про Ігри нескорених, програму відновлення поза межами Ігор і партнерства фонду.",
        href: "https://www.invictusgamesfoundation.org/news",
      },
      {
        id: "ncsdu-news",
        title: "Новини Національного комітету спорту інвалідів України",
        source: "НКСІУ",
        description:
          "Головна сторінка сайту з новинами й анонсами паралімпійського та дефлімпійського руху, календарем змагань і правилами.",
        href: "https://www.paralympic.org.ua/",
      },
      {
        id: "invictus-ua-news",
        title: "Новини проєкту «Ігри нескорених Україна»",
        source: "Invictus Games Team Ukraine",
        description:
          "Релізи проєкту: відбір збірної, всеукраїнські змагання, проєкти для ветеранів і спільноти.",
        href: "https://invictusgames.in.ua/category/releases-ua/",
      },
      {
        id: "invictus-ua-media",
        title: "Медіа про Ігри нескорених",
        source: "Invictus Games Team Ukraine",
        description:
          "Добірка публікацій інших видань про Ігри нескорених і ветеранський спорт, зокрема Суспільного та Kyiv Independent.",
        href: "https://invictusgames.in.ua/in-the-news/",
      },
      {
        id: "suspilne-sport",
        title: "Суспільне Спорт",
        source: "Суспільне",
        description:
          "Розділ спортивних новин громадського мовника, зокрема рубрики «Спорт під час війни» та «Зимовий спорт»; окремої рубрики про паралімпійський спорт на сторінці немає.",
        href: "https://suspilne.media/sport/",
      },
    ],
  },
  {
    id: "organisations",
    heading: "Організації та підтримка",
    items: [
      {
        id: "ipc",
        title: "Міжнародний паралімпійський комітет (IPC)",
        source: "paralympic.org",
        description:
          "Керівний орган паралімпійського руху: Ігри, види спорту, класифікація спортсменів, національні паралімпійські комітети.",
        href: "https://www.paralympic.org/",
      },
      {
        id: "ncsdu",
        title: "Національний комітет спорту інвалідів України",
        source: "НКСІУ",
        description:
          "Сайт паралімпійського та дефлімпійського руху України: збірні, федерації, спортивні споруди, правила змагань.",
        href: "https://www.paralympic.org.ua/",
      },
      {
        id: "mva",
        title: "Міністерство у справах ветеранів України",
        source: "mva.gov.ua",
        description:
          "Офіційний сайт міністерства: новини, інформація для ветеранів і надавачів послуг, перелік підпорядкованих установ, зокрема Українського ветеранського фонду.",
        href: "https://mva.gov.ua/",
      },
      {
        id: "veteran-sport-programme",
        title: "Ветеранський спорт: фінансова допомога на заняття спортом у Дії",
        source: "Дія, 16 січня 2025",
        description:
          "Оголошення про державну програму, за якою ветерани можуть отримувати 1 500 грн на квартал на фізичну активність через Дію; умови й строки подання змінювалися, тож перевіряйте актуальні.",
        href: "https://diia.gov.ua/news/veteranskyi-sport-otrymaite-finansovu-dopomohu-na-zaniattia-sportom-u-dii",
      },
      {
        id: "unbroken",
        title: "UNBROKEN | Незламні",
        source: "unbroken.org.ua",
        description:
          "Реабілітаційна екосистема у Львові: лікування, протезування, фізична й психологічна реабілітація; на сайті згадано проєкт UNBROKEN Sport.",
        href: "https://unbroken.org.ua/",
      },
      {
        id: "superhumans",
        title: "Superhumans Center",
        source: "superhumans.com",
        description:
          "Мережа центрів допомоги пораненим війною: протезування, реконструктивна хірургія, реабілітація та психологічна підтримка; за даними сайту, послуги безкоштовні.",
        href: "https://superhumans.com/en/",
      },
    ],
  },
];
