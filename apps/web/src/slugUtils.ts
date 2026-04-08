/** Internal URL-safe slug for DB uniqueness; never shown to users. */

export function slugFromDisplayName(name: string): string {
  const base = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return (base || "workspace").slice(0, 40);
}

export function randomSlugSuffix(): string {
  return crypto.randomUUID().replace(/-/g, "").slice(0, 10);
}

/** Base slug plus random suffix — avoids global / per-org collisions without user input. */
export function generatedSlugFromName(name: string): string {
  return `${slugFromDisplayName(name)}-${randomSlugSuffix()}`;
}

export function isUniqueViolation(err: { code?: string; message?: string } | null | undefined): boolean {
  if (!err) return false;
  if (err.code === "23505") return true;
  const m = (err.message ?? "").toLowerCase();
  return m.includes("unique") || m.includes("duplicate");
}
