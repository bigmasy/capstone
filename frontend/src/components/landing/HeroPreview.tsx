import { uk } from "../../i18n/uk";
import Avatar from "../Avatar/Avatar";
import styles from "./HeroPreview.module.css";

const text = uk.landing.hero.preview;

/**
 * A sample partner card for the opening band. It shows what the product returns (sports, a
 * distance band, a qualitative level) without any real person or point value. Decorative and
 * hidden from assistive technology, because the page text already says the same.
 */
const HeroPreview = () => (
  <div className={styles.wrap} aria-hidden="true">
    <div className={styles.card}>
      <p className={styles.label}>{text.label}</p>
      <div className={styles.who}>
        <Avatar profileId="hero-preview" name={text.name} hasPhoto={false} />
        <div>
          <p className={styles.name}>{text.name}</p>
          <p className={styles.place}>{text.place}</p>
        </div>
      </div>
      <ul className={styles.sports}>
        {text.sports.map((sport) => (
          <li key={sport}>{sport}</li>
        ))}
      </ul>
      <ul className={styles.criteria}>
        {text.criteria.map((criterion) => (
          <li key={criterion.name}>
            <span>{criterion.name}</span>
            <span className={styles.track}>
              <span
                className={styles.fill}
                style={{ width: `${criterion.share}%` }}
              />
            </span>
          </li>
        ))}
      </ul>
      <p className={styles.level}>{text.level}</p>
    </div>
    <div className={styles.privacy}>
      <span className={styles.cells}>
        {Array.from({ length: 9 }, (_, index) => (
          <span
            key={index}
            className={index === 4 ? styles.cellOn : styles.cell}
          />
        ))}
      </span>
      <span>{text.privacy}</span>
    </div>
  </div>
);

export default HeroPreview;
