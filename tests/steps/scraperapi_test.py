# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wurzel.utils import HAS_JOBLIB, HAS_REQUESTS

if not HAS_REQUESTS:
    pytest.skip("Requests is not available", allow_module_level=True)

if not HAS_JOBLIB:
    pytest.skip("Joblib is not available", allow_module_level=True)

import requests
import requests_mock

from wurzel.step_executor.base_executor import BaseStepExecutor
from wurzel.steps.scraperapi.step import ScraperAPIStep, UrlItem


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


def test_scraper_api_errors(tmp_path: Path, env, url_items):
    env.set("SCRAPERAPISTEP__TOKEN", "dummy token")
    output = tmp_path / f"{ScraperAPIStep.__name__}"
    os.mkdir(tmp_path / "input")
    shutil.copy("tests/data/markdown.json", tmp_path / "input/")
    output.mkdir(parents=True, exist_ok=True)
    side_effects = []
    for _url, path in url_items:
        successful_response = MagicMock()
        successful_response.status_code = 200
        successful_response.text = open(path, encoding="utf8").read()
        side_effects.append(successful_response)

    side_effects += [requests.exceptions.HTTPError, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError]

    with patch("requests.Session.get", side_effect=side_effects):
        with BaseStepExecutor() as ex:
            ex(ScraperAPIStep, [[url for url, _path in url_items + url_items]], output)
