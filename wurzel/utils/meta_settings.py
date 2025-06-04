# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from types import NoneType
from typing import Union

from pydantic import BaseModel
from pydantic import create_model as py_create_model

from wurzel.step.settings import Settings, SettingsBase
from wurzel.step.typed_step import TypedStep


# pylint: disable-next=invalid-name
def WZ(typ: type[TypedStep]):
    """Creates a Pipeline Element."""
    return TypedStep.__new__(typ)


def create_model(
    fields: Union[list[Union[TypedStep, type[TypedStep]]], TypedStep],
    allow_extra_fields=False,
) -> SettingsBase:
    """Takes all fields.setting_class and creates a pydantic_settings Model.

    - If input is a list:
        - If list of Type[TypedStep]: WZ(item) will be applied
        - If list of TypedStep (WZ was already aplpied): nothing
    - if input single TypedStep: required_steps will be traversed
        - Minimum step itself.



    Model takes the form of:
    ```python
        # For each step in fields:
        class MetaSettings_UPPERCASESTEPNAME(SettingsLeaf):
            # for each field_name, value pair in step.settings_cls
            field_name: field_annotation = value
            ...
        ...
        class MetaSettings_parent(SettingsBase):
            UPPERCASESTEPNAME: MetaSettings_UPPERCASESTEPNAME
            ...
    ```

    Args:
        fields (list[Union[TypedStep, Type[TypedStep]]]): will be fields
        allow_extra_fields (bool): if True, allows extra fields in the model

    Returns:
        SettingsBase: MetaModel with set fields

    """

    def clean(
        flds: Union[list[Union[TypedStep, type[TypedStep]]], TypedStep],
    ) -> list[TypedStep]:
        if isinstance(flds, TypedStep):
            return list(flds.traverse())
        cleaned: list[TypedStep] = [WZ(f) if isinstance(f, type) else f for f in flds]
        return cleaned

    clean_fields = clean(fields)
    base_class = py_create_model("SettingsLeaf_allow_extra", __base__=Settings)
    if allow_extra_fields:
        base_class.model_config["extra"] = "allow"
    inner_models: dict[str, Settings] = {
        step.__class__.__name__.upper(): py_create_model(
            "MetaSettings_" + step.__class__.__name__,
            **{name: (v.annotation, v) for name, v in step.settings_class.model_fields.items()},
            __base__=base_class,
        )
        for step in clean_fields
        if step.settings_class != NoneType
    }

    new_model_class: type[BaseModel] = py_create_model(
        "MetaSettings_Parent",
        **{name: (typ, ...) for name, typ in inner_models.items()},
        __base__=SettingsBase,
    )
    return new_model_class
