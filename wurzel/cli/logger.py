# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import logging.config

from wurzel.utils.logging import JsonFormatter


class WithExtraFormatter(JsonFormatter):
    """Custom formatter with some structured logging support."""

    def format(self, record: logging.LogRecord) -> str:
        super().format(record)
        json_part = self._get_output_dict(record)
        msg = json_part.pop("message")
        if self.reduced_levels and record.levelno in self.reduced_levels:
            json_part.pop("thread", None)
            json_part.pop("threadName", None)
            json_part.pop("processName", None)
            json_part.pop("process", None)
        json_part.pop("level", None)
        json_part.pop("@timestamp", None)
        json_part.pop("file", None)
        exc_text = json_part.pop("exc_text", "")
        return " ".join([f"'{msg}'" + (f" : {json.dumps(json_part)}" if json_part else "") + exc_text])
