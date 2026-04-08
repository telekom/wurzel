-- Allow each user to read their own membership rows. The peers-only policy
-- uses a self-referential EXISTS that does not reliably expose the caller's row
-- to PostgREST, so the web app saw zero orgs after sign-in.

create policy organization_members_select_self
  on public.organization_members for select
  to authenticated
  using (user_id = auth.uid());
