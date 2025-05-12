# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""consists of DVCSteps to embedd files and save them as for example as csv."""

# Standard library imports
from logging import getLogger

import pandas as pd

from wurzel.datacontract import MarkdownDataContract
from wurzel.step import Settings, TypedStep

# Local application/library specific imports


log = getLogger(__name__)


class DropStettings(Settings):
    """specify DROP_BY_FIELDS to field."""

    DROP_BY_FIELDS: list[str] = ["md"]


class DropDuplicationStep(TypedStep[DropStettings, list[MarkdownDataContract], list[MarkdownDataContract]]):
    """SimpleSplitterStep to split Markdown Documents rundimentory in medium size chunks."""

    def run(self, inpt: list[MarkdownDataContract]) -> list[MarkdownDataContract]:
        """Executes the split step by processing input markdown files, generating smaller splitted markdown files,
        by preserving the headline.
        """
        if self.settings.DROP_BY_FIELDS == ["*"]:
            self.settings.DROP_BY_FIELDS = None
        df = pd.DataFrame(i.model_dump() for i in inpt)
        if not df.duplicated(self.settings.DROP_BY_FIELDS).any():
            return inpt

        filtered = df.drop_duplicates(self.settings.DROP_BY_FIELDS)
        log.warning(
            "Removed duplicates",
            extra={
                "percentage": len(filtered) / len(df),
                "before": len(df),
                "after": len(filtered),
                "by": str(self.settings.DROP_BY_FIELDS),
            },
        )
        dumped = filtered.to_dict(orient="records")
        return [MarkdownDataContract.model_construct(**f) for f in dumped]
