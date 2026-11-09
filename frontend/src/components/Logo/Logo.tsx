import styles from "./Logo.module.css";

interface LogoProps {
  /** Rendered width and height in CSS pixels. */
  size?: number;
}

/**
 * Logo mark: an arch of two legs that lean towards each other, one light and one orange,
 * for two training partners side by side. It is decorative: the product name is always
 * written next to it.
 */
const Logo = ({ size = 40 }: LogoProps) => (
  <svg
    className={styles.logo}
    width={size}
    height={size}
    viewBox="0 0 48 48"
    aria-hidden="true"
    focusable="false"
  >
    <rect className={styles.tile} width="48" height="48" rx="11" />
    <path className={styles.legLeft} d="M14 36V22a8 8 0 0 1 8-8h1.4" />
    <path className={styles.legRight} d="M26.6 14H27a8 8 0 0 1 8 8v14" />
    <circle className={styles.footLeft} cx="14" cy="36" r="3.2" />
    <circle className={styles.footRight} cx="35" cy="36" r="3.2" />
  </svg>
);

export default Logo;
