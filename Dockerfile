# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11

# Build stage - includes build tools and compilers
FROM python:${PYTHON_VERSION}-slim AS builder

# Install uv with proper platform targeting
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install build dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' >/etc/apt/apt.conf.d/keep-cache && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        git \
        curl \
        ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set Python environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/tmp/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy

# Set working directory
WORKDIR /app

# Copy dependency files first (for better layer caching)
COPY pyproject.toml ./
COPY DIRECT_REQUIREMENTS.txt ./

# Install Python dependencies
RUN --mount=type=cache,target=/tmp/.cache/uv,id=uv-cache \
    uv sync --no-install-project --extra all

# Install additional requirements
RUN --mount=type=cache,target=/tmp/.cache/uv,id=uv-cache \
    uv pip install -r DIRECT_REQUIREMENTS.txt

# Copy application code
COPY wurzel ./wurzel

# Install the project itself
RUN --mount=type=cache,target=/tmp/.cache/uv,id=uv-cache \
    uv sync --inexact

# Production stage - minimal runtime environment
FROM python:${PYTHON_VERSION}-slim AS production

# Install only runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' >/etc/apt/apt.conf.d/keep-cache && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install jq depending on the platform
RUN case "$(uname -m)" in \
    x86_64) curl -L -o /usr/bin/jq https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64 ;; \
    aarch64) curl -L -o /usr/bin/jq https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-arm64 ;; \
    *) echo "Unsupported architecture"; exit 1 ;; \
    esac && \
    chmod +x /usr/bin/jq

# Create a non-privileged user
ARG UID=10001
RUN groupadd --gid $UID appgroup && \
    useradd --uid $UID --gid appgroup --shell /bin/bash --create-home appuser

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy the virtual environment from builder stage
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv

# Copy application code and entrypoint
COPY --chown=appuser:appgroup wurzel ./wurzel
COPY --chown=appuser:appgroup entrypoint.sh ./
COPY --chown=appuser:appgroup pyproject.toml ./

# Make entrypoint executable
RUN chmod +x ./entrypoint.sh

# Set system-level DVC configuration
RUN /app/.venv/bin/dvc config core.autostage true --system && \
    /app/.venv/bin/dvc config core.analytics false --system

# Switch to non-privileged user
USER appuser

# Set git configuration for the user
RUN git config --global user.name "wurzel" && \
    git config --global user.email "wurzel@example.com" && \
    git config --global init.defaultBranch main


# Environment variables for runtime
ENV DVC_DATA_PATH=/app/dvc-data \
    DVC_FILE=/app/dvc.yaml \
    DVC_CACHE_HISTORY_NUMBER=30 \
    WURZEL_PIPELINE=pipelinedemo:pipeline

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import wurzel" || exit 1

# Use exec form for better signal handling
ENTRYPOINT ["./entrypoint.sh"]
