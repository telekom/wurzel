# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Logging configuration setup for CLI."""

from __future__ import annotations

import logging.config


def update_log_level(log_level: str) -> None:
    """Configure logging level and handlers."""
    from wurzel.core.logging import get_logging_dict_config  # pylint: disable=import-outside-toplevel

    log_config = get_logging_dict_config(log_level)
    log_config["formatters"]["default"] = {
        "()": "wurzel.cli.logger.WithExtraFormatter",
        "reduced": ["INFO"],
    }
    log_config["handlers"]["default"] = {
        "()": "rich.logging.RichHandler",
        "formatter": "default",
    }
    logging.config.dictConfig(log_config)
