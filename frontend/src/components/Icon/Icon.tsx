import styles from "./Icon.module.css";

/** Stroke paths on a 24 x 24 grid; every icon is original and purely decorative. */
const paths = {
  profile: ["M12 4.5a3.75 3.75 0 1 0 0 7.5a3.75 3.75 0 0 0 0-7.5z", "M5 20c0-3.9 3.1-7 7-7s7 3.1 7 7"],
  area: ["M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z", "M12 4v16", "M4 12h16", "M12 12h8v8h-8z"],
  match: ["M9 7a5 5 0 1 0 0 10a5 5 0 0 0 0-10z", "M15 7a5 5 0 1 0 0 10a5 5 0 0 0 0-10z"],
  invite: ["M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M3.5 7.5l8.5 6l8.5-6"],
  shield: ["M12 3l7 3v5.5c0 4.4-2.9 8-7 9.5c-4.1-1.5-7-5.1-7-9.5V6z", "M9 12l2 2l4-4"],
  hidden: ["M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12z", "M12 9.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 0 0 0-5z", "M4 4l16 16"],
  lock: ["M5 11h14v9H5z", "M8 11V8a4 4 0 0 1 8 0v3"],
  trash: ["M4 7h16", "M9 7V4h6v3", "M6.5 7l1 13h9l1-13"],
  levels: ["M5 20v-5", "M12 20V10", "M19 20V4"],
  heart: ["M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"],
  path: ["M3 18c4 0 4-12 9-12s5 12 9 12"],
  chevron: ["M6 9l6 6l6-6"],
  menu: ["M4 7h16", "M4 12h16", "M4 17h16"],
  close: ["M6 6l12 12", "M18 6L6 18"],
  external: ["M14 4h6v6", "M20 4l-9 9", "M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"],
  calendar: ["M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z", "M4 10h16", "M8 3v3", "M16 3v3"],
  news: ["M5 4h11a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2z", "M18 9h2v9a2 2 0 0 1-2 2", "M8 8h7", "M8 12h7", "M8 16h4"],
  building: ["M4 20h16", "M6 20V8l6-4l6 4v12", "M10 20v-5h4v5"],
} as const;

export type IconName = keyof typeof paths;

interface IconProps {
  name: IconName;
  /** Rendered width and height in CSS pixels. */
  size?: number;
}

/** Decorative icon in the colour of the surrounding text (currentColor). */
const Icon = ({ name, size = 24 }: IconProps) => (
  <svg
    className={styles.icon}
    width={size}
    height={size}
    viewBox="0 0 24 24"
    aria-hidden="true"
    focusable="false"
  >
    {paths[name].map((d) => (
      <path key={d} d={d} />
    ))}
  </svg>
);

export default Icon;
