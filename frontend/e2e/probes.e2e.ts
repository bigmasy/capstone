import { expect, test } from "@playwright/test";
import { scan } from "./support/axe";
import { headingProblems, landmarkProblems, measureFocusIndicator, smallTargets } from "./support/probes";

/**
 * Negative controls: the probes behind the other tests must notice a defect when there is one,
 * otherwise a green run would prove nothing.
 */
test.describe("probes find real defects", () => {
  test("headings: a second h1 and a skipped level", async ({ page }) => {
    await page.setContent("<main><h1>One</h1><h1>Two</h1><h3>Skipped</h3></main>");
    const problems = await headingProblems(page);
    expect(problems.join("|")).toContain("exactly one h1");
    expect(problems.join("|")).toContain("h3");
  });

  test("landmarks: two navigations without names", async ({ page }) => {
    await page.setContent("<header></header><nav></nav><nav></nav><main></main><footer></footer>");
    expect((await landmarkProblems(page)).join("|")).toContain("no name");
  });

  test("focus: a removed outline is reported, a real one is measured", async ({ page }) => {
    await page.setContent(
      `<style>button{outline:none}.ok{outline:3px solid #000;outline-offset:2px}</style>
       <div style="background:#fff"><button id="bad">x</button><button id="ok" class="ok">y</button></div>`,
    );
    await page.locator("#bad").focus();
    expect((await measureFocusIndicator(page))?.outlineStyle).toBe("none");
    await page.locator("#ok").focus();
    const measured = await measureFocusIndicator(page);
    expect(measured?.outlineWidthPx).toBe(3);
    expect(measured?.contrast).toBeGreaterThan(10);
  });

  test("target size: a 10 px button is reported", async ({ page }) => {
    await page.setContent('<button style="width:10px;height:10px;padding:0">x</button>');
    expect(await smallTargets(page)).toHaveLength(1);
  });

  test("axe: real contrast failures are reported as WCAG, a best-practice rule separately", async ({ page }) => {
    await page.setContent(
      `<!doctype html><html lang="en"><head><title>t</title></head><body><main>
         <h1>Heading</h1>
         <p style="color:#999;background:#fff">Pale text on white</p>
         <img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">
         <h4>Skipped level</h4>
       </main></body></html>`,
    );
    const { wcag, bestPractice } = await scan(page);
    expect(wcag.map((finding) => finding.id)).toEqual(expect.arrayContaining(["color-contrast", "image-alt"]));
    expect(bestPractice.map((finding) => finding.id)).toContain("heading-order");
  });
});
