import { Link } from "react-router";
import { selectIsLoggedIn } from "../../redux/auth/selectors";
import { useAppSelector } from "../../redux/hooks";
import { uk } from "../../i18n/uk";

const text = uk.aboutPage;

/** What the platform is, how it ranks partners and which data it keeps. */
const AboutPage = () => {
  const isLoggedIn = useAppSelector(selectIsLoggedIn);

  return (
    <>
      <h1>{uk.pages.about.title}</h1>
      <p>{text.lead}</p>
      <h2>{text.goalHeading}</h2>
      <p>{text.goal}</p>
      <h2>{text.howHeading}</h2>
      <p>{text.how}</p>
      <h2>{text.dataHeading}</h2>
      <p>{text.data}</p>
      <h2>{text.privacyHeading}</h2>
      <p>{text.privacy}</p>
      <h2>{text.limitsHeading}</h2>
      <p>{text.limits}</p>
      <p>
        {isLoggedIn ? (
          <Link className="button" to="/matches">
            {uk.landing.hero.memberCta}
          </Link>
        ) : (
          <Link className="button" to="/register">
            {uk.landing.hero.registerCta}
          </Link>
        )}
      </p>
    </>
  );
};

export default AboutPage;
