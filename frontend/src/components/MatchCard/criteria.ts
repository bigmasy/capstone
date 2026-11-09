import type { MatchBreakdown } from "../../api/types";

/** The criteria whose baseline contribution is returned in points. */
export type PointCriterion = Exclude<keyof MatchBreakdown, "functional" | "total">;

/** Order in which the criteria are listed. The maxima of their points come from the API. */
export const POINT_CRITERIA: readonly PointCriterion[] = ["sport", "distance", "intensity"];
