/**
 * DAG chaining rules (aligned with wurzel.core.typed_step.TypedStep and
 * wurzel.temporal_worker.workflows.WurzelPipelineWorkflow):
 *
 * - Steps with no pipeline input (catalog `input_type_fqn` empty) are sources; they must not
 *   receive an incoming edge.
 * - Otherwise the upstream `output_type_fqn` must exactly match the downstream `input_type_fqn`
 *   (same strings as exported in the step catalog).
 * - The Temporal MVP allows at most one incoming edge per node.
 */

export function canChainByFqns(
  sourceOutputFqn: string | null | undefined,
  targetInputFqn: string | null | undefined,
): boolean {
  const tin = (targetInputFqn ?? "").trim();
  const sout = (sourceOutputFqn ?? "").trim();
  if (!tin) return false;
  if (!sout) return false;
  return sout === tin;
}

/** Human-readable reason when {@link canChainByFqns} is false (English, for UI). */
export function chainTypeMismatchMessage(
  sourceOutputFqn: string | null | undefined,
  targetInputFqn: string | null | undefined,
): string {
  const tin = (targetInputFqn ?? "").trim();
  if (!tin) return "This step has no pipeline input (it is a source) and cannot receive a connection.";
  const sout = (sourceOutputFqn ?? "").trim();
  if (!sout) return "The upstream step has no declared output type in the catalog.";
  return `Type mismatch: upstream outputs “${sout}” but this step expects “${tin}”.`;
}

export function targetAcceptsIncomingEdge(targetInputFqn: string | null | undefined): boolean {
  return Boolean((targetInputFqn ?? "").trim());
}

/** Minimal node shape for validating a proposed edge (no React Flow types). */
export type PipelineNodeRef = {
  id: string;
  step_key: string;
  input_type_fqn: string | null;
  output_type_fqn: string | null;
};

export type CatalogFqnsRow = {
  input_type_fqn?: string | null;
  output_type_fqn?: string | null;
};

/** Single source of truth for `isValidConnection` and user-facing rejection messages. */
export function validatePipelineConnection(
  sourceNodeId: string,
  targetNodeId: string,
  nodes: readonly PipelineNodeRef[],
  edges: readonly { source: string; target: string }[],
  catalogByKey: ReadonlyMap<string, CatalogFqnsRow>,
): { valid: true } | { valid: false; message: string } {
  if (!sourceNodeId || !targetNodeId || sourceNodeId === targetNodeId) {
    return { valid: false, message: "Cannot connect a step to itself." };
  }
  if (edges.some((e) => e.source === sourceNodeId && e.target === targetNodeId)) {
    return { valid: false, message: "This connection already exists." };
  }
  if (edges.some((e) => e.target === targetNodeId)) {
    return {
      valid: false,
      message: "This step already has an upstream step (only one incoming edge is allowed).",
    };
  }
  const srcNode = nodes.find((n) => n.id === sourceNodeId);
  const tgtNode = nodes.find((n) => n.id === targetNodeId);
  if (!srcNode || !tgtNode) {
    return { valid: false, message: "Cannot create this connection." };
  }
  const srcRow = catalogByKey.get(srcNode.step_key);
  const tgtRow = catalogByKey.get(tgtNode.step_key);
  const srcOut = (srcRow?.output_type_fqn ?? srcNode.output_type_fqn ?? "").trim() || null;
  const tgtIn = (tgtRow?.input_type_fqn ?? tgtNode.input_type_fqn ?? "").trim() || null;
  if (!canChainByFqns(srcOut, tgtIn)) {
    return { valid: false, message: chainTypeMismatchMessage(srcOut, tgtIn) };
  }
  if (wouldDirectedEdgeCreateCycle(edges, sourceNodeId, targetNodeId)) {
    return { valid: false, message: "That would create a cycle in the pipeline." };
  }
  return { valid: true };
}

/** True if adding `newSource → newTarget` would create a directed cycle (given existing edges only). */
export function wouldDirectedEdgeCreateCycle(
  existing: readonly { source: string; target: string }[],
  newSource: string,
  newTarget: string,
): boolean {
  if (newSource === newTarget) return true;
  const adj = new Map<string, string[]>();
  for (const e of existing) {
    if (!adj.has(e.source)) adj.set(e.source, []);
    adj.get(e.source)!.push(e.target);
  }
  const stack = [newTarget];
  const seen = new Set<string>();
  while (stack.length > 0) {
    const n = stack.pop()!;
    if (n === newSource) return true;
    if (seen.has(n)) continue;
    seen.add(n);
    for (const next of adj.get(n) ?? []) stack.push(next);
  }
  return false;
}
