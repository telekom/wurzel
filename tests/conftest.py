# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import os
from logging import getLogger
from pathlib import Path

import pytest
from prometheus_client import REGISTRY
from pydantic import BaseModel

log = getLogger(__name__)


class SetEnv:
    def __init__(self):
        self.envars = set()

    def set(self, name, value):
        self.envars.add(name)
        os.environ[name] = value

    def pop(self, name):
        self.envars.remove(name)
        os.environ.pop(name)

    def clear(self):
        for n in self.envars:
            os.environ.pop(n)

    def get(self, name):
        os.environ.get(name, None)

    def update(self, dic: dict):
        for k, v in dic.items():
            self.set(k, v)

    def set_from_settings(self, s: BaseModel):
        dump = s.model_dump(mode="json")
        for k, v in dump.items():
            self.set(k, v)


@pytest.fixture
def env():
    setenv = SetEnv()
    yield setenv

    setenv.clear()


@pytest.fixture(scope="module")
def milvus(env: SetEnv):
    env.set("MILVUS_HOST", "")
    env.set("MILVUS_PASSWORD", "")


@pytest.fixture(scope="function")
def input_output_folder(tmp_path: Path) -> tuple[Path, Path]:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    input_path.mkdir()
    output_path.mkdir()
    return input_path, output_path


@pytest.fixture(scope="session")
def html2md_bin():
    def _get_fallback():
        import platform

        default_path = {"x86_64": "./html2md", "arm64": "./html2md_arm"}
        fallback = default_path.get(platform.uname().machine, None)
        if fallback is None:
            log.error(f"Could not create path to binary from {platform.uname()}")
            pytest.fail("No binary path as fallback")
        return fallback

    path = os.getenv("HTML2MD_BINARY_PATH", None)
    if path is None:
        log.warning("HTML2MD_BINARY_PATH not set, trying to coerce default")
        path = _get_fallback()
    log.info(f"ENV: {os.getenv('HTML2MD_BINARY_PATH','')=}")
    os.environ["HTML2MD_BINARY_PATH"] = path
    yield Path(path)


def pytest_addoption(parser):
    parser.addoption(
        "--repeatability",
        action="store_true",
        default=False,
        help="run repetition tests",
    )


def pytest_collection_modifyitems(config, items):
    do_rep_tests = config.getoption("--repeatability")
    # Explicitly run test if only one is selected :)
    if len(items) == 1:
        return
    for item in items:
        has_repeatability_marker = pytest.mark.repeatability_test.mark in list(item.own_markers)
        if do_rep_tests and not has_repeatability_marker:
            item.add_marker(pytest.mark.skip(reason="need --repeatability option to run"))
            continue
        if not do_rep_tests and has_repeatability_marker:
            item.add_marker(pytest.mark.skip(reason="only running --repeatability tests"))


@pytest.fixture(scope="function", autouse=True)
def reset_prometheus_singleton():
    """Reset PrometheusStepExecutor singleton between tests to prevent registry conflicts.

    This fixture ensures proper test isolation for the deprecated PrometheusStepExecutor.
    Without this cleanup, tests running with coverage or in certain orders can fail with:
    - "Duplicated timeseries in CollectorRegistry" errors
    - "'PrometheusStepExecutor' object has no attribute 'counter_started'" errors

    The issue occurs because pytest-cov or test collection can reset the singleton instance
    but leave metrics registered in the global Prometheus REGISTRY, causing conflicts.
    """
    yield

    # Clean up after each test
    try:
        from wurzel.executors import PrometheusStepExecutor

        # Reset singleton instance
        PrometheusStepExecutor._instance = None
        PrometheusStepExecutor._metrics_initialized = False

        # Unregister prometheus metrics if they exist
        # pylint: disable=protected-access
        collectors_to_remove = []
        for collector in list(REGISTRY._collector_to_names.keys()):
            if hasattr(collector, "_name"):
                name = getattr(collector, "_name", "")
                if name in [
                    "steps_started",
                    "steps_failed",
                    "step_results",
                    "step_inputs",
                    "step_hist_save",
                    "step_hist_load",
                    "step_hist_execute",
                ]:
                    collectors_to_remove.append(collector)

        for collector in collectors_to_remove:
            try:
                REGISTRY.unregister(collector)
            except Exception:  # pylint: disable=broad-exception-caught
                # Collector might not be registered, that's fine
                pass
    except ImportError:
        # PrometheusStepExecutor not available, skip cleanup
        pass
