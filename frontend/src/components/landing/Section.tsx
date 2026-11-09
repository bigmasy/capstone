import { useId, type ReactNode } from "react";
import styles from "./Section.module.css";

interface SectionProps {
  heading: string;
  /** Short introduction under the heading. */
  lead?: string;
  /** Background band; alternating bands separate the sections without borders. */
  tone?: "plain" | "tint";
  children: ReactNode;
}

/** A landing page band: a labelled region with a centred container and a level 2 heading. */
const Section = ({ heading, lead, tone = "plain", children }: SectionProps) => {
  const headingId = useId();

  return (
    <section
      className={tone === "tint" ? `${styles.section} ${styles.tint}` : styles.section}
      aria-labelledby={headingId}
    >
      <div className="container">
        <header className={styles.header}>
          <h2 id={headingId} className={styles.heading}>
            {heading}
          </h2>
          {lead && <p className={styles.lead}>{lead}</p>}
        </header>
        {children}
      </div>
    </section>
  );
};

export default Section;
