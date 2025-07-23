# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0



# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


RUN apt update && apt install -y --no-install-recommends build-essential gcc git curl g++

RUN curl -L -o /usr/bin/jq https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64 \
    && chmod +x /usr/bin/jq


# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

ENV UV_CACHE_DIR=/tmp/.cache/uv
ENV UV_PROJECT_ENVIRONMENT=/usr/app/.venv
ENV UV_LINK_MODE=copy

WORKDIR /usr/app

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/go/dockerfile-user-best-practices/
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --shell "/sbin/nologin" \
    --uid "${UID}" \
    appuser



# Install dependencies including optional ones
RUN --mount=type=cache,target=/tmp/.cache/uv,id=uv-cache \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-install-project --extra all



# Copy the source code into the container.
COPY wurzel wurzel
COPY DIRECT_REQUIREMENTS.txt DIRECT_REQUIREMENTS.txt
COPY pyproject.toml pyproject.toml
COPY entrypoint.sh entrypoint.sh



RUN chown -R appuser:appuser /usr/app && \
    chmod +x /usr/app/entrypoint.sh

# Sync the project (still as root to avoid permission issues with cache)
RUN --mount=type=cache,target=/tmp/.cache/uv,id=uv-cache \
    uv sync --inexact && \
    uv pip install -r DIRECT_REQUIREMENTS.txt && \
    chown -R appuser:appuser /usr/app/.venv

# Set system-level DVC configuration while running as root
RUN /usr/app/.venv/bin/dvc config core.autostage true --system && \
    /usr/app/.venv/bin/dvc config core.analytics false --system

# Switch to the non-privileged user to run the application.
USER appuser

# Activate the virtual environment for the appuser
ENV PATH="/usr/app/.venv/bin:$PATH"

# Verify installation
RUN python -c "import wurzel; print('Wurzel installed successfully')"

RUN git config --global init.defaultBranch main
#RUN dvc config core.analytics false


ENV GIT_USER=wurzel
ENV GIT_MAIL=wurzel@example.com
ENV DVC_DATA_PATH=/usr/app/dvc-data
ENV DVC_FILE=/usr/app/dvc.yaml
ENV DVC_CACHE_HISTORY_NUMBER=30



# Run the application.
ENV WURZEL_PIPELINE=pipelinedemo:pipeline
CMD ["sh", "-c", "/bin/bash ./entrypoint.sh"]
