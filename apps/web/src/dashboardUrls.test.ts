import { describe, expect, it } from "vitest";
import { parseDashboardPath, resolveOrgRef, resolveProjectRef } from "./dashboardUrls";

describe("parseDashboardPath", () => {
  it("parses org list", () => {
    expect(parseDashboardPath("/orgs")).toEqual({ kind: "orgs" });
    expect(parseDashboardPath("/orgs/")).toEqual({ kind: "orgs" });
  });

  it("parses project list", () => {
    expect(parseDashboardPath("/org/acme/projects")).toEqual({
      kind: "orgProjects",
      orgRef: "acme",
    });
  });

  it("parses overview and pipeline", () => {
    expect(parseDashboardPath("/org/acme/project/p1/overview")).toEqual({
      kind: "projectOverview",
      orgRef: "acme",
      projectRef: "p1",
    });
    expect(parseDashboardPath("/org/acme/project/p1/pipeline")).toEqual({
      kind: "projectPipeline",
      orgRef: "acme",
      projectRef: "p1",
    });
  });

  it("returns unknown for legacy paths", () => {
    expect(parseDashboardPath("/old")).toEqual({ kind: "unknown" });
  });
});

describe("resolveOrgRef", () => {
  const orgs = [
    { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", slug: "acme", name: "Acme" },
  ];

  it("resolves by id or slug", () => {
    expect(resolveOrgRef(orgs, "acme")?.id).toBe(orgs[0]!.id);
    expect(resolveOrgRef(orgs, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")?.slug).toBe("acme");
  });
});

describe("resolveProjectRef", () => {
  const projects = [
    { id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", slug: "app", name: "App" },
  ];

  it("resolves by id or slug", () => {
    expect(resolveProjectRef(projects, "app")?.id).toBe(projects[0]!.id);
    expect(resolveProjectRef(projects, "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")?.slug).toBe("app");
  });
});
