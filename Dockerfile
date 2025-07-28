# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0

ARG PYTHON_VERSION=3.11


FROM python:${PYTHON_VERSION}-slim AS builder


LABEL org.opencontainers.image.title="wurzel"
LABEL org.opencontainers.image.description="ETL framework for Retrieval-Augmented Generation (RAG) systems"
LABEL org.opencontainers.image.vendor="Deutsche Telekom AG"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.source="https://github.com/telekom/wurzel"


COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' >/etc/apt/apt.conf.d/keep-cache && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential=12.9 \
        gcc=4:12.2.0-3 \
        g++=4:12.2.0-3 \
        git=1:2.39.5-0+deb12u2 \
        curl=7.88.1-10+deb12u12 \
        ca-certificates=20230311+deb12u1


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/tmp/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy


WORKDIR /app


COPY pyproject.toml DIRECT_REQUIREMENTS.txt ./
RUN --mount=type=cache,target=/tmp/.cache/uv,id=uv-cache \
    uv sync --no-install-project --extra all && \
    uv pip install -r DIRECT_REQUIREMENTS.txt


COPY wurzel ./wurzel
RUN --mount=type=cache,target=/tmp/.cache/uv,id=uv-cache \
    uv sync --inexact

FROM python:${PYTHON_VERSION}-slim AS production


ARG UID=10001
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' >/etc/apt/apt.conf.d/keep-cache && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        git=1:2.39.5-0+deb12u2 \
        curl=7.88.1-10+deb12u12 \
        ca-certificates=20230311+deb12u1 && \
    case "$(uname -m)" in \
        x86_64) curl -L -o /usr/bin/jq https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64 ;; \
        aarch64) curl -L -o /usr/bin/jq https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-arm64 ;; \
        *) echo "Unsupported architecture"; exit 1 ;; \
    esac && \
    chmod +x /usr/bin/jq && \
    apt-get purge -y curl && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --gid $UID appgroup && \
    useradd --uid $UID --gid appgroup --shell /bin/bash --create-home appuser


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"


WORKDIR /app
RUN chown appuser:appgroup /app


COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv


COPY --chown=appuser:appgroup wurzel ./wurzel
COPY --chown=appuser:appgroup entrypoint.sh ./
COPY --chown=appuser:appgroup pyproject.toml ./


RUN /app/.venv/bin/dvc config core.autostage true --system && \
    /app/.venv/bin/dvc config core.analytics false --system && \
    chmod +x ./entrypoint.sh


USER appuser


RUN git config --global user.name "wurzel" && \
    git config --global user.email "wurzel@example.com" && \
    git config --global init.defaultBranch main



ENV DVC_DATA_PATH=/app/dvc-data \
    DVC_FILE=/app/dvc.yaml \
    DVC_CACHE_HISTORY_NUMBER=30 \
    WURZEL_PIPELINE=pipelinedemo:pipeline


HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import wurzel" || exit 1


ENTRYPOINT ["./entrypoint.sh"]
