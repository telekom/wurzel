import { describe, expect, it } from "vitest";
import {
  mergeStepCatalogWithDatabase,
  stepSummaryFull,
  stepSummaryShort,
  stepTechnicalLines,
  type StepCatalogRow,
} from "./stepCatalogUtils";

describe("stepCatalogUtils", () => {
  it("uses schema description first paragraph for short summary", () => {
    const row: StepCatalogRow = {
      step_key: "a.b.Step",
      display_name: "Step",
      settings_json_schema: {
        description: "First paragraph.\n\nSecond paragraph ignored in short.",
      },
    };
    expect(stepSummaryShort(row)).toBe("First paragraph.");
  });

  it("truncates long first paragraph in short summary", () => {
    const long = "x".repeat(500);
    const row: StepCatalogRow = {
      step_key: "a.b.Step",
      display_name: null,
      settings_json_schema: { description: long },
    };
    const s = stepSummaryShort(row, 100);
    expect(s.length).toBe(100);
    expect(s.endsWith("…")).toBe(true);
  });

  it("falls back to display_name and I/O FQNs when no description", () => {
    const row: StepCatalogRow = {
      step_key: "a.b.MyStep",
      display_name: "MyStep",
      settings_json_schema: { type: "object" },
      input_type_fqn: "In",
      output_type_fqn: "Out",
    };
    expect(stepSummaryShort(row)).toBe("MyStep · In → Out");
  });

  it("falls back to import_path then step_key", () => {
    const row: StepCatalogRow = {
      step_key: "pkg.mod.Class",
      display_name: null,
      settings_json_schema: null,
      import_path: "pkg.mod.Class",
    };
    expect(stepSummaryShort(row)).toBe("pkg.mod.Class");
    const row2: StepCatalogRow = {
      step_key: "only.key",
      display_name: null,
      settings_json_schema: null,
    };
    expect(stepSummaryShort(row2)).toBe("only.key");
  });

  it("stepSummaryFull returns full description when present", () => {
    const row: StepCatalogRow = {
      step_key: "a.b.Step",
      display_name: "S",
      settings_json_schema: {
        description: "Line one.\n\nLine two after blank.",
      },
    };
    expect(stepSummaryFull(row)).toContain("Line two after blank");
  });

  it("mergeStepCatalogWithDatabase fills null settings_json_schema from baseline", () => {
    const baseline: StepCatalogRow[] = [
      {
        step_key: "wurzel.steps.manual_markdown.ManualMarkdownStep",
        display_name: "ManualMarkdownStep",
        settings_json_schema: { type: "object", required: ["FOLDER_PATH"], properties: { FOLDER_PATH: { type: "string" } } },
      },
    ];
    const db: StepCatalogRow[] = [
      {
        step_key: "wurzel.steps.manual_markdown.ManualMarkdownStep",
        display_name: "ManualMarkdownStep",
        settings_json_schema: null,
        input_type_fqn: null,
        output_type_fqn: "list[Markdown]",
      },
    ];
    const merged = mergeStepCatalogWithDatabase(baseline, db);
    const row = merged.find((r) => r.step_key.includes("ManualMarkdown"));
    expect(row?.settings_json_schema).toEqual(baseline[0].settings_json_schema);
    expect(row?.output_type_fqn).toBe("list[Markdown]");
  });

  it("stepTechnicalLines includes key, import, I/O", () => {
    const row: StepCatalogRow = {
      step_key: "k",
      display_name: null,
      settings_json_schema: null,
      import_path: "i",
      input_type_fqn: "in",
      output_type_fqn: "out",
    };
    expect(stepTechnicalLines(row)).toEqual([
      "step_key: k",
      "import_path: i",
      "input: in",
      "output: out",
    ]);
  });
});
