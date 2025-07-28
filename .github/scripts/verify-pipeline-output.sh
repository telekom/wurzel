#!/bin/bash
# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

set -e

echo "Checking if output was created..."
su -c "ls -la /app/data/" appuser

# Check if expected output directories exist
if [ ! -d "/app/data/ManualMarkdownStep" ] || [ ! -d "/app/data/SimpleSplitterStep" ]; then
    echo "ERROR: Expected output directories not found"
    exit 1
fi

# Check for specific expected outputs
if [ ! -f "/app/data/ManualMarkdownStep/ManualMarkdown.json" ]; then
    echo "WARNING: ManualMarkdown.json not found"
else
    echo "✓ Found ManualMarkdown.json"
    echo "File size: $(stat -c%s '/app/data/ManualMarkdownStep/ManualMarkdown.json') bytes"
fi

if [ ! -f "/app/data/SimpleSplitterStep/SimpleSplitter.json" ]; then
    echo "WARNING: SimpleSplitter.json not found"
else
    echo "✓ Found SimpleSplitter.json"
    echo "File size: $(stat -c%s '/app/data/SimpleSplitterStep/SimpleSplitter.json') bytes"
fi

echo "Pipeline test completed successfully!"
