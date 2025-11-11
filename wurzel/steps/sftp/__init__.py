# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.utils import HAS_PARAMIKO as _HAS_PARAMIKO

if _HAS_PARAMIKO:
    from .sftp_manual_markdown import SFTPManualMarkdownSettings, SFTPManualMarkdownStep

    __all__ = [
        "SFTPManualMarkdownStep",
        "SFTPManualMarkdownSettings",
    ]
else:
    __all__ = []
