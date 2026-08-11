# polars-uuid

[![CI](https://github.com/dennisobrien/polars_uuid/actions/workflows/publish_to_pypi.yml/badge.svg)](https://github.com/dennisobrien/polars_uuid/actions/workflows/publish_to_pypi.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

A [Polars](https://pola.rs/) plugin that adds UUID generation and introspection
expressions, implemented in Rust for speed.

## Installation

```bash
pip install polars-uuid-plugin
```

## Quick example

```python
import uuid

import polars as pl
import polars_uuid

df = pl.DataFrame({"name": ["example.com", "example.org", "example.com"]})
df.with_columns(
    polars_uuid.uuid4("name").alias("random_id"),
    polars_uuid.uuid5("name", namespace=uuid.NAMESPACE_DNS).alias("deterministic_id"),
    polars_uuid.uuid7("name").alias("time_ordered_id"),
)
```

Also included: `is_valid_uuid`, `uuid_version`, and `extract_timestamp` for working
with UUIDs already in your data. See
[`polars_uuid/README.md`](polars_uuid/README.md) for the full function reference,
plus instructions for building the plugin from source, running the test suite, and
cutting a release.

## Learn more

- [`notebooks/uuid_examples.ipynb`](notebooks/uuid_examples.ipynb) — a runnable
  walkthrough of every function
- [`notebooks/benchmarks.ipynb`](notebooks/benchmarks.ipynb) — this plugin vs. naive
  Python UUID generation in polars and pandas: ~9-26x faster hashing an existing text
  column in isolation, ~5-10x faster end-to-end on a realistic multi-column composite
  key (see [`polars_uuid/README.md`](polars_uuid/README.md) for what each number
  actually measures)

## Repository layout

The Rust/Python plugin project lives in the nested [`polars_uuid/`](polars_uuid/)
directory; the `Makefile` at this repo root wraps its build commands so you don't need
to `cd` into it yourself (`make help` lists the available commands).

## License

[Apache License 2.0](LICENSE)
