SHELL=/bin/bash

# The actual Rust/Python project lives in a nested subdirectory.
# Every target runs from there, so you can invoke `make` from the repo root.
PROJECT_DIR=polars_uuid

.PHONY: help sync install install-release pre-commit test run clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

sync:  ## Create/update the uv-managed virtual environment
	cd $(PROJECT_DIR) && uv sync

install:  ## Compile the Rust extension and install it (debug build)
	cd $(PROJECT_DIR) && uv run maturin develop

install-release:  ## Compile and install with optimizations (release build)
	cd $(PROJECT_DIR) && uv run maturin develop --release

pre-commit:  ## Format and lint Rust + Python
	cd $(PROJECT_DIR) && cargo fmt --all
	cd $(PROJECT_DIR) && cargo clippy --all-features
	cd $(PROJECT_DIR) && uvx ruff check . --fix
	cd $(PROJECT_DIR) && uvx ruff format polars_uuid

test: install  ## Run the test suite
	cd $(PROJECT_DIR) && uv run pytest

run: install  ## Build then run run.py
	cd $(PROJECT_DIR) && uv run python run.py

clean:  ## Remove Rust build artifacts
	cd $(PROJECT_DIR) && cargo clean
