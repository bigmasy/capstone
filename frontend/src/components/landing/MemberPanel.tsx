import { useId } from "react";
import { Link } from "react-router";
import { uk } from "../../i18n/uk";
import ProfileSummary from "../ProfileSummary/ProfileSummary";
import styles from "./MemberPanel.module.css";

/** Shown instead of the registration pitch to a logged-in visitor: their profile and the next steps. */
const MemberPanel = () => {
  const shortcutsId = useId();

  return (
    <section className={styles.panel} aria-label={uk.landing.member.heading}>
      <div className={`container ${styles.inner}`}>
        <div className={`card ${styles.profile}`}>
          <ProfileSummary />
        </div>
        <div className={`card ${styles.shortcuts}`}>
          <h2 id={shortcutsId} className={styles.heading}>
            {uk.pages.home.shortcutsHeading}
          </h2>
          <div className="cluster">
            <Link className="button" to="/matches">
              {uk.pages.home.openMatches}
            </Link>
            <Link className="button button-secondary" to="/invitations">
              {uk.pages.home.openInvitations}
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
};

export default MemberPanel;
