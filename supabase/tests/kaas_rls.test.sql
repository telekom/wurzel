-- KaaS RLS and RPC tests (pgTAP)
-- Practice from: https://supabase.com/docs/guides/local-development/testing/overview
-- and: https://supabase.com/blog/testing-for-vibe-coders-from-zero-to-production-confidence
begin;

create extension if not exists pgtap with schema extensions;
create extension if not exists pgcrypto;

select plan(16);

-- ---------------------------------------------------------------------------
-- Bootstrap: default DB role inserts auth.users (matches supabase db query).
-- service_role inserts public rows (bypasses RLS). Authenticated users cannot
-- read a new org before membership exists.
-- ---------------------------------------------------------------------------
insert into auth.users (
  id,
  instance_id,
  aud,
  role,
  email,
  encrypted_password,
  email_confirmed_at,
  raw_app_meta_data,
  raw_user_meta_data,
  created_at,
  updated_at
) values
  (
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated',
    'authenticated',
    'kaas_u1@test.local',
    crypt('test', gen_salt('bf')),
    now(),
    '{}',
    '{}',
    now(),
    now()
  ),
  (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated',
    'authenticated',
    'kaas_u2@test.local',
    crypt('test', gen_salt('bf')),
    now(),
    '{}',
    '{}',
    now(),
    now()
  );

set local role service_role;

insert into public.organizations (name, slug)
values ('KaaS RLS Org', 'kaas-rls-test-org');

insert into public.organization_members (organization_id, user_id, role)
select id, 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid, 'owner'
from public.organizations
where slug = 'kaas-rls-test-org';

insert into public.projects (organization_id, name, slug)
select id, 'KaaS RLS Project', 'kaas-rls-proj'
from public.organizations
where slug = 'kaas-rls-test-org';

-- ---------------------------------------------------------------------------
-- Schema / RLS presence (still useful as postgres-capable checks)
-- ---------------------------------------------------------------------------
select ok(
  (
    select c.relrowsecurity
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relname = 'projects'
  ),
  'public.projects has row level security enabled'
);

select ok(
  (
    select c.relrowsecurity
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relname = 'config_revisions'
  ),
  'public.config_revisions has row level security enabled'
);

select has_table('public', 'step_type_catalog', 'step_type_catalog table exists');

select has_table('public', 'pipeline_runs', 'pipeline_runs table exists');

-- ---------------------------------------------------------------------------
-- User 1: reads through RLS
-- ---------------------------------------------------------------------------
set local role authenticated;
set local request.jwt.claim.sub to 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

select results_eq(
  $$
    select count(*) from public.projects p
    join public.organizations o on o.id = p.organization_id
    where o.slug = 'kaas-rls-test-org'
  $$,
  array[1::bigint],
  'member user sees their project'
);

select results_eq(
  $$
    select count(*) from public.config_branches cb
    join public.projects p on p.id = cb.project_id
    where p.slug = 'kaas-rls-proj' and cb.name = 'main'
  $$,
  array[1::bigint],
  'new project has exactly one main branch'
);

select results_eq(
  $$
    select count(*) from public.config_revisions cr
    join public.config_branches cb on cb.id = cr.branch_id
    join public.projects p on p.id = cb.project_id
    where p.slug = 'kaas-rls-proj'
  $$,
  array[1::bigint],
  'new project has an initial config revision'
);

-- ---------------------------------------------------------------------------
-- User 2: no access; RPC rejected with forbidden when branch UUID is known
-- ---------------------------------------------------------------------------
set local request.jwt.claim.sub to 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';

select results_eq(
  $$select count(*) from public.projects$$,
  array[0::bigint],
  'non-member sees zero projects'
);

select lives_ok(
  $q$ select public.create_organization('U2 New', 'u2-new-org-slug') $q$,
  'create_organization RPC succeeds for user without prior membership'
);

select results_eq(
  $$ select count(*) from public.organizations where slug = 'u2-new-org-slug' $$,
  array[1::bigint],
  'create_organization persists organization row'
);

select throws_ok(
  $q$
    select public.create_config_revision(
      (select cb.id from public.config_branches cb
       join public.projects p on p.id = cb.project_id
       where p.slug = 'kaas-rls-proj' and cb.name = 'main'),
      '{"nodes":[],"edges":[]}'::jsonb,
      'hack',
      null
    )
  $q$
);

-- ---------------------------------------------------------------------------
-- User 1: RPCs
-- ---------------------------------------------------------------------------
set local request.jwt.claim.sub to 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

select lives_ok(
  $q$
    select public.create_config_revision(
      (select cb.id from public.config_branches cb
       join public.projects p on p.id = cb.project_id
       where p.slug = 'kaas-rls-proj' and cb.name = 'main'),
      '{"nodes":[{"id":"a","step_key":"wurzel.steps.manual_markdown.ManualMarkdownStep","settings":{}}],"edges":[]}'::jsonb,
      'edit',
      (select cr.id from public.config_revisions cr
       join public.config_branches cb on cb.id = cr.branch_id
       join public.projects p on p.id = cb.project_id
       where p.slug = 'kaas-rls-proj' and cb.name = 'main'
       order by cr.created_at desc limit 1)
    )
  $q$,
  'member can create_config_revision'
);

select lives_ok(
  $q$
    select public.promote_config_revision(
      (select cr.id from public.config_revisions cr
       join public.config_branches cb on cb.id = cr.branch_id
       join public.projects p on p.id = cb.project_id
       where p.slug = 'kaas-rls-proj' and cb.name = 'main'
       order by cr.created_at desc limit 1),
      'main'
    )
  $q$,
  'member can promote_config_revision to main'
);

select lives_ok(
  $q$
    select public.register_pipeline_run(
      (select cr.id from public.config_revisions cr
       join public.config_branches cb on cb.id = cr.branch_id
       join public.projects p on p.id = cb.project_id
       where p.slug = 'kaas-rls-proj' and cb.name = 'main'
       order by cr.created_at desc limit 1)
    )
  $q$,
  'member can register_pipeline_run'
);

-- ---------------------------------------------------------------------------
-- service_role: update_pipeline_run_temporal
-- ---------------------------------------------------------------------------
set local role service_role;

select lives_ok(
  $q$
    select public.update_pipeline_run_temporal(
      (select pr.id from public.pipeline_runs pr
       join public.projects p on p.id = pr.project_id
       where p.slug = 'kaas-rls-proj'
       order by pr.created_at desc limit 1),
      'wf-test-1',
      null,
      'running'
    )
  $q$,
  'service_role can update_pipeline_run_temporal'
);

-- ---------------------------------------------------------------------------
-- Anonymous: no project rows (clear JWT claim — it persists across RESET ROLE)
-- ---------------------------------------------------------------------------
reset role;
set local request.jwt.claim.sub to '';
set local role anon;

select results_eq(
  $$select count(*) from public.projects$$,
  array[0::bigint],
  'anon role cannot read projects'
);

select * from finish();
rollback;
