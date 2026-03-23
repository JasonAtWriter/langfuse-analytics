"""Script to count tokens sent to and received from the reranker preprocessor.

Usage:
    uv run python -m count_tokens.run --from START --until END

Arguments:
    --start / --from    ISO 8601 timestamp, or relative offset like -1w, -3d, -6h, -30m
    --end / --until     ISO 8601 timestamp, relative offset like -1w, -3d, -6h, -30m,
                        or relative to start like start+1w, start+3d, start+6h, start+30m
    --timeout           Per-request timeout in seconds (overrides LANGFUSE_TIMEOUT env var)
    --workers           Number of parallel time-window chunks (default: 1)
    --concurrency       Max simultaneous trace.get() requests per chunk (default: 10)
    -o / --output       Optional location to write the results, otherwise prints to console

Examples:
    uv run python -m count_tokens.run --start=-1w --end=-6d
    uv run python -m count_tokens.run --start=2026-01-01T00:00:00 --end=start+7d
    uv run python -m count_tokens.run --start=-1w --end=start+7d --workers=7 --timeout=60 --concurrency=10
"""

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime

from .datetime_utils import (
    parse_end_relative_to_start,
    parse_relative_offset,
    split_time_range,
)
from .fetcher import fetch_traces_in_window
from .logged_preprocessor_data import LoggedPreprocessorData

from dotenv import load_dotenv
from langfuse import get_client

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_all(
    client,
    start_time: datetime,
    end_time: datetime,
    n_workers: int,
    concurrency: int,
) -> list[LoggedPreprocessorData]:
    chunks = split_time_range(start_time, end_time, n_workers)
    tasks = [
        fetch_traces_in_window(
            client.async_api.trace, chunk_start, chunk_end, concurrency
        )
        for chunk_start, chunk_end in chunks
    ]
    chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

    all_data: list[LoggedPreprocessorData] = []
    for i, result in enumerate(chunk_results):
        if isinstance(result, BaseException):
            logger.error(
                f"Chunk {i} ({chunks[i][0].isoformat()} → {chunks[i][1].isoformat()}) "
                f"failed: {result}"
            )
        else:
            all_data.extend(result)
    return all_data


def main():
    start_time, end_time, n_workers, concurrency, output = parse_args()
    client = get_client()

    logged_data = asyncio.run(
        fetch_all(client, start_time, end_time, n_workers, concurrency)
    )
    logger.info(f"Total records collected: {len(logged_data)}")

    results = [ld.asdict() for ld in logged_data]
    if output is None:
        print(json.dumps(results, indent=2))
    else:
        with open(output, "w") as f:
            json.dump(results, f, indent=2)

    client.shutdown()


def parse_args() -> tuple[datetime, datetime, int, int, str | None]:
    parser = argparse.ArgumentParser(
        description="Download search traces in a timeframe, defaults to past hour."
    )
    parser.add_argument(
        "--start",
        "--from",
        default="-1h",
        help="Start time: ISO 8601 format or relative offset like -1w, -3d, -6h, -30m (default: -1h)",
        dest="start",
    )
    parser.add_argument(
        "--end",
        "--until",
        default="start+1h",
        help="End time: ISO 8601 format, relative offset like -1w, -3d, -6h, -30m, "
        "or relative to start like start+1w, start+3d (default: start+1h)",
        dest="end",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Per-request timeout in seconds (overrides LANGFUSE_TIMEOUT env var)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel time-window chunks to fetch concurrently (default: 1)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Max simultaneous trace.get() requests per chunk (default: 10)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output file to write the results to",
    )
    args = parser.parse_args()

    if args.timeout is not None:
        os.environ["LANGFUSE_TIMEOUT"] = str(args.timeout)

    offset = parse_relative_offset(args.start)
    if offset is not None:
        start_time = datetime.now() + offset
    else:
        try:
            start_time = datetime.fromisoformat(args.start)
        except Exception as e:
            raise ValueError(
                "Unable to parse start timestamp, must be ISO 8601 format or relative offset like -1w, -3d, -6h, -30m"
            ) from e

    end_time = parse_end_relative_to_start(args.end, start_time)
    if end_time is None:
        offset = parse_relative_offset(args.end)
        if offset is not None:
            end_time = datetime.now() + offset
        else:
            try:
                end_time = datetime.fromisoformat(args.end)
            except Exception as e:
                raise ValueError(
                    "Unable to parse end timestamp, must be ISO 8601 format, relative offset like -1w, -3d, -6h, -30m, "
                    "or relative to start like start+1w, start+3d"
                ) from e

    if start_time > end_time:
        raise ValueError("START must be less than or equal to END")

    if args.workers < 1:
        raise ValueError("--workers must be at least 1")
    if args.concurrency < 1:
        raise ValueError("--concurrency must be at least 1")

    return start_time, end_time, args.workers, args.concurrency, args.output


if __name__ == "__main__":
    main()
