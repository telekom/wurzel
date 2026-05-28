# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
import re
import sys

import pytest
from loguru import logger

from wurzel.core.logging import log_uncaught_exception, setup_logging, setup_uncaught_exception_logging

LEVELS = pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

# ── Regex constants that encode the frozen log format ───────────────────────
# "May 28, 2026 @ 14:43:29.382107"
_TIMESTAMP_RE = re.compile(r"^[A-Z][a-z]+ \d{1,2}, \d{4} @ \d{2}:\d{2}:\d{2}\.\d{6}$")
# "MainProcess(12345)"
_PROCESS_RE = re.compile(r"^.+\(\d+\)$")
# "MainThread(8526061184)"
_THREAD_RE = re.compile(r"^.+\(\d+\)$")
# "/path/to/file.py:42"
_FILE_RE = re.compile(r"^.+:\d+$")

# Exact set of top-level keys emitted for a plain log line (no extra, no exception, no correlationId)
_BASELINE_KEYS = {"level", "message", "logger_name", "file", "@timestamp", "process", "thread"}


@pytest.fixture(autouse=True)
def reset_loguru():
    """Ensure loguru has a clean handler state for each test."""
    logger.remove()
    yield
    logger.remove()


# ── Frozen-format tests ──────────────────────────────────────────────────────


def _capture_one(capsys) -> dict:
    """Helper: read the last JSON line from stderr and parse it."""
    err = capsys.readouterr().err.strip()
    assert err, "Expected log output on stderr"
    return json.loads(err.splitlines()[-1])


def test_format_baseline_keys(capsys):
    """A plain log line must have exactly the documented top-level keys."""
    setup_logging("DEBUG")
    logger.info("baseline")
    data = _capture_one(capsys)
    assert set(data.keys()) == _BASELINE_KEYS


def test_format_level_value(capsys):
    """``level`` must be the upper-case level name string."""
    setup_logging("DEBUG")
    logger.warning("lvl")
    data = _capture_one(capsys)
    assert data["level"] == "WARNING"
    assert isinstance(data["level"], str)


def test_format_timestamp_pattern(capsys):
    """``@timestamp`` must match 'Month D, YYYY @ HH:mm:ss.microseconds'."""
    setup_logging("DEBUG")
    logger.info("ts")
    data = _capture_one(capsys)
    ts = data["@timestamp"]
    assert _TIMESTAMP_RE.match(ts), f"Unexpected @timestamp format: {ts!r}"


def test_format_process_pattern(capsys):
    """``process`` must match 'Name(pid)'."""
    setup_logging("DEBUG")
    logger.info("proc")
    data = _capture_one(capsys)
    assert _PROCESS_RE.match(data["process"]), f"Unexpected process format: {data['process']!r}"


def test_format_thread_pattern(capsys):
    """``thread`` must match 'Name(id)'."""
    setup_logging("DEBUG")
    logger.info("thr")
    data = _capture_one(capsys)
    assert _THREAD_RE.match(data["thread"]), f"Unexpected thread format: {data['thread']!r}"


def test_format_file_pattern(capsys):
    """``file`` must match 'path:lineno'."""
    setup_logging("DEBUG")
    logger.info("f")
    data = _capture_one(capsys)
    assert _FILE_RE.match(data["file"]), f"Unexpected file format: {data['file']!r}"


def test_format_logger_name_is_string(capsys):
    """``logger_name`` must be a non-empty string."""
    setup_logging("DEBUG")
    logger.info("name")
    data = _capture_one(capsys)
    assert isinstance(data["logger_name"], str)
    assert data["logger_name"]


def test_format_extra_key_present_only_when_bound(capsys):
    """``extra`` must be absent when nothing is bound, present when data is bound."""
    setup_logging("DEBUG")

    logger.info("no extra")
    data_no_extra = _capture_one(capsys)
    assert "extra" not in data_no_extra

    logger.bind(foo="bar").info("with extra")
    data_with_extra = _capture_one(capsys)
    assert "extra" in data_with_extra
    assert set(data_with_extra.keys()) == _BASELINE_KEYS | {"extra"}


def test_format_extra_is_dict(capsys):
    """``extra`` must be a JSON object (dict) in normal mode."""
    setup_logging("DEBUG")
    logger.bind(x=1, y=2).info("extra dict")
    data = _capture_one(capsys)
    assert isinstance(data["extra"], dict)
    assert data["extra"]["x"] == 1
    assert data["extra"]["y"] == 2


