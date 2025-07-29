# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


from wurzel.step_executor import BaseStepExecutor
from wurzel.steps.dedupe_hash.step import QdrantCompareStep

with BaseStepExecutor() as ex:
    ex(QdrantCompareStep, [], None)
