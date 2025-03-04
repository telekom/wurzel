# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import logging.config
import pytest

from wurzel.utils.logging import get_logging_dict_config
import logging
def test_logging_dict_config():
    confg = get_logging_dict_config("INFO")
    logging.config.dictConfig(confg)
def test_logging_dict_config_invalid():
    config = get_logging_dict_config("INFO")
    config["version"] = "BN"
    with pytest.raises(ValueError):
        logging.config.dictConfig(config)
def test_warning_override():
    from wurzel.utils.logging import warnings_to_logger
    warnings_to_logger("Test", "None", __file__, lineno= "123")
    #Dummy test