#!/bin/bash
# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

set -e

# This script is intended to be run inside the container.
# It handles the setup and execution of the pipeline tests.

# Ensure we are root to fix permissions
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root."
    exit 1
fi

echo "Setting up test environment..."

# Change ownership of the workspace to appuser
# GITHUB_WORKSPACE is mounted to the container
if [ -n "$GITHUB_WORKSPACE" ]; then
    chown -R appuser:appgroup "$GITHUB_WORKSPACE"
fi

# Ensure appuser has read/write access to output directory
mkdir -p /usr/app/data
chown -R appuser:appgroup /usr/app/data

# Copy pipeline configuration
echo "Copying pipeline configuration..."
if [ -f "$GITHUB_WORKSPACE/examples/pipeline/pipelinedemo.py" ]; then
    su -c "cp $GITHUB_WORKSPACE/examples/pipeline/pipelinedemo.py /usr/app/" appuser
else
    echo "ERROR: pipelinedemo.py not found at $GITHUB_WORKSPACE/examples/pipeline/pipelinedemo.py"
    exit 1
fi

if [ -d "$GITHUB_WORKSPACE/examples/pipeline/demo-data" ]; then
    su -c "cp -r $GITHUB_WORKSPACE/examples/pipeline/demo-data /usr/app/" appuser
else
    echo "ERROR: demo-data not found at $GITHUB_WORKSPACE/examples/pipeline/demo-data"
    exit 1
fi

# Run pipeline
echo "Running pipeline..."
su -c "cd /usr/app && python pipelinedemo.py" appuser

# Verify pipeline output
echo "Verifying pipeline output..."
if [ -f "$GITHUB_WORKSPACE/.github/scripts/verify-pipeline-output.sh" ]; then
    chmod +x "$GITHUB_WORKSPACE/.github/scripts/verify-pipeline-output.sh"
    "$GITHUB_WORKSPACE/.github/scripts/verify-pipeline-output.sh"
else
    echo "ERROR: verify-pipeline-output.sh not found!"
    exit 1
fi

echo "Test finished successfully."
