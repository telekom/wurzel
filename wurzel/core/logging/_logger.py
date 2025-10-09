# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Thin wrapper around loguru that accepts stdlib-style ``extra=`` and ``exc_info=`` kwargs.

This lets call sites write::

    logger.info("hello", extra={"user_id": 42})
    logger.warning("oops", exc_info=True)

instead of the verbose loguru equivalents (``logger.bind(...).info(...)``,
``logger.opt(exception=True).warning(...)``). All other loguru attributes
(``bind``, ``opt``, ``add``, ``remove``, ``patch``, …) are delegated unchanged.
"""

from loguru import logger as _loguru_logger

_LEVEL_METHODS = ("trace", "debug", "info", "success", "warning", "error", "critical")


class _LoggerProxy:
    """Loguru proxy supporting ``extra=`` and ``exc_info=`` keyword arguments."""

    __slots__ = ()

    def _emit(self, level: str, message: str, args: tuple, kwargs: dict) -> None:
        extra = kwargs.pop("extra", None)
        exc_info = kwargs.pop("exc_info", None)
        log = _loguru_logger
        if extra:
            log = log.bind(**extra)
        opt_kwargs: dict = {"depth": 2}
        if exc_info:
            opt_kwargs["exception"] = True if exc_info is True else exc_info
        log = log.opt(**opt_kwargs)
        log.log(level, message, *args, **kwargs)

    def trace(self, msg, *args, **kwargs):
        self._emit("TRACE", msg, args, kwargs)

    def debug(self, msg, *args, **kwargs):
        self._emit("DEBUG", msg, args, kwargs)

    def info(self, msg, *args, **kwargs):
        self._emit("INFO", msg, args, kwargs)

    def success(self, msg, *args, **kwargs):
        self._emit("SUCCESS", msg, args, kwargs)

    def warning(self, msg, *args, **kwargs):
        self._emit("WARNING", msg, args, kwargs)

    def error(self, msg, *args, **kwargs):
        self._emit("ERROR", msg, args, kwargs)

    def critical(self, msg, *args, **kwargs):
        self._emit("CRITICAL", msg, args, kwargs)

    def exception(self, msg, *args, **kwargs):
        kwargs.setdefault("exc_info", True)
        self._emit("ERROR", msg, args, kwargs)

    def log(self, level, msg, *args, **kwargs):
        self._emit(level, msg, args, kwargs)

    def __getattr__(self, name: str):
        # Delegate everything else (bind, opt, add, remove, level, patch, contextualize, catch, ...)
        return getattr(_loguru_logger, name)


logger = _LoggerProxy()

__all__ = ["logger"]
