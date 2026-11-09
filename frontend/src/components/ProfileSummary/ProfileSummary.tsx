import { Link } from "react-router";
import { taxonomyLabel } from "../../i18n/taxonomy";
import { uk } from "../../i18n/uk";
import { isNoProfile, useGetMyProfileQuery, useGetTaxonomyQuery } from "../../redux/api/profileApi";
import Loader from "../Loader/Loader";
import styles from "./ProfileSummary.module.css";

const text = uk.pages.home;
const summary = uk.profile.summary;

/**
 * Short view of the caller's own profile for the home page, with a link to edit it.
 * Contact and functional answers are deliberately left out: the page can be seen over
 * the shoulder, and the profile page is the place for them.
 */
const ProfileSummary = () => {
  const profile = useGetMyProfileQuery();
  const taxonomy = useGetTaxonomyQuery();

  if (profile.isLoading || taxonomy.isLoading) return <Loader label={uk.profile.loading} />;

  if (isNoProfile(profile.error)) {
    return (
      <section>
        <p>{text.noProfile}</p>
        <Link className="button" to="/profile">
          {text.createProfile}
        </Link>
      </section>
    );
  }

  if (profile.isError || !profile.data) {
    return (
      <section>
        <p className={styles.error} role="alert">
          <strong>{uk.form.errorPrefix}</strong> {text.summaryFailed}
        </p>
        <button className="button button-secondary" type="button" onClick={() => void profile.refetch()}>
          {uk.profile.retry}
        </button>
      </section>
    );
  }

  const { data } = profile;
  // The labels need the taxonomy version; until it arrives the codes themselves are shown
  const version = taxonomy.data?.version ?? "";
  const district = data.district_code
    ? taxonomyLabel(version, "districts", data.district_code)
    : summary.districtNone;

  return (
    <section aria-labelledby="home-profile-heading">
      <h2 id="home-profile-heading">{text.summaryHeading}</h2>
      <p className={styles.name}>{data.display_name}</p>
      <dl className={styles.facts}>
        <div>
          <dt>{summary.district}</dt>
          <dd>{district}</dd>
        </div>
        <div>
          <dt>{summary.intensity}</dt>
          <dd>{`${data.intensity}: ${taxonomyLabel(version, "intensities", String(data.intensity))}`}</dd>
        </div>
        <div>
          <dt>{summary.sports}</dt>
          <dd>
            <ul className={styles.sports}>
              {data.sports.map(({ sport, skill }) => (
                <li key={sport}>
                  {taxonomyLabel(version, "sports", sport)} ({taxonomyLabel(version, "skills", skill).toLowerCase()})
                </li>
              ))}
            </ul>
          </dd>
        </div>
      </dl>
      <ul className={styles.flags}>
        <li>{data.is_visible ? summary.visible : summary.hidden}</li>
        <li>{data.functional_data_consent ? summary.consentGiven : summary.consentNotGiven}</li>
      </ul>
      <Link className="button" to="/profile">
        {text.editProfile}
      </Link>
    </section>
  );
};

export default ProfileSummary;
