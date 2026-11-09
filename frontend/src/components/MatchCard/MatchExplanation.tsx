import type { MatchItem, MatchMaxPoints, RankInfluence } from "../../api/types";
import { formatPoints } from "../../i18n/format";
import { uk } from "../../i18n/uk";
import { POINT_CRITERIA } from "./criteria";
import styles from "./MatchExplanation.module.css";

const text = uk.feed.card;

/** Symbols for the influence of a criterion; the wording next to them carries the meaning. */
const INFLUENCE_SYMBOL: Readonly<Record<RankInfluence, string>> = {
  raises: "▲",
  neutral: "●",
  lowers: "▼",
};

interface InfluenceProps {
  value: RankInfluence;
}

const Influence = ({ value }: InfluenceProps) => (
  <span className={styles.influence}>
    <span aria-hidden="true">{INFLUENCE_SYMBOL[value]}</span> {text.influence[value]}
  </span>
);

interface MatchExplanationProps {
  match: Pick<MatchItem, "breakdown" | "rank_source" | "rank_influence">;
  /** Highest points of each criterion, as sent by the API with the feed. */
  maxPoints: MatchMaxPoints;
}

/**
 * Explains the position of a candidate: points of each baseline criterion, the functional
 * criterion as a level only, the baseline total, which strategy ordered the feed and, for a
 * learned ranking, whether each criterion raised or lowered the position. Every value is
 * written out as text; the bars are decoration.
 */
const MatchExplanation = ({ match, maxPoints }: MatchExplanationProps) => {
  const { breakdown, rank_source: source, rank_influence: influence } = match;
  const learned = source === "learned";

  return (
    // A disclosure, not a labelled section: a region landmark would be repeated in every card.
    // It is closed by default so that a feed of ten candidates stays easy to scan.
    <details className={styles.explanation}>
      <summary className={styles.summary}>
        <h4 className={styles.heading}>{text.explanationHeading}</h4>
        <span className={styles.hint}>{text.explanationHint}</span>
      </summary>
      <p className={styles.source}>
        <span className={`${styles.badge} ${learned ? styles.badgeLearned : ""}`}>
          {text.rankSource[source]}
        </span>
      </p>
      {learned && <p className={styles.note}>{text.learnedNote}</p>}
      <dl className={styles.criteria}>
        {POINT_CRITERIA.map((criterion) => {
          const max = maxPoints[criterion];
          const points = breakdown[criterion];
          const share = Math.min(100, Math.max(0, (points / max) * 100));
          return (
            <div key={criterion} className={styles.row}>
              <dt>{text.criteria[criterion]}</dt>
              <dd>
                <span>{text.points(formatPoints(points), max)}</span>
                <span className={styles.track} aria-hidden="true">
                  <span className={styles.fill} style={{ width: `${share}%` }} />
                </span>
                {learned && influence && <Influence value={influence[criterion]} />}
              </dd>
            </div>
          );
        })}
        <div className={styles.row}>
          <dt>{text.criteria.functional}</dt>
          <dd>
            <span>{text.functionalLevel[breakdown.functional]}</span>
            <span className={styles.note}>{text.functionalNote}</span>
            {/* "Medium" is also what a pair without comparable data gets, so say so */}
            {breakdown.functional === "medium" && (
              <span className={styles.note}>{text.functionalMediumHint}</span>
            )}
            {learned && influence && <Influence value={influence.functional} />}
          </dd>
        </div>
      </dl>
      <p className={styles.total}>{text.total(formatPoints(breakdown.total))}</p>
      <p className={styles.note}>{text.totalNote}</p>
    </details>
  );
};

export default MatchExplanation;
