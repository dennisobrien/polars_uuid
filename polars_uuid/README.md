# polars-uuid

A [Polars](https://pola.rs/) plugin that adds UUID generation and introspection
expressions, implemented in Rust for speed (see `notebooks/benchmarks.ipynb` — the
plugin is roughly 9-25x faster than the equivalent naive Python loop in polars or
pandas).

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
- `uuid5(expr, namespace)` — a deterministic UUID derived from `namespace` (a `str` or
  `uuid.UUID`, e.g. `uuid.NAMESPACE_DNS`) and each value of `expr`.
- `uuid7(expr)` — a random, time-ordered UUID for each row (sorts by creation time).
  Only the length of `expr` matters; its values are ignored.
- `is_valid_uuid(expr)` — whether each value of `expr` parses as a valid UUID. Null
  input produces a null result (not `False`).
- `uuid_version(expr)` — the version number (1-8) of each UUID string in `expr`. Null
  for invalid UUIDs or null input.
- `extract_timestamp(expr)` — the embedded creation timestamp of each time-based (v1,
  v6, v7) UUID in `expr`. Null for other versions, invalid UUIDs, or null input.

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
