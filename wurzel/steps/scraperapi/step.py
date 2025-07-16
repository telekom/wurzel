# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""interacts with the scraperAPI service and converts the retrieved Documents to Markdown."""

# Standard library imports
import logging

import lxml
import requests
from joblib import Parallel, delayed
from requests.adapters import HTTPAdapter, Retry
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
    """ScraperAPIStep uses the ScraperAPI service to srape the html by the given url through list[UrlItem].
    this html gets filtered and transformed to MarkdownDataContract.
    """

    def run(self, inpt: list[UrlItem]) -> list[MarkdownDataContract]:
        def fetch_and_process(url_item: UrlItem, recursion_depth=0):
            session = requests.Session()
            retries = Retry(
                total=self.settings.RETRY, backoff_factor=0.1, raise_on_status=False, status_forcelist=[403, 500, 502, 503, 504]
            )
            session.mount("https://", HTTPAdapter(max_retries=retries))
            payload = {
                "api_key": self.settings.TOKEN,
                "url": url_item.url,
                "device_type": self.settings.DEVICE_TYPE,
                "follow_redirect": str(self.settings.FOLLOW_REDIRECT).lower(),
                "wait_for_selector": self.settings.WAIT_FOR_SELECTOR,
                "country_code": self.settings.COUNTRY_CODE,
                "render": str(self.settings.RENDER).lower(),
                "premium": str(self.settings.PREMIUM).lower(),
                "ultra_premium": str(self.settings.ULTRA_PREMIUM).lower(),
                "screenshot": str(self.settings.SCREENSHOT).lower(),
                "max_cost": str(self.settings.MAX_COST),
            }
            try:
                r = None  # for short error handling
                r = session.get(self.settings.API, params=payload, timeout=self.settings.TIMEOUT)
                r.raise_for_status()
            except requests.exceptions.ReadTimeout:
                log.warning(
                    "Crawling failed due to timeout",
                    extra={"url": url_item.url},
                )
                return None
            except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
                log.warning(
                    "Crawling failed",
                    extra={"url": url_item.url, "status": r.status_code if r else None, "retries": self.settings.RETRY},
                )
                return None

            try:
                md = to_markdown(self._filter_body(r.text))
            except (KeyError, IndexError):
                if recursion_depth > self.settings.RETRY:
                    log.warning("xpath retry failed", extra={"filter": self.settings.XPATH, "url": url_item.url})
                    return None
                log.warning(
                    "website does not have the searched xpath, retrying", extra={"filter": self.settings.XPATH, "url": url_item.url}
                )
                return fetch_and_process(url_item, recursion_depth=recursion_depth + 1)

            progress_bar.update(1)
            return MarkdownDataContract(md=md, url=url_item.url, keywords=url_item.title)

        with tqdm(total=len(inpt), desc="Processing URLs") as progress_bar:
            results = Parallel(n_jobs=self.settings.CONCURRENCY_NUM, backend="threading")(delayed(fetch_and_process)(item) for item in inpt)

        filtered_results = [res for res in results if res]
        if not filtered_results:
            raise StepFailed("no results from scraperAPI")

        return filtered_results

    def __init__(self) -> None:
        logging.getLogger("urllib3").setLevel("ERROR")
        super().__init__()

    def finalize(self) -> None:
        logging.getLogger("urllib3").setLevel("WARNING")

        return super().finalize()

    def _filter_body(self, html: str) -> str:
        tree: lxml.html = lxml.html.fromstring(html)
        tree = tree.xpath(self.settings.XPATH)[0]
        return html2str(tree)
