import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import toast from "react-hot-toast";
import { afterEach, expect, vi } from "vitest";
import * as axeMatchers from "vitest-axe/matchers";

expect.extend(axeMatchers);

// jsdom has no canvas; axe probes it and jsdom would log "not implemented" for each probe.
// Colour contrast cannot be computed in jsdom, so it is covered by src/styles/tokens.test.ts.
vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);

// jsdom does not implement pseudo-element styles and logs for every axe probe; ignore the argument
const getComputedStyleOfElement = window.getComputedStyle.bind(window);
window.getComputedStyle = (element: Element) => getComputedStyleOfElement(element);

// jsdom has no matchMedia; libraries read prefers-reduced-motion and similar queries through it
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }),
});

afterEach(() => {
  cleanup();
  // Toasts live in a module-level store and would leak into the next test
  toast.remove();
  window.sessionStorage.clear();
  document.title = "";
});
