import type { ReactNode } from "react";
import type { MatchItem } from "../../api/types";
import { taxonomyLabel } from "../../i18n/taxonomy";
import { uk } from "../../i18n/uk";
import styles from "./PartnerFacts.module.css";

interface PartnerFactsProps {
  /** Public fields of another user; a feed candidate and an invitation partner both fit. */
  partner: Pick<MatchItem, "district_code" | "intensity" | "sports">;
  /** Taxonomy version that selects the label tables. */
  version: string;
  /** Extra rows shown after the common ones, such as the distance band. */
  children?: ReactNode;
}

const text = uk.feed.card;

/** Description list with the public profile fields of another user. */
const PartnerFacts = ({ partner, version, children }: PartnerFactsProps) => (
  <dl className={styles.facts}>
    <div>
      <dt>{text.district}</dt>
      <dd>
        {partner.district_code
          ? taxonomyLabel(version, "districts", partner.district_code)
          : text.districtNone}
      </dd>
    </div>
    {children}
    <div>
      <dt>{text.intensity}</dt>
      <dd>{`${partner.intensity}: ${taxonomyLabel(version, "intensities", String(partner.intensity))}`}</dd>
    </div>
    <div>
      <dt>{text.sports}</dt>
      <dd>
        <ul className={styles.sports}>
          {partner.sports.map(({ sport, skill }) => (
            <li key={sport}>
              {text.sport(
                taxonomyLabel(version, "sports", sport),
                taxonomyLabel(version, "skills", skill).toLowerCase(),
              )}
            </li>
          ))}
        </ul>
      </dd>
    </div>
  </dl>
);

export default PartnerFacts;
