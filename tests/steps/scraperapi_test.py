# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
from pathlib import Path

import pytest
import requests_mock

from wurzel.step_executor.base_executor import BaseStepExecutor
from wurzel.steps.scraperapi.step import ScraperAPIStep, UrlItem
from tests import env

@pytest.fixture(scope="function")
def mock_scraper_api(requests_mock: requests_mock.Mocker, url_items, env):
    env.set("SCRAPERAPISTEP__TOKEN", "dummy token")
    requests_mock.get(
        "https://api.scraperapi.com/",
        response_list=[{"text": open(path, encoding="utf8").read()} for _url, path in url_items],
    )


@pytest.fixture(scope="module")
def url_items() -> list[tuple[UrlItem, str]]:
    return [
        (
            UrlItem(url="https://de.wikipedia.org/wiki/Wurzel_(Pflanze)", title="Wurzel"),
            Path("tests/data/scraperapi/wikipedia_wurzel.html"),
        ),
        (
            UrlItem(url="https://en.wikipedia.org/wiki/Root", title="Wurzel"),
            Path("tests/data/scraperapi/wikipedia_root.html"),
        ),
        (
            UrlItem(url="https://creativecommons.org/licenses/by-sa/4.0/deed.de", title="Wurzel"),
            Path("tests/data/scraperapi/CCO_deed.html"),
        ),
    ]


def test_scraper_api(tmp_path: Path, mock_scraper_api, url_items):
    output = tmp_path / f"{ScraperAPIStep.__name__}"
    os.mkdir(tmp_path / "input")
    shutil.copy("tests/data/markdown.json", tmp_path / "input/")
    output.mkdir(parents=True, exist_ok=True)
    with BaseStepExecutor() as ex:
        result = ex(ScraperAPIStep, [[url for url, _path in url_items]], output)

    assert list(output.iterdir())
    assert len(result[0][0]) == 3
