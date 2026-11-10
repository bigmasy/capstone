import { Link } from "react-router";
import { uk } from "../../i18n/uk";
import Icon from "../Icon/Icon";
import HeroPreview from "./HeroPreview";
import styles from "./Hero.module.css";

interface HeroProps {
  isLoggedIn: boolean;
}

const text = uk.landing.hero;

/**
 * Opening band of the landing page: a photograph of a pool under a dark veil, the value
 * proposition, the calls to action, and a sample partner card. The photograph is decorative.
 */
const Hero = ({ isLoggedIn }: HeroProps) => (
  <section className={styles.hero}>
    <img
      className={styles.photo}
      src="/images/pool.jpg"
      alt=""
      width="1600"
      height="1200"
      fetchPriority="high"
    />
    <div className={styles.veil} aria-hidden="true" />
    <div className={`container ${styles.inner}`}>
      <div className={styles.copy}>
        <h1 className={styles.title}>{uk.pages.home.title}</h1>
        <p className={styles.lead}>{uk.pages.home.lead}</p>
        <div className="cluster">
          {isLoggedIn ? (
            <>
              <Link className="button button-lg button-inverse" to="/matches">
                {text.memberCta}
              </Link>
              <Link
                className="button button-lg button-inverse-outline"
                to="/profile"
              >
                {text.memberSecondary}
              </Link>
            </>
          ) : (
            <>
              <Link className="button button-lg button-inverse" to="/register">
                {text.registerCta}
              </Link>
              <Link
                className="button button-lg button-inverse-outline"
                to="/about"
              >
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
