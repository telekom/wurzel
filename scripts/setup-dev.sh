#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
#
# Sets up a local development environment with:
#   - Supabase (via Supabase CLI)
#   - Temporal (via Temporal CLI)
# Safe to re-run – skips steps that already done.
#
# Both services run via their respective CLIs:
#   - Supabase: supabase start (uses Docker via Colima)
#   - Temporal: temporal server start-dev
#
# Requirements:
#   - Colima (brew install colima)
#   - Docker CLI (brew install docker)
#   - Supabase CLI (brew install supabase/tap/supabase)
#   - Temporal CLI (brew install temporal)
#
# This uses Colima for a lightweight Docker-compatible runtime.
#
# Usage: bash scripts/setup-dev.sh
#        (or via: make setup-dev)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SUPABASE_DIR="${REPO_ROOT}/supabase"
TEMPORAL_DB_DIR="${REPO_ROOT}/.temporal"

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

  command -v git      >/dev/null 2>&1 || error "git is required but not found."
  command -v colima   >/dev/null 2>&1 || error "colima is required but not found. Install via: brew install colima"
  command -v docker   >/dev/null 2>&1 || error "docker CLI is required but not found. Install via: brew install docker"
  command -v supabase >/dev/null 2>&1 || error "supabase CLI is required but not found. Install via: brew install supabase/tap/supabase"
  command -v temporal >/dev/null 2>&1 || error "temporal CLI is required but not found. Install via: brew install temporal"

  info "All prerequisites satisfied."
}

# ── Initialize and configure Colima ────────────────────────────────────────
setup_colima() {
  info "Setting up Colima..."
  
  # Check if DOCKER_HOST is set to Podman and warn/unset it
  if [ -n "${DOCKER_HOST:-}" ]; then
    if [[ "$DOCKER_HOST" == *"podman"* ]]; then
      warning "DOCKER_HOST is set to Podman socket: ${DOCKER_HOST}"
      warning "Unsetting DOCKER_HOST to use Colima..."
      unset DOCKER_HOST
      export DOCKER_HOST=""
    fi
  fi
  
  # Check if Colima is already running
  if colima status >/dev/null 2>&1; then
    info "Colima is already running."
  else
    info "Starting Colima (this may take a minute)..."
    # Start with sensible defaults: 4 CPUs, 8GB RAM, 100GB disk
    colima start --cpu 4 --memory 8 --disk 100 --arch "$(uname -m)"
  fi
  
  # Set Docker context to Colima explicitly
  if docker context ls --format "{{.Name}}" 2>/dev/null | grep -q "^colima$"; then
    info "Switching Docker context to Colima..."
    docker context use colima >/dev/null 2>&1 || true
  fi
  
  # Verify Docker CLI can connect
  if ! docker info >/dev/null 2>&1; then
    error "Docker CLI cannot connect to Colima. Try: colima restart"
  fi
  
  local docker_version
  docker_version="$(docker --version 2>/dev/null || echo 'unknown')"
  local colima_status
  colima_status="$(colima status 2>/dev/null || echo 'unknown')"
  
  info "Docker CLI version: ${docker_version}"
  info "Colima status: ${colima_status}"
  info "Colima is ready."
}

# ── Initialize Supabase project ────────────────────────────────────────────
init_supabase() {
  if [ -f "${SUPABASE_DIR}/config.toml" ]; then
    info "Supabase project already initialized – skipping init."
    return
  fi

  info "Initializing Supabase project..."
  cd "${REPO_ROOT}"
  supabase init
  info "Supabase project initialized → ${SUPABASE_DIR}"
}

# ── Start Supabase ──────────────────────────────────────────────────────────
start_supabase() {
  info "Starting Supabase services..."
  cd "${REPO_ROOT}"
  
  if supabase status >/dev/null 2>&1; then
    info "Supabase is already running."
    return
  fi
  
  info "This may take a few minutes on first run..."
  info "Using --ignore-health-check flag for Colima compatibility..."
  
  # Start with ignore health check to avoid vector/logging issues on Colima
  if ! supabase start --ignore-health-check 2>&1; then
    echo ""
    error "Failed to start Supabase.

KNOWN ISSUE: Supabase CLI has compatibility issues with Colima on macOS.

RECOMMENDED SOLUTION:
  Use Docker Desktop for the most reliable experience:
  1. Install: brew install --cask docker
  2. Start: open -a Docker
  3. Re-run: make setup-dev

ALTERNATIVE: Try Colima with different settings:
  1. colima stop && colima delete
  2. colima start --cpu 4 --memory 8 --disk 100 --vm-type=vz --mount-type=virtiofs
  3. make setup-dev

For debugging: supabase start --debug"
  fi
  
  info "Supabase services started."
  warning "Note: Started with --ignore-health-check due to Colima limitations."
  warning "Analytics/logging (vector) may not be available, but core services should work."
}

# ── Initialize Temporal database directory ──────────────────────────────────
init_temporal() {
  if [ -d "${TEMPORAL_DB_DIR}" ]; then
    info "Temporal database directory already exists – skipping init."
  else
    info "Creating Temporal database directory..."
    mkdir -p "${TEMPORAL_DB_DIR}"
    info "Temporal database directory created → ${TEMPORAL_DB_DIR}"
  fi
}

# ── Summary ──────────────────────────────────────────────────────────────────
print_summary() {
  echo ""
  printf "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
  printf "${GREEN}  Development environment is ready!${RESET}\n"
  printf "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
  echo ""
  printf "${YELLOW}Environment:${RESET}\n"
  printf "  Backend      : Colima (Docker runtime)\n"
  printf "  Status       : $(colima status 2>/dev/null || echo 'unknown')\n"
  echo ""
  printf "${YELLOW}Supabase:${RESET}\n"
  printf "  Studio URL   : http://localhost:54323\n"
  printf "  API URL      : http://localhost:54321\n"
  printf "  DB URL       : postgresql://postgres:postgres@localhost:54322/postgres\n"
  printf "  anon key     : Run 'supabase status' for API keys\n"
  printf "  service_role : Run 'supabase status' for API keys\n"
  printf "  Stop with    : supabase stop\n"
  printf "  Status check : supabase status\n"
  echo ""
  printf "${YELLOW}Temporal:${RESET}\n"
  printf "  To start     : temporal server start-dev --db-filename ${TEMPORAL_DB_DIR}/temporal.db\n"
  printf "  Web UI       : http://localhost:8233 (after starting)\n"
  printf "  gRPC Frontend: localhost:7233 (after starting)\n"
  printf "  Stop with    : Press Ctrl+C in the terminal running Temporal\n"
  echo ""
  printf "${GREEN}Quick commands:${RESET}\n"
  printf "  • View Supabase status : supabase status\n"
  printf "  • View Supabase logs   : supabase logs\n"
  printf "  • Stop Supabase        : supabase stop\n"
  printf "  • Access Supabase Studio: http://localhost:54323\n"
  printf "  • Start Temporal       : temporal server start-dev --db-filename ${TEMPORAL_DB_DIR}/temporal.db\n"
  printf "  • Colima status        : colima status\n"
  printf "  • Stop Colima          : colima stop\n"
  echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  check_prereqs
  setup_colima
  init_supabase
  start_supabase
  init_temporal
  print_summary
}

main "$@"
