import { useId } from "react";
import { Link } from "react-router";
import { uk } from "../../i18n/uk";
import styles from "./FinalCta.module.css";

interface FinalCtaProps {
  isLoggedIn: boolean;
}

const text = uk.landing.finalCta;

/** Closing call to action on a dark band. */
const FinalCta = ({ isLoggedIn }: FinalCtaProps) => {
  const headingId = useId();

  return (
    <section className={styles.band} aria-labelledby={headingId}>
      <div className={`container ${styles.inner}`}>
        <h2 id={headingId} className={styles.heading}>
          {isLoggedIn ? text.memberHeading : text.heading}
        </h2>
        <p className={styles.text}>{isLoggedIn ? text.memberText : text.text}</p>
        <div className="cluster">
          {isLoggedIn ? (
            <>
              <Link className="button button-lg button-inverse" to="/matches">
                {uk.landing.hero.memberCta}
              </Link>
              <Link className="button button-lg button-inverse-outline" to="/invitations">
                {text.invitations}
              </Link>
            </>
          ) : (
            <>
              <Link className="button button-lg button-inverse" to="/register">
                {uk.landing.hero.registerCta}
              </Link>
              <Link className="button button-lg button-inverse-outline" to="/login">
                {uk.nav.login}
              </Link>
            </>
          )}
        </div>
      </div>
    </section>
  );
};

export default FinalCta;
