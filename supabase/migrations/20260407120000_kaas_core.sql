-- Wurzel KaaS: orgs, projects, config branches/revisions, runs, step catalog, RLS, RPCs

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Core tables
-- ---------------------------------------------------------------------------

create table public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  created_at timestamptz not null default now()
);

create table public.organization_members (
  organization_id uuid not null references public.organizations (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'admin', 'member')),
  created_at timestamptz not null default now(),
  primary key (organization_id, user_id)
);

create table public.projects (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations (id) on delete cascade,
  name text not null,
  slug text not null,
  created_at timestamptz not null default now(),
  unique (organization_id, slug)
);

create table public.config_branches (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  name text not null,
  created_at timestamptz not null default now(),
  unique (project_id, name)
);

create table public.config_revisions (
  id uuid primary key default gen_random_uuid(),
  branch_id uuid not null references public.config_branches (id) on delete cascade,
  parent_revision_id uuid references public.config_revisions (id) on delete set null,
  created_by uuid references auth.users (id) on delete set null,
  dag_json jsonb not null default '{"nodes":[],"edges":[]}'::jsonb,
  summary text,
  created_at timestamptz not null default now()
);

create index config_revisions_branch_created_at_idx
  on public.config_revisions (branch_id, created_at desc);

create table public.promotion_events (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  source_revision_id uuid not null references public.config_revisions (id) on delete cascade,
  target_branch_id uuid not null references public.config_branches (id) on delete cascade,
  new_revision_id uuid not null references public.config_revisions (id) on delete cascade,
  promoted_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now()
);

create table public.step_type_catalog (
  id uuid primary key default gen_random_uuid(),
  step_key text not null unique,
  display_name text,
  import_path text not null,
  settings_json_schema jsonb,
  input_json_schema jsonb,
  output_json_schema jsonb,
  input_type_fqn text,
  output_type_fqn text,
  updated_at timestamptz not null default now()
);

