# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""interacts with the scraperAPI service and converts the retrieved Documents to Markdown."""

# Standard library imports
from typing import Optional

from wurzel.datacontract.datacontract import PydanticModel

# Local application/library specific imports


class UrlItem(PydanticModel):
    """Item from webmaster api."""

    url: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
