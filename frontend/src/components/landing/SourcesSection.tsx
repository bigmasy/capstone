import { adaptiveSportColumns, verifiedOn, type InfoItem } from "../../content/adaptiveSport";
import { uk } from "../../i18n/uk";
import ExternalLink from "../ExternalLink/ExternalLink";
import Icon, { type IconName } from "../Icon/Icon";
import Section from "./Section";
import styles from "./SourcesSection.module.css";

const text = uk.landing.sources;

const columnIcons: Record<(typeof adaptiveSportColumns)[number]["id"], IconName> = {
  games: "calendar",
  news: "news",
  organisations: "building",
};

const dateFormat = new Intl.DateTimeFormat("uk-UA", { day: "numeric", month: "long", year: "numeric" });

/** Items shown before the rest of a column is folded away, so the section stays short. */
const VISIBLE_ITEMS = 3;

const renderItem = (item: InfoItem) => (
  <li className={styles.item} key={item.id}>
    <h4 className={styles.itemTitle}>
      <ExternalLink href={item.href}>{item.title}</ExternalLink>
    </h4>
    <p className={styles.source}>{item.source}</p>
    <p className={styles.description}>{item.description}</p>
  </li>
);

/** Three columns of verified external sources about adaptive sport, with a disclaimer. */
const SourcesSection = () => (
  <Section heading={text.heading} lead={text.lead} tone="tint">
    <div className={`grid grid-3 ${styles.columns}`}>
      {adaptiveSportColumns.map((column) => (
        <div className={`card ${styles.column}`} key={column.id}>
          <h3 className={styles.columnHeading}>
            <Icon name={columnIcons[column.id]} size={22} />
            <span>{column.heading}</span>
          </h3>
          <ul className={styles.items}>{column.items.slice(0, VISIBLE_ITEMS).map(renderItem)}</ul>
          {column.items.length > VISIBLE_ITEMS && (
            <details className={styles.more}>
              <summary className={styles.moreSummary}>
                {text.showMore(column.items.length - VISIBLE_ITEMS)}
              </summary>
              <ul className={styles.items}>{column.items.slice(VISIBLE_ITEMS).map(renderItem)}</ul>
            </details>
          )}
        </div>
      ))}
    </div>
    <p className={styles.disclaimer}>
      {text.disclaimer} {text.verified(dateFormat.format(new Date(`${verifiedOn}T12:00:00`)))}
    </p>
  </Section>
);

export default SourcesSection;
