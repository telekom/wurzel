# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
from inspect import getfile
from types import NoneType

from pydantic_core import PydanticUndefined

from wurzel.step import Settings, TypedStep
from wurzel.step.settings import NoSettings
from wurzel.utils import WZ


def main(step: type[TypedStep], gen_env=False):
    """Execute."""
    ins = WZ(step)
    set_cls: Settings = ins.settings_class
    env_prefix = step.__name__.upper()
    data = {
        "Name": step.__name__,
        "Input": "None" if ins.input_model_class == NoneType else ins.input_model_class,
        "Output": ins.output_model_type,
        "settings": {
            "env_prefix": env_prefix,
        },
    }
    if set_cls != NoneType and set_cls is not None and set_cls != NoSettings:
        data["settings"]["fields"] = {k: str(v) for k, v in set_cls.model_fields.items()}
    if gen_env:
        setts = {True: [], False: []}
        for name, info in set_cls.model_fields.items():
            default = info.get_default(call_default_factory=True)
            default = "" if default == PydanticUndefined or default is None else default
            setts[info.is_required()].append(f"{env_prefix}__{name}={default}")
        print(f"# Env for {step.__name__} -> {getfile(step)}")  # noqa: T201
        print("# Required")  # noqa: T201
        print("\n".join(setts[True]))  # noqa: T201
        print("# Optional")  # noqa: T201
        print("\n".join(setts[False]))  # noqa: T201
    else:
        print(json.dumps(data, indent="  ", default=str))  # noqa: T201