create table public.pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  config_revision_id uuid not null references public.config_revisions (id) on delete restrict,
  status text not null default 'pending'
    check (status in ('pending', 'running', 'succeeded', 'failed', 'cancelled')),
  temporal_workflow_id text,
  temporal_run_id text,
  error_message text,
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index pipeline_runs_project_created_at_idx
  on public.pipeline_runs (project_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Default `main` branch for every new project
-- ---------------------------------------------------------------------------

create or replace function public.create_default_main_branch()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.config_branches (project_id, name)
  values (new.id, 'main');
  insert into public.config_revisions (branch_id, dag_json, summary)
  select cb.id, '{"nodes":[],"edges":[]}'::jsonb, 'initial empty pipeline'
  from public.config_branches cb
  where cb.project_id = new.id and cb.name = 'main';
  return new;
end;
$$;

create trigger projects_after_insert_main_branch
  after insert on public.projects
  for each row execute function public.create_default_main_branch();

-- ---------------------------------------------------------------------------
-- Helpers for RLS
-- ---------------------------------------------------------------------------

create or replace function public.is_org_member(_user_id uuid, _org_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.organization_members m
    where m.user_id = _user_id and m.organization_id = _org_id
  );
$$;

create or replace function public.project_org_id(_project_id uuid)
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select organization_id from public.projects where id = _project_id;
$$;

create or replace function public.user_can_access_project(_user_id uuid, _project_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.is_org_member(_user_id, public.project_org_id(_project_id));
$$;

create or replace function public.branch_project_id(_branch_id uuid)
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select project_id from public.config_branches where id = _branch_id;
$$;

create or replace function public.revision_branch_id(_revision_id uuid)
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select branch_id from public.config_revisions where id = _revision_id;
$$;

-- ---------------------------------------------------------------------------
-- RPC: append a new revision on a branch
-- ---------------------------------------------------------------------------

create or replace function public.create_config_revision(
  p_branch_id uuid,
  p_dag_json jsonb,
  p_summary text default null,
  p_parent_revision_id uuid default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_project uuid;
  v_rev uuid;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;

  select project_id into v_project from public.config_branches where id = p_branch_id;
  if v_project is null then
    raise exception 'branch not found';
  end if;

  if not public.user_can_access_project(auth.uid(), v_project) then
    raise exception 'forbidden';
  end if;

  insert into public.config_revisions (
    branch_id, parent_revision_id, created_by, dag_json, summary
  ) values (
    p_branch_id, p_parent_revision_id, auth.uid(), p_dag_json, p_summary
  )
  returning id into v_rev;

  return v_rev;
end;
$$;

grant execute on function public.create_config_revision(uuid, jsonb, text, uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- RPC: promote a revision onto `main` (copy snapshot)
-- ---------------------------------------------------------------------------

create or replace function public.promote_config_revision(
  p_source_revision_id uuid,
  p_target_branch_name text default 'main'
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_src_branch uuid;
  v_src_project uuid;
  v_target_branch uuid;
  v_dag jsonb;
  v_new_rev uuid;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;

  select cr.branch_id, cb.project_id, cr.dag_json
  into v_src_branch, v_src_project, v_dag
  from public.config_revisions cr
  join public.config_branches cb on cb.id = cr.branch_id
  where cr.id = p_source_revision_id;

  if v_src_project is null then
    raise exception 'source revision not found';
  end if;

  if not public.user_can_access_project(auth.uid(), v_src_project) then
    raise exception 'forbidden';
  end if;

  select id into v_target_branch
  from public.config_branches
  where project_id = v_src_project and name = p_target_branch_name;

  if v_target_branch is null then
    raise exception 'target branch % not found', p_target_branch_name;
  end if;

  insert into public.config_revisions (
    branch_id, parent_revision_id, created_by, dag_json, summary
  ) values (
    v_target_branch,
    p_source_revision_id,
    auth.uid(),
    v_dag,
    format('promoted from revision %s', p_source_revision_id)
  )
  returning id into v_new_rev;

  insert into public.promotion_events (
    project_id, source_revision_id, target_branch_id, new_revision_id, promoted_by
  ) values (
    v_src_project, p_source_revision_id, v_target_branch, v_new_rev, auth.uid()
  );

  return v_new_rev;
end;
$$;

grant execute on function public.promote_config_revision(uuid, text) to authenticated;

-- ---------------------------------------------------------------------------
-- RPC: create an additional named branch (optional head revision)
-- ---------------------------------------------------------------------------

create or replace function public.create_config_branch(
  p_project_id uuid,
  p_branch_name text,
  p_from_revision_id uuid default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_branch uuid;
  v_dag jsonb := '{"nodes":[],"edges":[]}'::jsonb;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;

  if not public.user_can_access_project(auth.uid(), p_project_id) then
    raise exception 'forbidden';
  end if;

  if p_branch_name = 'main' then
    raise exception 'branch main already exists by default';
  end if;

  insert into public.config_branches (project_id, name)
  values (p_project_id, p_branch_name)
  returning id into v_branch;

  if p_from_revision_id is not null then
    select dag_json into v_dag
    from public.config_revisions
    where id = p_from_revision_id
      and branch_id in (select id from public.config_branches where project_id = p_project_id);
    if v_dag is null then
      raise exception 'from_revision not in this project';
    end if;
  end if;

  insert into public.config_revisions (branch_id, parent_revision_id, created_by, dag_json, summary)
  values (v_branch, p_from_revision_id, auth.uid(), v_dag,
    case when p_from_revision_id is null then 'new branch' else 'branched from revision' end);

  return v_branch;
end;
$$;

grant execute on function public.create_config_branch(uuid, text, uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- RPC: register pipeline run (called before Edge Function starts Temporal)
-- ---------------------------------------------------------------------------

create or replace function public.register_pipeline_run(p_config_revision_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_project uuid;
  v_run uuid;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;

  select cb.project_id into v_project
  from public.config_revisions cr
  join public.config_branches cb on cb.id = cr.branch_id
  where cr.id = p_config_revision_id;

  if v_project is null then
    raise exception 'revision not found';
  end if;

  if not public.user_can_access_project(auth.uid(), v_project) then
    raise exception 'forbidden';
  end if;

  insert into public.pipeline_runs (
    project_id, config_revision_id, status, created_by
  ) values (
    v_project, p_config_revision_id, 'pending', auth.uid()
  )
  returning id into v_run;

  return v_run;
end;
$$;

grant execute on function public.register_pipeline_run(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- RPC: service role / Edge Function — attach Temporal ids and status
-- ---------------------------------------------------------------------------

create or replace function public.update_pipeline_run_temporal(
  p_run_id uuid,
  p_temporal_workflow_id text,
  p_temporal_run_id text default null,
  p_status text default 'running'
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.pipeline_runs
  set
    temporal_workflow_id = coalesce(p_temporal_workflow_id, temporal_workflow_id),
    temporal_run_id = coalesce(p_temporal_run_id, temporal_run_id),
    status = p_status,
    updated_at = now()
  where id = p_run_id;
end;
$$;

-- Only service_role should call this (no grant to authenticated)
grant execute on function public.update_pipeline_run_temporal(uuid, text, text, text) to service_role;

-- ---------------------------------------------------------------------------
-- Row level security
-- ---------------------------------------------------------------------------

alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.projects enable row level security;
alter table public.config_branches enable row level security;
alter table public.config_revisions enable row level security;
alter table public.promotion_events enable row level security;
alter table public.pipeline_runs enable row level security;
alter table public.step_type_catalog enable row level security;

-- Organizations: members read
create policy organizations_select_member
  on public.organizations for select
  using (public.is_org_member(auth.uid(), id));

-- Members: see peers in orgs you belong to
create policy organization_members_select_peers
  on public.organization_members for select
  using (
    exists (
      select 1 from public.organization_members m2
      where m2.organization_id = organization_members.organization_id
        and m2.user_id = auth.uid()
    )
  );

-- Projects
create policy projects_all_member
  on public.projects for all
  using (public.is_org_member(auth.uid(), organization_id))
  with check (public.is_org_member(auth.uid(), organization_id));

-- Config branches
create policy config_branches_all
  on public.config_branches for all
  using (public.user_can_access_project(auth.uid(), project_id))
  with check (public.user_can_access_project(auth.uid(), project_id));

-- Config revisions
create policy config_revisions_all
  on public.config_revisions for all
  using (
    public.user_can_access_project(auth.uid(), public.branch_project_id(branch_id))
  )
  with check (
    public.user_can_access_project(auth.uid(), public.branch_project_id(branch_id))
  );

-- Promotion events
create policy promotion_events_select
  on public.promotion_events for select
  using (public.user_can_access_project(auth.uid(), project_id));

-- Pipeline runs
create policy pipeline_runs_all
  on public.pipeline_runs for all
  using (public.user_can_access_project(auth.uid(), project_id))
  with check (public.user_can_access_project(auth.uid(), project_id));

-- Step catalog: readable by any authenticated user; writes via service_role only
create policy step_type_catalog_select_auth
  on public.step_type_catalog for select
  to authenticated
  using (true);

-- Service role bypasses RLS by default in Supabase

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------

grant usage on schema public to anon, authenticated, service_role;

grant select, insert, update, delete on public.organizations to authenticated;
grant select, insert, update, delete on public.organization_members to authenticated;
grant select, insert, update, delete on public.projects to authenticated;
grant select, insert, update, delete on public.config_branches to authenticated;
grant select, insert, update, delete on public.config_revisions to authenticated;
grant select on public.promotion_events to authenticated;
grant select, insert, update, delete on public.pipeline_runs to authenticated;
grant select on public.step_type_catalog to authenticated;

grant all on all sequences in schema public to authenticated, service_role;

-- Allow first user bootstrap: create org (app will add self as owner via separate insert)
-- Restrict inserts on organization_members — only owners can add members (simplified: allow insert if user inserts self as owner of new org - handled in app)
-- For demo, we allow authenticated users to insert organizations they create
create policy organizations_insert_authenticated
  on public.organizations for insert
  to authenticated
  with check (true);

create policy organization_members_insert_self
  on public.organization_members for insert
  to authenticated
  with check (user_id = auth.uid());
