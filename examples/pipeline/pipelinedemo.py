# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: Apache-2.0
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.steps.splitter import SimpleSplitterStep
from wurzel.utils import WZ

source = WZ(ManualMarkdownStep)
splitter = WZ(SimpleSplitterStep)

source >> splitter

pipeline = splitter
