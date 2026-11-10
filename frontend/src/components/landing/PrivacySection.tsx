import { useId } from "react";
import { uk } from "../../i18n/uk";
import Icon from "../Icon/Icon";
import styles from "./PrivacySection.module.css";

const text = uk.landing.privacy;

/** The four promises about personal data, on a dark band so that they are the page's one statement. */
const PrivacySection = () => {
  const headingId = useId();

  return (
    <section className={styles.band} aria-labelledby={headingId}>
      <div className="container">
        <header className={styles.header}>
          <h2 id={headingId} className={styles.heading}>
            {text.heading}
          </h2>
          <p className={styles.lead}>{text.lead}</p>
        </header>
        <ul className={`grid grid-2 ${styles.list}`}>
          {text.items.map((item) => (
            <li className={styles.item} key={item.title}>
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
      </div>
    </section>
  );
};

export default PrivacySection;
