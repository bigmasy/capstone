import { useEffect, useId, useRef, useState } from "react";
import { Link, useLocation } from "react-router";
import { uk } from "../../i18n/uk";
import Icon from "../Icon/Icon";
import Logo from "../Logo/Logo";
import Navigation from "../Navigation/Navigation";
import styles from "./AppBar.module.css";

/**
 * Page header (banner landmark): logo, product name and the main navigation.
 *
 * On a narrow screen the navigation is a disclosure: a button with aria-expanded and
 * aria-controls shows and hides it, Escape closes it and returns focus to the button, and
 * it closes by itself after a link was followed. The open state is tied to the router
 * location key, so a route change collapses the menu without an effect.
 */
const AppBar = () => {
  const location = useLocation();
  const navId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [openKey, setOpenKey] = useState<string | null>(null);
  const open = openKey === location.key;

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpenKey(null);
      buttonRef.current?.focus();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  return (
    <header className={styles.header}>
      <div className={`container ${styles.inner}`}>
        <Link className={styles.brand} to="/">
          <Logo size={40} />
          <span className={styles.brandText}>
            <span className={styles.brandName}>{uk.app.name}</span>
            <span className={styles.brandDescriptor} aria-hidden="true">{uk.app.descriptor}</span>
          </span>
        </Link>
        <button
          ref={buttonRef}
          className={styles.menuButton}
          type="button"
          aria-expanded={open}
          aria-controls={navId}
          onClick={() => setOpenKey(open ? null : location.key)}
        >
          <Icon name={open ? "close" : "menu"} size={22} />
          <span>{uk.nav.menu}</span>
        </button>
        <Navigation id={navId} open={open} onNavigate={() => setOpenKey(null)} />
      </div>
    </header>
  );
};

export default AppBar;
