# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import NoneType
from typing import Any, get_args, get_origin

import pydantic
from temporalio import activity  # pylint: disable=import-error

from wurzel.utils import WZ

from .registry import resolve_step_class


def _deserialize_input(step_cls: type, payload: Any) -> Any:
    inn = step_cls.input_model_type
    if inn is None or inn is NoneType:
        return None

    origin = get_origin(inn)
    args = get_args(inn)

    if origin in (list,) and args:
        inner = args[0]
        if isinstance(inner, type) and issubclass(inner, pydantic.BaseModel):
            if not isinstance(payload, list):
                raise TypeError("expected list input payload")
            return [inner.model_validate(x) for x in payload]
        raise TypeError(f"unsupported list input contract: {inn}")

    if isinstance(inn, type) and issubclass(inn, pydantic.BaseModel):
        return inn.model_validate(payload)

    raise TypeError(f"unsupported input contract for activity: {inn}")


def _serialize_output(out: Any) -> Any:
    import pandas as pd  # pylint: disable=import-outside-toplevel

    if isinstance(out, list):
        serialized: list[Any] = []
        for item in out:
            if hasattr(item, "model_dump"):
                serialized.append(item.model_dump())
            else:
                serialized.append(item)
        return serialized
    if hasattr(out, "model_dump"):
        return out.model_dump()
    if isinstance(out, pd.DataFrame):
        return {"__kind__": "dataframe", "records": out.to_dict(orient="records")}
    return out


@activity.defn(name="execute_wurzel_node")
def execute_wurzel_node(req: dict[str, Any]) -> Any:
    """Run a single ``TypedStep`` with JSON-friendly settings and I/O."""
    step_key = req["step_key"]
    settings_dict = req.get("settings") or {}
    input_payload = req.get("input_payload")

    step_cls = resolve_step_class(step_key)
    proto = WZ(step_cls)
    settings_cls = proto.settings_class

    if settings_cls in (None, NoneType):
        settings_obj = None
    else:
        settings_obj = settings_cls.model_validate(settings_dict)

    inst = WZ(step_cls)
    inst.settings = settings_obj  # type: ignore[assignment]

    inpt = _deserialize_input(step_cls, input_payload)
    out = inst.run(inpt)
    return _serialize_output(out)
