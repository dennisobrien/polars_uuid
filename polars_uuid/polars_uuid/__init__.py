from __future__ import annotations

import uuid
from pathlib import Path

import polars as pl
from polars.plugins import register_plugin_function

from polars_uuid._internal import __version__ as __version__

IntoExprColumn = pl.Expr | str | pl.Series

LIB = Path(__file__).parent


def uuid4(expr: IntoExprColumn) -> pl.Expr:
    """Generate a random (v4) UUID for each row of `expr`.

    Only the length of `expr` is used; its values are ignored. Reuse the
    resulting expression for only one column — polars' common subexpression
    elimination would otherwise evaluate it once and copy the result.
    """
    return register_plugin_function(
        args=[expr],
        plugin_path=LIB,
        function_name="uuid4",
        is_elementwise=True,
    )


def uuid7(expr: IntoExprColumn) -> pl.Expr:
    """Generate a time-ordered (v7) UUID for each row of `expr`.

    Only the length of `expr` is used; its values are ignored. Reuse the
    resulting expression for only one column — polars' common subexpression
    elimination would otherwise evaluate it once and copy the result.
    """
    return register_plugin_function(
        args=[expr],
        plugin_path=LIB,
        function_name="uuid7",
        is_elementwise=True,
    )


def uuid5(expr: IntoExprColumn, namespace: str | uuid.UUID) -> pl.Expr:
    """Generate a deterministic (v5) UUID from a namespace and `expr`."""
    return register_plugin_function(
        args=[expr],
        plugin_path=LIB,
        function_name="uuid5",
        is_elementwise=True,
        kwargs={"namespace": str(namespace)},
    )


def is_valid_uuid(expr: IntoExprColumn) -> pl.Expr:
    """Return whether each value of `expr` parses as a valid UUID.

    Null input produces a null result (not `False`), so "unknown" stays
    distinguishable from "invalid".
    """
    return register_plugin_function(
        args=[expr],
        plugin_path=LIB,
        function_name="is_valid_uuid",
        is_elementwise=True,
    )


def uuid_version(expr: IntoExprColumn) -> pl.Expr:
    """Extract the version number (1-8) from each UUID string in `expr`.

    Null for invalid UUIDs or null input.
    """
    return register_plugin_function(
        args=[expr],
        plugin_path=LIB,
        function_name="uuid_version",
        is_elementwise=True,
    )


def extract_timestamp(expr: IntoExprColumn) -> pl.Expr:
    """Extract the embedded creation timestamp from a time-based UUID.

    Only versions 1, 6, and 7 carry a timestamp. Null for other versions,
    invalid UUIDs, or null input.
    """
    return register_plugin_function(
        args=[expr],
        plugin_path=LIB,
        function_name="extract_timestamp",
        is_elementwise=True,
    )
