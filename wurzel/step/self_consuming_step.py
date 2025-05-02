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
    def _static_type_check_self(cls):
        """Confirms the type annotations of child classes TypedStep"""
        type_annotations = [
            get_args(parent)
            for parent in getattr(cls, "__orig_bases__", [])
            if get_args(parent)
        ][0]
        if type_annotations == ():
            raise StaticTypeError(
                f"No type-annotation provided when creating subclass of {cls.__name__}"
                + f"Use: MyStep({cls.__name__}[INPUT_T, OUTPUT_T])"
            )
        cls.settings_class, cls.output_model_type = type_annotations
        cls.input_model_type = cls.output_model_type | None

        if not issubclass(cls.settings_class, (Settings, NoneType)):
            raise StaticTypeError(
                "Settings provided in TypedStep[<>, ...]"
                + " is not a subclass of settings_class"
            )
        out_t = cls._unpack_list_containers(cls.output_model_type)

        def has_no_annotation(c: list, t: type):
            return c == [] and t == NoneType

        if has_no_annotation(*out_t):
            raise StaticTypeError(
                f"Type-annotation for output of {cls.__name__}[..., None] can't be None"
            )

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
