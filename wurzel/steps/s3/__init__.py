# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.utils import HAS_BOTO3 as _HAS_BOTO3

if _HAS_BOTO3:
    from .settings import S3MarkdownStepSettings
    from .step import S3MarkdownStep

    __all__ = [
        "S3MarkdownStep",
        "S3MarkdownStepSettings",
    ]
else:
    __all__ = []
