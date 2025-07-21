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


WORKDIR /app

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/go/dockerfile-user-best-practices/
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser



# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-install-project



# Copy the source code into the container.
COPY wurzel wurzel
COPY DIRECT_REQUIREMENTS.txt DIRECT_REQUIREMENTS.txt
COPY pyproject.toml pyproject.toml
COPY entrypoint.sh entrypoint.sh

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --inexact && \
    uv pip install -r DIRECT_REQUIREMENTS.txt




# Switch to the non-privileged user to run the application.
USER appuser

ENV GIT_USER=wurzel
ENV GIT_MAIL=wurzel@example.com
ENV DVC_DATA_PATH=/app/dvc-data
ENV DVC_FILE=/app/dvc.yaml


# Run the application.
ARG WURZEL_PIPELINE=pipelinedemo:pipeline
CMD ["sh", "-c", "/bin/bash ./entrypoint.sh"]
