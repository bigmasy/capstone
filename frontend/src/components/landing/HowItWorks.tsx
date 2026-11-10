import { uk } from "../../i18n/uk";
import Section from "./Section";
import styles from "./HowItWorks.module.css";

const text = uk.landing.how;

/** Four numbered steps from the profile to the accepted invitation, set as a row of large numerals. */
const HowItWorks = () => (
  <Section heading={text.heading} lead={text.lead} tone="tint">
    <ol className={`grid grid-4 ${styles.steps}`}>
      {text.steps.map((step, index) => (
        <li className={styles.step} key={step.title}>
          <span className={styles.numeral} aria-hidden="true">
            {index + 1}
          </span>
          <span className="visually-hidden">{text.stepLabel(index + 1)}</span>
          <h3 className={styles.title}>{step.title}</h3>
          <p className={styles.text}>{step.text}</p>
        </li>
      ))}
    </ol>
  </Section>
);

export default HowItWorks;
