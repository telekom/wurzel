#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
#
# Sets up a local Supabase development environment with MinIO S3 backend.
# Safe to re-run – skips steps that are already done.
#
# The Supabase docker stack is bootstrapped from the official upstream repo on
# first run and placed in infra/superbase/ (gitignored).  Only the overlay
# files in scripts/overlays/ need to live in this repo.
#
# Usage: bash scripts/setup-dev.sh
#        (or via: make setup-dev)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SUPABASE_DIR="${REPO_ROOT}/infra/superbase"
OVERLAYS_DIR="${SCRIPT_DIR}/overlays"

# Pinned to the same release visible in docker-compose.yml
# (supabase/studio:2026.03.16-sha-5528817)
SUPABASE_REPO="https://github.com/supabase/supabase"
SUPABASE_BRANCH="master"

# ── Colour helpers ──────────────────────────────────────────────────────────
if [ -t 1 ]; then
  GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; RESET='\033[0m'
else
  GREEN=''; YELLOW=''; RED=''; RESET=''
fi

info()    { printf "${GREEN}[setup-dev]${RESET} %s\n" "$*"; }
warning() { printf "${YELLOW}[setup-dev] WARNING:${RESET} %s\n" "$*"; }
error()   { printf "${RED}[setup-dev] ERROR:${RESET} %s\n" "$*" >&2; exit 1; }

# ── Prerequisite checks ─────────────────────────────────────────────────────
check_prereqs() {
  info "Checking prerequisites..."

  command -v git    >/dev/null 2>&1 || error "git is required but not found."
  command -v podman >/dev/null 2>&1 || error "podman is required but not found. Install via: brew install podman"
  command -v openssl>/dev/null 2>&1 || error "openssl is required but not found."

  if ! podman compose version >/dev/null 2>&1; then
    error "podman compose is required but not found. Install via: brew install podman-compose"
  fi

  if ! podman info >/dev/null 2>&1; then
    error "Podman machine is not running. Start it with: podman machine start"
  fi

  info "All prerequisites satisfied."
}

# ── Bootstrap Supabase docker stack ─────────────────────────────────────────
# Downloads the official Supabase docker directory from GitHub using a sparse
# checkout (no full clone) and places it at infra/superbase/.
bootstrap_supabase() {
  if [ -f "${SUPABASE_DIR}/docker-compose.yml" ]; then
    info "Supabase docker stack already present – skipping bootstrap."
    return
  fi

  info "Bootstrapping Supabase docker stack from upstream..."
  info "  → ${SUPABASE_REPO} (branch: ${SUPABASE_BRANCH})"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '${tmp_dir}'" EXIT

  # Sparse checkout – only downloads the docker/ subdirectory (~1 MB vs ~1 GB)
  git clone \
    --filter=blob:none \
    --no-checkout \
    --depth 1 \
    --branch "${SUPABASE_BRANCH}" \
    "${SUPABASE_REPO}" \
    "${tmp_dir}/supabase" \
    2>&1 | sed 's/^/  /'

  git -C "${tmp_dir}/supabase" sparse-checkout set --cone docker
  git -C "${tmp_dir}/supabase" checkout "${SUPABASE_BRANCH}" 2>&1 | sed 's/^/  /'

  mkdir -p "${SUPABASE_DIR}"
  cp -r "${tmp_dir}/supabase/docker/." "${SUPABASE_DIR}/"

  info "Bootstrap complete → ${SUPABASE_DIR}"
}

