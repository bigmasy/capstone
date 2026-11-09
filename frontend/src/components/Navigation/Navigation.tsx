import { NavLink } from "react-router";
import { uk } from "../../i18n/uk";
import { selectIsLoggedIn } from "../../redux/auth/selectors";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import { logout } from "../../redux/auth/slice";
import styles from "./Navigation.module.css";

interface NavItem {
  to: string;
  label: string;
  /** Rendered as a button-looking call to action. */
  emphasis?: boolean;
}

const visitorItems: NavItem[] = [
  { to: "/", label: uk.nav.home },
  { to: "/about", label: uk.nav.about },
  { to: "/login", label: uk.nav.login },
  { to: "/register", label: uk.nav.register, emphasis: true },
];
const memberItems: NavItem[] = [
  { to: "/matches", label: uk.nav.matches },
  { to: "/invitations", label: uk.nav.invitations },
  { to: "/profile", label: uk.nav.profile },
];

interface NavigationProps {
  /** Id that the menu button of the header points to with aria-controls. */
  id?: string;
  /** Whether the list is expanded on a narrow screen; a wide screen always shows it. */
  open?: boolean;
  /** Called after a link or the sign out button was used, so that the header can collapse the menu. */
  onNavigate?: () => void;
}

/**
 * Main navigation landmark; NavLink sets aria-current="page" on the active link. A visitor
 * gets the public pages, a logged-in user gets the member pages and the sign out button.
 */
const Navigation = ({ id, open = false, onNavigate }: NavigationProps) => {
  const dispatch = useAppDispatch();
  const isLoggedIn = useAppSelector(selectIsLoggedIn);
  const items = isLoggedIn ? memberItems : visitorItems;

  const handleLogout = () => {
    // The session watcher sends the user to the landing page, whose heading receives focus
    dispatch(logout());
    onNavigate?.();
  };

  return (
    <nav
      id={id}
      className={open ? `${styles.nav} ${styles.navOpen}` : styles.nav}
      aria-label={uk.a11y.mainNavigation}
    >
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end
              className={item.emphasis ? `button ${styles.cta}` : styles.link}
              onClick={onNavigate}
            >
              {item.label}
            </NavLink>
          </li>
        ))}
        {isLoggedIn && (
          <li>
            <button className={`button button-secondary ${styles.logout}`} type="button" onClick={handleLogout}>
              {uk.nav.logout}
            </button>
          </li>
        )}
      </ul>
    </nav>
  );
};

export default Navigation;
