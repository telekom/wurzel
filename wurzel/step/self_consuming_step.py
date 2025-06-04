# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


from typing import Generic, Optional, get_args

from wurzel.step import TypedStep
from wurzel.step.typed_step import OUTCONTRACT, SETTS


class SelfConsumingLeafStep(TypedStep[SETTS, OUTCONTRACT, OUTCONTRACT], Generic[SETTS, OUTCONTRACT]):
    """Some use cases require self awareness about their last results to reduce double work."""

    def run(self, inpt: Optional[OUTCONTRACT]) -> OUTCONTRACT:
        return super().run(inpt)

    @classmethod
    def _prepare_datamodels(cls, type_annotations):
        cls.settings_class, cls.output_model_type = type_annotations
        cls.input_model_type = cls.output_model_type | None

    @classmethod
    def _prepare_instance_datamodels(cls, instance):
        instance.input_model_class = instance.output_model_class = (get_args(instance.output_model_type) or [instance.output_model_type])[
            -1
        ]
