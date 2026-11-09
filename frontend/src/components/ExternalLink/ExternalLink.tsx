import type { ReactNode } from "react";
import { uk } from "../../i18n/uk";
import Icon from "../Icon/Icon";
import styles from "./ExternalLink.module.css";

interface ExternalLinkProps {
  href: string;
  children: ReactNode;
}

/**
 * Link to another site. It opens in a new tab, so the link says so in text for assistive
 * technology and shows an icon for everyone; rel keeps the new page from reaching this one.
 */
const ExternalLink = ({ href, children }: ExternalLinkProps) => (
  <a className={styles.link} href={href} target="_blank" rel="noopener noreferrer">
    {children} <span className="visually-hidden">({uk.a11y.opensInNewTab})</span>
    <Icon name="external" size={16} />
  </a>
);

export default ExternalLink;
