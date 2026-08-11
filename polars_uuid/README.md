# polars-uuid

A [Polars](https://pola.rs/) plugin that adds UUID generation and introspection
expressions, implemented in Rust for speed. How much faster depends heavily on what
you're measuring — see [`notebooks/benchmarks.ipynb`](../notebooks/benchmarks.ipynb)
for the full script and methodology, but roughly:

- **~9-26x** faster than a naive Python loop (`map_elements` in polars, a list
  comprehension in pandas) when hashing a single already-text column — this isolates
  the hash cost, at 1,000,000 rows.
- **~5-10x** faster end-to-end on a more realistic 9-column composite key, where the
  type-conversion step (identical across all three approaches) dominates more of the
  total and dilutes the ratio — also at 1,000,000 rows.

Neither number is "the" number; which one predicts your workload depends on whether
you're hashing data that's already text or building a key from several typed columns
first (see [below](#building-ids-that-reproduce-across-engines) either way).

## Installation

```bash
pip install polars-uuid-plugin
```

(The PyPI distribution is named `polars-uuid-plugin`; the Python package you import
is `polars_uuid`.)

## Usage

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

- `uuid4(expr)` — a random UUID for each row. Only the length of `expr` matters; its
  values are ignored.
- `uuid5(expr, namespace)` — a deterministic UUID derived from `namespace` and each
  value of `expr`. Null input produces a null result. `namespace` is a `uuid.UUID` (e.g.
  `uuid.NAMESPACE_DNS`) or an equivalent UUID `str` — **not** a namespace name like
  `"dns"`, and not an arbitrary string that gets hashed into one. A `namespace` that
  doesn't parse as a UUID raises `pl.exceptions.ComputeError`. Output is byte-identical
  to Python's `uuid.uuid5` for the same namespace and value — checked continuously by
  [`test_uuid5_matches_stdlib_sweep`](tests/test_uuid.py), a seeded sweep over ~2,000
  generated strings (including multi-byte UTF-8) plus edge cases like the empty string
  and very long strings.
- `uuid7(expr)` — a random, time-ordered UUID for each row (sorts by creation time).
  Only the length of `expr` matters; its values are ignored.
- `is_valid_uuid(expr)` — whether each value of `expr` parses as a valid UUID. Null
  input produces a null result (not `False`).
- `uuid_version(expr)` — the version number (1-8) of each UUID string in `expr`. Null
  for invalid UUIDs or null input.
- `extract_timestamp(expr)` — the embedded creation timestamp of each time-based (v1,
  v6, v7) UUID in `expr`. Null for other versions, invalid UUIDs, or null input.

## Building ids that reproduce across engines

`uuid5` hashes text, so the id depends on how a typed value becomes text — and polars,
pandas, and Spark don't all agree on that conversion. If the same logical value needs to
produce the same id in more than one engine, never rely on a default string cast; fix
the format explicitly for every column.

- **Timestamps**: the default text depends on the `Datetime` time unit — `us` gives 6
  fraction digits, `ns` gives 9 — so a frame that arrived via `pl.from_pandas` (which
  defaults to `ns`) formats differently than one built natively in polars for the same
  instant. Fix the precision instead of casting:
  ```python
  pl.col("created_at").dt.to_string("%Y-%m-%d %H:%M:%S%.6f")
  ```
- **Integers**: normalize the width so an `Int16` column and an `Int64` column agree on
  the same number:
  ```python
  pl.col("code").cast(pl.Int64).cast(pl.String)
  ```
- **Dates**: pin the format rather than relying on the default:
  ```python
  pl.col("cohort_date").dt.to_string("%Y-%m-%d")
  ```
- **Nulls**: give them text, so a null can't silently vanish from a composite key. By
  default `pl.concat_str` propagates null (the whole key becomes null — safe), but
  `ignore_nulls=True` drops the null field instead: `("a", None, "c")` and
  `("a", "c", None)` then both produce `"a|c"`, colliding two different rows onto the
  same id.
  ```python
  expr.fill_null("\x1f")  # a control character that can't occur in normal data
  ```
  An empty string is a poor substitute for a sentinel — it makes a null and a real empty
  string hash to the same id, trading one collision for another.
- **Floats**: don't put them in a key. polars, pandas, and Spark each format `1e-05`
  differently (`0.00001`, `1e-05`, `1.0E-5` respectively), so the same number produces
  three different ids.

### A worked example: composite keys

Almost nobody hashes one text column — a real id is usually built from several typed
columns. Applying the rules above:

```python
import uuid
from datetime import date, datetime

import polars as pl
import polars_uuid

NULL_SENTINEL = "\x1f"  # a control character cannot occur in normal data

events_df = pl.DataFrame(
    {
        "cohort_date": [date(2026, 8, 9), date(2026, 8, 10)],
        "property_id": [3370, 42],  # Int64
        "occ_code": pl.Series([168, 7], dtype=pl.Int16),
        "created_at": [datetime(2026, 8, 9, 7, 51, 1, 34000), None],
    }
)

key_expr = pl.concat_str(
    [
        pl.col("cohort_date").dt.to_string("%Y-%m-%d"),
        pl.col("property_id").cast(pl.Int64).cast(pl.String),
        pl.col("occ_code").cast(pl.Int64).cast(pl.String),
        pl.col("created_at").dt.to_string("%Y-%m-%d %H:%M:%S%.6f"),
    ],
    separator="|",
)

events_df = events_df.with_columns(
    polars_uuid.uuid5(key_expr.fill_null(NULL_SENTINEL), namespace=uuid.NAMESPACE_DNS)
    .alias("event_id")
)
```

Self-check against the stdlib, to confirm the built key text is what you think it is:

```python
expected = [
    str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
    for name in events_df.select(key_expr.fill_null(NULL_SENTINEL)).to_series()
]
assert events_df["event_id"].to_list() == expected
```

Note there's no `uuid5_from_columns`-style helper for this — the separator, the null
sentinel, and each column's text format are choices that have to match whatever other
system reads the ids, so they belong to you, not to the library. This example shows the
pattern; it's deliberately not baked into a function.

None of this is about the hash itself — `uuid5`'s output is byte-identical to Python's
stdlib `uuid.uuid5` regardless of which engine calls it (see above). Every case above is
about the text you hand it not being the text you think it is.

## Developing and Testing

This project is a Rust-backed Polars plugin built with [maturin](https://www.maturin.rs/)
and [pyo3-polars](https://github.com/pola-rs/pyo3-polars). The compiled extension is
imported by Python as `polars_uuid._internal`.

A Rust toolchain (`cargo`) and [uv](https://docs.astral.sh/uv/) are required. Everything
else (including `maturin`, `pytest`, etc.) is declared in `pyproject.toml`; `uv run`
installs it on demand.

### Quick start

All commands below are run from the **repository root** (the `Makefile` handles `cd`ing
into this nested project directory for you).

```bash
make sync        # 1. create/update the virtual environment (first time only)
make install     # 2. compile the Rust extension and install it
make test        # 3. run the tests
```

The development cycle is then:

1. Edit the Rust (`src/`) or Python (`polars_uuid/`) source.
2. `make install` — rebuild and install the extension.
3. `make test` (or `make run`) — verify your changes.

### Makefile

A `Makefile` at the **repository root** wraps the common commands so you don't have to
`cd` into this nested project directory. Run any of these from the repo root:

| Command | What it does |
| --- | --- |
| `make help` | List all available targets |
| `make sync` | `uv sync` — create/update the virtual environment |
| `make install` | Compile the Rust extension and install it (debug build) |
| `make install-release` | Same, with optimizations (release build) |
| `make test` | Build, then run the test suite with `pytest` |
| `make run` | Build, then run `run.py` (a scratchpad for trying the plugin) |
| `make pre-commit` | Format and lint Rust (`cargo fmt`/`clippy`) and Python (`ruff`) |
| `make clean` | `cargo clean` |

The sections below describe what those targets do under the hood.

### Build & install (the dev loop)

```bash
make install            # or: uv run maturin develop
make install-release    # or: uv run maturin develop --release
```

`maturin develop` compiles the Rust **and** installs the correctly named
`_internal.abi3.so` into the package in one step.

> **Do not use `cargo build` for the dev loop.** It produces
> `target/debug/libpolars_uuid.so`, which is *not* the file Python imports
> (`polars_uuid/_internal.abi3.so`). Use `cargo check` / `cargo build` only as a quick
> "does it compile?" check. Use `maturin develop` to actually update what Python loads.

### Testing

Tests live in `tests/` and run with `pytest`:

```bash
make test               # or: uv run pytest
```

`make test` builds the extension first, so it always tests your latest Rust changes.

### Trying it out

`run.py` is a small scratchpad for exercising the plugin:

```bash
make run                # or: uv run python run.py
```

### Using in a Jupyter notebook

Register this project's virtual environment as a Jupyter kernel **once** (re-run only if
the venv path changes):

```bash
uv run python -m ipykernel install \
    --user \
    --name polars-uuid \
    --display-name "Python (polars-uuid)"
```

Then select the **Python (polars-uuid)** kernel in the notebook. After rebuilding the
extension (`make install`), restart the kernel to pick up the change.

### Troubleshooting

If `import polars_uuid` fails or an attribute like `uuid4` is "missing", the compiled
extension is usually stale or mismatched. Useful checks:

```bash
# Surfaces the real ImportError if the module is broken
uv run python -c "import polars_uuid"

# Confirm which files are actually being imported
uv run python -c "import polars_uuid, polars_uuid._internal as i; print(polars_uuid.__file__); print(i.__file__)"

# Verify the extension exports its init symbol (PyInit__internal must be present)
nm -D --defined-only polars_uuid/_internal.abi3.so | grep PyInit
```

The fix is almost always to rebuild with `uv run maturin develop`.

### Releasing

Releases are built and published to PyPI automatically by
[`.github/workflows/publish_to_pypi.yml`](../.github/workflows/publish_to_pypi.yml),
authenticating via PyPI [trusted publishing](https://docs.pypi.org/trusted-publishers/)
(OIDC — no API token involved). Every push and PR runs the test matrix; only pushing a
tag triggers a publish attempt.

The Python package version is **not** set in `pyproject.toml` (`dynamic = ["version"]`)
— maturin reads it from `Cargo.toml`'s `[package] version` field.

To cut a release:

1. Bump `version` in `Cargo.toml`.
2. Run `make install` once locally so `Cargo.lock` picks up the new version, then
   commit both files (e.g. `git commit -am "Bump version to 0.2.0"`).
3. Tag the commit and push the tag:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
4. This triggers the workflow's `linux`/`windows`/`macos`/`sdist` jobs to build wheels,
   then the `release` job. That job targets the `pypi` GitHub environment, which
   requires manual approval — go to the workflow run under the repo's **Actions** tab
   and approve the pending deployment.
5. Once approved, the wheels are published to PyPI. The publish step passes
   `--skip-existing`, so re-running a workflow for a version already on PyPI is a
   no-op rather than a failure (PyPI itself still rejects re-uploading the same
   version with different contents).

To sanity-check the build/wheel steps without publishing, trigger the workflow
manually from the **Actions** tab (`workflow_dispatch`) on a non-tag ref — it runs
everything except the final publish step.
