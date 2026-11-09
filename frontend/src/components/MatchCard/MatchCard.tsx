import { useId } from "react";
import type { MatchItem, MatchMaxPoints } from "../../api/types";
import { uk } from "../../i18n/uk";
import InviteAction from "../InviteAction/InviteAction";
import PartnerFacts from "../PartnerFacts/PartnerFacts";
import MatchExplanation from "./MatchExplanation";
import styles from "./MatchCard.module.css";

interface MatchCardProps {
  match: MatchItem;
  /** Highest points of each criterion, from the feed response. */
  maxPoints: MatchMaxPoints;
  version: string;
  invited: boolean;
  onInvited: (profileId: string) => void;
}

const text = uk.feed.card;

/**
 * One candidate of the feed: public fields, the distance band, the explanation of the
 * position and the invitation button. Only fields of the public API model are used.
 */
const MatchCard = ({ match, maxPoints, version, invited, onInvited }: MatchCardProps) => {
  const headingId = useId();
  // The band comes from the API as a fixed set of values; an unknown one is shown as sent
  const band = text.distanceBand[match.distance_band] ?? match.distance_band;

  return (
    <li>
      <article className={styles.card} aria-labelledby={headingId}>
        <h3 className={styles.name} id={headingId}>
          {match.display_name}
        </h3>
        <PartnerFacts partner={match} version={version}>
          <div>
            <dt>{text.distance}</dt>
            <dd>{band}</dd>
          </div>
        </PartnerFacts>
        <MatchExplanation match={match} maxPoints={maxPoints} />
        <InviteAction
          profileId={match.id}
          name={match.display_name}
          sent={invited}
          onSent={onInvited}
        />
      </article>
    </li>
  );
};

export default MatchCard;
