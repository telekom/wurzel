# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from pathlib import Path
from wurzel import BaseStepExecutor, TypedStep, NoSettings, MarkdownDataContract
from wurzel.exceptions import StepFailed
import asgi_correlation_id


class OkExc(Exception):
    pass


class TestableStep(TypedStep[None, None, list[MarkdownDataContract]]):
    def run(self, inputs):
        assert asgi_correlation_id.correlation_id.get() == self.__class__.__name__
        raise OkExc("Oki")


def test_setting_of_cor_id():
    assert asgi_correlation_id.correlation_id.get() is None
    with BaseStepExecutor() as ex:
        with pytest.raises(StepFailed) as err:
            ex(TestableStep, set(), Path("Hey"))
        assert err
    assert asgi_correlation_id.correlation_id.get() is None
