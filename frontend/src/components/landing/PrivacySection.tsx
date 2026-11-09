import { uk } from "../../i18n/uk";
import Icon from "../Icon/Icon";
import Section from "./Section";
import styles from "./PrivacySection.module.css";

const text = uk.landing.privacy;

/** The four promises about personal data, each with an icon. */
const PrivacySection = () => (
  <Section heading={text.heading} lead={text.lead} tone="tint">
    <ul className={`grid grid-2 ${styles.list}`}>
      {text.items.map((item) => (
        <li className={`card ${styles.item}`} key={item.title}>
          <span className={styles.iconWrap}>
            <Icon name={item.icon} size={26} />
          </span>
          <div>
            <h3 className={styles.title}>{item.title}</h3>
            <p className={styles.text}>{item.text}</p>
          </div>
        </li>
      ))}
    </ul>
  </Section>
);

export default PrivacySection;
