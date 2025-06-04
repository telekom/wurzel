# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
# to reduce the CI pipeline drastical
FROM ghcr.io/telekom/wurzel:latest

# -------------------------- if your steps are located in other dependencies
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
# --------------------------
COPY pipelinedemo.py .
# adressing the last step
ENV WURZEL_PIPELINE=".pipeline:pipeline"
