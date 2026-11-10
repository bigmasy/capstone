import { NavLink, useLocation } from "react-router";
import { uk } from "../../i18n/uk";
import { selectIsLoggedIn } from "../../redux/auth/selectors";
import { useAppSelector } from "../../redux/hooks";
import Logo from "../Logo/Logo";
import { PHOTO_PATHS } from "../Layout/photoPages";
import styles from "./Footer.module.css";

const visitorLinks = [
  { to: "/", label: uk.nav.home },
  { to: "/about", label: uk.nav.about },
  { to: "/login", label: uk.nav.login },
  { to: "/register", label: uk.nav.register },
];
const memberLinks = [
  { to: "/", label: uk.nav.home },
  { to: "/about", label: uk.nav.about },
  { to: "/matches", label: uk.nav.matches },
  { to: "/invitations", label: uk.nav.invitations },
  { to: "/profile", label: uk.nav.profile },
];

/** Page footer (contentinfo landmark): product name, links to the pages and a short privacy note. */
const Footer = () => {
  const isLoggedIn = useAppSelector(selectIsLoggedIn);
  const links = isLoggedIn ? memberLinks : visitorLinks;
  // The credits belong to the photographs; a page without one has nothing to credit
  const showCredits = PHOTO_PATHS.has(useLocation().pathname);

  return (
    <footer className={styles.footer}>
      <div className={`container ${styles.inner}`}>
        <div>
          <p className={styles.brand}>
            <Logo size={32} />
            <span>{uk.app.name}</span>
          </p>
          <p className={styles.muted}>{uk.footer.tagline}</p>
        </div>
        <nav aria-label={uk.a11y.footerNavigation}>
          <h2 className={styles.heading}>{uk.footer.linksHeading}</h2>
          <ul className={styles.links}>
            {links.map((link) => (
              <li key={link.to}>
                <NavLink to={link.to} end className={styles.link}>
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div>
          <h2 className={styles.heading}>{uk.footer.privacyHeading}</h2>
          <p className={styles.muted}>{uk.footer.note}</p>
        </div>
        {showCredits && (
          <p className={styles.credits} data-credits>
            {uk.footer.photosLabel}{" "}
            {uk.footer.photos.map((photo, index) => (
              <span key={photo.href}>
                {index > 0 && ", "}
                <a href={photo.href} target="_blank" rel="noreferrer">
                  {photo.author}
                </a>{" "}
                ({photo.licence})
              </span>
            ))}
          </p>
        )}
      </div>
    </footer>
  );
};

export default Footer;
