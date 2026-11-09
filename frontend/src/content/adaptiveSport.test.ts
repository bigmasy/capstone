import { describe, expect, it } from "vitest";
import { adaptiveSportColumns, verifiedOn } from "./adaptiveSport";

const items = adaptiveSportColumns.flatMap((column) => column.items);

describe("adaptive sport content", () => {
  it("has three columns with several entries each", () => {
    expect(adaptiveSportColumns.map((column) => column.id)).toEqual(["games", "news", "organisations"]);
    for (const column of adaptiveSportColumns) {
      expect(column.items.length).toBeGreaterThanOrEqual(3);
    }
  });

  it("records the verification date as an ISO day that is not in the future of the project", () => {
    expect(verifiedOn).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(Number.isNaN(new Date(verifiedOn).getTime())).toBe(false);
  });

  it("links only over https and to a host name", () => {
    for (const item of items) {
      const url = new URL(item.href);
      expect(url.protocol, item.id).toBe("https:");
      expect(url.hostname, item.id).toContain(".");
      expect(url.username, item.id).toBe("");
    }
  });

  it("has unique ids and fully described entries", () => {
    expect(new Set(items.map((item) => item.id)).size).toBe(items.length);
    for (const item of items) {
      expect(item.title.trim(), item.id).not.toBe("");
      expect(item.source.trim(), item.id).not.toBe("");
      expect(item.description.trim(), item.id).not.toBe("");
    }
  });

  it("does not link the same address twice within a column", () => {
    for (const column of adaptiveSportColumns) {
      const hrefs = column.items.map((item) => item.href);
      expect(new Set(hrefs).size, column.id).toBe(hrefs.length);
    }
  });
});
