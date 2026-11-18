import { useId, useRef, useState, type ChangeEvent } from "react";
import { uk } from "../../i18n/uk";
import {
  PHOTO_ACCEPT,
  PHOTO_MAX_BYTES,
  photoRejection,
  useDeleteMyPhotoMutation,
  useUploadMyPhotoMutation,
} from "../../redux/api/photoApi";
import Avatar from "../Avatar/Avatar";
import styles from "./PhotoSection.module.css";
import { preparePhoto } from "./preparePhoto";

const text = uk.profile.photo;

interface PhotoSectionProps {
  profileId: string;
  name: string;
  hasPhoto: boolean;
}

type Outcome = { kind: "done" | "failed"; message: string } | null;

/**
 * The photograph of the caller's profile: the current picture or its placeholder, a button to
 * choose a file and a button to remove the photograph. It stands apart from the profile form
 * because a picture is saved the moment it is chosen, not with the rest of the fields.
 */
const PhotoSection = ({ profileId, name, hasPhoto }: PhotoSectionProps) => {
  const headingId = useId();
  const noteId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [upload, uploading] = useUploadMyPhotoMutation();
  const [remove, removing] = useDeleteMyPhotoMutation();
  const [outcome, setOutcome] = useState<Outcome>(null);
  const busy = uploading.isLoading || removing.isLoading;

  const onChoose = async (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0];
    // The same file can be chosen again after a failure
    event.target.value = "";
    if (!chosen || busy) return;
    setOutcome(null);
    const file = await preparePhoto(chosen);
    if (file.size > PHOTO_MAX_BYTES) {
      setOutcome({ kind: "failed", message: text.tooLarge });
      return;
    }
    const result = await upload({ profileId, file });
    if ("error" in result) {
      const reason = photoRejection(result.error);
      setOutcome({
        kind: "failed",
        message:
          reason === "photo_too_large"
            ? text.tooLarge
            : reason === "photo_invalid"
              ? text.invalid
              : text.failed,
      });
    } else {
      setOutcome({ kind: "done", message: text.saved });
    }
  };

  const onRemove = async () => {
    if (busy) return;
    setOutcome(null);
    const result = await remove({ profileId });
    setOutcome(
      "error" in result
        ? { kind: "failed", message: text.failed }
        : { kind: "done", message: text.removed },
    );
  };

  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <Avatar profileId={profileId} name={name} hasPhoto={hasPhoto} size="lg" />
      <div className={styles.body}>
        <h2 className={styles.heading} id={headingId}>
          {text.heading}
        </h2>
        <p className={styles.note} id={noteId}>
          {hasPhoto ? text.noteWithPhoto : text.noteWithoutPhoto} {text.rules}
        </p>
        <div className={styles.actions}>
          <input
            ref={inputRef}
            className="visually-hidden"
            type="file"
            accept={PHOTO_ACCEPT}
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => void onChoose(event)}
          />
          <button
            className="button button-secondary"
            type="button"
            aria-describedby={noteId}
            aria-disabled={busy ? true : undefined}
            onClick={() => {
              if (!busy) inputRef.current?.click();
            }}
          >
            {hasPhoto ? text.replace : text.choose}
          </button>
          {hasPhoto && (
            <button
              className="button button-secondary"
              type="button"
              aria-disabled={busy ? true : undefined}
              onClick={() => void onRemove()}
            >
              {text.remove}
            </button>
          )}
        </div>
        {/* Always in the DOM so that a result added later is announced */}
        <p
          className={outcome?.kind === "failed" ? styles.failed : styles.status}
          role={outcome?.kind === "failed" ? "alert" : "status"}
        >
          {busy ? text.working : outcome ? outcome.message : ""}
        </p>
      </div>
    </section>
  );
};

export default PhotoSection;
