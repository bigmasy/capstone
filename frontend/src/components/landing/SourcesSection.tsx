import type { NewsColumn, NewsItem } from "../../api/types";
import { formatDate } from "../../i18n/format";
import { uk } from "../../i18n/uk";
import { useGetNewsQuery } from "../../redux/api/newsApi";
import ExternalLink from "../ExternalLink/ExternalLink";
import Icon, { type IconName } from "../Icon/Icon";
import Loader from "../Loader/Loader";
import Section from "./Section";
import styles from "./SourcesSection.module.css";

const text = uk.landing.sources;

const columnIcons: Record<NewsColumn["id"], IconName> = {
  world: "calendar",
  ukraine: "news",
  veterans: "building",
};

const renderItem = (item: NewsItem) => (
  <li className={styles.item} key={item.url}>
    <h4 className={styles.itemTitle}>
      <ExternalLink href={item.url}>{item.title}</ExternalLink>
    </h4>
    <p className={styles.source}>
      <span>{item.source}</span>
      <time className={styles.date} dateTime={item.published_at}>
        {formatDate(item.published_at)}
      </time>
    </p>
  </li>
);

/**
 * News about adaptive sport, collected from public feeds by a worker once a day and read
 * from the API here. It shows what was stored, never a list written into the page: a column
 * with nothing in it is left out, and a failed request offers to try again.
 */
const SourcesSection = () => {
  const { data, isLoading, isError, refetch } = useGetNewsQuery();

  // A column with nothing in it is not drawn, and a digest with nothing at all hides the section
  const filled = data?.columns.filter((column) => column.items.length > 0) ?? [];
  if (data && !isError && filled.length === 0) return null;

  let body;
  if (isLoading) {
    body = <Loader label={text.loading} />;
  } else if (isError || !data) {
    body = (
      <div>
        <p role="alert">{text.failed}</p>
        <button className="button button-secondary" type="button" onClick={() => void refetch()}>
          {text.retry}
        </button>
      </div>
    );
  } else {
    body = (
      <div className={`grid grid-3 ${styles.columns}`}>
        {filled.map((column) => (
          <div className={`card ${styles.column}`} key={column.id}>
            <h3 className={styles.columnHeading}>
              <Icon name={columnIcons[column.id]} size={22} />
              <span>{text.columns[column.id]}</span>
            </h3>
            <ul className={styles.items}>{column.items.map(renderItem)}</ul>
          </div>
        ))}
      </div>
    );
  }

  return (
    <Section heading={text.heading} lead={text.lead} tone="tint">
      {body}
      <p className={styles.disclaimer}>{text.disclaimer}</p>
    </Section>
  );
};

export default SourcesSection;
