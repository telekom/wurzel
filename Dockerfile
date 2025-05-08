# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
#
# https://github.com/github/gitignore/blob/main/Python.gitignore
#
# Byte-compiled / optimized / DLL files
# to reduce the CI pipeline drastical
FROM python:3.11-slim@sha256:974cb5b34070dd2f5358ca1de1257887bec76ba87f6e727091669035e5f3484d AS dependencies
RUN apt update && apt install -y --no-install-recommends build-essential gcc git curl g++
RUN apt install -y --no-install-recommends curl jq

ENV VENV=/usr/app/venv
COPY pyproject.toml .
COPY wurzel wurzel
RUN python -m venv ${VENV}

RUN . ${VENV}/bin/activate
# against CVE-2024-6345 of baseimage
RUN . ${VENV}/bin/activate && pip install setuptools==78.1.0



RUN . ${VENV}/bin/activate &&  pip install uv

RUN . ${VENV}/bin/activate && uv pip install --upgrade pip && \
                               uv pip install ".[all]"
# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1
ENV GIT_USER=wurzel
ENV GIT_MAIL=wurzel@example.com
ENV DVC_DATA_PATH=/usr/app/dvc-data
ENV DVC_FILE=/usr/app/dvc.yaml
RUN groupadd -g 999 python && \
    useradd -r -u 999 -m -g python python
RUN chown python:python /usr/app
WORKDIR /usr/app
USER 999
COPY entrypoint.sh .
COPY examples/pipeline/pipelinedemo.py .
ENV WURZEL_PIPELINE=pipelinedemo:pipeline
ENV PATH="/usr/app/venv/bin:$PATH"
CMD [".", "${VENV}/bin/activate", "&&", "/bin/bash", "./entrypoint.sh"]
