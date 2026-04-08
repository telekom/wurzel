import {
  addEdge,
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Connection,
  type Edge,
  type FinalConnectionState,
  type Node,
  type NodeProps,
  useEdgesState,
  useNodesState,
  useStore,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import Form from "@rjsf/core";
import { customizeValidator } from "@rjsf/validator-ajv8";
import type { RJSFSchema } from "@rjsf/utils";
import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  parseDashboardPath,
  pathOrganizations,
  pathOrgProjects,
  pathProjectOverview,
  pathProjectPipeline,
  resolveOrgRef,
  resolveProjectRef,
} from "./dashboardUrls";
import { supabase } from "./supabaseClient";
import { generatedSlugFromName, isUniqueViolation } from "./slugUtils";
import { validatePipelineConnection } from "./stepChainUtils";
import {
  mergeStepCatalogWithDatabase,
  stepSummaryFull,
  stepSummaryShort,
  stepTechnicalLines,
  type StepCatalogRow,
} from "./stepCatalogUtils";

import type { Session } from "@supabase/supabase-js";

type DagNode = {
  id: string;
  step_key: string;
  settings?: Record<string, unknown>;
  /** Canvas layout; ignored by the Temporal runner. */
  position?: { x: number; y: number };
};
type DagEdge = { source: string; target: string };
type DagJson = { nodes: DagNode[]; edges: DagEdge[] };

type CatalogRow = StepCatalogRow;

type StepNodeData = {
  label: string;
  step_key: string;
  settings: Record<string, unknown>;
  settingsSchema: Record<string, unknown> | null;
  /** From catalog; drives handle availability and connection validation. */
  input_type_fqn: string | null;
  output_type_fqn: string | null;
};

/** Pydantic `Path` fields emit `format: "path"`; register it so AJV accepts filled values. */
const settingsFormValidator = customizeValidator({
  customFormats: {
    path: /^[\s\S]*$/,
  },
});

function resolveNodeSettingsSchema(
  n: Node<StepNodeData>,
  catalog: Map<string, CatalogRow>,
): Record<string, unknown> | null {
  const fromNode = n.data.settingsSchema;
  if (fromNode != null && typeof fromNode === "object") return fromNode;
  const fromCat = catalog.get(n.data.step_key)?.settings_json_schema;
  return fromCat != null && typeof fromCat === "object" ? fromCat : null;
}

/** Aggregate RJSF/AJV errors for every canvas node that has a settings schema (e.g. required fields). */
function validateAllPipelineStepSettings(nodes: Node<StepNodeData>[], catalog: Map<string, CatalogRow>): string | null {
  const parts: string[] = [];
  for (const n of nodes) {
    const schema = resolveNodeSettingsSchema(n, catalog);
    if (schema == null) continue;
    const formData = n.data.settings ?? {};
    const { errors } = settingsFormValidator.validateFormData(formData, schema as RJSFSchema);
    if (errors.length > 0) {
      const label = n.data.label || n.data.step_key;
      for (const err of errors) {
        parts.push(`${label}: ${err.stack ?? err.message ?? "Invalid setting"}`);
      }
    }
  }
  return parts.length > 0 ? parts.join(" ") : null;
}

function emptyDag(): DagJson {
  return { nodes: [], edges: [] };
}

/** Horizontal gap between grid columns; must exceed max node width to avoid overlap. */
const FLOW_GRID_COL_STEP = 320;
const FLOW_GRID_ROW_STEP = 180;

function flowGridPosition(index: number): { x: number; y: number } {
  const col = index % 4;
  const row = Math.floor(index / 4);
  return { x: 40 + col * FLOW_GRID_COL_STEP, y: 40 + row * FLOW_GRID_ROW_STEP };
}

