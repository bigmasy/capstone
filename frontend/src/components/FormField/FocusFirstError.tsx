import { useFormikContext } from "formik";
import { useEffect, useRef, type RefObject } from "react";

interface FocusFirstErrorProps {
  /** The form element that holds the fields; the search never leaves it. */
  formRef: RefObject<HTMLFormElement | null>;
}

/**
 * Moves focus to the first invalid field of its form after a failed submit (WCAG 3.3.1, 3.3.3).
 * Must be rendered inside a Formik form; renders nothing.
 */
const FocusFirstError = ({ formRef }: FocusFirstErrorProps) => {
  const { submitCount, isSubmitting, isValidating, isValid } = useFormikContext();
  const handledSubmit = useRef(0);

  useEffect(() => {
    if (isSubmitting || isValidating || submitCount === handledSubmit.current) return;
    handledSubmit.current = submitCount;
    if (!isValid) {
      formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
    }
  }, [submitCount, isSubmitting, isValidating, isValid, formRef]);

  return null;
};

export default FocusFirstError;
