# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""interacts with the scraperAPI service and converts the retrieved Documents to Markdown."""

# Standard library imports
import logging

import lxml
import requests
from tqdm import tqdm

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import StepFailed
from wurzel.step.typed_step import TypedStep
from wurzel.steps.scraperapi.data import UrlItem
from wurzel.steps.scraperapi.settings import ScraperAPISettings
from wurzel.utils.to_markdown.html2md import html2str, to_markdown

# Local application/library specific imports

log = logging.getLogger(__name__)


class ScraperAPIStep(TypedStep[ScraperAPISettings, list[UrlItem], list[MarkdownDataContract]]):
    """Data Source for md files from a configurable path."""

    def run(self, inpt: list[UrlItem]) -> list[MarkdownDataContract]:
        result = []
        for url_item in tqdm(inpt):
            log.debug("scraping")
            payload = {
                "api_key": self.settings.TOKEN,
                "url": url_item.url,
                "render": "true",
                "device_type": "desktop",
            }
            try:
                r = requests.get(self.settings.API, params=payload, timeout=self.settings.TIMEOUT)
                r.raise_for_status()
            except requests.exceptions.ReadTimeout:
                log.warning(
                    "Crawling failed due to timeout",
                    extra={"url": url_item.url},
                )
                continue
            except requests.exceptions.HTTPError:
                log.warning(
                    "Crawling failed",
                    extra={
                        "url": url_item.url,
                        "error": r.text,
                        "status": r.status_code,
                    },
                )
                continue

            md = to_markdown(self._filter_body(r.text))
            keywords = url_item.title
            result.append(MarkdownDataContract(md=md, url=url_item.url, keywords=keywords))
        if not result:
            raise StepFailed("no results from scraperAPI")
        return result

    def _filter_body(self, html: str) -> str:
        tree: lxml.html = lxml.html.fromstring(html)
        tree = tree.xpath(self.settings.XPATH)[0]
        return html2str(tree)