function dagPositionFromJson(p: unknown): { x: number; y: number } | null {
  if (!p || typeof p !== "object") return null;
  const x = (p as { x?: unknown }).x;
  const y = (p as { y?: unknown }).y;
  if (typeof x !== "number" || typeof y !== "number") return null;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

function dagToFlow(dag: DagJson): { nodes: Node<StepNodeData>[]; edges: Edge[] } {
  const nodes: Node<StepNodeData>[] = dag.nodes.map((n, i) => ({
    id: n.id,
    type: "step",
    position: dagPositionFromJson(n.position) ?? flowGridPosition(i),
    data: {
      label: n.step_key.split(".").pop() ?? n.step_key,
      step_key: n.step_key,
      settings: (n.settings ?? {}) as Record<string, unknown>,
      settingsSchema: null,
      input_type_fqn: null,
      output_type_fqn: null,
    },
  }));
  const edges: Edge[] = dag.edges.map((e, i) => ({
    id: `e-${e.source}-${e.target}-${i}`,
    source: e.source,
    target: e.target,
  }));
  return { nodes, edges };
}

function flowToDag(nodes: Node<StepNodeData>[], edges: Edge[]): DagJson {
  return {
    nodes: nodes.map((n) => {
      const base: DagNode = {
        id: n.id,
        step_key: n.data.step_key,
        settings: n.data.settings,
      };
      const { x, y } = n.position;
      if (typeof x === "number" && typeof y === "number" && Number.isFinite(x) && Number.isFinite(y)) {
        base.position = { x, y };
      }
      return base;
    }),
    edges: edges.map((e) => ({ source: e.source, target: e.target })),
  };
}

function StepNode(props: NodeProps<Node<StepNodeData>>) {
  const id = props.id;
  const data = props.data;
  const incomingCount = useStore((s) => s.edges.filter((e) => e.target === id).length);
  const needsUpstream = Boolean((data.input_type_fqn ?? "").trim());
  const targetConnectable = needsUpstream && incomingCount === 0;
  return (
    <div className="flow-step-node">
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={targetConnectable}
        className={targetConnectable ? "flow-handle-target" : "flow-handle-target flow-handle--blocked"}
        aria-label={needsUpstream ? "Incoming data from upstream step" : "No upstream input (source step)"}
      />
      <strong>{data.label}</strong>
      <div className="flow-step-key">{data.step_key}</div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="flow-handle-source"
        aria-label="Outgoing data to downstream step"
      />
    </div>
  );
}

const nodeTypes = { step: StepNode };

const STORAGE_ORG = "wurzel.orgId";
const STORAGE_PROJECT = "wurzel.projectId";

type OrgRow = { id: string; name: string; slug: string };
type ProjectRow = { id: string; name: string; slug: string };
type AppScreen = "projectOverview" | "workspace" | "organization" | "project";

type OverviewPipelineRun = {
  id: string;
  status: string;
  created_at: string;
  updated_at: string | null;
  temporal_workflow_id: string | null;
};

const ACTIVE_PIPELINE_STATUSES = ["pending", "running"] as const;
const STOPPED_PIPELINE_STATUSES = ["succeeded", "failed", "cancelled"] as const;

const LAST_PATH_KEY = "wurzel.lastPath";

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);

  const [orgsLoading, setOrgsLoading] = useState(false);
  const [orgs, setOrgs] = useState<OrgRow[]>([]);
  const [orgId, setOrgId] = useState<string | null>(null);
  const [orgName, setOrgName] = useState("");
  const [newOrgName, setNewOrgName] = useState("");
  const [orgSearch, setOrgSearch] = useState("");
  const [projectSearch, setProjectSearch] = useState("");
  const [projectCountByOrgId, setProjectCountByOrgId] = useState<Record<string, number>>({});
  const [showNewOrgInline, setShowNewOrgInline] = useState(false);

  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");

  const [appScreen, setAppScreen] = useState<AppScreen>("project");
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewBranches, setOverviewBranches] = useState<number | null>(null);
  const [overviewRevisions, setOverviewRevisions] = useState<number | null>(null);
  const [overviewRuns, setOverviewRuns] = useState<number | null>(null);
  const [overviewActiveCount, setOverviewActiveCount] = useState<number | null>(null);
  const [overviewStoppedCount, setOverviewStoppedCount] = useState<number | null>(null);
  const [overviewActiveRuns, setOverviewActiveRuns] = useState<OverviewPipelineRun[]>([]);
  const [overviewStoppedRuns, setOverviewStoppedRuns] = useState<OverviewPipelineRun[]>([]);
  const [branches, setBranches] = useState<{ id: string; name: string }[]>([]);
  const [branchId, setBranchId] = useState<string | null>(null);
  const [revisionId, setRevisionId] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<CatalogRow[]>([]);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<StepNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  /** Filled after Run on Temporal: Temporal + DB status (gateway) or DB-only without gateway. */
  const [workflowRunStatus, setWorkflowRunStatus] = useState<string | null>(null);
  const [errMsg, setErrMsg] = useState<string | null>(null);
  /** Shown under the DAG when the user drops an invalid connection (e.g. type mismatch). */
  const [connectErrMsg, setConnectErrMsg] = useState<string | null>(null);
  const [selectedEdgeIds, setSelectedEdgeIds] = useState<string[]>([]);
  const lastPersistedDagJsonRef = useRef("");
  const revisionIdRef = useRef<string | null>(null);
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const branchIdRef = useRef(branchId);
  const [stepSelectorOpen, setStepSelectorOpen] = useState(false);
  const [stepSelectorSearch, setStepSelectorSearch] = useState("");
  const [selectedCatalogKey, setSelectedCatalogKey] = useState<string | null>(null);
  const [branchMenuOpen, setBranchMenuOpen] = useState(false);
  const [branchManageOpen, setBranchManageOpen] = useState(false);
  const branchMenuRef = useRef<HTMLDivElement>(null);
  const projectIdRef = useRef<string | null>(null);
  projectIdRef.current = projectId;

  const catalogByKey = useMemo(() => {
    const m = new Map<string, CatalogRow>();
    for (const r of catalog) m.set(r.step_key, r);
    return m;
  }, [catalog]);

  const catalogByKeyRef = useRef(catalogByKey);
  catalogByKeyRef.current = catalogByKey;

  const filteredCatalog = useMemo(() => {
    const q = stepSelectorSearch.trim().toLowerCase();
    if (!q) return catalog;
    return catalog.filter(
      (c) =>
        c.step_key.toLowerCase().includes(q) || (c.display_name ?? "").toLowerCase().includes(q),
    );
  }, [catalog, stepSelectorSearch]);

  useEffect(() => {
    if (!stepSelectorOpen) return;
    if (filteredCatalog.length === 0) {
      setSelectedCatalogKey(null);
      return;
    }
    setSelectedCatalogKey((prev) => {
      if (prev && filteredCatalog.some((c) => c.step_key === prev)) return prev;
      return filteredCatalog[0]!.step_key;
    });
  }, [stepSelectorOpen, filteredCatalog]);

  useEffect(() => {
    if (appScreen !== "workspace") {
      setBranchMenuOpen(false);
      setBranchManageOpen(false);
    }
  }, [appScreen]);

  useEffect(() => {
    if (!branchMenuOpen) return;
    function onDocMouseDown(e: MouseEvent) {
      const el = branchMenuRef.current;
      const t = e.target;
      if (el && t instanceof globalThis.Node && !el.contains(t)) setBranchMenuOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setBranchMenuOpen(false);
    }
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [branchMenuOpen]);

  useEffect(() => {
    if (!branchManageOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setBranchManageOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [branchManageOpen]);

  const selectedCatalogRow = useMemo(
    () => (selectedCatalogKey ? catalog.find((c) => c.step_key === selectedCatalogKey) ?? null : null),
    [catalog, selectedCatalogKey],
  );

  useEffect(() => {
    revisionIdRef.current = revisionId;
  }, [revisionId]);

  useEffect(() => {
    nodesRef.current = nodes;
    edgesRef.current = edges;
  }, [nodes, edges]);

  useEffect(() => {
    branchIdRef.current = branchId;
  }, [branchId]);

  const currentOrg = useMemo(() => orgs.find((o) => o.id === orgId) ?? null, [orgs, orgId]);
  const currentProject = useMemo(() => projects.find((p) => p.id === projectId) ?? null, [projects, projectId]);
  const projectDisplayName = currentProject?.name ?? projectName;
  const currentBranchName = useMemo(
    () => branches.find((b) => b.id === branchId)?.name ?? "",
    [branches, branchId],
  );

  const navigateTo = useCallback(
    (screen: AppScreen) => {
      const org = orgs.find((o) => o.id === orgId) ?? null;
      const proj = projects.find((p) => p.id === projectId) ?? null;
      let path: string;
      if (screen === "organization") {
        path = pathOrganizations();
      } else if (!org) {
        path = pathOrganizations();
      } else if (screen === "project") {
        path = pathOrgProjects(org);
      } else if (!proj) {
        path = pathOrgProjects(org);
      } else if (screen === "projectOverview") {
        path = pathProjectOverview(org, proj);
      } else {
        path = pathProjectPipeline(org, proj);
      }
      sessionStorage.setItem(LAST_PATH_KEY, path);
      navigate(path);
    },
    [navigate, orgs, projects, orgId, projectId],
  );

  const filteredOrgs = useMemo(() => {
    const q = orgSearch.trim().toLowerCase();
    if (!q) return orgs;
    return orgs.filter((o) => o.name.toLowerCase().includes(q));
  }, [orgs, orgSearch]);

  const filteredProjects = useMemo(() => {
    const q = projectSearch.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter((p) => p.name.toLowerCase().includes(q));
  }, [projects, projectSearch]);

  const loadOrgs = useCallback(
    async (preferredOrgId?: string | null): Promise<OrgRow[]> => {
      if (!session?.user) {
        setOrgs([]);
        setOrgId(null);
        setOrgsLoading(false);
        return [];
      }
      setOrgsLoading(true);
      const uid = session.user.id;
      const { data: mem, error: memErr } = await supabase.from("organization_members").select("organization_id").eq("user_id", uid);
      if (memErr) {
        setErrMsg(memErr.message);
        setOrgs([]);
        setOrgId(null);
        setOrgsLoading(false);
        return [];
      }
      const ids = (mem ?? []).map((m) => m.organization_id as string);
      if (!ids.length) {
        setOrgs([]);
        setOrgId(null);
        setOrgsLoading(false);
        return [];
      }
      const { data: orgRows, error: orgErr } = await supabase.from("organizations").select("id,name,slug").in("id", ids);
      if (orgErr) {
        setErrMsg(orgErr.message);
        setOrgs([]);
        setOrgId(null);
        setOrgsLoading(false);
        return [];
      }
      const rows = (orgRows ?? []) as OrgRow[];
      setOrgs(rows);
      if (preferredOrgId && rows.some((o) => o.id === preferredOrgId)) {
        setOrgId(preferredOrgId);
        sessionStorage.setItem(STORAGE_ORG, preferredOrgId);
      }
      setOrgsLoading(false);
      return rows;
    },
    [session],
  );

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session ?? null));
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session) return;
    void (async () => {
      let baseline: CatalogRow[] = [];
      try {
        const res = await fetch("/step_catalog.json");
        if (res.ok) baseline = (await res.json()) as CatalogRow[];
      } catch {
        /* ignore */
      }

      const { data: rows } = await supabase
        .from("step_type_catalog")
        .select("step_key,display_name,settings_json_schema,import_path,input_type_fqn,output_type_fqn");

      if (rows?.length) {
        setCatalog(mergeStepCatalogWithDatabase(baseline, rows as CatalogRow[]));
        return;
      }
      if (baseline.length) setCatalog(baseline);
    })();
  }, [session]);

  useEffect(() => {
    if (!session?.user) {
      setOrgs([]);
      setOrgId(null);
      setProjects([]);
      setProjectId(null);
      setOrgsLoading(false);
      return;
    }
    void loadOrgs();
  }, [session, loadOrgs]);

  useEffect(() => {
    if (!session?.user || orgs.length === 0) {
      setProjectCountByOrgId({});
      return;
    }
    const ids = orgs.map((o) => o.id);
    void (async () => {
      const { data, error } = await supabase.from("projects").select("organization_id").in("organization_id", ids);
      if (error) return;
      const m: Record<string, number> = {};
      for (const id of ids) m[id] = 0;
      for (const row of data ?? []) {
        const oid = row.organization_id as string;
        m[oid] = (m[oid] ?? 0) + 1;
      }
      setProjectCountByOrgId(m);
    })();
  }, [session, orgs]);

  useEffect(() => {
    if (!orgId) {
      setProjects([]);
      setProjectId(null);
      return;
    }
    let cancelled = false;
    setProjects([]);
    setProjectId(null);
    void (async () => {
      const { data: projs, error } = await supabase.from("projects").select("id,name,slug").eq("organization_id", orgId);
      if (cancelled) return;
      if (error) {
        setErrMsg(error.message);
        setProjects([]);
        setProjectId(null);
        return;
      }
      const list = (projs ?? []) as ProjectRow[];
      setProjects(list);
    })();
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  /** `/` → last dashboard path or organization list */
  useEffect(() => {
    if (!session?.user || orgsLoading) return;
    if (orgs.length === 0) return;
    const path = location.pathname.replace(/\/+$/, "") || "/";
    if (path !== "/" && path !== "") return;
    const last = sessionStorage.getItem(LAST_PATH_KEY);
    if (last) {
      const parsed = parseDashboardPath(last.split("?")[0] ?? "");
      if (parsed.kind !== "unknown") {
        if (parsed.kind === "orgs") {
          navigate(pathOrganizations(), { replace: true });
          return;
        }
        const org = resolveOrgRef(orgs, parsed.orgRef);
        if (org) {
          navigate(last, { replace: true });
          return;
        }
      }
    }
    navigate(pathOrganizations(), { replace: true });
  }, [session, orgsLoading, orgs, location.pathname, navigate]);

  /** URL → org, project, and screen (slug or UUID segments). */
  useEffect(() => {
    if (!session?.user || orgsLoading || orgs.length === 0) return;
    const path = location.pathname.replace(/\/+$/, "") || "/";
    if (path === "/" || path === "") return;

    const parsed = parseDashboardPath(path);
    if (parsed.kind === "unknown") {
      navigate(pathOrganizations(), { replace: true });
      return;
    }

    if (parsed.kind === "orgs") {
      setAppScreen("organization");
      setProjectId(null);
      if (!orgId) {
        const first = orgs[0];
        if (first) {
          setOrgId(first.id);
          sessionStorage.setItem(STORAGE_ORG, first.id);
        }
      }
      sessionStorage.setItem(LAST_PATH_KEY, path);
      return;
    }

    const org = resolveOrgRef(orgs, parsed.orgRef);
    if (!org) {
      navigate(pathOrganizations(), { replace: true });
      return;
    }
    if (orgId !== org.id) {
      setOrgId(org.id);
      sessionStorage.setItem(STORAGE_ORG, org.id);
      return;
    }

    if (parsed.kind === "orgProjects") {
      setAppScreen("project");
      setProjectId(null);
      sessionStorage.setItem(LAST_PATH_KEY, path);
      return;
    }

    if (projects.length === 0) return;

    const proj = resolveProjectRef(projects, parsed.projectRef);
    if (!proj) {
      navigate(pathOrgProjects(org), { replace: true });
      return;
    }
    if (projectId !== proj.id) {
      setProjectId(proj.id);
      sessionStorage.setItem(STORAGE_PROJECT, proj.id);
    }
    setAppScreen(parsed.kind === "projectOverview" ? "projectOverview" : "workspace");
    sessionStorage.setItem(LAST_PATH_KEY, path);
  }, [
    session,
    orgsLoading,
    orgs,
    orgId,
    projects,
    projectId,
    location.pathname,
    navigate,
  ]);

  const refreshProjectOverview = useCallback(async (showLoading: boolean) => {
    const pid = projectIdRef.current;
    if (!pid) return;

    const stillHere = () => projectIdRef.current === pid;

    if (showLoading) {
      setOverviewLoading(true);
      setOverviewBranches(null);
      setOverviewRevisions(null);
      setOverviewRuns(null);
      setOverviewActiveCount(null);
      setOverviewStoppedCount(null);
      setOverviewActiveRuns([]);
      setOverviewStoppedRuns([]);
    }

    try {
      const { data: br } = await supabase.from("config_branches").select("id").eq("project_id", pid);
      if (!stillHere()) return;
      const branchIds = (br ?? []).map((b) => b.id as string);
      setOverviewBranches(branchIds.length);
      let revCount = 0;
      if (branchIds.length > 0) {
        const { count } = await supabase
          .from("config_revisions")
          .select("id", { count: "exact", head: true })
          .in("branch_id", branchIds);
        revCount = count ?? 0;
      }
      if (!stillHere()) return;
      setOverviewRevisions(revCount);

      const { count: runCount } = await supabase
        .from("pipeline_runs")
        .select("id", { count: "exact", head: true })
        .eq("project_id", pid);
      if (!stillHere()) return;
      setOverviewRuns(runCount ?? 0);

      const { count: activeCnt } = await supabase
        .from("pipeline_runs")
        .select("id", { count: "exact", head: true })
        .eq("project_id", pid)
        .in("status", [...ACTIVE_PIPELINE_STATUSES]);
      if (!stillHere()) return;
      setOverviewActiveCount(activeCnt ?? 0);

      const { count: stoppedCnt } = await supabase
        .from("pipeline_runs")
        .select("id", { count: "exact", head: true })
        .eq("project_id", pid)
        .in("status", [...STOPPED_PIPELINE_STATUSES]);
      if (!stillHere()) return;
      setOverviewStoppedCount(stoppedCnt ?? 0);

      const { data: activeRows } = await supabase
        .from("pipeline_runs")
        .select("id,status,created_at,updated_at,temporal_workflow_id")
        .eq("project_id", pid)
        .in("status", [...ACTIVE_PIPELINE_STATUSES])
        .order("created_at", { ascending: false })
        .limit(30);
      if (!stillHere()) return;
      setOverviewActiveRuns((activeRows ?? []) as OverviewPipelineRun[]);

      const { data: stoppedRows } = await supabase
        .from("pipeline_runs")
        .select("id,status,created_at,updated_at,temporal_workflow_id")
        .eq("project_id", pid)
        .in("status", [...STOPPED_PIPELINE_STATUSES])
        .order("created_at", { ascending: false })
        .limit(30);
      if (!stillHere()) return;
      setOverviewStoppedRuns((stoppedRows ?? []) as OverviewPipelineRun[]);
    } finally {
      if (showLoading && stillHere()) setOverviewLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!projectId || appScreen !== "projectOverview") return;
    void refreshProjectOverview(true);
  }, [projectId, appScreen, refreshProjectOverview]);

  useEffect(() => {
    if (!projectId || appScreen !== "projectOverview") return;
    const tick = window.setInterval(() => void refreshProjectOverview(false), 20_000);
    return () => window.clearInterval(tick);
  }, [projectId, appScreen, refreshProjectOverview]);

  useEffect(() => {
    if (!projectId && (appScreen === "workspace" || appScreen === "projectOverview")) setAppScreen("project");
  }, [projectId, appScreen]);

  useEffect(() => {
    if (appScreen !== "workspace") setStepSelectorOpen(false);
  }, [appScreen]);

  useEffect(() => {
    if (!projectId) {
      setBranches([]);
      setBranchId(null);
      return;
    }
    void (async () => {
      const { data: br } = await supabase.from("config_branches").select("id,name").eq("project_id", projectId);
      setBranches((br ?? []) as { id: string; name: string }[]);
      const main = (br ?? []).find((b) => b.name === "main");
      setBranchId((main ?? br?.[0])?.id ?? null);
    })();
  }, [projectId]);

  useEffect(() => {
    if (!branchId) {
      setRevisionId(null);
      setNodes([]);
      setEdges([]);
      lastPersistedDagJsonRef.current = JSON.stringify(flowToDag([], []));
      return;
    }
    void (async () => {
      const { data: rev } = await supabase
        .from("config_revisions")
        .select("id,dag_json")
        .eq("branch_id", branchId)
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle();
      if (!rev) return;
      setRevisionId(rev.id as string);
      const dag = (rev.dag_json ?? emptyDag()) as DagJson;
      const { nodes: ns, edges: es } = dagToFlow(dag.nodes?.length ? dag : emptyDag());
      lastPersistedDagJsonRef.current = JSON.stringify(flowToDag(ns, es));
      setNodes(ns);
      setEdges(es);
    })();
  }, [branchId, setEdges, setNodes]);

  /** Merge step catalog into canvas nodes when the catalog loads or updates — without replacing layout from the server. */
  useEffect(() => {
    setNodes((nds) => {
      let changed = false;
      const next = nds.map((n) => {
        const row = catalogByKey.get(n.data.step_key);
        if (!row) return n;
        const settingsSchema = row.settings_json_schema ?? n.data.settingsSchema ?? null;
        const input_type_fqn = row.input_type_fqn ?? n.data.input_type_fqn;
        const output_type_fqn = row.output_type_fqn ?? n.data.output_type_fqn;
        if (
          n.data.settingsSchema === settingsSchema &&
          n.data.input_type_fqn === input_type_fqn &&
          n.data.output_type_fqn === output_type_fqn
        ) {
          return n;
        }
        changed = true;
        return {
          ...n,
          data: {
            ...n.data,
            settingsSchema,
            input_type_fqn,
            output_type_fqn,
          },
        };
      });
      return changed ? next : nds;
    });
  }, [catalogByKey, setNodes]);

  useEffect(() => {
    setConnectErrMsg(null);
  }, [branchId]);

  useEffect(() => {
    setSelectedEdgeIds((ids) => ids.filter((id) => edges.some((e) => e.id === id)));
  }, [edges]);

  const pipelineNodeRefs = useMemo(
    () =>
      nodes.map((n) => ({
        id: n.id,
        step_key: n.data.step_key,
        input_type_fqn: n.data.input_type_fqn,
        output_type_fqn: n.data.output_type_fqn,
      })),
    [nodes],
  );

  const isValidConnection = useCallback(
    (conn: Connection | Edge) => {
      const src = conn.source;
      const tgt = conn.target;
      if (!src || !tgt) return false;
      return validatePipelineConnection(src, tgt, pipelineNodeRefs, edges, catalogByKey).valid;
    },
    [pipelineNodeRefs, edges, catalogByKey],
  );

  const onConnectStart = useCallback(() => {
    setConnectErrMsg(null);
  }, []);

  const onConnectEnd = useCallback(
    (_event: MouseEvent | TouchEvent, state: FinalConnectionState) => {
      if (state.isValid !== false) return;
      const fromId = state.fromNode?.id;
      const toId = state.toNode?.id;
      if (fromId == null || toId == null) return;
      const r = validatePipelineConnection(fromId, toId, pipelineNodeRefs, edges, catalogByKey);
      if (!r.valid) setConnectErrMsg(r.message);
    },
    [pipelineNodeRefs, edges, catalogByKey],
  );

  const onConnect = useCallback(
    (p: Connection) => {
      setConnectErrMsg(null);
      setEdges((eds) => addEdge({ ...p, id: `e-${p.source}-${p.target}-${eds.length}` }, eds));
    },
    [setEdges],
  );

  const onFlowSelectionChange = useCallback(
    ({ edges: selEdges }: { nodes: Node<StepNodeData>[]; edges: Edge[] }) => {
      setSelectedEdgeIds(selEdges.map((e) => e.id));
    },
    [],
  );

  const removeSelectedConnections = useCallback(() => {
    if (selectedEdgeIds.length === 0) return;
    setConnectErrMsg(null);
    setEdges((eds) => eds.filter((e) => !selectedEdgeIds.includes(e.id)));
    setSelectedEdgeIds([]);
  }, [selectedEdgeIds, setEdges]);

  const commitDagRevision = useCallback(async (summary: string, options?: { quiet?: boolean }) => {
    const bid = branchIdRef.current;
    if (!bid) return;

    const settingsErr = validateAllPipelineStepSettings(nodesRef.current, catalogByKeyRef.current);
    if (settingsErr) {
      if (!options?.quiet) setErrMsg(settingsErr);
      return;
    }

    const dag = flowToDag(nodesRef.current, edgesRef.current);
    const snapshot = JSON.stringify(dag);
    if (options?.quiet && snapshot === lastPersistedDagJsonRef.current) return;

    if (!options?.quiet) {
      setErrMsg(null);
      setStatusMsg(null);
    }

    const { data: newId, error } = await supabase.rpc("create_config_revision", {
      p_branch_id: bid,
      p_dag_json: dag,
      p_summary: summary,
      p_parent_revision_id: revisionIdRef.current,
    });

    if (error) {
      setErrMsg(error.message);
      return;
    }

    lastPersistedDagJsonRef.current = snapshot;
    const newRev = newId as string;
    revisionIdRef.current = newRev;
    setRevisionId(newRev);
    setErrMsg(null);
    if (!options?.quiet) setStatusMsg("Revision saved.");

    queueMicrotask(() => {
      const latest = JSON.stringify(flowToDag(nodesRef.current, edgesRef.current));
      if (latest === lastPersistedDagJsonRef.current) return;
      void commitDagRevision("auto-saved from web UI", { quiet: true });
    });
  }, []);

  useEffect(() => {
    if (!branchId) return;
    const snapshot = JSON.stringify(flowToDag(nodes, edges));
    if (snapshot === lastPersistedDagJsonRef.current) return;

    const t = window.setTimeout(() => {
      const latest = JSON.stringify(flowToDag(nodesRef.current, edgesRef.current));
      if (latest === lastPersistedDagJsonRef.current) return;
      void commitDagRevision("auto-saved from web UI", { quiet: true });
    }, 800);

    return () => window.clearTimeout(t);
  }, [nodes, edges, branchId, commitDagRevision]);

  const selectedNode = nodes.find((n) => n.id === selectedId) ?? null;

  async function signUpClick() {
    setAuthError(null);
    const { error } = await supabase.auth.signUp({ email, password });
    setAuthError(error?.message ?? null);
  }

  async function signIn(e: FormEvent) {
    e.preventDefault();
    setAuthError(null);
    setErrMsg(null);
    setStatusMsg(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setAuthError(error?.message ?? null);
  }

  async function signOut() {
    await supabase.auth.signOut();
    setErrMsg(null);
    setStatusMsg(null);
    sessionStorage.removeItem(LAST_PATH_KEY);
    sessionStorage.removeItem("wurzel.appScreen");
    navigate("/", { replace: true });
    setAppScreen("project");
  }

  async function createOrg(e: FormEvent) {
    e.preventDefault();
    setErrMsg(null);
    const name = orgName.trim();
    if (!name) {
      setErrMsg("Enter an organization name.");
      return;
    }
    for (let attempt = 0; attempt < 8; attempt++) {
      const slug = generatedSlugFromName(name);
      const { data: newOrgId, error: oerr } = await supabase.rpc("create_organization", {
        p_name: name,
        p_slug: slug,
      });
      if (!oerr && newOrgId != null) {
        sessionStorage.setItem(STORAGE_ORG, newOrgId as string);
        const rows = await loadOrgs(newOrgId as string);
        const created = rows.find((o) => o.id === (newOrgId as string));
        if (created) {
          const path = pathOrgProjects(created);
          sessionStorage.setItem(LAST_PATH_KEY, path);
          navigate(path, { replace: true });
        }
        setOrgName("");
        return;
      }
      if (!isUniqueViolation(oerr)) {
        setErrMsg(oerr?.message ?? "Could not create organization.");
        return;
      }
    }
    setErrMsg("Could not create organization. Try a different name.");
  }

  async function createAnotherOrg(e: FormEvent) {
    e.preventDefault();
    setErrMsg(null);
    const name = newOrgName.trim();
    if (!name) {
      setErrMsg("Enter an organization name.");
      return;
    }
    for (let attempt = 0; attempt < 8; attempt++) {
      const slug = generatedSlugFromName(name);
      const { data: newOrgId, error: oerr } = await supabase.rpc("create_organization", {
        p_name: name,
        p_slug: slug,
      });
      if (!oerr && newOrgId != null) {
        setNewOrgName("");
        setShowNewOrgInline(false);
        sessionStorage.removeItem(STORAGE_PROJECT);
        sessionStorage.setItem(STORAGE_ORG, newOrgId as string);
        const rows = await loadOrgs(newOrgId as string);
        const created = rows.find((o) => o.id === (newOrgId as string));
        if (created) {
          const path = pathOrgProjects(created);
          sessionStorage.setItem(LAST_PATH_KEY, path);
          navigate(path, { replace: true });
        }
        return;
      }
      if (!isUniqueViolation(oerr)) {
        setErrMsg(oerr?.message ?? "Could not create organization.");
        return;
      }
    }
    setErrMsg("Could not create organization. Try a different name.");
  }

  function switchOrganization(nextOrgId: string) {
    const o = orgs.find((x) => x.id === nextOrgId);
    if (!o) return;
    sessionStorage.removeItem(STORAGE_PROJECT);
    sessionStorage.setItem(STORAGE_ORG, nextOrgId);
    const path = pathOrgProjects(o);
    sessionStorage.setItem(LAST_PATH_KEY, path);
    navigate(path);
  }

  function selectProject(nextProjectId: string) {
    const o = orgs.find((x) => x.id === orgId);
    const p = projects.find((x) => x.id === nextProjectId);
    if (!o || !p) return;
    sessionStorage.setItem(STORAGE_PROJECT, nextProjectId);
    const path = pathProjectOverview(o, p);
    sessionStorage.setItem(LAST_PATH_KEY, path);
    navigate(path);
  }

  async function createProject(e: FormEvent) {
    e.preventDefault();
    if (!orgId) return;
    setErrMsg(null);
    const name = projectName.trim();
    if (!name) {
      setErrMsg("Enter a project name.");
      return;
    }
    for (let attempt = 0; attempt < 8; attempt++) {
      const slug = generatedSlugFromName(name);
      const { data: p, error } = await supabase
        .from("projects")
        .insert({ organization_id: orgId, name, slug })
        .select("id,name,slug")
        .single();
      if (!error && p) {
        const row = p as ProjectRow;
        setProjects((prev) => {
          const rest = prev.filter((x) => x.id !== row.id);
          return [...rest, row].sort((a, b) => a.name.localeCompare(b.name));
        });
        sessionStorage.setItem(STORAGE_PROJECT, row.id);
        const o = orgs.find((x) => x.id === orgId);
        if (o) {
          const path = pathProjectOverview(o, row);
          sessionStorage.setItem(LAST_PATH_KEY, path);
          navigate(path, { replace: true });
        }
        setProjectName("");
        return;
      }
      if (!isUniqueViolation(error)) {
        setErrMsg(error?.message ?? "Could not create project.");
        return;
      }
    }
    setErrMsg("Could not create project. Try a different name.");
  }

  function openStepSelector() {
    setStepSelectorSearch("");
    setStepSelectorOpen(true);
  }

  function closeStepSelector() {
    setStepSelectorOpen(false);
    setStepSelectorSearch("");
  }

  function addStepNodeWithKey(step_key: string) {
    const row = catalogByKey.get(step_key);
    const id = `n-${crypto.randomUUID().slice(0, 8)}`;
    setNodes((nds) => [
      ...nds,
      {
        id,
        type: "step",
        position: flowGridPosition(nds.length),
        data: {
          label: step_key.split(".").pop() ?? step_key,
          step_key,
          settings: {},
          settingsSchema: row?.settings_json_schema ?? null,
          input_type_fqn: row?.input_type_fqn ?? null,
          output_type_fqn: row?.output_type_fqn ?? null,
        },
      },
    ]);
  }

  function confirmAddFromSelector() {
    if (!selectedCatalogKey) return;
    addStepNodeWithKey(selectedCatalogKey);
    closeStepSelector();
  }

  async function saveRevision() {
    if (!branchId) return;
    await commitDagRevision("edited from web UI");
  }

  async function promoteToMain() {
    if (!revisionId) return;
    setErrMsg(null);
    setStatusMsg(null);
    const { data: newRev, error } = await supabase.rpc("promote_config_revision", {
      p_source_revision_id: revisionId,
      p_target_branch_name: "main",
    });
    if (error) {
      setErrMsg(error.message);
      return;
    }
    setStatusMsg(`Promoted to main as revision ${newRev}`);
    const main = branches.find((b: { name: string }) => b.name === "main");
    if (main) setBranchId(main.id);
  }

  async function createBranch() {
    const name = window.prompt("New branch name");
    if (!name || !projectId) return;
    setErrMsg(null);
    const { data: bid, error } = await supabase.rpc("create_config_branch", {
      p_project_id: projectId,
      p_branch_name: name,
      p_from_revision_id: revisionId,
    });
    if (error) {
      setErrMsg(error.message);
      return;
    }
    setBranches((prev: { id: string; name: string }[]) => [...prev, { id: bid as string, name }]);
    setBranchId(bid as string);
  }

  async function createBranchFromMenu() {
    setBranchMenuOpen(false);
    await createBranch();
  }

  async function runPipeline() {
    if (!revisionId) {
      setErrMsg("Save a revision before running.");
      return;
    }
    const settingsErr = validateAllPipelineStepSettings(nodesRef.current, catalogByKeyRef.current);
    if (settingsErr) {
      setErrMsg(settingsErr);
      return;
    }
    setErrMsg(null);
    setStatusMsg(null);
    setWorkflowRunStatus(null);

    const terminalTemporal = new Set([
      "COMPLETED",
      "FAILED",
      "CANCELED",
      "TERMINATED",
      "TIMED_OUT",
      "CONTINUED_AS_NEW",
    ]);

    async function refreshWorkflowRunStatus(temporalWorkflowId: string): Promise<{ done: boolean }> {
      const gatewayBase = (import.meta.env.VITE_KAAS_GATEWAY_URL as string | undefined)?.trim();
      const token = session?.access_token;
      const anon = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
      if (gatewayBase && token) {
        const statusUrl = `${gatewayBase.replace(/\/$/, "")}/api/v1/workflow-status?workflow_id=${encodeURIComponent(temporalWorkflowId)}`;
        const res = await fetch(statusUrl, {
          headers: {
            Authorization: `Bearer ${token}`,
            ...(anon ? { apikey: anon } : {}),
          },
        });
        const payload = (await res.json().catch(() => ({}))) as {
          temporal_status?: string;
          db_status?: string;
          error?: string;
          detail?: string;
        };
        if (!res.ok) {
          setWorkflowRunStatus(
            payload.detail
              ? `${payload.error ?? "Status"}: ${payload.detail}`
              : (payload.error ?? `HTTP ${res.status}`),
          );
          return { done: false };
        }
        const ts = payload.temporal_status ?? "?";
        const ds = payload.db_status ?? "?";
        setWorkflowRunStatus(`Temporal: ${ts} · DB: ${ds}`);
        return { done: terminalTemporal.has(ts) };
      }
      const { data, error: rowErr } = await supabase
        .from("pipeline_runs")
        .select("status")
        .eq("temporal_workflow_id", temporalWorkflowId)
        .maybeSingle();
      if (rowErr) {
        setWorkflowRunStatus(rowErr.message);
        return { done: false };
      }
      const st = data?.status ?? "unknown";
      setWorkflowRunStatus(`Pipeline run: ${st}`);
      return { done: st === "succeeded" || st === "failed" || st === "cancelled" };
    }

    async function pollUntilWorkflowSettles(temporalWorkflowId: string) {
      for (let i = 0; i < 60; i++) {
        const { done } = await refreshWorkflowRunStatus(temporalWorkflowId);
        if (done) return;
        await new Promise((r) => setTimeout(r, 1000));
      }
    }

    const gatewayBase = (import.meta.env.VITE_KAAS_GATEWAY_URL as string | undefined)?.trim();
    if (gatewayBase) {
      const token = session?.access_token;
      if (!token) {
        setErrMsg("Not signed in.");
        return;
      }
      const anon = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
      const url = `${gatewayBase.replace(/\/$/, "")}/api/v1/pipeline-runs/start`;
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          ...(anon ? { apikey: anon } : {}),
        },
        body: JSON.stringify({ config_revision_id: revisionId }),
      });
      const payload = (await res.json().catch(() => ({}))) as {
        temporal_workflow_id?: string;
        error?: string;
        detail?: string;
      };
      if (!res.ok) {
        const msg = payload.detail
          ? `${payload.error ?? "Request failed"}: ${payload.detail}`
          : (payload.error ?? `HTTP ${res.status}`);
        setErrMsg(msg);
        return;
      }
      const wid = payload.temporal_workflow_id;
      setStatusMsg(`Started workflow: ${wid ?? JSON.stringify(payload)}`);
      if (wid) void pollUntilWorkflowSettles(wid);
      return;
    }

    const { data, error } = await supabase.functions.invoke("start-pipeline-run", {
      body: { config_revision_id: revisionId },
    });
    if (error) {
      setErrMsg(error.message);
      return;
    }
    const wid = (data as { temporal_workflow_id?: string }).temporal_workflow_id;
    setStatusMsg(`Started workflow: ${wid ?? JSON.stringify(data)}`);
    if (wid) void pollUntilWorkflowSettles(wid);
  }

  if (!session) {
    return (
      <div className="auth-layout">
        <div className="panel auth-card">
          <h1>Wurzel KaaS</h1>
          <p className="auth-lead">Sign in with email and password. Local Supabase must have the Email provider enabled.</p>
          <form onSubmit={signIn} data-testid="sign-in-form">
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                data-testid="auth-email"
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                data-testid="auth-password"
              />
            </label>
            <div className="field-row">
              <button type="submit" className="btn btn-primary" data-testid="sign-in-submit">
                Sign in
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => void signUpClick()} data-testid="sign-up-submit">
                Sign up
              </button>
            </div>
          </form>
          {authError && (
            <p className="error status-banner status-banner--error" data-testid="auth-error" role="alert">
              {authError}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (orgsLoading) {
    return (
      <div className="auth-layout">
        <p className="workspace-subtitle" data-testid="orgs-loading">
          Loading your workspace…
        </p>
      </div>
    );
  }

  if (orgs.length === 0) {
    return (
      <div className="dash-shell dash-shell--center">
        <div className="dash-onboard-card">
          <h1 className="dash-page-title">Create your organization</h1>
          <p className="dash-lead">Enter a name. You can add projects after this step.</p>
          <form onSubmit={createOrg} data-testid="create-org-form">
            <label className="field dash-field">
              <span>Organization name</span>
              <input value={orgName} onChange={(e) => setOrgName(e.target.value)} required data-testid="org-name" placeholder="My team" />
            </label>
            <button type="submit" className="btn btn-dash-primary" data-testid="create-org-submit">
              Create organization
            </button>
          </form>
          {errMsg && (
            <p className="error status-banner status-banner--error" data-testid="form-error" role="alert">
              {errMsg}
            </p>
          )}
          <div className="onboarding-actions">
            <button type="button" className="btn btn-ghost" onClick={() => void signOut()} data-testid="sign-out-onboarding">
              Sign out
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!orgId) {
    return (
      <div className="auth-layout">
        <p className="workspace-subtitle" data-testid="orgs-reconcile-loading">
          Preparing organization…
        </p>
      </div>
    );
  }

  const dashSidebar = (
    <aside
      className="dash-sidebar fixed left-0 top-0 z-[45] flex h-dvh w-[52px] shrink-0 flex-col items-center gap-4 border-r border-[var(--dash-border)] bg-[#141414] py-3"
      aria-label="Sidebar"
    >
      <div className="dash-sidebar-mark" title="Wurzel" />
      <div className="dash-sidebar-divider" aria-hidden />
      <nav className="dash-sidebar-nav" aria-label="Main views" data-testid="main-nav">
        {projectId ? (
          <>
            <button
              type="button"
              className={`dash-sidebar-btn${appScreen === "projectOverview" ? " dash-sidebar-btn--active" : ""}`}
              title="Overview"
              aria-label="Overview"
              aria-current={appScreen === "projectOverview" ? "page" : undefined}
              data-testid="nav-overview"
              onClick={() => navigateTo("projectOverview")}
            >
              <svg className="dash-sidebar-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
                <rect x="3" y="3" width="7" height="9" rx="1" />
                <rect x="14" y="3" width="7" height="5" rx="1" />
                <rect x="14" y="11" width="7" height="10" rx="1" />
                <rect x="3" y="15" width="7" height="6" rx="1" />
              </svg>
            </button>
            <button
              type="button"
              className={`dash-sidebar-btn${appScreen === "workspace" ? " dash-sidebar-btn--active" : ""}`}
              title="Pipeline"
              aria-label="Pipeline"
              aria-current={appScreen === "workspace" ? "page" : undefined}
              data-testid="nav-workspace"
              onClick={() => navigateTo("workspace")}
            >
              <svg className="dash-sidebar-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
                <circle cx="6" cy="8" r="2.25" />
                <circle cx="18" cy="8" r="2.25" />
                <circle cx="12" cy="17" r="2.25" />
                <path d="M8.25 8h7.5M12 10.25V14.75" strokeLinecap="round" />
              </svg>
            </button>
          </>
        ) : null}
        <button
          type="button"
          className={`dash-sidebar-btn${appScreen === "organization" ? " dash-sidebar-btn--active" : ""}`}
          title="Organizations"
          aria-label="Organizations"
          aria-current={appScreen === "organization" ? "page" : undefined}
          data-testid="nav-organization"
          onClick={() => navigateTo("organization")}
        >
          <svg className="dash-sidebar-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        </button>
        <button
          type="button"
          className={`dash-sidebar-btn${appScreen === "project" ? " dash-sidebar-btn--active" : ""}`}
          title="Projects"
          aria-label="Projects"
          aria-current={appScreen === "project" ? "page" : undefined}
          data-testid="nav-project"
          onClick={() => navigateTo("project")}
        >
          <svg className="dash-sidebar-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" strokeLinejoin="round" />
          </svg>
        </button>
      </nav>
    </aside>
  );

  const projectViewPanel = (
    <div className="dash-page" data-testid="project-view">
      <h1 className="dash-sr-only">Projects</h1>
      <p className="dash-context-line">
        Organization <strong data-testid="project-view-org-name">{currentOrg?.name ?? "—"}</strong>
      </p>
      <div className="dash-toolbar">
        <input
          type="search"
          className="dash-search"
          placeholder="Search project"
          value={projectSearch}
          onChange={(e) => setProjectSearch(e.target.value)}
          data-testid="project-search"
          aria-label="Search projects"
        />
      </div>
      {filteredProjects.length > 0 ? (
        <div className="dash-card-grid" data-testid="project-list">
          {filteredProjects.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`dash-card dash-card--project${p.id === projectId ? " dash-card--active" : ""}`}
              data-testid="project-list-item"
              onClick={() => selectProject(p.id)}
            >
              <div className="dash-card-icon" aria-hidden />
              <div className="dash-card-body">
                <strong className="dash-card-title">{p.name}</strong>
                <span className="dash-card-meta">Pipeline · branches &amp; revisions</span>
              </div>
            </button>
          ))}
        </div>
      ) : projects.length === 0 ? (
        <p className="dash-empty" data-testid="project-empty">
          No projects yet. Create one below.
        </p>
      ) : (
        <p className="dash-empty">No projects match this search.</p>
      )}
      <form id="new-project-form" className="dash-new-form" onSubmit={createProject} data-testid="create-project-form">
        <h2 className="dash-section-title">New project</h2>
        <div className="dash-new-form-row">
          <label className="field dash-field">
            <span>Project name</span>
            <input value={projectName} onChange={(e) => setProjectName(e.target.value)} required data-testid="project-name" placeholder="My pipeline" />
          </label>
          <button type="submit" className="btn btn-dash-primary" data-testid="create-project-submit">
            Create project
          </button>
        </div>
      </form>
      {errMsg && appScreen === "project" ? (
        <p className="error status-banner status-banner--error" data-testid="form-error" role="alert">
          {errMsg}
        </p>
      ) : null}
    </div>
  );

  const organizationViewPanel = (
    <div className="dash-page" data-testid="org-view">
      <h1 className="dash-sr-only">Your organizations</h1>
      <div className="dash-toolbar">
        <input
          type="search"
          className="dash-search"
          placeholder="Search for an organization"
          value={orgSearch}
          onChange={(e) => setOrgSearch(e.target.value)}
          data-testid="org-search"
          aria-label="Search organizations"
        />
      </div>
      {showNewOrgInline ? (
        <form
          className="dash-inline-form panel"
          onSubmit={(e) => {
            void createAnotherOrg(e);
          }}
          data-testid="create-additional-org-form"
        >
          <h2 className="dash-section-title">New organization</h2>
          <div className="dash-new-form-row">
            <label className="field dash-field">
              <span>Organization name</span>
              <input value={newOrgName} onChange={(e) => setNewOrgName(e.target.value)} required data-testid="new-org-name" placeholder="Name" />
            </label>
            <button type="submit" className="btn btn-dash-primary" data-testid="create-additional-org-submit">
              Create
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setShowNewOrgInline(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}
      <div className="dash-card-grid">
        {filteredOrgs.map((o) => (
          <button
            key={o.id}
            type="button"
            className={`dash-card dash-card--org${o.id === orgId ? " dash-card--active" : ""}`}
            data-testid="org-list-item"
            onClick={() => switchOrganization(o.id)}
          >
            <div className="dash-card-icon dash-card-icon--org" aria-hidden />
            <div className="dash-card-body">
              <strong className="dash-card-title" data-testid={o.id === orgId ? "org-detail-name" : undefined}>
                {o.name}
              </strong>
              <span className="dash-card-meta">
                {projectCountByOrgId[o.id] ?? 0} project{(projectCountByOrgId[o.id] ?? 0) === 1 ? "" : "s"}
              </span>
            </div>
          </button>
        ))}
      </div>
      {errMsg && appScreen === "organization" ? (
        <p className="error status-banner status-banner--error" data-testid="org-view-error" role="alert">
          {errMsg}
        </p>
      ) : null}
    </div>
  );

  const appHeader = (
    <header className="dash-topbar sticky top-0 z-[30] flex flex-wrap items-center justify-between gap-3 border-b border-[var(--dash-border)] bg-[var(--dash-bg)] px-5 py-2.5">
      <div className="dash-topbar-cluster flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-2">
        <div className="dash-topbar-brand inline-flex items-center gap-2">
          <span className="dash-logo" aria-hidden />
          <span className="dash-product">Wurzel</span>
        </div>
        <nav className="dash-breadcrumb-bar" aria-label="Organization and project">
          <div className="dash-crumb-segment">
            <span className="dash-crumb-icon dash-crumb-icon--org" aria-hidden />
            {orgs.length > 1 ? (
              <select
                className="dash-crumb-select"
                value={orgId ?? ""}
                onChange={(e) => switchOrganization(e.target.value)}
                data-testid="org-switcher"
                aria-label="Organization"
              >
                {orgs.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            ) : (
              <span className="dash-crumb-static">{currentOrg?.name ?? "—"}</span>
            )}
            <span className="dash-badge dash-badge--free">FREE</span>
          </div>
          <span className="dash-crumb-sep" aria-hidden>
            /
          </span>
          <div className="dash-crumb-segment">
            <span className="dash-crumb-icon dash-crumb-icon--project" aria-hidden />
            {projectId && projects.length > 0 ? (
              <select
                className="dash-crumb-select"
                value={projectId}
                onChange={(e) => selectProject(e.target.value)}
                data-testid="project-switcher"
                aria-label="Project"
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            ) : (
              <span className="dash-crumb-static">Projects</span>
            )}
          </div>
          {projectId ? (
            <>
              {appScreen === "workspace" ? (
                <>
                  <span className="dash-crumb-sep" aria-hidden>
                    /
                  </span>
                  <div className="dash-crumb-segment dash-crumb-segment--branch">
                    <div className="dash-branch-picker" ref={branchMenuRef}>
                      <button
                        type="button"
                        className="dash-branch-trigger"
                        data-testid="branch-select"
                        data-active-branch={currentBranchName}
                        aria-label="Branch"
                        aria-expanded={branchMenuOpen}
                        aria-haspopup="listbox"
                        onClick={() => setBranchMenuOpen((o) => !o)}
                      >
                        <span className="dash-branch-trigger-text">{currentBranchName || "Branch"}</span>
                      </button>
                      {currentBranchName === "main" ? (
                        <span className="dash-badge dash-badge--production">PRODUCTION</span>
                      ) : null}
                      {branchMenuOpen ? (
                        <div className="dash-branch-dropdown" role="listbox" data-testid="branch-menu-dropdown">
                          {branches.map((b: { id: string; name: string }) => (
                            <button
                              key={b.id}
                              type="button"
                              role="option"
                              aria-selected={b.id === branchId}
                              data-testid="branch-menu-option"
                              data-branch-name={b.name}
                              className={`dash-branch-menu-row${b.id === branchId ? " dash-branch-menu-row--active" : ""}`}
                              onClick={() => {
                                setBranchId(b.id);
                                setBranchMenuOpen(false);
                              }}
                            >
                              {b.name === "main" ? (
                                <span className="dash-branch-shield" aria-hidden title="Protected branch">
                                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden>
                                    <path
                                      d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
                                      stroke="#f97316"
                                      strokeWidth="1.5"
                                      strokeLinejoin="round"
                                    />
                                  </svg>
                                </span>
                              ) : (
                                <span className="dash-branch-shield-spacer" aria-hidden />
                              )}
                              <span className="dash-branch-menu-label">{b.name}</span>
                              {b.id === branchId ? (
                                <span className="dash-branch-check" aria-hidden>
                                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden>
                                    <path
                                      d="M20 6L9 17l-5-5"
                                      stroke="currentColor"
                                      strokeWidth="2"
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                    />
                                  </svg>
                                </span>
                              ) : (
                                <span className="dash-branch-check-spacer" aria-hidden />
                              )}
                            </button>
                          ))}
                          <div className="dash-branch-menu-sep" role="separator" />
                          <button
                            type="button"
                            className="dash-branch-menu-action"
                            data-testid="new-branch"
                            onClick={() => void createBranchFromMenu()}
                          >
                            <span className="dash-branch-action-icon" aria-hidden>
                              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden>
                                <path
                                  d="M12 5v14M5 12h14"
                                  stroke="currentColor"
                                  strokeWidth="1.75"
                                  strokeLinecap="round"
                                />
                              </svg>
                            </span>
                            Create branch
                          </button>
                          <button
                            type="button"
                            className="dash-branch-menu-action"
                            data-testid="manage-branches"
                            onClick={() => {
                              setBranchMenuOpen(false);
                              setBranchManageOpen(true);
                            }}
                          >
                            <span className="dash-branch-action-icon" aria-hidden>
                              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden>
                                <path
                                  d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"
                                  stroke="currentColor"
                                  strokeWidth="1.75"
                                  strokeLinecap="round"
                                />
                              </svg>
                            </span>
                            Manage branches
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </>
              ) : null}
            </>
          ) : null}
        </nav>
      </div>
      <div className="dash-topbar-right flex shrink-0 flex-wrap items-center gap-2 sm:gap-3">
        {appScreen === "organization" ? (
          <button type="button" className="btn btn-dash-primary btn-dash-primary--compact" onClick={() => setShowNewOrgInline(true)}>
            + New organization
          </button>
        ) : null}
        {appScreen === "project" && orgId ? (
          <button
            type="button"
            className="btn btn-dash-primary btn-dash-primary--compact"
            onClick={() => document.getElementById("new-project-form")?.scrollIntoView({ behavior: "smooth" })}
          >
            + New project
          </button>
        ) : null}
        <span className="dash-user" data-testid="workspace-user">
          {session.user.email ?? session.user.id}
        </span>
        <button type="button" className="btn btn-dash-outline" onClick={() => void signOut()} data-testid="sign-out-header">
          Sign out
        </button>
      </div>
    </header>
  );

  const projectOverviewPanel = (
    <div className="dash-page" data-testid="project-overview">
      <h1 className="dash-sr-only">Project overview</h1>
      {overviewLoading ? (
        <p className="dash-lead" data-testid="overview-loading">
          Loading metrics…
        </p>
      ) : (
        <>
          <div className="dash-metric-grid">
            <div className="dash-metric-card" data-testid="metric-branches">
              <span className="dash-metric-label">Branches</span>
              <span className="dash-metric-value">{overviewBranches ?? "—"}</span>
            </div>
            <div className="dash-metric-card" data-testid="metric-revisions">
              <span className="dash-metric-label">Revisions</span>
              <span className="dash-metric-value">{overviewRevisions ?? "—"}</span>
            </div>
            <div className="dash-metric-card" data-testid="metric-runs">
              <span className="dash-metric-label">Pipeline runs (total)</span>
              <span className="dash-metric-value">{overviewRuns ?? "—"}</span>
            </div>
            <div className="dash-metric-card" data-testid="metric-active-workflows">
              <span className="dash-metric-label">Running / pending</span>
              <span className="dash-metric-value dash-metric-value--accent">{overviewActiveCount ?? "—"}</span>
            </div>
            <div className="dash-metric-card" data-testid="metric-stopped-workflows">
              <span className="dash-metric-label">Stopped (finished)</span>
              <span className="dash-metric-value">{overviewStoppedCount ?? "—"}</span>
            </div>
          </div>

          <h2 className="dash-section-title">Workflow runs</h2>
          <p className="dash-workflow-lead workspace-subtitle">
            Status comes from the project&apos;s pipeline runs in the database (pending, running, succeeded, failed,
            cancelled). Lists refresh every 20 seconds while you stay on this page.
          </p>
          <div className="dash-workflow-overview">
            <div className="dash-workflow-column" data-testid="overview-active-workflows">
              <h3 className="dash-workflow-column-title">Running &amp; pending</h3>
              {overviewActiveRuns.length === 0 ? (
                <p className="dash-empty">No active workflows.</p>
              ) : (
                <ul className="dash-recent-runs dash-recent-runs--fluid">
                  {overviewActiveRuns.map((r) => (
                    <li key={r.id}>
                      <div className="dash-run-main">
                        <span className={`dash-run-status dash-run-status--${r.status}`}>{r.status}</span>
                        <span className="dash-run-workflow-id" title={r.temporal_workflow_id ?? r.id}>
                          {r.temporal_workflow_id ?? `${r.id.slice(0, 8)}…`}
                        </span>
                      </div>
                      <time className="dash-run-time">{new Date(r.created_at).toLocaleString()}</time>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="dash-workflow-column" data-testid="overview-stopped-workflows">
              <h3 className="dash-workflow-column-title">Stopped</h3>
              {overviewStoppedRuns.length === 0 ? (
                <p className="dash-empty">No finished runs yet.</p>
              ) : (
                <ul className="dash-recent-runs dash-recent-runs--fluid">
                  {overviewStoppedRuns.map((r) => (
                    <li key={r.id}>
                      <div className="dash-run-main">
                        <span className={`dash-run-status dash-run-status--${r.status}`}>{r.status}</span>
                        <span className="dash-run-workflow-id" title={r.temporal_workflow_id ?? r.id}>
                          {r.temporal_workflow_id ?? `${r.id.slice(0, 8)}…`}
                        </span>
                      </div>
                      <time className="dash-run-time">{new Date(r.created_at).toLocaleString()}</time>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );

  const routePathForLayout = location.pathname.replace(/\/+$/, "") || "/";
  const pathKindForLayout = parseDashboardPath(routePathForLayout);
  const loadingProjectFromUrl =
    !projectId &&
    (pathKindForLayout.kind === "projectOverview" || pathKindForLayout.kind === "projectPipeline");

  if (!projectId && !loadingProjectFromUrl) {
    return (
      <div className="dash-shell min-h-dvh min-h-[100dvh] bg-[var(--dash-bg)] pl-[52px] text-[var(--color-text)]">
        {dashSidebar}
        <div className="dash-main mx-auto w-full max-w-[1200px]">
          {appHeader}
          <div className="dash-content">{appScreen === "organization" ? organizationViewPanel : projectViewPanel}</div>
        </div>
      </div>
    );
  }

  if (loadingProjectFromUrl) {
    return (
      <div className="dash-shell min-h-dvh min-h-[100dvh] bg-[var(--dash-bg)] pl-[52px] text-[var(--color-text)]">
        {dashSidebar}
        <div className="dash-main mx-auto flex min-h-dvh w-full max-w-[1200px] flex-col">
          {appHeader}
          <div className="dash-content">
            <p className="dash-lead" data-testid="project-route-loading">
              Loading project…
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dash-shell dash-shell--project min-h-dvh min-h-[100dvh] bg-[var(--dash-bg)] pl-[52px] text-[var(--color-text)]">
      {dashSidebar}
      <div
        className={`dash-main flex min-h-dvh min-w-0 flex-col ${
          appScreen === "workspace" ? "dash-main--editor w-full max-w-none" : "mx-auto w-full max-w-[1200px]"
        }`}
        data-testid={appScreen === "workspace" ? "workspace" : "app-shell"}
      >
        {appHeader}
        <div className="dash-content">
          {appScreen === "projectOverview" ? projectOverviewPanel : null}
          {appScreen === "organization" ? organizationViewPanel : null}
          {appScreen === "project" ? projectViewPanel : null}

      {appScreen === "workspace" ? (
        <div className="workspace-editor" data-testid="workspace-editor">
          <div
            className="workspace-editor-toolbar editor-actions"
            data-testid="editor-actions"
            aria-label="Pipeline editor"
          >
            <button type="button" className="btn btn-secondary" onClick={() => void promoteToMain()} data-testid="promote-to-main">
              Promote to main
            </button>
            <div className="revision-summary" data-testid="revision-summary" title={`Revision: ${revisionId ?? "—"} · Project: ${projectDisplayName || projectId}`}>
              Revision: {revisionId ?? "—"} · Project: {projectDisplayName || projectId}
            </div>
            <div className="workspace-editor-toolbar__actions">
              <button type="button" className="btn btn-secondary" onClick={openStepSelector} data-testid="add-step-node">
                Add step
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={removeSelectedConnections}
                disabled={selectedEdgeIds.length === 0}
                data-testid="remove-selected-connection"
                title="Select a connection on the canvas first"
              >
                Remove selected connection
              </button>
              <button type="button" className="btn btn-primary" onClick={() => void saveRevision()} data-testid="save-revision">
                Save revision
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => void runPipeline()} data-testid="run-pipeline">
                Run on Temporal
              </button>
            </div>
            {statusMsg ? (
              <p className="status-banner status-banner--success status-banner--toolbar" data-testid="status-success" role="status">
                {statusMsg}
              </p>
            ) : null}
            {workflowRunStatus ? (
              <p
                className="status-banner status-banner--success status-banner--toolbar"
                data-testid="workflow-run-status"
                role="status"
              >
                {workflowRunStatus}
              </p>
            ) : null}
            {errMsg ? (
              <p className="status-banner status-banner--error status-banner--toolbar" data-testid="status-error" role="alert">
                {errMsg}
              </p>
            ) : null}
          </div>

          <div className="workspace-editor-main">
            <div className="panel flow-wrap flow-wrap--workspace" data-testid="flow-canvas">
              <p className="workspace-subtitle flow-chaining-hint" data-testid="dag-chaining-hint">
                Drag from the bottom handle to the top of another step. The downstream step must expect the same catalog type
                as the upstream output. Steps with no input type are sources and cannot receive edges. Each step may have at most
                one incoming edge; cycles are not allowed (Temporal DAG runner). Click a connection line to select it, then use
                Remove selected connection or press Delete / Backspace.
              </p>
              {connectErrMsg ? (
                <p className="flow-connect-error" data-testid="connection-error" role="alert">
                  {connectErrMsg}
                </p>
              ) : null}
              <div className="flow-wrap__canvas">
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  onConnectStart={onConnectStart}
                  onConnectEnd={onConnectEnd}
                  isValidConnection={isValidConnection}
                  nodeTypes={nodeTypes}
                  onNodeClick={(_, n) => setSelectedId(n.id)}
                  onSelectionChange={onFlowSelectionChange}
                  deleteKeyCode={["Backspace", "Delete"]}
                  elevateEdgesOnSelect
                  fitView
                >
                  <MiniMap />
                  <Controls />
                  <Background />
                </ReactFlow>
              </div>
            </div>

            {selectedNode ? (
              <div className="panel edit-node-panel" data-testid="edit-node-panel">
          <h3>Edit node</h3>
          <p
            className="workspace-subtitle edit-node-summary"
            data-testid="edit-node-summary"
            style={{ marginBottom: "0.75rem", whiteSpace: "pre-wrap" }}
          >
            {stepSummaryShort(
              catalogByKey.get(selectedNode.data.step_key) ?? {
                step_key: selectedNode.data.step_key,
                display_name: selectedNode.data.label,
                settings_json_schema: selectedNode.data.settingsSchema,
              },
              400,
            )}
          </p>
          {(() => {
            const row = catalogByKey.get(selectedNode.data.step_key);
            const tin = (row?.input_type_fqn ?? selectedNode.data.input_type_fqn ?? "").trim();
            const tout = (row?.output_type_fqn ?? selectedNode.data.output_type_fqn ?? "").trim();
            return (
              <p className="workspace-subtitle edit-node-chaining" data-testid="edit-node-chaining">
                {tin
                  ? `Expects upstream output (catalog): ${tin}`
                  : "Source step — no pipeline input; do not connect another step into this node."}
                {tout ? ` · Outputs: ${tout}` : " · Output type not listed in catalog."}
              </p>
            );
          })()}
          <label className="field">
            <span>Step type</span>
            <select
              value={selectedNode.data.step_key}
              data-testid="step-type-select"
              aria-label="Step type"
              onChange={(e) => {
                const sk = e.target.value;
                const row = catalogByKey.get(sk);
                setNodes((nds) =>
                  nds.map((n) =>
                    n.id === selectedNode.id
                      ? {
                          ...n,
                          data: {
                            ...n.data,
                            step_key: sk,
                            label: sk.split(".").pop() ?? sk,
                            settings: {},
                            settingsSchema: row?.settings_json_schema ?? null,
                            input_type_fqn: row?.input_type_fqn ?? null,
                            output_type_fqn: row?.output_type_fqn ?? null,
                          },
                        }
                      : n,
                  ),
                );
              }}
            >
              {catalog.map((c: CatalogRow) => (
                <option key={c.step_key} value={c.step_key}>
                  {c.display_name ?? c.step_key}
                </option>
              ))}
            </select>
          </label>
          {(() => {
            const effectiveSettingsSchema = resolveNodeSettingsSchema(selectedNode, catalogByKey);
            return effectiveSettingsSchema ? (
              <div style={{ marginTop: 12 }} data-testid="step-settings-form">
                <Form
                  schema={effectiveSettingsSchema as RJSFSchema}
                  formData={selectedNode.data.settings}
                  validator={settingsFormValidator}
                  liveValidate
                  onChange={(e) => {
                    const fd = e.formData as Record<string, unknown>;
                    setNodes((nds) =>
                      nds.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, settings: fd } } : n)),
                    );
                  }}
                />
              </div>
            ) : (
              <p className="workspace-subtitle" style={{ marginTop: "0.75rem" }}>
                No settings schema for this step (optional / none).
              </p>
            );
          })()}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {branchManageOpen ? (
        <div
          className="modal-backdrop"
          data-testid="branch-manage-backdrop"
          role="presentation"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setBranchManageOpen(false);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="branch-manage-title"
            className="modal-dialog branch-manage-dialog"
            data-testid="branch-manage-dialog"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <h2 id="branch-manage-title" className="branch-manage-title">
              Branches
            </h2>
            <p className="workspace-subtitle branch-manage-lead">Switch the active branch or create one from the header menu.</p>
            <ul className="branch-manage-list">
              {branches.map((b: { id: string; name: string }) => (
                <li key={b.id}>
                  <button
                    type="button"
                    className={`branch-manage-row${b.id === branchId ? " branch-manage-row--active" : ""}`}
                    data-testid="branch-manage-option"
                    data-branch-name={b.name}
                    onClick={() => {
                      setBranchId(b.id);
                      setBranchManageOpen(false);
                    }}
                  >
                    {b.name === "main" ? (
                      <span className="dash-branch-shield" aria-hidden>
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden>
                          <path
                            d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
                            stroke="#f97316"
                            strokeWidth="1.5"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </span>
                    ) : (
                      <span className="dash-branch-shield-spacer" aria-hidden />
                    )}
                    <span>{b.name}</span>
                    {b.id === branchId ? <span className="branch-manage-current">Current</span> : null}
                  </button>
                </li>
              ))}
            </ul>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setBranchManageOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {stepSelectorOpen ? (
        <div
          className="modal-backdrop"
          data-testid="step-selector-backdrop"
          role="presentation"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) closeStepSelector();
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="step-selector-title"
            className="modal-dialog step-selector-dialog"
            data-testid="step-selector-dialog"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <h2 id="step-selector-title" className="step-selector-title">
              Add pipeline step
            </h2>
            <p className="workspace-subtitle step-selector-lead">
              Search the catalog, read what each step does, then add it to the graph.
            </p>
            <div className="step-selector-grid">
              <div className="step-selector-column">
                <label className="field">
                  <span>Search</span>
                  <input
                    type="search"
                    value={stepSelectorSearch}
                    onChange={(e) => setStepSelectorSearch(e.target.value)}
                    placeholder="Filter by name or step key…"
                    data-testid="step-catalog-search"
                    autoFocus
                  />
                </label>
                <ul className="step-catalog-list" data-testid="step-catalog-list">
                  {filteredCatalog.length === 0 ? (
                    <li className="step-catalog-empty">No steps match this filter.</li>
                  ) : (
                    filteredCatalog.map((c) => (
                      <li key={c.step_key}>
                        <button
                          type="button"
                          className={`step-catalog-item${selectedCatalogKey === c.step_key ? " step-catalog-item--active" : ""}`}
                          data-testid="step-catalog-item"
                          data-step-key={c.step_key}
                          onClick={() => setSelectedCatalogKey(c.step_key)}
                        >
                          <span className="step-catalog-item-title">{c.display_name ?? c.step_key}</span>
                          <span className="step-catalog-item-blurb">{stepSummaryShort(c, 140)}</span>
                        </button>
                      </li>
                    ))
                  )}
                </ul>
              </div>
              <div className="step-selector-column step-detail-panel" data-testid="step-detail-panel">
                {selectedCatalogRow ? (
                  <>
                    <h3 className="step-detail-heading">{selectedCatalogRow.display_name ?? selectedCatalogRow.step_key}</h3>
                    <p className="step-detail-summary" data-testid="step-detail-summary">
                      {stepSummaryFull(selectedCatalogRow)}
                    </p>
                    <pre className="step-detail-technical" data-testid="step-detail-technical">
                      {stepTechnicalLines(selectedCatalogRow).join("\n")}
                    </pre>
                  </>
                ) : (
                  <p className="workspace-subtitle">Select a step from the list.</p>
                )}
              </div>
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                data-testid="step-selector-cancel"
                onClick={closeStepSelector}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                data-testid="step-selector-add"
                disabled={!selectedCatalogKey}
                onClick={confirmAddFromSelector}
              >
                Add step
              </button>
            </div>
          </div>
        </div>
      ) : null}
        </div>
      </div>
    </div>
  );
}
