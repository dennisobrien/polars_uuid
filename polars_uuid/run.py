"""Scratchpad for trying out the polars-uuid plugin.

Run with `make run` (from the repo root) or `uv run python run.py` (from this dir).
"""

import uuid

import polars as pl

import polars_uuid

print(f"polars-uuid version: {polars_uuid.__version__}")

df = pl.DataFrame({"name": ["example.com", "example.org", "example.com"]})
result = df.with_columns(
    polars_uuid.uuid4("name").alias("random_id"),
    polars_uuid.uuid5("name", namespace=uuid.NAMESPACE_DNS).alias("deterministic_id"),
    polars_uuid.uuid7("name").alias("time_ordered_id"),
)
print(result)

introspect = result.select(
    polars_uuid.is_valid_uuid("time_ordered_id").alias("valid"),
    polars_uuid.uuid_version("time_ordered_id").alias("version"),
    polars_uuid.extract_timestamp("time_ordered_id").alias("created_at"),
)
print(introspect)
