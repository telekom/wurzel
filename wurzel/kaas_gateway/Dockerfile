# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

# Build from repository root:
#   docker build -f wurzel/kaas_gateway/Dockerfile -t wurzel-kaas-gateway .

FROM python:3.12-slim AS runtime
WORKDIR /src

COPY pyproject.toml VERSION README.md LICENSES ./
COPY wurzel ./wurzel

RUN pip install --no-cache-dir ".[kaas-gateway]"

ENV KAAS_GATEWAY_HOST=0.0.0.0
EXPOSE 8010

CMD ["wurzel-kaas-gateway"]
