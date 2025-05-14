# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.datacontract import PydanticModel


class Result(PydanticModel):
    """dummy output because its required to have a output data contract."""

    old: str
    new: str
