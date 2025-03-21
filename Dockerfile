# to reduce the CI pipeline drastical
FROM python:3.11-slim@sha256:6459da0f052d819e59b5329bb8f76b2f2bd16427ce6fd4db91e11b3759850380 AS apt
RUN apt update && apt install -y --no-install-recommends build-essential gcc git curl
RUN apt install -y --no-install-recommends curl jq

FROM apt AS dependencies
ENV VENV=/usr/app/venv
COPY pyproject.toml .
RUN python -m venv ${VENV}
COPY wurzel .
RUN . ${VENV}/bin/activate && \
    pip install uv && \
    uv pip install wurzel


FROM dependencies
RUN groupadd -g 999 python && \
    useradd -r -u 999 -m -g python python
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
