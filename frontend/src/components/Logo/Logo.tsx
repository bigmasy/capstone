import styles from "./Logo.module.css";

interface LogoProps {
  /** Rendered width and height in CSS pixels. */
  size?: number;
}

/**
 * Logo mark: two training partners standing side by side, one light and one orange, on a pine
 * green tile. It is decorative: the product name is always written next to it.
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
    <rect className={styles.tile} width="48" height="48" rx="14" />
    <circle className={styles.headLeft} cx="16.5" cy="14.5" r="4.6" />
    <rect
      className={styles.bodyLeft}
      x="10.5"
      y="22"
      width="12"
      height="17"
      rx="6"
    />
    <circle className={styles.headRight} cx="31.5" cy="16.5" r="4.6" />
    <rect
      className={styles.bodyRight}
      x="25.5"
      y="24"
      width="12"
      height="15"
      rx="6"
    />
  </svg>
);

export default Logo;
