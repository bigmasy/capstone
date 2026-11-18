import type { ReactNode } from "react";
import { uk } from "../../i18n/uk";
import { useGetProfilePhotoQuery } from "../../redux/api/photoApi";
import styles from "./Avatar.module.css";
import { initialOf, placeholderLook, type Motif } from "./placeholder";

interface AvatarProps {
  /** Identifier of the profile: it selects the placeholder and addresses the photograph. */
  profileId: string;
  /** Name shown next to the picture; its first letter is drawn on the placeholder. */
  name: string;
  /** Whether the profile has a photograph the caller may load. */
  hasPhoto: boolean;
  size?: "sm" | "md" | "lg";
}

/** The six scenes, each drawn in a 64 by 64 box with the current colour. */
const SCENES: Record<Motif, ReactNode> = {
  // Lanes of a running track bending around a corner
  track: (
    <g fill="none" stroke="currentColor" strokeWidth="3.5">
      <circle cx="0" cy="64" r="22" />
      <circle cx="0" cy="64" r="34" />
      <circle cx="0" cy="64" r="46" />
      <circle cx="0" cy="64" r="58" />
    </g>
  ),
  // Water of a pool with a lane rope
  waves: (
    <g fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round">
      <path d="M-4 40 q9 -8 18 0 t18 0 t18 0 t18 0" />
      <path d="M-4 51 q9 -8 18 0 t18 0 t18 0 t18 0" />
      <path d="M-4 62 q9 -8 18 0 t18 0 t18 0 t18 0" />
      <path d="M4 26 h56" strokeDasharray="1 7" />
    </g>
  ),
  // Mountains with a low sun, for the outdoor sports
  peaks: (
    <g fill="currentColor">
      <circle cx="47" cy="17" r="6" opacity="0.55" />
      <path d="M-2 66 L20 30 L34 50 L44 38 L66 66 Z" opacity="0.85" />
      <path d="M20 30 L26 39 L20 43 L15 38 Z" fill="var(--avatar-background)" />
    </g>
  ),
  // An archery target seen from the side of the frame
  target: (
    <g fill="none" stroke="currentColor" strokeWidth="3.5">
      <circle cx="46" cy="46" r="30" />
      <circle cx="46" cy="46" r="19" />
      <circle cx="46" cy="46" r="8" fill="currentColor" stroke="none" />
    </g>
  ),
  // A net with a ball above it
  net: (
    <g stroke="currentColor" strokeWidth="2.5" fill="none">
      <path d="M0 40 h64 M0 50 h64 M0 60 h64" />
      <path d="M8 38 v28 M20 38 v28 M32 38 v28 M44 38 v28 M56 38 v28" />
      <path d="M0 38 h64" strokeWidth="4" />
      <circle cx="46" cy="18" r="7" fill="currentColor" stroke="none" />
    </g>
  ),
  // A sun rising over a road, for the early training
  sunrise: (
    <g fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round">
      <path d="M12 48 a20 20 0 0 1 40 0" fill="currentColor" stroke="none" opacity="0.8" />
      <path d="M32 14 v8 M10 26 l6 5 M54 26 l-6 5" />
      <path d="M0 56 h64" />
    </g>
  ),
};

/**
 * The picture of a profile: its photograph, or a placeholder drawn from the profile identifier.
 *
 * Purely decorative next to the name it belongs to, so it is hidden from assistive technology;
 * the name is always shown beside it. The placeholder is also what is shown while a photograph
 * is loading and when it cannot be loaded.
 */
const Avatar = ({ profileId, name, hasPhoto, size = "md" }: AvatarProps) => {
  const photo = useGetProfilePhotoQuery(profileId, { skip: !hasPhoto });
  const look = placeholderLook(profileId);
  const className = `${styles.avatar} ${styles[size]}`;

  if (hasPhoto && photo.data && !photo.isError) {
    return (
      <img className={className} src={photo.data} alt="" data-avatar="photo" />
    );
  }

  return (
    <svg
      className={className}
      viewBox="0 0 64 64"
      aria-hidden="true"
      focusable="false"
      data-avatar={look.motif}
      style={{ "--avatar-background": look.background, color: look.ink } as React.CSSProperties}
    >
      <rect width="64" height="64" fill="var(--avatar-background)" />
      <g transform={look.flipped ? "translate(64 0) scale(-1 1)" : undefined} opacity="0.5">
        {SCENES[look.motif]}
      </g>
      <text className={styles.initial} x="32" y="33" textAnchor="middle" dominantBaseline="central">
        {initialOf(name) || uk.avatar.noInitial}
      </text>
    </svg>
  );
};

export default Avatar;
