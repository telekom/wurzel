#!/bin/bash
# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
# This script is used in GitHub Actions to verify the output of the pipeline in the Docker container.
# It is executed as part of the end-to-end integration test process.
# For more details, see: ../create-docker-img.yml

set -e

echo "Checking if output was created..."
su -c "ls -la /usr/app/data/" appuser

# Check if expected output directories exist
if [ ! -d "/usr/app/data/ManualMarkdownStep" ] || [ ! -d "/usr/app/data/SimpleSplitterStep" ]; then
    echo "ERROR: Expected output directories not found"
    exit 1
fi

# Check for specific expected outputs (search recursively)
MANUAL_JSON=$(find /usr/app/data/ManualMarkdownStep -name "*.json" -type f | head -n 1)
if [ -z "$MANUAL_JSON" ]; then
    echo "WARNING: No JSON files found in ManualMarkdownStep"
else
    echo "✓ Found $(basename $MANUAL_JSON)"
    echo "File size: $(stat -c%s "$MANUAL_JSON") bytes"
fi

SPLITTER_JSON=$(find /usr/app/data/SimpleSplitterStep -name "*.json" -type f | head -n 1)
if [ -z "$SPLITTER_JSON" ]; then
    echo "WARNING: No JSON files found in SimpleSplitterStep"
else
    echo "✓ Found $(basename $SPLITTER_JSON)"
    echo "File size: $(stat -c%s "$SPLITTER_JSON") bytes"
    # Copy one output file for PR comment to the mounted /tmp directory
    # This makes it accessible from the host
    cp "$SPLITTER_JSON" /tmp/sample-output.json
    chmod 644 /tmp/sample-output.json
fi

echo "Pipeline test completed successfully!"
