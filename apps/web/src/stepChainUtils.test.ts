import { describe, expect, it } from "vitest";
import {
  canChainByFqns,
  chainTypeMismatchMessage,
  targetAcceptsIncomingEdge,
  validatePipelineConnection,
  wouldDirectedEdgeCreateCycle,
} from "./stepChainUtils";

describe("stepChainUtils", () => {
  const mdList = "list[wurzel.datacontract.common.MarkdownDataContract]";
  const embOut = "pandera.typing.pandas.DataFrame[wurzel.steps.data.EmbeddingResult]";

  it("allows exact FQN match", () => {
    expect(canChainByFqns(mdList, mdList)).toBe(true);
    expect(canChainByFqns(embOut, embOut)).toBe(true);
  });

  it("rejects when target has no input (source step)", () => {
    expect(canChainByFqns(mdList, null)).toBe(false);
    expect(canChainByFqns(mdList, "")).toBe(false);
    expect(canChainByFqns(mdList, "  ")).toBe(false);
  });

  it("rejects when source output is unknown", () => {
    expect(canChainByFqns(null, mdList)).toBe(false);
    expect(canChainByFqns("", mdList)).toBe(false);
  });

  it("rejects FQN mismatch", () => {
    expect(canChainByFqns(mdList, embOut)).toBe(false);
  });

  it("targetAcceptsIncomingEdge mirrors empty input FQN", () => {
    expect(targetAcceptsIncomingEdge(null)).toBe(false);
    expect(targetAcceptsIncomingEdge(mdList)).toBe(true);
  });

  it("chainTypeMismatchMessage covers main cases", () => {
    expect(chainTypeMismatchMessage(mdList, null)).toMatch(/source/i);
    expect(chainTypeMismatchMessage(null, mdList)).toMatch(/no declared output/i);
    expect(chainTypeMismatchMessage(mdList, embOut)).toMatch(/mismatch/i);
  });

  it("wouldDirectedEdgeCreateCycle detects back-edge", () => {
    const edges = [{ source: "a", target: "b" }];
    expect(wouldDirectedEdgeCreateCycle(edges, "b", "a")).toBe(true);
    expect(wouldDirectedEdgeCreateCycle(edges, "a", "c")).toBe(false);
  });

  it("validatePipelineConnection rejects type mismatch with a clear message", () => {
    const md = "list[wurzel.datacontract.common.MarkdownDataContract]";
    const emb = "pandera.typing.pandas.DataFrame[wurzel.steps.data.EmbeddingResult]";
    const nodes = [
      { id: "n1", step_key: "s1", input_type_fqn: null, output_type_fqn: md },
      { id: "n2", step_key: "s2", input_type_fqn: emb, output_type_fqn: emb },
    ];
    const cat = new Map([
      ["s1", { input_type_fqn: null, output_type_fqn: md }],
      ["s2", { input_type_fqn: emb, output_type_fqn: emb }],
    ]);
    const r = validatePipelineConnection("n1", "n2", nodes, [], cat);
    expect(r.valid).toBe(false);
    if (!r.valid) expect(r.message).toMatch(/mismatch/i);
  });

  it("validatePipelineConnection allows matching types", () => {
    const md = "list[wurzel.datacontract.common.MarkdownDataContract]";
    const nodes = [
      { id: "n1", step_key: "a", input_type_fqn: null, output_type_fqn: md },
      { id: "n2", step_key: "b", input_type_fqn: md, output_type_fqn: md },
    ];
    const cat = new Map([
      ["a", { input_type_fqn: null, output_type_fqn: md }],
      ["b", { input_type_fqn: md, output_type_fqn: md }],
    ]);
    expect(validatePipelineConnection("n1", "n2", nodes, [], cat)).toEqual({ valid: true });
  });
});
