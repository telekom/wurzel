# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
#
# https://github.com/github/gitignore/blob/main/Python.gitignore
#
# Byte-compiled / optimized / DLL files
# to reduce the CI pipeline drastical
FROM python:3.11-slim@sha256:7029b00486ac40bed03e36775b864d3f3d39dcbdf19cd45e6a52d541e6c178f0 AS apt
RUN apt update && apt install -y --no-install-recommends build-essential gcc git curl g++
RUN apt install -y --no-install-recommends curl jq

FROM apt AS dependencies
ENV VENV=/usr/app/venv
COPY pyproject.toml .
RUN python -m venv ${VENV}
COPY wurzel .
RUN . ${VENV}/bin/activate && \
    pip install uv && \
    pip install .


FROM dependencies

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1


RUN groupadd -g 999 python && \
    useradd -r -u 999 -m -g --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \python python
ENV GIT_USER=wurzel
ENV GIT_MAIL=wurzel@example.com
ENV WURZEL_PIPELINE=pipeline:pipeline
ENV DVC_DATA_PATH=/usr/app/dvc-data
ENV DVC_FILE=/usr/app/dvc.yml
RUN chown python:python /usr/app
WORKDIR /usr/app

COPY --chown=python:python --from=dependencies /usr/bin/git /usr/bin/git
COPY --chown=python:python --from=dependencies /usr/app/venv ./venv

COPY entrypoint.sh .
USER 999
ENV PATH="/usr/app/venv/bin:$PATH"
CMD . ${VENV}/bin/activate && ./entrypoint.sh
