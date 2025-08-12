# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: Apache-2.0
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.steps.splitter import SimpleSplitterStep

# Create pipeline using direct class chaining
pipeline = ManualMarkdownStep >> SimpleSplitterStep
