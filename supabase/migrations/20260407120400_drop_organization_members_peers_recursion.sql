-- The peers SELECT policy referenced organization_members inside its own USING
-- clause, which made Postgres detect infinite recursion (42P17) for any read.
-- The app only needs each user to read their own rows; use select_self (prior
-- migration) for that. Peer listing can be reintroduced later via a
-- security definer helper if needed.

drop policy if exists organization_members_select_peers on public.organization_members;
