# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import abc
import gc
import hashlib
import json
import time
import types
import typing
from ast import literal_eval
from logging import getLogger
from pathlib import Path
from typing import Optional, Self, Union, get_origin

import pandera as pa
import pandera.typing as patyp
import pydantic

log = getLogger(__name__)


class BatchWriter:  # pylint: disable=too-many-instance-attributes
    """Context manager that accumulates items and periodically flushes them to numbered batch files.

    Items are collected in an in-memory buffer.  Once the buffer reaches
    ``flush_size`` items it is sorted (best-effort), persisted via
    ``model_class.save_to_path``, and the memory is released via
    ``gc.collect()``.  Remaining items are flushed when the context manager
    exits.

    Usage::

        with DataModel.batch_writer(output_path, "MyStep") as writer:
            for item in stream:
                writer.extend([item])
        print(writer.total_items, writer.file_count)
    """

    DEFAULT_FLUSH_SIZE: int = 500

    def __init__(
        self,
        model_class: type["DataModel"],
        output_path: Optional[Path],
        prefix: str,
        flush_size: int = DEFAULT_FLUSH_SIZE,
    ) -> None:
        self._model_class = model_class
        self._output_path = output_path
        self._prefix = prefix
        self._flush_size = flush_size
        self._buffer: list = []
        self._file_count: int = 0
        self._total_items: int = 0
        self._store_time: float = 0.0

    # -- read-only stats ------------------------------------------------

    @property
    def total_items(self) -> int:
        """Total number of items flushed to disk so far."""
        return self._total_items

    @property
    def file_count(self) -> int:
        """Number of batch files written so far."""
        return self._file_count

    @property
    def store_time(self) -> float:
        """Cumulative wall-clock time spent writing to disk (seconds)."""
        return self._store_time

    # -- mutators -------------------------------------------------------

    def extend(self, items) -> None:
        """Add *items* to the buffer, flushing full batches to disk as needed."""
        if isinstance(items, list):
            self._buffer.extend(items)
        else:
            self._buffer.extend(list(items))

        while len(self._buffer) >= self._flush_size:
            self._flush(self._buffer[: self._flush_size])
            self._buffer = self._buffer[self._flush_size :]

    def flush(self) -> None:
        """Force-write any remaining buffered items to disk."""
        if self._buffer:
            self._flush(self._buffer)
            self._buffer = []

    # -- internals ------------------------------------------------------

    def _flush(self, items: list) -> None:
        count = len(items)
        if self._output_path:
            store_start = time.time()
            items = self._try_sort(items)
            self._model_class.save_to_path(
                self._output_path / f"{self._prefix}_batch{self._file_count:04d}",
                items,
            )
            self._store_time += time.time() - store_start
        self._total_items += count
        log.info(f"Batch {self._file_count}: saved {count} items (total: {self._total_items})")
        self._file_count += 1
        del items
        gc.collect()

    @staticmethod
    def _try_sort(items: list) -> list:
        """Best-effort sort; returns *items* unchanged when not comparable."""
        try:
            return sorted(items)
        except TypeError:
            return items

    # -- context manager ------------------------------------------------

    def __enter__(self) -> "BatchWriter":
        if self._output_path and not self._output_path.is_dir():
            self._output_path.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.flush()
        return False


class DataModel:
    """interface definition of a Contract model
    Contains method to store and load to a path.
    """

    @classmethod
    @abc.abstractmethod
    def save_to_path(cls, path: Path, obj: Union[Self, list[Self]]) -> Path:
        """Abstract function to save the obj at the given path."""

    @classmethod
    @abc.abstractmethod
    def load_from_path(cls, path: Path, *args) -> Self:
        """Abstract function to load the data from the given Path."""

    @classmethod
    def batch_writer(
        cls,
        output_path: Optional[Path],
        prefix: str,
        flush_size: int = BatchWriter.DEFAULT_FLUSH_SIZE,
    ) -> BatchWriter:
        """Return a :class:`BatchWriter` bound to this model class.

        Args:
            output_path: Directory for batch files (``None`` = no disk output).
            prefix: Filename prefix for batch files.
            flush_size: Max items buffered before a flush.
        """
        return BatchWriter(cls, output_path, prefix, flush_size)


