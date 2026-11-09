import { uk } from "../../i18n/uk";
import Icon from "../Icon/Icon";
import Section from "./Section";
import styles from "./AudienceSection.module.css";

const text = uk.landing.audience;

/** Who the service is for: three short cards. */
const AudienceSection = () => (
  <Section heading={text.heading}>
    <ul className={`grid grid-3 ${styles.list}`}>
      {text.items.map((item) => (
        <li className={styles.item} key={item.title}>
          <span className={styles.iconWrap}>
            <Icon name={item.icon} size={26} />
          </span>
          <h3 className={styles.title}>{item.title}</h3>
          <p className={styles.text}>{item.text}</p>
        </li>
      ))}
    </ul>
  </Section>
);

export default AudienceSection;
