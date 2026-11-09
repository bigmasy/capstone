import type { MouseEvent } from "react";
import { uk } from "../../i18n/uk";
import styles from "./SkipLink.module.css";

interface SkipLinkProps {
  /** Id of the element that holds the main content; it must be focusable (tabIndex -1). */
  targetId: string;
}

/** First focusable element of the page; lets keyboard users bypass the navigation (WCAG 2.4.1). */
const SkipLink = ({ targetId }: SkipLinkProps) => {
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    const target = document.getElementById(targetId);
    if (!target) return;
    // Moving focus explicitly works in every browser and keeps the URL free of a hash
    event.preventDefault();
    target.focus();
  };

  return (
    <a className={styles.skipLink} href={`#${targetId}`} onClick={handleClick}>
      {uk.a11y.skipToContent}
    </a>
  );
};

export default SkipLink;
