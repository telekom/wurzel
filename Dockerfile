# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS base

# Install uv with proper platform targeting
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install system dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' >/etc/apt/apt.conf.d/keep-cache && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
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
    UV_CACHE_DIR=/tmp/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files first (for better layer caching)
COPY --chown=appuser:appgroup pyproject.toml ./
COPY --chown=appuser:appgroup DIRECT_REQUIREMENTS.txt ./

# Install Python dependencies as root (for cache access)
RUN --mount=type=cache,target=/tmp/.cache/uv,id=uv-cache \
    uv sync --no-install-project --extra all

# Install additional requirements
RUN --mount=type=cache,target=/tmp/.cache/uv,id=uv-cache \
    uv pip install -r DIRECT_REQUIREMENTS.txt

# Copy application code
COPY --chown=appuser:appgroup wurzel ./wurzel
COPY --chown=appuser:appgroup entrypoint.sh ./

# Make entrypoint executable
RUN chmod +x ./entrypoint.sh

# Install the project itself
RUN --mount=type=cache,target=/tmp/.cache/uv,id=uv-cache \
    uv sync --inexact

# Set system-level DVC configuration
RUN /app/.venv/bin/dvc config core.autostage true --system && \
    /app/.venv/bin/dvc config core.analytics false --system

# Switch to non-privileged user
USER appuser

# Set git configuration for the user
RUN git config --global user.name "wurzel" && \
    git config --global user.email "wurzel@example.com" && \
    git config --global init.defaultBranch main

# Verify installation
RUN python -c "import wurzel; print('Wurzel installed successfully')"

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
