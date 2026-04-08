# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Discover TypedStep classes and emit JSON Schema metadata for the KaaS UI and catalog."""

from __future__ import annotations

import json
import uuid
from types import NoneType
from typing import Any, TypedDict, get_args, get_origin

import pydantic

from wurzel.core.settings import NoSettings
from wurzel.core.typed_step import TypedStep
from wurzel.datacontract import PanderaDataFrameModel
from wurzel.utils import WZ, find_typed_steps_in_package


class StepCatalogEntry(TypedDict, total=False):
    step_key: str
    display_name: str
    import_path: str
    settings_json_schema: dict[str, Any] | None
    input_json_schema: dict[str, Any] | None
    output_json_schema: dict[str, Any] | None
    input_type_fqn: str | None
    output_type_fqn: str | None


def _fqn(tp: type | None) -> str | None:
    if tp is None or tp is NoneType:
        return None
    return f"{tp.__module__}.{tp.__qualname__}"


def _schema_for_pydantic_model(model_cls: type[pydantic.BaseModel]) -> dict[str, Any]:
    return model_cls.model_json_schema(mode="serialization")


def _schema_for_type(annotation: Any, *, title: str) -> dict[str, Any] | None:
    """Build a JSON Schema-ish description for contracts (Pydantic, None, list[T], etc.)."""
    if annotation is None or annotation is NoneType:
        return {"type": "null", "title": title}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is list and args:
        inner = _schema_for_type(args[0], title=f"{title}_item")
        return {"type": "array", "title": title, "items": inner or {"type": "object"}}

    if origin is set and args:
        inner = _schema_for_type(args[0], title=f"{title}_item")
        return {"type": "array", "uniqueItems": True, "title": title, "items": inner or {"type": "object"}}

    ann = annotation
    if isinstance(ann, type):
        if issubclass(ann, pydantic.BaseModel):
            schema = _schema_for_pydantic_model(ann)
            schema.setdefault("title", ann.__name__)
            return schema
        if issubclass(ann, PanderaDataFrameModel):
            return {
                "type": "object",
                "title": ann.__name__,
                "x-wurzel-model": "pandera-dataframe",
                "x-wurzel-fqn": _fqn(ann),
            }

    return {
        "type": "object",
        "title": title,
        "x-wurzel-fqn": _fqn(ann) if isinstance(ann, type) else str(ann),
    }


def _settings_schema(settings_cls: type) -> dict[str, Any] | None:
    if settings_cls in (None, NoneType, NoSettings):
        return None
    if isinstance(settings_cls, type) and issubclass(settings_cls, pydantic.BaseModel):
        return _schema_for_pydantic_model(settings_cls)
    return None


def _annotation_fqn(annotation: Any) -> str | None:
    if annotation is None or annotation is NoneType:
        return None
    if isinstance(annotation, type):
        return _fqn(annotation)
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is list and args:
        inner = _annotation_fqn(args[0])
        return f"list[{inner or 'Any'}]"
    if origin is set and args:
        inner = _annotation_fqn(args[0])
        return f"set[{inner or 'Any'}]"
    return str(annotation)


def build_entry(step_cls: type[TypedStep]) -> StepCatalogEntry:
    """Introspect a TypedStep subclass (same pattern as ``wurzel.cli.cmd_inspect``)."""
    proto = WZ(step_cls)
    settings_cls = proto.settings_class
    in_t = step_cls.input_model_type
    out_t = step_cls.output_model_type

    in_schema = _schema_for_type(in_t, title="input")
    out_schema = _schema_for_type(out_t, title="output")

    step_key = f"{step_cls.__module__}.{step_cls.__name__}"
    import_path = step_key

    return StepCatalogEntry(
        step_key=step_key,
        display_name=step_cls.__name__,
        import_path=import_path,
        settings_json_schema=_settings_schema(settings_cls),
        input_json_schema=in_schema,
        output_json_schema=out_schema,
        input_type_fqn=_annotation_fqn(in_t),
        output_type_fqn=_annotation_fqn(out_t),
    )


def iter_step_catalog_entries(package: str = "wurzel.steps") -> list[StepCatalogEntry]:
    """Return catalog rows for every concrete ``TypedStep`` discoverable under *package*."""
    found = find_typed_steps_in_package(package)
    entries: list[StepCatalogEntry] = []
    for step_cls in sorted(found.values(), key=lambda c: (c.__module__, c.__name__)):
        try:
            entries.append(build_entry(step_cls))
        except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
            # Optional step modules may fail static init; skip them for catalog.
            continue
    return entries


def catalog_to_json(entries: list[StepCatalogEntry], *, indent: int | None = 2) -> str:
    return json.dumps(entries, indent=indent, default=str)


def catalog_to_sql_upserts(entries: list[StepCatalogEntry]) -> str:
    """Generate SQL ``INSERT ... ON CONFLICT`` for ``public.step_type_catalog``."""
    lines = [
        "-- Generated by scripts/sync_step_catalog.py — do not hand-edit.",
        "insert into public.step_type_catalog",
        "  (step_key, display_name, import_path, settings_json_schema, input_json_schema,",
        "   output_json_schema, input_type_fqn, output_type_fqn, updated_at)",
        "values",
    ]
    value_rows: list[str] = []
    for e in entries:
        settings = e.get("settings_json_schema")
        inp = e.get("input_json_schema")
        out = e.get("output_json_schema")

        def dollar_json(obj: dict[str, Any] | None) -> str:
            if obj is None:
                return "null"
            body = json.dumps(obj, default=str)
            t = f"k{uuid.uuid4().hex}"
            return f"${t}${body}${t}$::jsonb"

        sk = e["step_key"].replace("'", "''")
        dn = (e.get("display_name") or "").replace("'", "''")
        ip = e["import_path"].replace("'", "''")
        infqn = (e.get("input_type_fqn") or "").replace("'", "''")
        outfqn = (e.get("output_type_fqn") or "").replace("'", "''")

        value_rows.append(
            "  ("
            f"'{sk}', '{dn}', '{ip}', {dollar_json(settings)}, {dollar_json(inp)}, "
            f"{dollar_json(out)}, "
            f"nullif('{infqn}', '')::text, nullif('{outfqn}', '')::text, now())"
        )

    lines.append(",\n".join(value_rows))
    lines.append(
        "on conflict (step_key) do update set\n"
        "  display_name = excluded.display_name,\n"
        "  import_path = excluded.import_path,\n"
        "  settings_json_schema = excluded.settings_json_schema,\n"
        "  input_json_schema = excluded.input_json_schema,\n"
        "  output_json_schema = excluded.output_json_schema,\n"
        "  input_type_fqn = excluded.input_type_fqn,\n"
        "  output_type_fqn = excluded.output_type_fqn,\n"
        "  updated_at = now();"
    )
    return "\n".join(lines)
