import type { SearchRadius, SportCode, Taxonomy } from "../../api/types";
import { taxonomyLabel } from "../../i18n/taxonomy";
import { uk } from "../../i18n/uk";
import SelectField from "../SelectField/SelectField";
import styles from "./MatchFilters.module.css";

/** Radii the API accepts, in kilometres. */
export const RADII: readonly SearchRadius[] = [5, 10, 25];

const text = uk.feed.filters;

interface MatchFiltersProps {
  radius: SearchRadius | undefined;
  sport: SportCode | undefined;
  /** Without the taxonomy there are no sports to choose from, so only the radius is offered. */
  taxonomy: Taxonomy | undefined;
  onRadiusChange: (radius: SearchRadius | undefined) => void;
  onSportChange: (sport: SportCode | undefined) => void;
}

/** The radius and sport filters of the feed; the choice is applied as soon as it is made. */
const MatchFilters = ({
  radius,
  sport,
  taxonomy,
  onRadiusChange,
  onSportChange,
}: MatchFiltersProps) => (
  <fieldset className={styles.filters}>
    <legend>{text.legend}</legend>
    <SelectField
      label={text.radius}
      name="radius"
      placeholder={text.radiusAll}
      options={RADII.map((km) => ({ value: String(km), label: text.radiusOption(km) }))}
      value={radius === undefined ? "" : String(radius)}
      onChange={(event) => {
        const chosen = RADII.find((km) => String(km) === event.target.value);
        onRadiusChange(chosen);
      }}
    />
    {taxonomy && (
      <SelectField
        label={text.sport}
        name="sport"
        placeholder={text.sportAll}
        options={taxonomy.sports.map((code) => ({
          value: code,
          label: taxonomyLabel(taxonomy.version, "sports", code),
        }))}
        value={sport ?? ""}
        onChange={(event) => {
          onSportChange(taxonomy.sports.find((code) => code === event.target.value));
        }}
      />
    )}
  </fieldset>
);

export default MatchFilters;
