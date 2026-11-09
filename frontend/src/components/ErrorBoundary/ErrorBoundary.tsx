import { Component, useEffect, useRef, type ReactNode } from "react";
import { uk } from "../../i18n/uk";

interface ErrorBoundaryProps {
  children: ReactNode;
  /**
   * Use at the root, outside the page layout: the fallback then brings its own `main`
   * landmark because the layout that normally provides it may be the thing that failed.
   */
  standalone?: boolean;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

interface FallbackProps {
  standalone: boolean;
  onRetry: () => void;
}

/**
 * The fallback is a new screen for assistive technology: it sets the document title and
 * moves focus to its heading, so a keyboard or screen reader user lands on the message.
 */
const Fallback = ({ standalone, onRetry }: FallbackProps) => {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    document.title = `${uk.errors.title}${uk.app.titleSeparator}${uk.app.name}`;
    headingRef.current?.focus();
  }, []);

  const content = (
    <>
      <h1 ref={headingRef} tabIndex={-1}>
        {uk.errors.title}
      </h1>
      <p>{uk.errors.description}</p>
      <p>
        <button className="button" type="button" onClick={onRetry}>
          {uk.errors.retry}
        </button>{" "}
        {/* A plain link on purpose: it reloads the app, which also works when the router failed */}
        <a href="/">{uk.errors.home}</a>
      </p>
    </>
  );

  return standalone ? <main>{content}</main> : <div>{content}</div>;
};

/**
 * Catches render errors of the tree below it and shows a recoverable fallback.
 *
 * The error message is deliberately not shown: it can contain user data. The boundary
 * adds no logging of its own; React still reports caught errors to the console.
 */
class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidUpdate(_props: ErrorBoundaryProps, previous: ErrorBoundaryState) {
    // The retry button unmounts itself, so focus would fall back to the body. If the page
    // renders again, move focus to its heading; if it fails again, the new fallback does it.
    if (previous.hasError && !this.state.hasError) {
      const heading = document.querySelector<HTMLElement>("main h1, h1");
      heading?.setAttribute("tabindex", "-1");
      heading?.focus();
    }
  }

  private handleRetry = () => {
    this.setState({ hasError: false });
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return <Fallback standalone={this.props.standalone ?? false} onRetry={this.handleRetry} />;
  }
}

export default ErrorBoundary;
