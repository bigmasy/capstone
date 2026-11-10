import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router";
import { uk } from "../../i18n/uk";
import AppBar from "../AppBar/AppBar";
import ErrorBoundary from "../ErrorBoundary/ErrorBoundary";
import Footer from "../Footer/Footer";
import SkipLink from "../SkipLink/SkipLink";
import VerificationBanner from "../VerificationBanner/VerificationBanner";
import { AUTH_PATHS } from "./photoPages";
import styles from "./Layout.module.css";

const MAIN_ID = "main-content";
const LANDING_PATH = "/";
// Sign-in and account pages sit beside a photograph on a wide screen
// The partner feed is a grid of cards and gets the full container width
const WIDE_APP_PATHS = new Set(["/matches", "/about"]);

function mainClass(pathname: string): string {
  if (pathname === LANDING_PATH) return `${styles.main} ${styles.mainWide}`;
  if (AUTH_PATHS.has(pathname)) return `${styles.main} ${styles.mainAuth}`;
  if (WIDE_APP_PATHS.has(pathname)) return `${styles.main} ${styles.mainApp}`;
  return styles.main ?? "";
}

/**
 * Page shell with the landmarks (banner, navigation, main, contentinfo).
 *
 * On every client-side navigation it updates the document title, moves focus to the
 * page heading and announces the new page through a polite live region, because a
 * single-page app does not trigger these browser behaviours on its own (WCAG 2.4.3, 4.1.3).
 */
const Layout = () => {
  const location = useLocation();
  const announcerRef = useRef<HTMLDivElement>(null);
  const handledLocationKey = useRef(location.key);

  useEffect(() => {
    const heading = document.querySelector<HTMLElement>(`#${MAIN_ID} h1`);
    const headingText = heading?.textContent?.trim() ?? "";
    document.title = headingText
      ? `${headingText}${uk.app.titleSeparator}${uk.app.name}`
      : uk.app.name;

    // Keep the first page load untouched so the skip link stays the first tab stop
    if (handledLocationKey.current === location.key) return;
    handledLocationKey.current = location.key;

    if (heading) {
      heading.setAttribute("tabindex", "-1");
      heading.focus();
    }
    if (announcerRef.current) {
      announcerRef.current.textContent = headingText;
    }
  }, [location.key]);

  return (
    <div className={styles.shell}>
      <SkipLink targetId={MAIN_ID} />
      <AppBar />
      <VerificationBanner />
      <main id={MAIN_ID} className={mainClass(location.pathname)} tabIndex={-1}>
        {AUTH_PATHS.has(location.pathname) ? (
          <div className={styles.authSplit}>
            <div className={styles.authForm}>
              <ErrorBoundary key={location.key}>
                <Outlet />
              </ErrorBoundary>
            </div>
            <div className={styles.authPhoto} aria-hidden="true" />
          </div>
        ) : (
          <ErrorBoundary key={location.key}>
            <Outlet />
          </ErrorBoundary>
        )}
      </main>
      <Footer />
      <div className="visually-hidden" role="status" ref={announcerRef} />
    </div>
  );
};

export default Layout;
