# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""interacts with the scraperAPI service and converts the retrieved Documents to Markdown."""

# Standard library imports
from pydantic import Field

from wurzel.step.settings import Settings

# Local application/library specific imports


class ScraperAPISettings(Settings):
    """Settings of ScraperAPIStep. Mainly the list of https://docs.scraperapi.com/python/credits-and-requests."""

    API: str = "https://api.scraperapi.com/"
    RETRY: int = Field(ge=0, default=5)
    TOKEN: str
    TIMEOUT: int = 61.0
    XPATH: str = "//main"
    CONCURRENCY_NUM: int = Field(gt=0, default=1)
    DEVICE_TYPE: str = "desktop"
    FOLLOW_REDIRECT: bool = True
    WAIT_FOR_SELECTOR: str = "#cookies-notification-accept-cookie"
    COUNTRY_CODE: str = "en"
    RENDER: bool = True
    PREMIUM: bool = False
    ULTRA_PREMIUM: bool = False
    SCREENSHOT: bool = False
    MAX_COST: int = Field(gt=0, default=30)
