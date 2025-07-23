# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0


FROM ghcr.io/telekom/wurzel:latest

# -------------------------- if your steps are located in other dependencies
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
# --------------------------
COPY pipelinedemo.py .
# addressing the last step
ENV WURZEL_PIPELINE="pipelinedemo:pipeline"