class PanderaDataFrameModel(pa.DataFrameModel, DataModel):
    """Data Model contract specified with pandera
    Using Panda Dataframe. Mainly for CSV shaped data.
    """

    @classmethod
    def batch_writer(cls, output_path, prefix, flush_size=BatchWriter.DEFAULT_FLUSH_SIZE):
        """Not supported for DataFrame models.

        ``BatchWriter`` accumulates items in a Python list and flushes them
        via ``save_to_path``.  ``PanderaDataFrameModel.save_to_path`` expects
        a ``pandas.DataFrame``, not a list, so the two are incompatible.
        Use ``save_to_path`` directly with a DataFrame instead.
        """
        raise TypeError(
            f"{cls.__name__} does not support batch_writer(). "
            "PanderaDataFrameModel.save_to_path() requires a DataFrame, "
            "not a list of items. Use save_to_path() directly with a DataFrame."
        )

    @classmethod
    def save_to_path(cls, path: Path, obj: Union[Self, list[Self]]) -> Path:
        import pandas as pd  # pylint: disable=import-outside-toplevel

        path = path.with_suffix(".csv")
        if not isinstance(obj, pd.DataFrame):
            raise NotImplementedError(f"Cannot store {type(obj)}")
        obj.to_csv(path, index=False)
        return path

    @classmethod
    def load_from_path(cls, path: Path, *args) -> Self:
        """Switch case to find the matching file ending."""
        import pandas as pd  # pylint: disable=import-outside-toplevel

        # Load CSV from path
        with path.open(encoding="utf-8") as f:
            read_data = pd.read_csv(f)

        def _literal_eval_or_passthrough(value):
            """Convert stringified literals to Python objects because pandas keeps CSV cells as strings."""
            if not isinstance(value, str):
                return value
            stripped = value.strip()
            if stripped == "":
                return None
            try:
                return literal_eval(stripped)
            except (ValueError, SyntaxError):
                return value

        # Iterate over coluns and load data
        for key, atr in cls.to_schema().columns.items():
            if key not in read_data.columns:
                continue
            if atr.dtype.type in {list, dict}:
                read_data[key] = read_data[key].apply(_literal_eval_or_passthrough)

        return patyp.DataFrame[cls](read_data)


class PydanticModel(pydantic.BaseModel, DataModel):
    """DataModel contract specified with pydantic."""

    @classmethod
    def save_to_path(cls, path: Path, obj: Union[Self, list[Self]]):
        """Wurzel save model.

        Args:
            path (Path): location
            obj (Union[Self, list[Self]]): obj(s) to store

        Raises:
            NotImplementedError

        """
        path = path.with_suffix(".json")
        if isinstance(obj, list):
            # Stream JSON array item-by-item to avoid building the entire
            # serialised string in memory (critical for large lists).
            with path.open("wt", encoding="UTF-8") as fp:
                fp.write("[")
                for i, item in enumerate(obj):
                    if i > 0:
                        fp.write(",")
                    if isinstance(item, pydantic.BaseModel):
                        fp.write(item.model_dump_json())
                    else:
                        json.dump(item, fp)
                fp.write("]")
        elif isinstance(obj, cls):
            with path.open("wt", encoding="UTF-8") as fp:
                fp.write(obj.model_dump_json())
        else:
            raise NotImplementedError(f"Cannot store {type(obj)}")
        return path

    # pylint: disable=arguments-differ
    @classmethod
    def load_from_path(cls, path: Path, model_type: type[Union[Self, list[Self]]]) -> Union[Self, list[Self]]:
        """Wurzel load model.

        Args:
            path (Path): load model from
            model_type (type[Union[Self, list[Self]]]): expected type

        Raises:
            NotImplementedError

        Returns:
            Union[Self, list[Self]]: dependent on expected type

        """
        # isinstace does not work for union pylint: disable=unidiomatic-typecheck
        if type(model_type) is types.UnionType:
            model_type = [ty for ty in typing.get_args(model_type) if ty][0]
        if get_origin(model_type) is None:
            if issubclass(model_type, pydantic.BaseModel):
                with path.open(encoding="utf-8") as f:
                    return cls(**json.load(f))
        elif get_origin(model_type) is list:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            for i, entry in enumerate(data):
                data[i] = cls(**entry)
            return data

        raise NotImplementedError(f"Can not load {model_type}")

    def __hash__(self) -> int:
        """Compute a hash based on all not-none field values."""
        # pylint: disable-next=not-an-iterable
        return int(
            hashlib.sha256(
                bytes(
                    "".join([str(getattr(self, name) or "") for name in sorted(type(self).model_fields)]),
                    encoding="utf-8",
                ),
                usedforsecurity=False,
            ).hexdigest(),
            16,
        )

    def __eq__(self, other: object) -> bool:
        # pylint: disable-next=not-an-iterable
        for field in type(self).model_fields:
            other_value = getattr(other, field, None)
            if isinstance(other, dict):
                other_value = other.get(field, None)
            if getattr(self, field) != other_value:
                return False
        return True

    def __lt__(self, other: object) -> bool:
        return hash(self) < hash(other)
