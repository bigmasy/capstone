import { uk } from "../../i18n/uk";
import Icon from "../Icon/Icon";
import Section from "./Section";
import styles from "./HowItWorks.module.css";

const text = uk.landing.how;

/** Four numbered steps from the profile to the accepted invitation. */
const HowItWorks = () => (
  <Section heading={text.heading} lead={text.lead} tone="tint">
    <ol className={`grid grid-4 ${styles.steps}`}>
      {text.steps.map((step, index) => (
        <li className={`card ${styles.step}`} key={step.title}>
          <div className={styles.top}>
            <span className={styles.iconWrap}>
              <Icon name={step.icon} size={28} />
            </span>
            <span className={styles.number}>{text.stepLabel(index + 1)}</span>
          </div>
          <h3 className={styles.title}>{step.title}</h3>
          <p className={styles.text}>{step.text}</p>
        </li>
      ))}
    </ol>
  </Section>
);

export default HowItWorks;
