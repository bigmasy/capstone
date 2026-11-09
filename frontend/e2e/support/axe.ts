import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo } from "@playwright/test";
import { appendFileSync } from "node:fs";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const ALL_TAGS = [...WCAG_TAGS, "best-practice"];

export interface Finding {
  id: string;
  impact: string | null | undefined;
  tags: string[];
  help: string;
  nodes: string[];
}

export interface ScanResult {
  /** Violations of a WCAG 2.0/2.1 A or AA rule: these fail the test. */
  wcag: Finding[];
  /** Violations of best-practice rules only: reported, not failing. */
  bestPractice: Finding[];
  /** Checks axe could not decide (needs review by a person); never failing, listed for the manual checklist. */
  incomplete: Finding[];
}

function toFinding(violation: {
  id: string;
  impact?: string | null;
  tags: string[];
  help: string;
  nodes: { target: unknown }[];
}): Finding {
  return {
    id: violation.id,
    impact: violation.impact,
    tags: violation.tags,
    help: violation.help,
    nodes: violation.nodes.map((node) => JSON.stringify(node.target)).slice(0, 8),
  };
}

/** Runs axe with the WCAG A/AA tags and the best-practice tag, and splits the violations. */
export async function scan(page: Page): Promise<ScanResult> {
  const results = await new AxeBuilder({ page }).withTags(ALL_TAGS).analyze();
  const wcag: Finding[] = [];
  const bestPractice: Finding[] = [];
  for (const violation of results.violations) {
    const finding = toFinding(violation);
    (violation.tags.some((tag) => WCAG_TAGS.includes(tag)) ? wcag : bestPractice).push(finding);
  }
  return { wcag, bestPractice, incomplete: results.incomplete.map(toFinding) };
}

/**
 * Scans the page, writes every finding to the file named by E2E_AXE_LOG (one JSON line per
 * scan, outside the repository) and fails on WCAG violations. Best-practice findings are
 * attached to the test as an annotation.
 */
export async function expectNoViolations(page: Page, testInfo: TestInfo, label: string): Promise<void> {
  const { wcag, bestPractice, incomplete } = await scan(page);
  const log = process.env.E2E_AXE_LOG;
  if (log) {
    appendFileSync(log, `${JSON.stringify({ label, wcag, bestPractice, incomplete })}\n`);
  }
  if (bestPractice.length > 0) {
    testInfo.annotations.push({
      type: "best-practice",
      description: bestPractice.map((finding) => `${finding.id}: ${finding.nodes.join(", ")}`).join(" | "),
    });
  }
  expect(
    wcag.map((finding) => `${finding.id} (${finding.impact}): ${finding.nodes.join(", ")}`),
    `axe WCAG violations on ${label}`,
  ).toEqual([]);
}
