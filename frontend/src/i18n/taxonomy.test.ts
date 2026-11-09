import { describe, expect, it } from "vitest";
import { taxonomyLabel } from "./taxonomy";

describe("taxonomyLabel", () => {
  it("returns the Ukrainian label for a known code and version", () => {
    expect(taxonomyLabel("1.0.0", "sports", "swimming")).toBe("Плавання");
    expect(taxonomyLabel("1.0.0", "districts", "kyiv_podilskyi")).toBe("Київ, Подільський");
  });

  it("falls back to the code for an unknown code", () => {
    expect(taxonomyLabel("1.0.0", "sports", "curling")).toBe("curling");
  });

  it("falls back to the code for an unknown taxonomy version", () => {
    expect(taxonomyLabel("9.9.9", "sports", "swimming")).toBe("swimming");
  });

  it("labels skills, capability levels, intensities and category hints", () => {
    expect(taxonomyLabel("1.0.0", "skills", "advanced")).toBe("Просунутий");
    expect(taxonomyLabel("1.0.0", "capabilityLevels", "0")).toBe("неможливо");
    expect(taxonomyLabel("1.0.0", "intensities", "3")).toBe("помірна");
    expect(taxonomyLabel("1.0.0", "categoryHints", "vision")).toContain("орієнтація");
  });
});
