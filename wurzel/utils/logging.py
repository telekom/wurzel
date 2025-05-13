# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import logging.config
import os
import sys
from collections.abc import Mapping
from typing import Any, Optional

from asgi_correlation_id import correlation_id

log = logging.getLogger(__name__)


# pylint: disable-next=too-many-positional-arguments
def warnings_to_logger(message: str, category: str, filename: str, lineno: str, file=None, line=None):
    """Replaces the default `warnings.showwarning` function to log warnings using the Python logging framework.

    This function captures warning messages and logs them to a logger associated with the module where the warning originated.
    If the module cannot be determined, it uses the filename as the logger name.

        message (str): The warning message to be logged.
        category (str): The category of the warning (e.g., `UserWarning`, `DeprecationWarning`).
        filename (str): The name of the file where the warning was triggered.
        lineno (str): The line number in the file where the warning was triggered.
        file (Optional[IO], optional): Not used. Included for compatibility with `warnings.showwarning`. Defaults to None.
        line (Optional[str], optional): Not used. Included for compatibility with `warnings.showwarning`. Defaults to None.

    """
    # pylint: disable=unused-argument
    for module_name, module in sys.modules.items():
        module_path = getattr(module, "__file__", None)
        if module_path and os.path.abspath(module_path) == os.path.abspath(filename):
            break
    else:
        module_name = os.path.splitext(os.path.split(filename)[1])[0]
    logger = logging.getLogger(module_name)
    extra = {
        "warnings.category": category,
        "warnings.filename": filename,
        "warnings.lineno": lineno,
    }
    logger.warning(message, extra=extra)


def _make_dict_serializable(item: Any):
    secret_words = ["password", "key", "secret"]
    match item:
        case dict():
            new_dict = {}
            for k, v in item.items():
                # If value is None remove item
                if v is None:
                    continue
                key = k if isinstance(k, str) else repr(k)
                # Could also use SecretStr but changes usage of Settings object
                if any(keyword in key.lower() for keyword in secret_words):
                    new_dict[key] = "****"
                else:
                    new_dict[key] = _make_dict_serializable(v)
            return new_dict
        case str() | int() | float():
            return item
        case list() | set():
            return [_make_dict_serializable(i) for i in item]
        case _:
            return repr(item)


class JsonFormatter(logging.Formatter):
    """Custom formatter for structured logging."""

    key_blacklist = [
        "msg",
        "message",
        "args",
        "created",
        "msecs",
        "relativeCreated",
        "levelno",
        "filename",
        "color_message",
    ]

    def __init__(
        self,
        datefmt: Optional[str] = "%Y-%m-%dT%H:%M:%S%z",
        reduced: Optional[list[str]] = None,
        indent: Optional[str] = None,
        *,
        defaults: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Create a new Formatter.

        Args:
            datefmt (str, optional): Used in @timestamp. Defaults to "%Y-%m-%dT%H:%M:%S%z".
            reduced (Optional[List[str]], optional): List of loglevels to reduce output by. Defaults to None.
                Reduced output removes filename, thread and process information
            indent (Optional[str], optional): indent for json dumps. Defaults to None.

        """
        super().__init__(None, datefmt, defaults=defaults)
        self.indent = indent
        self.reduced_levels = [logging.getLevelNamesMapping().get(level) for level in reduced or []]

    def _get_output_dict(self, record: logging.LogRecord) -> dict[str, Any]:
        data = {k: v for k, v in record.__dict__.items() if k not in self.key_blacklist and v is not None}
        logger_name = f"{data.pop('module')}.{data.pop('name')}"
        func_name = data.pop("funcName")
        if func_name != "<module>":
            logger_name = logger_name + "." + func_name
        output = {
            "level": data.pop("levelname"),
            "message": record.getMessage(),
            "logger_name": logger_name,
            "file": f"{data.pop('pathname')}:{data.pop('lineno')}",
            "extra": {},
            "@timestamp": self.formatTime(record, self.datefmt),
            "process": f"{data.pop('processName')}({data.pop('process')})",
            "thread": f"{data.pop('threadName')}({data.pop('thread')})",
        }
        if all(key in data for key in ["warnings.category", "warnings.filename", "warnings.lineno"]):
            output["file"] = f"{data.pop('warnings.filename')}:{data.pop('warnings.lineno')}"
        if data:
            output["extra"] = _make_dict_serializable(data)
        cor_id = correlation_id.get()
        if cor_id is not None:
            output["correlationId"] = cor_id
        if self.reduced_levels and record.levelno in self.reduced_levels:
            del output["process"]
            del output["logger_name"]
            del output["thread"]
        if not output["extra"]:
            del output["extra"]
        return output

    def format(self, record: logging.LogRecord) -> str:
        super().format(record)
        output = self._get_output_dict(record)
        return json.dumps(output, default=repr, indent=self.indent)


def get_logging_dict_config(level) -> dict[str, str]:
    """Generate a logging.config.dictConfig compatible dict.

    Returns:
        dict: logging.config.dictConfig

    """
    default_formatter = {
        "json_formatter": {
            "()": "wurzel.utils.logging.JsonFormatter",
            "reduced": ["INFO"],
        }
    }
    default_handler = {
        "default": {
            "level": level,
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "json_formatter",
        },
    }
    logger_template = {"level": level, "handlers": ["default"], "propagate": False}
    return {
        "version": 1,
        "root": {},
        "disable_existing_loggers": False,
        "formatters": {**default_formatter},
        "handlers": {**default_handler},
        "loggers": {
            "root": {**logger_template},
            "": {**logger_template},
            "uvicorn.error": {**logger_template},
            "uvicorn.access": {
                "level": "WARNING",
                "handlers": ["default"],
                "propagate": False,
            },
            "gunicorn.access": {"propagate": True},
            "gunicorn.error": {"propagate": True},
            "transaction": {**logger_template},
        },
    }
