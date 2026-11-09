import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import type { SearchRadius, SportCode } from "../../api/types";
import ErrorNotice from "../../components/ErrorNotice/ErrorNotice";
import Loader from "../../components/Loader/Loader";
import MatchCard from "../../components/MatchCard/MatchCard";
import MatchFilters from "../../components/MatchFilters/MatchFilters";
import Pagination from "../../components/Pagination/Pagination";
import { uk } from "../../i18n/uk";
import { FEED_PAGE_SIZE, useGetMatchesQuery } from "../../redux/api/feedApi";
import { isNoProfile, useGetTaxonomyQuery } from "../../redux/api/profileApi";
import styles from "./MatchesPage.module.css";

const text = uk.feed;

/**
 * The feed: filters, one page of candidates with the explanation of each position, and
 * pagination. A caller without a profile is sent to the profile page (the API answers 404).
 */
const MatchesPage = () => {
  const [radius, setRadius] = useState<SearchRadius>();
  const [sport, setSport] = useState<SportCode>();
  const [page, setPage] = useState(0);
  const [invited, setInvited] = useState<ReadonlySet<string>>(new Set());
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  const focusResults = useRef(false);

  const taxonomy = useGetTaxonomyQuery();
  const feed = useGetMatchesQuery({ page, radius, sport });
  // currentData belongs to the arguments shown now; data may still be the previous page
  const data = feed.currentData;
  const total = data?.total ?? 0;
  const lastPage = Math.max(0, Math.ceil(total / FEED_PAGE_SIZE) - 1);

  // The feed shrank while a later page was open: step back to the last page that exists.
  // Adjusting state while rendering is the supported way to derive it from fetched data.
  if (data && data.items.length === 0 && total > 0 && page > lastPage) setPage(lastPage);

  useEffect(() => {
    // After a page change the old focus target has been replaced, so focus the new results
    if (data && focusResults.current) {
      focusResults.current = false;
      resultsHeading.current?.focus();
    }
  }, [data]);

  const changeFilter = (apply: () => void) => {
    apply();
    setPage(0);
  };

  const changePage = (next: number) => {
    focusResults.current = true;
    setPage(next);
  };

  const markInvited = (profileId: string) => {
    setInvited((previous) => new Set(previous).add(profileId));
  };

  let announcement = "";
  let content;
  if (isNoProfile(feed.error)) {
    content = (
      <div>
        <p>{text.noProfile}</p>
        <Link className="button" to="/profile">
          {text.noProfileLink}
        </Link>
      </div>
    );
  } else if (!data && feed.isError) {
    content = (
      <ErrorNotice
        message={text.loadFailed}
        onRetry={() => void feed.refetch()}
        retryLabel={text.retry}
      />
    );
  } else if (!data) {
    content = <Loader label={text.loading} />;
  } else if (total === 0) {
    announcement = text.empty;
    content = (
      <section className={styles.empty}>
        <p>{text.emptyAdvice}</p>
        <Link className="button button-secondary" to="/profile">
          {text.emptyProfileLink}
        </Link>
      </section>
    );
  } else {
    const version = taxonomy.data?.version ?? "";
    const from = data.skip + 1;
    const to = data.skip + data.items.length;
    announcement = text.summary(from, to, total);
    content = (
      <>
        <h2 className={styles.resultsHeading} tabIndex={-1} ref={resultsHeading}>
          {text.resultsHeading}
        </h2>
        <ul className={styles.list}>
          {data.items.map((match) => (
            <MatchCard
              key={match.id}
              match={match}
              maxPoints={data.max_points}
              version={version}
              invited={invited.has(match.id)}
              onInvited={markInvited}
            />
          ))}
        </ul>
        <Pagination
          position={uk.pagination.pageOf(page + 1, lastPage + 1)}
          hasPrevious={page > 0}
          hasNext={page < lastPage}
          onPrevious={() => changePage(page - 1)}
          onNext={() => changePage(page + 1)}
        />
      </>
    );
  }

  return (
    <>
      <h1>{uk.pages.matches.title}</h1>
      <p>{text.lead}</p>
      <MatchFilters
        radius={radius}
        sport={sport}
        taxonomy={taxonomy.data}
        onRadiusChange={(value) => changeFilter(() => setRadius(value))}
        onSportChange={(value) => changeFilter(() => setSport(value))}
      />
      {/* Stays mounted so that a change of its text (the number of results) is announced */}
      <p className={styles.summary} role="status">
        {announcement}
      </p>
      {content}
    </>
  );
};

export default MatchesPage;
