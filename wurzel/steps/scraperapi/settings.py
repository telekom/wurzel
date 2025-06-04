# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""interacts with the scraperAPI service and converts the retrieved Documents to Markdown."""

# Standard library imports
from wurzel.step.settings import Settings

# Local application/library specific imports


class ScraperAPISettings(Settings):
    """Settings of ScraperAPIStep."""

    API: str = "https://api.scraperapi.com/"
    TOKEN: str = ""
    TIMEOUT: int = 30.0
    XPATH: str = "//main"
    CONCURRENCY_NUM: int = 1
