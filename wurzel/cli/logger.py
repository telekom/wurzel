# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import sys

from loguru import logger


def setup_cli_logging(level: str = "INFO") -> None:
    """Configure loguru for interactive terminal sessions.

    Uses a human-readable, colourised format instead of JSON so that
    log output is easy to scan in a developer's terminal.

    Args:
        level: Minimum log level (e.g. ``"DEBUG"``, ``"INFO"``).

    """
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSSSSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )
