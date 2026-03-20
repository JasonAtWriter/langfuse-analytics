# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the main script (default: past 1 hour)
uv run python -m count_tokens.run

# Run with specific time range
uv run python -m count_tokens.run --start -1w --end start+7d
uv run python -m count_tokens.run --start 2026-01-01T00:00:00 --end 2026-01-08T00:00:00

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/count_tokens/test_datetime_utils.py
```

## CLI Arguments

`--start` / `--from`: ISO 8601 timestamp or relative offset (`-1w`, `-3d`, `-6h`, `-30m`). Default: `-1h`.

`--end` / `--until`: ISO 8601 timestamp, relative offset, or relative to start (`start+1w`, `start+3d`). Default: `start+1h`.

## Architecture

The script queries LangFuse for traces named `"POST /search"` in a time window, then for each trace finds the observation named `enterprise_knowledge_core.reranker.preprocessor.ColbertPreprocessor.select_chunks` and extracts preprocessor metadata (`n_docs`, `n_long_docs`, `n_chunks`).

That raw data is wrapped in `LoggedPreprocessorData` (a dataclass in `logged_preprocessor_data.py`), which computes derived metrics using constants from `constants.py` (ColBERT token/word ratios, chunk size limits). The results are serialized to JSON via `.asdict()`.

`datetime_utils.py` handles the flexible time-argument parsing used by `run.py`.

## Environment

Requires a `.env` file with `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_HOST`.
