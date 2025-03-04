# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import logging.config

from wurzel.utils.logging import JsonFormatter, _make_dict_serializable



class WithExtraFormatter(JsonFormatter):
    """Custom formatter with some structured logging support"""
    def format(self, record: logging.LogRecord) -> str:
        super().format(record)
        data = {k: v for k, v in record.__dict__.items() if k not in self.key_blacklist and v is not None}
        logger_name = f"{data.pop('module')}.{data.pop('name')}"
        func_name = data.pop('funcName')
        if func_name != '<module>':
            logger_name = logger_name +"."+func_name
        msg = record.getMessage()
        #pylint: disable-next=protected-access
        json_part = _make_dict_serializable(data)
        if self.reduced_levels and record.levelno in self.reduced_levels:
            json_part.pop('thread', None)
            json_part.pop('threadName', None)
            json_part.pop('processName', None)
            json_part.pop('process', None)
        json_part.pop('levelname', None)
        json_part.pop('levelname', None)
        json_part['pathname'] = json_part.get('pathname', '') + f":{json_part.pop('lineno', '')}"
        exc_text = json_part.pop("exc_text", "")
        return " ".join([
            f"'{msg}'" + (f" : {json.dumps(json_part)}" if json_part else "") + exc_text
        ])
