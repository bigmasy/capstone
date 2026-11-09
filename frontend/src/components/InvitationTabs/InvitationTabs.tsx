import { useRef, type KeyboardEvent } from "react";
import type { InvitationDirection } from "../../api/types";
import { uk } from "../../i18n/uk";
import styles from "./InvitationTabs.module.css";

const DIRECTIONS: readonly InvitationDirection[] = ["incoming", "outgoing"];

const labels: Readonly<Record<InvitationDirection, string>> = {
  incoming: uk.invitations.incoming,
  outgoing: uk.invitations.outgoing,
};

/** Ids that tie a tab to the panel it controls; the page puts `panelId` on its panel. */
export const tabIds = (idBase: string, direction: InvitationDirection) => `${idBase}-${direction}`;

interface InvitationTabsProps {
  value: InvitationDirection;
  onChange: (direction: InvitationDirection) => void;
  idBase: string;
  panelId: string;
}

/**
 * Incoming and outgoing as a tab list (WAI-ARIA tabs pattern with manual focus handling):
 * only the selected tab is in the tab order, and the arrow keys, Home and End move between
 * the tabs and select them.
 */
const InvitationTabs = ({ value, onChange, idBase, panelId }: InvitationTabsProps) => {
  const tabRefs = useRef<Partial<Record<InvitationDirection, HTMLButtonElement | null>>>({});

  const select = (direction: InvitationDirection) => {
    onChange(direction);
    tabRefs.current[direction]?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const index = DIRECTIONS.indexOf(value);
    const last = DIRECTIONS.length - 1;
    let next: number | undefined;
    if (event.key === "ArrowRight") next = index === last ? 0 : index + 1;
    else if (event.key === "ArrowLeft") next = index === 0 ? last : index - 1;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = last;
    if (next === undefined) return;
    event.preventDefault();
    select(DIRECTIONS[next] as InvitationDirection);
  };

  return (
    <div className={styles.tabs} role="tablist" aria-label={uk.invitations.directionLabel}>
      {DIRECTIONS.map((direction) => {
        const selected = direction === value;
        return (
          <button
            key={direction}
            ref={(element) => {
              tabRefs.current[direction] = element;
            }}
            className={styles.tab}
            type="button"
            role="tab"
            id={tabIds(idBase, direction)}
            aria-selected={selected}
            aria-controls={panelId}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(direction)}
            onKeyDown={handleKeyDown}
          >
            {labels[direction]}
          </button>
        );
      })}
    </div>
  );
};

export default InvitationTabs;