# ── Copy repo-tracked overlays into the bootstrapped directory ───────────────
copy_overlays() {
  if [ ! -d "${OVERLAYS_DIR}" ]; then
    return
  fi

  info "Copying overlay files into ${SUPABASE_DIR}..."
  for f in "${OVERLAYS_DIR}"/*; do
    [ -f "${f}" ] || continue
    local dest="${SUPABASE_DIR}/$(basename "${f}")"
    if [ ! -f "${dest}" ] || ! diff -q "${f}" "${dest}" >/dev/null 2>&1; then
      cp "${f}" "${dest}"
      info "  ✓ $(basename "${f}")"
    fi
  done
}

# ── .env setup ──────────────────────────────────────────────────────────────
setup_env() {
  local env_file="${SUPABASE_DIR}/.env"
  local env_example="${SUPABASE_DIR}/.env.example"

  if [ ! -f "${env_file}" ]; then
    if [ -f "${env_example}" ]; then
      info "Copying .env.example → .env"
      cp "${env_example}" "${env_file}"
    else
      error ".env not found and no .env.example to copy from in ${SUPABASE_DIR}"
    fi
  else
    info ".env already exists – skipping copy."
  fi
}

# ── Secret generation ────────────────────────────────────────────────────────
# Detect whether the .env still contains the well-known placeholder values
# shipped in .env.example.  If so, regenerate all secrets automatically.
PLACEHOLDER_POSTGRES_PASSWORD="your-super-secret-and-long-postgres-password"
PLACEHOLDER_JWT_SECRET="your-super-secret-jwt-token-with-at-least-32-characters-long"

secrets_are_placeholder() {
  local env_file="${SUPABASE_DIR}/.env"
  grep -qF "POSTGRES_PASSWORD=${PLACEHOLDER_POSTGRES_PASSWORD}" "${env_file}" || \
  grep -qF "JWT_SECRET=${PLACEHOLDER_JWT_SECRET}" "${env_file}"
}

generate_secrets() {
  if secrets_are_placeholder; then
    info "Placeholder secrets detected – generating fresh secrets..."
    (cd "${SUPABASE_DIR}" && sh utils/generate-keys.sh --update-env)
    info "Secrets written to .env."
  else
    info "Secrets already configured – skipping generation."
  fi
}

# ── MinIO / S3 credentials sync ──────────────────────────────────────────────
# Ensure MINIO_ROOT_PASSWORD in .env matches the generated S3 storage secret
# so MinIO and Supabase Storage stay in sync after key regeneration.
sync_minio_credentials() {
  local env_file="${SUPABASE_DIR}/.env"
  local old_default="secret1234"

  if grep -qF "MINIO_ROOT_PASSWORD=${old_default}" "${env_file}"; then
    local new_pass
    new_pass="$(grep '^S3_PROTOCOL_ACCESS_KEY_SECRET=' "${env_file}" | cut -d= -f2 | head -c 32)"
    if [ -n "${new_pass}" ]; then
      info "Syncing MINIO_ROOT_PASSWORD with generated S3 secret..."
      sed -i.bak "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=${new_pass}|" "${env_file}"
      rm -f "${env_file}.bak"
    fi
  fi
}

# ── Compose file list ────────────────────────────────────────────────────────
COMPOSE_FILES=(
  -f docker-compose.yml
  -f docker-compose.s3.yml
  -f docker-compose.healthcheck-override.yml
)

# ── Pull images ─────────────────────────────────────────────────────────────
pull_images() {
  info "Pulling latest Supabase + MinIO images (this may take a while on first run)..."
  (cd "${SUPABASE_DIR}" && podman compose "${COMPOSE_FILES[@]}" pull --quiet)
}

# ── Start services ───────────────────────────────────────────────────────────
start_services() {
  info "Starting Supabase with S3 (MinIO) backend..."
  (cd "${SUPABASE_DIR}" && podman compose "${COMPOSE_FILES[@]}" up -d --remove-orphans)
}

# ── Health check ─────────────────────────────────────────────────────────────
wait_for_healthy() {
  local timeout=180
  local interval=5
  local elapsed=0

  info "Waiting for all services to become healthy (timeout: ${timeout}s)..."

  while [ "${elapsed}" -lt "${timeout}" ]; do
    local not_healthy
    not_healthy=$(
      cd "${SUPABASE_DIR}" && podman compose "${COMPOSE_FILES[@]}" \
        ps --format json 2>/dev/null \
      | grep -v '"Health":"healthy"' \
      | grep -v '"Health":""' \
      | grep '"State":"running"' \
      | wc -l | tr -d ' '
    )

    local exited
    exited=$(
      cd "${SUPABASE_DIR}" && podman compose "${COMPOSE_FILES[@]}" \
        ps --format json 2>/dev/null \
      | grep '"State":"exited"' \
      | grep -v 'minio-createbucket' \
      | wc -l | tr -d ' '
    )

    if [ "${exited}" -gt 0 ]; then
      warning "One or more containers exited unexpectedly."
      warning "Run: podman compose ${COMPOSE_FILES[*]} ps  (from ${SUPABASE_DIR})"
    fi

    if [ "${not_healthy}" -eq 0 ]; then
      info "All services are healthy."
      return 0
    fi

    printf "  ... ${not_healthy} service(s) not yet healthy (%ds elapsed)\r" "${elapsed}"
    sleep "${interval}"
    elapsed=$((elapsed + interval))
  done

  warning "Timeout reached. Some services may still be starting up."
  warning "Run: podman compose ${COMPOSE_FILES[*]} ps  (from ${SUPABASE_DIR})"
}

# ── Summary ──────────────────────────────────────────────────────────────────
print_summary() {
  local env_file="${SUPABASE_DIR}/.env"
  local public_url dashboard_user dashboard_pass
  public_url="$(grep '^SUPABASE_PUBLIC_URL=' "${env_file}" | cut -d= -f2)"
  dashboard_user="$(grep '^DASHBOARD_USERNAME=' "${env_file}" | cut -d= -f2)"
  dashboard_pass="$(grep '^DASHBOARD_PASSWORD=' "${env_file}" | cut -d= -f2)"

  echo ""
  printf "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
  printf "${GREEN}  Supabase dev environment is ready!${RESET}\n"
  printf "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
  echo ""
  printf "  Studio URL   : %s\n"           "${public_url:-http://localhost:8000}"
  printf "  Dashboard    : %s / %s\n"      "${dashboard_user:-supabase}" "${dashboard_pass:-(see infra/superbase/.env)}"
  printf "  REST API     : %s/rest/v1/\n"  "${public_url:-http://localhost:8000}"
  printf "  Auth API     : %s/auth/v1/\n"  "${public_url:-http://localhost:8000}"
  printf "  Storage API  : %s/storage/v1/\n" "${public_url:-http://localhost:8000}"
  printf "  S3 backend   : MinIO (internal)\n"
  echo ""
  printf "  Stack dir    : %s\n" "${SUPABASE_DIR}"
  printf "  Stop with    : cd %s && podman compose %s down\n" \
    "${SUPABASE_DIR}" "${COMPOSE_FILES[*]}"
  echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  check_prereqs
  bootstrap_supabase
  copy_overlays
  setup_env
  generate_secrets
  sync_minio_credentials
  pull_images
  start_services
  wait_for_healthy
  print_summary
}

main "$@"
