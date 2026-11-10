import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router";
import type { InvitationDirection, InvitationStatus } from "../../api/types";
import ErrorNotice from "../../components/ErrorNotice/ErrorNotice";
import InvitationCard from "../../components/InvitationCard/InvitationCard";
import type { ActionFeedback } from "../../components/InvitationCard/InvitationActions";
import InvitationTabs, { tabIds } from "../../components/InvitationTabs/InvitationTabs";
import Loader from "../../components/Loader/Loader";
import Pagination from "../../components/Pagination/Pagination";
import SelectField from "../../components/SelectField/SelectField";
import { uk } from "../../i18n/uk";
import { pageOfInvitations, useGetInvitationsQuery } from "../../redux/api/invitationsApi";
import { useGetTaxonomyQuery } from "../../redux/api/profileApi";
import styles from "./InvitationsPage.module.css";

const text = uk.invitations;

const STATUSES: readonly InvitationStatus[] = [
  "pending",
  "accepted",
  "declined",
  "cancelled",
  "expired",
];

/**
 * Incoming and outgoing invitations with a status filter and pagination. The answer to an
 * action is reported in a message above the list, which takes focus, because the card that
 * was answered usually changes or leaves the list.
 */
const InvitationsPage = () => {
  const idBase = useId();
  const panelId = `${idBase}-panel`;
  const [direction, setDirection] = useState<InvitationDirection>("incoming");
  const [status, setStatus] = useState<InvitationStatus>();
  const [page, setPage] = useState(0);
  const [feedback, setFeedback] = useState<ActionFeedback | null>(null);
  const feedbackRef = useRef<HTMLParagraphElement>(null);
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  const focusResults = useRef(false);

  const taxonomy = useGetTaxonomyQuery();
  const invitations = useGetInvitationsQuery({ direction, status, page });
  const data = invitations.currentData;
  const shown = data ? pageOfInvitations(data) : undefined;

  // The last invitation of a later page was answered: step back to the page before it
  if (shown && shown.items.length === 0 && page > 0) setPage(page - 1);

  useEffect(() => {
    if (feedback) feedbackRef.current?.focus();
  }, [feedback]);

  useEffect(() => {
    // After a page change the old focus target has been replaced, so focus the new results
    if (data && focusResults.current) {
      focusResults.current = false;
      resultsHeading.current?.focus();
    }
  }, [data]);

  const changeView = (apply: () => void) => {
    apply();
    setPage(0);
    setFeedback(null);
  };

  const changePage = (next: number) => {
    focusResults.current = true;
    setFeedback(null);
    setPage(next);
  };

  let announcement = "";
  let content;
  if (!shown && invitations.isError) {
    content = (
      <ErrorNotice
        message={text.loadFailed}
        onRetry={() => void invitations.refetch()}
        retryLabel={text.retry}
      />
    );
  } else if (!shown) {
    content = <Loader label={text.loading} />;
  } else if (shown.items.length === 0) {
    announcement = status
      ? text.emptyFiltered
      : direction === "incoming"
        ? text.emptyIncoming
        : text.emptyOutgoing;
    content =
      direction === "outgoing" && !status ? (
        <Link className="button button-secondary" to="/matches">
          {text.toMatches}
        </Link>
      ) : null;
  } else {
    const version = taxonomy.data?.version ?? "";
    announcement = text.summary(shown.items.length);
    content = (
      <>
        <h2 className={styles.resultsHeading} tabIndex={-1} ref={resultsHeading}>
          {text.listHeading}
        </h2>
        <ul className={styles.list}>
          {shown.items.map((invitation) => (
            <InvitationCard
              key={invitation.id}
              invitation={invitation}
              version={version}
              onFeedback={setFeedback}
            />
          ))}
        </ul>
      </>
    );
  }

  const showPagination = shown !== undefined && (page > 0 || shown.hasNext);

  return (
    <>
      <h1>{uk.pages.invitations.title}</h1>
      <p>{text.lead}</p>
      <InvitationTabs
        value={direction}
        onChange={(value) => changeView(() => setDirection(value))}
        idBase={idBase}
        panelId={panelId}
      />
      {/* With nothing sent or received there is nothing to sort by status; a set filter stays */}
      {(status !== undefined || (shown !== undefined && (shown.items.length > 0 || page > 0))) && (
        <SelectField
          label={text.statusFilter}
          name="status"
          placeholder={text.statusAll}
          options={STATUSES.map((value) => ({ value, label: text.status[value] }))}
          value={status ?? ""}
          onChange={(event) =>
            changeView(() => setStatus(STATUSES.find((value) => value === event.target.value)))
          }
        />
      )}
      {feedback && (
        <p
          className={feedback.kind === "error" ? styles.feedbackError : styles.feedback}
          role={feedback.kind === "error" ? "alert" : "status"}
          tabIndex={-1}
          ref={feedbackRef}
        >
          {feedback.kind === "error" && <strong>{uk.form.errorPrefix}</strong>} {feedback.text}
        </p>
      )}
      <div role="tabpanel" id={panelId} aria-labelledby={tabIds(idBase, direction)}>
        {/* Stays mounted so that a change of its text (the number of results) is announced */}
        <p className={styles.summary} role="status">
          {announcement}
        </p>
        {content}
        {showPagination && (
          <Pagination
            position={uk.pagination.page(page + 1)}
            hasPrevious={page > 0}
            hasNext={shown.hasNext}
            onPrevious={() => changePage(page - 1)}
            onNext={() => changePage(page + 1)}
          />
        )}
      </div>
    </>
  );
};

export default InvitationsPage;
