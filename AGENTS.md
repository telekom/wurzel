# Testing

- **Python:** `make install` then `make test` (or `uv run pytest tests/`).
- **Supabase DB (pgTAP):** `supabase start` (migrations applied), then `make test-supabase-db` or `supabase test db`.
- **Web unit (Vitest):** `cd apps/web && npm ci && npm test`.
- **Web E2E (Playwright):** `supabase start`; set `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` in `apps/web/.env` (from `supabase status -o env`); `cd apps/web && npx playwright install chromium && npm run test:e2e`. Optional: `make test-web-e2e` from repo root.
- **KaaS FastAPI gateway (pipeline start via Python Temporal client):** `uv sync --extra kaas-gateway`; export `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (same values as local Supabase), `TEMPORAL_ADDRESS=127.0.0.1:7233`; run `uv run wurzel-kaas-gateway`. In `apps/web/.env`, set `VITE_KAAS_GATEWAY_URL=http://127.0.0.1:8010` so the UI calls the gateway instead of the `start-pipeline-run` Edge Function. The UI polls `GET /api/v1/workflow-status?workflow_id=…` on the same base URL to show Temporal execution status.

If RPC/RLS errors appear, run `supabase db reset --local` so migrations match the app.
