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
      {item.source}
      <span aria-hidden="true"> · </span>
      <time dateTime={item.published_at}>{formatDate(item.published_at)}</time>
    </p>
  </li>
);

/**
 * News about adaptive sport, collected from public feeds by a worker once a day and read
 * from the API here. It shows what was stored, never a list written into the page: a column
 * with nothing in it says so, and a failed request offers to try again.
 */
const SourcesSection = () => {
  const { data, isLoading, isError, refetch } = useGetNewsQuery();

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
        {data.columns.map((column) => (
          <div className={`card ${styles.column}`} key={column.id}>
            <h3 className={styles.columnHeading}>
              <Icon name={columnIcons[column.id]} size={22} />
              <span>{text.columns[column.id]}</span>
            </h3>
            {column.items.length > 0 ? (
              <ul className={styles.items}>{column.items.map(renderItem)}</ul>
            ) : (
              <p className={styles.empty}>{text.empty}</p>
            )}
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
