# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import inspect
import json
from typing import Any, TypeAlias, Union, get_origin

from pydantic import create_model, model_validator
from pydantic_core import InitErrorDetails, PydanticUndefined, ValidationError
from pydantic_settings import (
    BaseSettings as _PydanticBaseSettings,
)
from pydantic_settings import (
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class SettingsBase(_PydanticBaseSettings):
    """Used as the PydanticSettingsBase
    Sets delimiter etc.

    When creating a custom Settings object keep these things in mind:
    1. The base settings object should inherit from SettingsBase
    2. So far only 1 layer of nesting is supported
    3. All other member settings objects need to inherit from SettingsLeaf
    4. When defining the base settings object call no SettingsLeaf constructor
    ```
        class _DBSettings(SettingsLeaf):
            USER: str
            PASSWORD: str = Field("", repr=False)
        class MySettings(SettingsBase)
            DB: _DBSettings
    ```
    """

    # Dev Note: to support n layer nesting SettingsBase
    #           needs to support the with_prefix method
    # pydantic-internal
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="forbid",
        case_sensitive=True,
        frozen=False,
        revalidate_instances="always",
    )

    @classmethod
    # pylint: disable-next=too-many-positional-arguments
    def settings_customise_sources(
        cls,
        settings_cls: type[_PydanticBaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, env_settings

    @model_validator(mode="before")
    @classmethod
    def before(cls, data: Any):  # pylint: disable=too-many-branches
        """Before Validator, handles updating."""
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(data, dict):
            for key, field in cls.model_fields.items():
                if key in data:
                    if get_origin(field.annotation) is dict:
                        continue
                    if isinstance(data[key], str) and inspect.isclass(field.annotation) and issubclass(field.annotation, SettingsBase):
                        data[key] = json.loads(data[key])
                    # if annotation is optional and not a SettingsBase
                    elif (
                        hasattr(field.annotation, "__origin__")
                        and field.annotation.__origin__ == Union
                        and data[key]
                        and inspect.isclass(field.annotation.__args__[0])
                        and not issubclass(field.annotation.__args__[0], SettingsBase)
                    ):
                        data[key] = field.annotation.__args__[0](data[key])
                        continue
                    continue
                # Is not a typing.<Dict | List | anything> and inherits from _SettingsBase
                if get_origin(field.annotation) is None:
                    if issubclass(field.annotation, SettingsLeaf):
                        try:
                            data[key] = field.annotation.with_prefix(f"{key}__")()
                        except ValidationError as verr:
                            raise ValidationError.from_exception_data(
                                verr.title,
                                [
                                    InitErrorDetails(
                                        type=err["type"],
                                        loc=(key, *err["loc"]),
                                        input=err["input"],
                                        ctx={"error": err},
                                    )
                                    for err in verr.errors()
                                ],
                            )
                    elif issubclass(field.annotation, SettingsLeaf):
                        data[key] = field.annotation()
                elif field.default != PydanticUndefined:
                    data[key] = field.default
                elif field.default_factory is not None:
                    data[key] = field.default_factory()
                elif hasattr(cls, key):
                    data[key] = getattr(cls, key)
        return data


class SettingsLeaf(SettingsBase):
    """Base Class for all Setting which are not the main Setting.
    This class is mainly used to fix pydantic_settings incorrect loading of env vars.
    It might be made obsolete by future pydantic_settings releases
    https://github.com/pydantic/pydantic-settings/pull/261.
    """

    @classmethod
    def with_prefix(cls, prefix: str) -> "SettingsLeaf":
        """Returns a new class with env_prefix set."""
        cpy = create_model(prefix + "." + cls.__class__.__name__, __base__=cls)
        cpy.model_config["env_prefix"] = prefix
        return cpy


class Settings(SettingsLeaf):
    """Settings for Typed Steps
    In general if a class var is called `YOUR_AD_COULD_BE_HERE` the framework will try to load,
    from os.environ, a variable called `YOUR_AD_COULD_BE_HERE`.

    However for nested Settings, there will be prefixes applied separated with __ : `PARENT_VAR__YOUR_AD_COULD_BE_HERE`
    will be read from env.

    Same goes for TypedStepSettings. Their prefix is *always* `STEP_NAME_IN_UPPER_CASE`.
    ## Example
    ```python
    class KafkaSettings(Settings):
        \"\"\"Settings for Kafka\"\"\"
        # No default is given --> there must be a corresponding env_value
        BROKER_URLS: list[str] = Field([
            "kafka.example.com:9093",
            "kafka.example.com:9094",
            "kafka.example.com:9095"
            ],
            description="List of bootstrap servers")
        SASL_USER: str = "<USER_NAME>"
        SASL_PASSWORD: str
        # variables with password, key or secret won't usually be printed to terminals.
        SSL_CA_FILE: str = Field("./kafka_ca.pem", description="Path to ca file")
        TOPIC: str = "cc_mm_coupon_meta_bot"
        CONSUMER_TIMEOUT: int = Field(5*1000, description="timeout for kafka consumer in ms")
    ```
    """


# pylint: disable-next=invalid-name
NoSettings: TypeAlias = None
__all__ = ["Settings"]
