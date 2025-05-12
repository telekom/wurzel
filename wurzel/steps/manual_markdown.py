# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from wurzel.datacontract import MarkdownDataContract
from wurzel.step import Settings, TypedStep


class ManualMarkdownSettings(Settings):
    """Settings fro ManMdstep."""

    FOLDER_PATH: Path


class ManualMarkdownStep(TypedStep[ManualMarkdownSettings, None, list[MarkdownDataContract]]):
    """Data Source for md files from a configurable path."""

    def run(self, inpt: None) -> list[MarkdownDataContract]:
        return [
            MarkdownDataContract.from_file(fp, url_prefix=self.__class__.__name__ + "/") for fp in self.settings.FOLDER_PATH.rglob("*.md")
        ]
