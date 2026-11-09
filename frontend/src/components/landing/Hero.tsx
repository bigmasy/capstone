import { Link } from "react-router";
import { uk } from "../../i18n/uk";
import Icon from "../Icon/Icon";
import HeroPreview from "./HeroPreview";
import styles from "./Hero.module.css";

interface HeroProps {
  isLoggedIn: boolean;
}

const text = uk.landing.hero;

/** Opening band of the landing page: the value proposition, the calls to action and the privacy assurances. */
const Hero = ({ isLoggedIn }: HeroProps) => (
  <section className={styles.hero}>
    {/* The soft shapes live in a box of their own, so that the section itself never clips text */}
    <div className={styles.decor} aria-hidden="true" />
    <div className={`container ${styles.inner}`}>
      <div className={styles.copy}>
        <p className="eyebrow">{text.eyebrow}</p>
        <h1 className={styles.title}>{uk.pages.home.title}</h1>
        <p className={styles.lead}>{uk.pages.home.lead}</p>
        <div className="cluster">
          {isLoggedIn ? (
            <>
              <Link className="button button-lg" to="/matches">
                {text.memberCta}
              </Link>
              <Link className="button button-lg button-secondary" to="/profile">
                {text.memberSecondary}
              </Link>
            </>
          ) : (
            <>
              <Link className="button button-lg" to="/register">
                {text.registerCta}
              </Link>
              <Link className="button button-lg button-secondary" to="/about">
                {text.learnMore}
              </Link>
            </>
          )}
        </div>
        <ul className={styles.assurances} aria-label={text.assurancesLabel}>
          {text.assurances.map((assurance) => (
            <li key={assurance}>
              <Icon name="shield" size={20} />
              <span>{assurance}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className={styles.art}>
        <HeroPreview />
      </div>
    </div>
  </section>
);

export default Hero;
