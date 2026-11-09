import styles from "./HeroIllustration.module.css";

/**
 * Hero artwork: a map card with a 4 x 4 grid whose single highlighted cell stands for the
 * rounded training area, two partners joined by a dashed line, and a three-level meter.
 * Decorative, so it is hidden from assistive technology.
 */
const HeroIllustration = () => (
  <svg
    className={styles.art}
    viewBox="0 0 480 400"
    aria-hidden="true"
    focusable="false"
    preserveAspectRatio="xMidYMid meet"
  >
    <circle className={styles.blob} cx="250" cy="200" r="190" />
    <circle className={styles.blobSmall} cx="420" cy="70" r="34" />

    {/* Map card */}
    <rect className={styles.card} x="70" y="46" width="260" height="260" rx="22" />
    <g className={styles.gridLines}>
      <path d="M135 46v260M200 46v260M265 46v260" />
      <path d="M70 111h260M70 176h260M70 241h260" />
    </g>
    <rect className={styles.cell} x="200" y="111" width="65" height="65" />
    <circle className={styles.cellDot} cx="232.5" cy="143.5" r="7" />

    {/* Partners and the line between them */}
    <path className={styles.link} d="M128 292C150 230 196 232 232 214C268 196 300 214 322 248" />
    <g>
      <circle className={styles.personA} cx="116" cy="316" r="22" />
      <path className={styles.personA} d="M78 372c2-24 18-36 38-36s36 12 38 36z" />
    </g>
    <g>
      <circle className={styles.personB} cx="344" cy="278" r="22" />
      <path className={styles.personB} d="M306 334c2-24 18-36 38-36s36 12 38 36z" />
    </g>

    {/* Level meter: only a coarse level is ever shown to others */}
    <rect className={styles.meterCard} x="332" y="64" width="112" height="86" rx="16" />
    <rect className={styles.barOn} x="352" y="108" width="16" height="26" rx="4" />
    <rect className={styles.barOn} x="380" y="92" width="16" height="42" rx="4" />
    <rect className={styles.barOff} x="408" y="80" width="16" height="54" rx="4" />
  </svg>
);

export default HeroIllustration;
