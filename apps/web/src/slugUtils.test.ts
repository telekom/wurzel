import { describe, expect, it } from "vitest";
import { generatedSlugFromName, isUniqueViolation, slugFromDisplayName } from "./slugUtils";

describe("slugUtils", () => {
  it("slugFromDisplayName normalizes text", () => {
    expect(slugFromDisplayName("  My Org Name!  ")).toBe("my-org-name");
  });

  it("generatedSlugFromName appends suffix", () => {
    const a = generatedSlugFromName("Acme");
    const b = generatedSlugFromName("Acme");
    expect(a.startsWith("acme-")).toBe(true);
    expect(b.startsWith("acme-")).toBe(true);
    expect(a).not.toBe(b);
  });

  it("isUniqueViolation detects postgres code", () => {
    expect(isUniqueViolation({ code: "23505", message: "" })).toBe(true);
    expect(isUniqueViolation({ message: "duplicate key value violates unique constraint" })).toBe(true);
    expect(isUniqueViolation({ message: "other" })).toBe(false);
  });
});
