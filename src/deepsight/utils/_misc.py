# Copyright 2024 The DeepSight Team.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Iterable
from typing import Any

from deepsight.typing import Configurable


def to_2tuple[T](value: T | tuple[T, T]) -> tuple[T, T]:
    """Convert a value to a 2-tuple."""
    if isinstance(value, tuple):
        if len(value) != 2:
            msg = f"Expected a 2-tuple, got {value}."
            raise ValueError(msg)
        return value

    return value, value


def to_tuple[T](value: T | Iterable[T]) -> tuple[T, ...]:
    """Convert a value to a tuple."""
    if isinstance(value, tuple):
        return value
    elif isinstance(value, Iterable):
        return tuple(value)
    else:
        return (value,)


def to_set[T](value: T | Iterable[T]) -> set[T]:
    """Convert a value to a set."""
    if isinstance(value, set):
        return value
    elif isinstance(value, Iterable):
        return set(value)
    else:
        return {value}


def full_class_name(obj: object) -> str:
    """Get the full class name of an object."""
    return f"{obj.__class__.__module__}.{obj.__class__.__name__}"


def get_config(obj: object, recursive: bool = True) -> dict[str, Any]:
    """Get the configuration of an object.

    The generated configuration is a dictionary that contains the class name of
    the object and its configuration if it is configurable.

    Args:
        obj: The object.
        recursive: Whether to recursively get the configurations of the sub-objects.
    """
    config = {"__class__": full_class_name(obj)}
    if isinstance(obj, Configurable):
        config.update(obj.get_config(recursive))

    return config
