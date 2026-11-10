import { Link } from "react-router";
import { uk } from "../../i18n/uk";
import Section from "./Section";
import styles from "./WhySection.module.css";

const text = uk.landing.why;

/** The problem the service addresses, phrased without claims that cannot be sourced. */
const WhySection = () => (
  <Section heading={text.heading}>
    <div className={styles.layout}>
      <div className={styles.photo} aria-hidden="true" />
      <div className={styles.story}>
        <h3>{text.problemHeading}</h3>
        <p>{text.problem}</p>
        <h3>{text.supportHeading}</h3>
        <p>{text.support}</p>
        <h3>{text.approachHeading}</h3>
        <p>{text.approach}</p>
        <p className={styles.limits}>{text.limits}</p>
        <Link className="link-standalone" to="/about">
          {text.readMore}
        </Link>
      </div>
    </div>
  </Section>
);

export default WhySection;
