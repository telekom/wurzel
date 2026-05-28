# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import sys
import traceback
from typing import Any

from asgi_correlation_id import correlation_id
from loguru import logger


def _make_dict_serializable(item: Any):
    match item:
        case dict():
            new_dict = {}
            for k, v in item.items():
                # If value is None remove item
                if v is None:
                    continue

                key = k if isinstance(k, str) else repr(k)
                new_dict[key] = _make_dict_serializable(v)
            return new_dict
        case str() | int() | float() | bool():
            return item
        case list():
            return [_make_dict_serializable(i) for i in item]
        case set():
            # Convert set to list for JSON serialization
            return [_make_dict_serializable(i) for i in item]
        case _:
            return repr(item)


def _build_json_record(record: dict, *, serialize_extra_as_string: bool = False) -> dict[str, Any]:
    """Build a JSON-serializable dict from a loguru record dict."""
    module = record["name"]
    function = record["function"]
    logger_name = f"{module}.{function}" if function and function != "<module>" else module

    t = record["time"]
    timestamp = f"{t.strftime('%B')} {t.day}, {t.year} @ {t.strftime('%H:%M:%S')}.{t.microsecond:06d}"

    output: dict[str, Any] = {
        "level": record["level"].name,
        "message": record["message"],
        "logger_name": logger_name,
        "file": f"{record['file'].path}:{record['line']}",
        "@timestamp": timestamp,
        "process": f"{record['process'].name}({record['process'].id})",
        "thread": f"{record['thread'].name}({record['thread'].id})",
    }

    exc = record.get("exception")
    if exc is not None and exc.type is not None:
        output["exception"] = "".join(traceback.format_exception(exc.type, exc.value, exc.traceback))

    cor_id = correlation_id.get()
    if cor_id is not None:
        output["correlationId"] = cor_id

    extra = dict(record.get("extra", {}))
    if extra:
        serialized = _make_dict_serializable(extra)
        output["extra"] = json.dumps(serialized) if serialize_extra_as_string else serialized

    return output


def _json_sink(message) -> None:
    """Custom loguru sink: writes a JSON line to stderr."""
    output = _build_json_record(message.record)
    sys.stderr.write(json.dumps(output, default=repr) + "\n")


def _json_string_sink(message) -> None:
    """Like _json_sink but serializes the extra dict as a JSON string."""
    output = _build_json_record(message.record, serialize_extra_as_string=True)
    sys.stderr.write(json.dumps(output, default=repr) + "\n")


class InterceptHandler(logging.Handler):
    """Bridge stdlib logging records to loguru.

    Install on the stdlib root logger so that third-party libraries
    (uvicorn, gunicorn, urllib3, …) are routed through loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(level: int | str = "INFO", *, json_string: bool = False) -> None:
    """Configure loguru as the application logging backend.

    Removes all existing loguru handlers and adds a JSON sink to stderr.
    Installs :class:`InterceptHandler` on the stdlib root logger so that
    third-party libraries are automatically routed through loguru.

    Args:
        level: Minimum log level (name or numeric value).
        json_string: When True, the ``extra`` dict is serialised as a JSON
            string instead of a nested object (useful for log shippers that
            expect a flat structure).

    """
    logger.remove()
    sink = _json_string_sink if json_string else _json_sink
    logger.add(sink, level=level, format="{message}", colorize=False)

    # Route all stdlib logging to loguru (uvicorn, gunicorn, third-party libs)
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(0)
    for name in list(logging.root.manager.loggerDict):  # pylint: disable=no-member
        existing = logging.getLogger(name)
        existing.handlers = []
        existing.propagate = True


def log_uncaught_exception(exc_type: type[BaseException], exc_value: BaseException, exc_traceback) -> None:
    """Log uncaught exceptions via loguru."""
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).error("Uncaught exception")


def setup_uncaught_exception_logging() -> None:
    """Set up logging for uncaught exceptions."""
    sys.excepthook = log_uncaught_exception


def warnings_to_logger(message: str, category: str, filename: str, lineno: str, *, file=None, line=None):
    """Route :mod:`warnings` output to loguru.

    Replaces the default ``warnings.showwarning`` function.

        message (str): The warning message.
        category (str): The warning category (e.g. ``UserWarning``).
        filename (str): File where the warning was triggered.
        lineno (str): Line number where the warning was triggered.
        file: Not used. Included for compatibility with ``warnings.showwarning``.
        line: Not used. Included for compatibility with ``warnings.showwarning``.

    """
    # pylint: disable=unused-argument
    abs_filename = os.path.abspath(filename)
    for _, mod in sys.modules.items():
        module_path = getattr(mod, "__file__", None)
        if module_path and os.path.abspath(module_path) == abs_filename:
            break
    logger.bind(**{"warnings.category": category, "warnings.filename": filename, "warnings.lineno": lineno}).warning("{}", message)
