import { useId, useState, type ReactNode } from "react";
import Icon from "../Icon/Icon";
import styles from "./Accordion.module.css";

export interface AccordionItem {
  /** Visible question or title; it is the text of the button. */
  heading: string;
  content: ReactNode;
}

interface AccordionProps {
  items: readonly AccordionItem[];
  /** Level of the headings that wrap the buttons; choose the one that fits the page outline. */
  headingLevel?: 3 | 4;
}

/**
 * Group of disclosure widgets. Each heading contains one button with aria-expanded and
 * aria-controls; the panel is removed from the accessibility tree and the tab order while
 * collapsed (the hidden attribute). Several panels may be open at once, and the buttons are
 * ordinary tab stops, so no arrow-key handling is needed.
 */
const Accordion = ({ items, headingLevel = 3 }: AccordionProps) => {
  const baseId = useId();
  const [open, setOpen] = useState<ReadonlySet<number>>(new Set());
  const Heading = `h${headingLevel}` as const;

  const toggle = (index: number) => {
    setOpen((previous) => {
      const next = new Set(previous);
      if (!next.delete(index)) next.add(index);
      return next;
    });
  };

  return (
    <div className={styles.accordion}>
      {items.map((item, index) => {
        const isOpen = open.has(index);
        const buttonId = `${baseId}-button-${index}`;
        const panelId = `${baseId}-panel-${index}`;
        return (
          <div className={styles.item} key={item.heading}>
            <Heading className={styles.heading}>
              <button
                type="button"
                className={styles.button}
                id={buttonId}
                aria-expanded={isOpen}
                aria-controls={panelId}
                onClick={() => toggle(index)}
              >
                <span>{item.heading}</span>
                <span className={isOpen ? styles.chevronOpen : styles.chevron}>
                  <Icon name="chevron" />
                </span>
              </button>
            </Heading>
            <div className={styles.panel} id={panelId} hidden={!isOpen}>
              {item.content}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default Accordion;
