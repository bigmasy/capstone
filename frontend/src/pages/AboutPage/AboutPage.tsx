import { Link } from "react-router";
import Icon, { type IconName } from "../../components/Icon/Icon";
import { selectIsLoggedIn } from "../../redux/auth/selectors";
import { useAppSelector } from "../../redux/hooks";
import { uk } from "../../i18n/uk";
import styles from "./AboutPage.module.css";

const text = uk.aboutPage;

/** What the platform is, how it ranks partners and which data it keeps. */
const AboutPage = () => {
  const isLoggedIn = useAppSelector(selectIsLoggedIn);

  const sections: { icon: IconName; heading: string; body: string }[] = [
    { icon: "heart", heading: text.goalHeading, body: text.goal },
    { icon: "match", heading: text.howHeading, body: text.how },
    { icon: "profile", heading: text.dataHeading, body: text.data },
    { icon: "shield", heading: text.privacyHeading, body: text.privacy },
    { icon: "hidden", heading: text.limitsHeading, body: text.limits },
  ];

  return (
    <div className={styles.layout}>
      <div className={styles.text}>
        <h1>{uk.pages.about.title}</h1>
        <p className={styles.lead}>{text.lead}</p>
        {sections.map(({ icon, heading, body }) => (
          <section className={styles.section} key={heading}>
            <h2 className={styles.heading}>
              <Icon name={icon} size={22} />
              <span>{heading}</span>
            </h2>
            <p>{body}</p>
          </section>
        ))}
      </div>
      <aside className={styles.aside}>
        <div className={styles.photo} aria-hidden="true" />
        <div className={styles.action}>
          {isLoggedIn ? (
            <Link className="button" to="/matches">
              {uk.landing.hero.memberCta}
            </Link>
          ) : (
            <Link className="button" to="/register">
              {uk.landing.hero.registerCta}
            </Link>
          )}
        </div>
      </aside>
    </div>
  );
};

export default AboutPage;
