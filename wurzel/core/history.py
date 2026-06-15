# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
from collections.abc import Iterable
from contextvars import ContextVar
from typing import Optional

from .typed_step import TypedStep

step_history: ContextVar[Optional["History"]] = ContextVar("step_history", default=None)
step_history.set(None)


class History:
    """internal history object."""

    __SEP_STR = "-"
    _history: list[str]

    def __init__(self, *args: TypedStep | str | list[str], initial: list[str] | None = None) -> None:
        if initial is None:
            initial = []
        self._history = initial
        for item in args:
            self += item

    def __add(self, s: str):
        self._history.append(s[:-4] if s.endswith("Step") else s)

    @staticmethod
    def __name_of(value: object) -> str:
        if isinstance(value, type):
            return value.__name__
        return value.__class__.__name__

    def __iadd__(self, other: TypedStep | str | list[str]) -> "History":
        if isinstance(other, str):
            self.__add(other)
        elif isinstance(other, Iterable) and not isinstance(other, type):
            for i in other:
                if isinstance(i, str):
                    self.__add(i)
                else:
                    self.__add(self.__name_of(i))
        else:
            self.__add(self.__name_of(other))
        return self

    def copy(self) -> "History":
        """Returns a copy of self."""
        return History(initial=self.get())

    def get(self) -> list[str]:
        """Get History.

        Returns:
            list[str]: history (copy)

        """
        return self._history.copy()

    def __add__(self, other):
        if isinstance(other, History):
            return History(initial=[*self._history, *other._history])
        cpy = self.copy()
        cpy += other
        return cpy

    def __str__(self) -> str:
        return History.__SEP_STR.join(self._history)

    def __repr__(self) -> str:
        return f"History({self._history})"

    def __getitem__(self, key: str | int | slice):
        if isinstance(key, str):
            raise TypeError
        return History(self._history[key])

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, History):
            return False
        return self._history == value._history

    def to_json(self):
        """Converts to json string.

        Returns:
            str: json list of str

        """
        return json.dumps(self._history)

    @classmethod
    def from_json(cls, s: str) -> "History":
        """Converts from json string.

        Args:
            s (str): json string list of str

        Returns:
            History: new Instance

        """
        return History(initial=json.loads(s))

    @classmethod
    def from_str(cls, s: str) -> "History":
        """Converts from str(History).

        Args:
            s (str)

        Returns:
            History: new Instance

        """
        return History(initial=json.loads(s))
