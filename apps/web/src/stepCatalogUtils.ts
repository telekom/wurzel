export type StepCatalogRow = {
  step_key: string;
  display_name: string | null;
  settings_json_schema: Record<string, unknown> | null;
  import_path?: string | null;
  input_type_fqn?: string | null;
  output_type_fqn?: string | null;
};

/** Merge DB catalog rows with bundled `public/step_catalog.json`: fill null JSON columns from the baseline. */
export function mergeStepCatalogWithDatabase(baseline: StepCatalogRow[], dbRows: StepCatalogRow[]): StepCatalogRow[] {
  const map = new Map<string, StepCatalogRow>(baseline.map((r) => [r.step_key, { ...r }]));
  for (const db of dbRows) {
    const prev = map.get(db.step_key);
    map.set(db.step_key, {
      step_key: db.step_key,
      display_name: db.display_name ?? prev?.display_name ?? null,
      import_path: db.import_path ?? prev?.import_path ?? null,
      settings_json_schema: db.settings_json_schema ?? prev?.settings_json_schema ?? null,
      input_type_fqn: db.input_type_fqn ?? prev?.input_type_fqn ?? null,
      output_type_fqn: db.output_type_fqn ?? prev?.output_type_fqn ?? null,
    });
  }
  return [...map.values()].sort((a, b) => a.step_key.localeCompare(b.step_key));
}

function schemaDescription(schema: unknown): string | null {
  if (schema === null || schema === undefined) return null;
  if (typeof schema !== "object" || Array.isArray(schema)) return null;
  const d = (schema as Record<string, unknown>).description;
  return typeof d === "string" ? d : null;
}

/** First paragraph or full string, truncated for list rows. */
export function stepSummaryShort(row: StepCatalogRow, maxLen = 400): string {
  const desc = schemaDescription(row.settings_json_schema);
  if (desc) {
    const firstPara = desc.split(/\n\n/)[0]?.trim() ?? desc;
    if (firstPara.length <= maxLen) return firstPara;
    return `${firstPara.slice(0, Math.max(1, maxLen - 1))}…`;
  }
  const bits: string[] = [];
  if (row.display_name) bits.push(row.display_name);
  if (row.input_type_fqn || row.output_type_fqn) {
    bits.push([row.input_type_fqn, row.output_type_fqn].filter(Boolean).join(" → "));
  }
  if (bits.length) return bits.join(" · ");
  if (row.import_path) return row.import_path;
  return row.step_key;
}

/** Full schema description or fallback summary. */
export function stepSummaryFull(row: StepCatalogRow): string {
  const desc = schemaDescription(row.settings_json_schema);
  if (desc) return desc.trim();
  return stepSummaryShort(row, 10_000);
}

/** Technical identifiers for the detail panel. */
export function stepTechnicalLines(row: StepCatalogRow): string[] {
  const lines: string[] = [`step_key: ${row.step_key}`];
  if (row.import_path) lines.push(`import_path: ${row.import_path}`);
  if (row.input_type_fqn) lines.push(`input: ${row.input_type_fqn}`);
  if (row.output_type_fqn) lines.push(`output: ${row.output_type_fqn}`);
  return lines;
}
