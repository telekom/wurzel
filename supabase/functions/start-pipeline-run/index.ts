// SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
// SPDX-License-Identifier: Apache-2.0

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { Client, Connection } from "npm:@temporalio/client@1.11.7";

const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const authHeader = req.headers.get("Authorization");
  if (!authHeader) {
    return new Response(JSON.stringify({ error: "Missing Authorization" }), {
      status: 401,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  let body: { config_revision_id?: string };
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const revisionId = body.config_revision_id;
  if (!revisionId || typeof revisionId !== "string") {
    return new Response(JSON.stringify({ error: "config_revision_id required" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

  const supabaseUser = createClient(supabaseUrl, anonKey, {
    global: { headers: { Authorization: authHeader } },
  });

  const { data: rev, error: revErr } = await supabaseUser
    .from("config_revisions")
    .select("id, dag_json")
    .eq("id", revisionId)
    .single();

  if (revErr || !rev) {
    return new Response(
      JSON.stringify({ error: revErr?.message ?? "revision not found" }),
      { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }

  const { data: runId, error: runErr } = await supabaseUser.rpc("register_pipeline_run", {
    p_config_revision_id: revisionId,
  });

  if (runErr || runId == null) {
    return new Response(JSON.stringify({ error: runErr?.message ?? "could not register run" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const temporalAddress = Deno.env.get("TEMPORAL_ADDRESS") ?? "127.0.0.1:7233";
  const temporalNamespace = Deno.env.get("TEMPORAL_NAMESPACE") ?? "default";
  const taskQueue = Deno.env.get("WURZEL_TEMPORAL_TASK_QUEUE") ?? "wurzel-kaas";

  let workflowId: string;
  try {
    const connection = await Connection.connect({ address: temporalAddress });
    const temporal = new Client({ connection, namespace: temporalNamespace });
    const handle = await temporal.workflow.start("WurzelPipelineWorkflow", {
      taskQueue,
      workflowId: `wurzel-pipeline-${runId}`,
      args: [
        {
          dag_json: rev.dag_json,
          pipeline_run_id: runId,
        },
      ],
    });
    workflowId = handle.workflowId;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return new Response(JSON.stringify({ error: "Temporal start failed", detail: msg }), {
      status: 502,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const supabaseService = createClient(supabaseUrl, serviceKey);
  const { error: updErr } = await supabaseService.rpc("update_pipeline_run_temporal", {
    p_run_id: runId,
    p_temporal_workflow_id: workflowId,
    p_temporal_run_id: null,
    p_status: "running",
  });

  if (updErr) {
    return new Response(JSON.stringify({ error: "Run started but DB update failed", detail: updErr.message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  return new Response(
    JSON.stringify({
      pipeline_run_id: runId,
      temporal_workflow_id: workflowId,
    }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" } },
  );
});
