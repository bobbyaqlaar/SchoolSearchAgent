import { describe, expect, it } from "vitest";
import {
  buildCompareHref,
  parseCompareIds,
  resolveSchoolId,
  slugify,
} from "@/lib/util";

describe("slugify", () => {
  it("lowercases and hyphenates", () => {
    expect(slugify("GEMS Modern Academy")).toBe("gems-modern-academy");
  });

  it("strips punctuation", () => {
    expect(slugify("Horizons English School L.L.C")).toBe(
      "horizons-english-school-llc",
    );
  });
});

describe("resolveSchoolId", () => {
  it("prefers school_id when present", () => {
    expect(resolveSchoolId("gems-modern", "GEMS Modern Academy")).toBe(
      "gems-modern",
    );
  });

  it("falls back to slugified name", () => {
    expect(resolveSchoolId(undefined, "GEMS Modern Academy")).toBe(
      "gems-modern-academy",
    );
  });
});

describe("compare url helpers", () => {
  it("builds compare href with repeated ids param", () => {
    expect(buildCompareHref(["a", "b"])).toBe("/compare?ids=a&ids=b");
  });

  it("parses ids from search string", () => {
    expect(parseCompareIds("?ids=a&ids=b")).toEqual(["a", "b"]);
  });
});
