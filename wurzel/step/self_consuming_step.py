# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


from types import NoneType
from typing import Generic, Optional, Self, get_args

from wurzel.exceptions import StaticTypeError
from wurzel.path.path import PathToFolderWithBaseModels
from wurzel.step import TypedStep
from wurzel.step.settings import Settings
from wurzel.step.typed_step import OUTCONTRACT, SETTS


class SelfConsumingStep(
    TypedStep[SETTS, OUTCONTRACT, OUTCONTRACT], Generic[SETTS, OUTCONTRACT]
):
    """Some use cases require self awareness about their last results to reduce double work."""

    def run(self, inpt: Optional[OUTCONTRACT]) -> OUTCONTRACT:
        return super().run(inpt)


    @classmethod
    def _prepare_datamodels(cls, type_annotations):
        cls.settings_class, cls.output_model_type = type_annotations
        cls.input_model_type = cls.output_model_type | None

    def __new__(cls) -> Self:
        instance = super(TypedStep, cls).__new__(cls)
        super().__init__(instance)
        # Get Input and output type from annotations
        # Get Type annotations, fallback to None if they don't exist
        # pylint: disable-next=no-member
        instance._static_type_check_self()

        instance.input_model_class = instance.output_model_class = (
            get_args(instance.output_model_type) or [instance.output_model_type]
        )[-1]

        instance._static_type_check_run()

        class OutCls(PathToFolderWithBaseModels[instance.output_model_type]):
            """Used internally"""

        instance._internal_input_class = instance._internal_output_class = OutCls
        return instance