def test_format_extra_is_string_in_json_string_mode(capsys):
    """``extra`` must be a JSON *string* (not object) in json_string mode."""
    setup_logging("DEBUG", json_string=True)
    logger.bind(z=42).info("extra str")
    data = _capture_one(capsys)
    assert isinstance(data["extra"], str)
    inner = json.loads(data["extra"])
    assert inner["z"] == 42


def test_format_exception_key_present_on_error(capsys):
    """``exception`` must be present (and contain the message) when an exception is logged."""
    setup_logging("DEBUG")
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logger.exception("caught it")
    data = _capture_one(capsys)
    assert "exception" in data
    assert isinstance(data["exception"], str)
    assert "boom" in data["exception"]
    assert set(data.keys()) == _BASELINE_KEYS | {"exception"}


def test_format_correlation_id_key_present_when_set(capsys):
    """``correlationId`` must appear when asgi_correlation_id is set."""
    from uuid import uuid4

    import asgi_correlation_id

    uid = str(uuid4())
    asgi_correlation_id.correlation_id.set(uid)
    setup_logging("DEBUG")
    logger.info("cor")
    data = _capture_one(capsys)
    assert data.get("correlationId") == uid
    assert set(data.keys()) == _BASELINE_KEYS | {"correlationId"}


def test_format_output_is_valid_json_for_all_levels(capsys):
    """Every log level must produce a line that is valid JSON."""
    setup_logging("DEBUG")
    for lvl in ("debug", "info", "warning", "error", "critical"):
        getattr(logger, lvl)(f"{lvl} message")
    err = capsys.readouterr().err.strip()
    lines = err.splitlines()
    assert len(lines) == 5
    for line in lines:
        json.loads(line)  # must not raise


# ── Functional tests (non-format) ───────────────────────────────────────────


@LEVELS
def test_setup_logging_produces_json(capsys, level):
    setup_logging("DEBUG")
    getattr(logger, level.lower())("hello from test")
    data = _capture_one(capsys)
    assert data["message"] == "hello from test"
    assert data["level"] == level


def test_setup_logging_json_string_mode(capsys):
    setup_logging("DEBUG", json_string=True)
    logger.bind(structured={"key": "val"}).info("json string test")
    data = _capture_one(capsys)
    assert data["message"] == "json string test"
    assert isinstance(data.get("extra"), str)


def test_setup_logging_extra_data(capsys):
    setup_logging("DEBUG")
    logger.bind(a=1, b="hello").info("extra test")
    data = _capture_one(capsys)
    assert data["extra"]["a"] == 1
    assert data["extra"]["b"] == "hello"


def test_setup_logging_cor_id(capsys):
    from uuid import uuid4

    import asgi_correlation_id

    uuid = uuid4()
    asgi_correlation_id.correlation_id.set(str(uuid))
    setup_logging("DEBUG")
    logger.info("cor id test")
    data = _capture_one(capsys)
    assert data.get("correlationId") == str(uuid)


def test_setup_uncaught_exception_logging(capsys):
    original_hook = sys.excepthook
    try:
        setup_uncaught_exception_logging()
        assert sys.excepthook == log_uncaught_exception
    finally:
        sys.excepthook = original_hook


def test_log_uncaught_exception(capsys):
    setup_logging("DEBUG")
    exc_type = exc_value = exc_traceback = None
    try:
        raise ValueError("Test exception")
    except ValueError:
        exc_type, exc_value, exc_traceback = sys.exc_info()

    assert exc_type is not None
    log_uncaught_exception(exc_type, exc_value, exc_traceback)
    data = _capture_one(capsys)
    assert "Uncaught exception" in data["message"]
    assert "Test exception" in data.get("exception", "")


def test_uncaught_exception_causes_exit_code_1(tmp_path):
    """Test that uncaught exceptions in steps cause proper logging and exit behavior."""
    from wurzel.exceptions import StepFailed
    from wurzel.executors import BaseStepExecutor

    step_file = tmp_path / "exception_step.py"
    step_file.write_text("""
from wurzel.core import TypedStep, NoSettings
from wurzel.datacontract import PydanticModel

class TestInput(PydanticModel):
    value: str

class TestOutput(PydanticModel):
    result: str

class FailingStep(TypedStep[NoSettings, TestInput, TestOutput]):
    def run(self, input_data: TestInput) -> TestOutput:
        raise RuntimeError("This step always fails!")
""")

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "data.json").write_text('{"value": "test"}')

    sys.path.insert(0, str(tmp_path))
    try:
        from exception_step import FailingStep

        executor = BaseStepExecutor()

        with pytest.raises(StepFailed) as exc_info:
            with executor:
                executor(FailingStep, {input_dir}, tmp_path / "output")

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert "This step always fails!" in str(exc_info.value.__cause__)
    finally:
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))
