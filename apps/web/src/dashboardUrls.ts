/** Browser path helpers and parsing for org / project navigation. */

export type OrgRef = { id: string; slug: string };
export type ProjectRef = { id: string; slug: string };

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function resolveOrgRef<T extends OrgRef>(orgs: T[], ref: string): T | null {
  const decoded = safeDecode(ref);
  if (UUID_RE.test(decoded)) return orgs.find((o) => o.id === decoded) ?? null;
  return orgs.find((o) => o.slug === decoded) ?? null;
}

export function resolveProjectRef<T extends ProjectRef>(projects: T[], ref: string): T | null {
  const decoded = safeDecode(ref);
  if (UUID_RE.test(decoded)) return projects.find((p) => p.id === decoded) ?? null;
  return projects.find((p) => p.slug === decoded) ?? null;
}

function safeDecode(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

function enc(segment: string): string {
  return encodeURIComponent(segment);
}

export function pathOrganizations(): string {
  return "/orgs";
}

export function pathOrgProjects(org: OrgRef): string {
  return `/org/${enc(org.slug)}/projects`;
}

export function pathProjectOverview(org: OrgRef, project: ProjectRef): string {
  return `/org/${enc(org.slug)}/project/${enc(project.slug)}/overview`;
}

export function pathProjectPipeline(org: OrgRef, project: ProjectRef): string {
  return `/org/${enc(org.slug)}/project/${enc(project.slug)}/pipeline`;
}

export type ParsedDashboardPath =
  | { kind: "orgs" }
  | { kind: "orgProjects"; orgRef: string }
  | { kind: "projectOverview"; orgRef: string; projectRef: string }
  | { kind: "projectPipeline"; orgRef: string; projectRef: string }
  | { kind: "unknown" };

export function parseDashboardPath(pathname: string): ParsedDashboardPath {
  const p = pathname.replace(/\/+$/, "") || "/";
  if (p === "/orgs") return { kind: "orgs" };

  const mp = /^\/org\/([^/]+)\/projects$/.exec(p);
  if (mp) return { kind: "orgProjects", orgRef: mp[1]! };

  const mo = /^\/org\/([^/]+)\/project\/([^/]+)\/overview$/.exec(p);
  if (mo) return { kind: "projectOverview", orgRef: mo[1]!, projectRef: mo[2]! };

  const mw = /^\/org\/([^/]+)\/project\/([^/]+)\/pipeline$/.exec(p);
  if (mw) return { kind: "projectPipeline", orgRef: mw[1]!, projectRef: mw[2]! };

  return { kind: "unknown" };
}
