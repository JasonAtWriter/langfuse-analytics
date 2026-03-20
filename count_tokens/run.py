"""Script to count tokens sent to and received from the reranker preprocessor.

Usage:
    uv run python -m count_tokens.run --from START --until END

Arguments:
    --start / --from    ISO 8601 timestamp, or relative offset like -1w, -3d, -6h, -30m
    --end / --until     ISO 8601 timestamp, relative offset like -1w, -3d, -6h, -30m,
                        or relative to start like start+1w, start+3d, start+6h, start+30m
    -o / --output       Optional location to write the results, otherwise prints to console

Examples:
    uv run python -m count_tokens.run --start -1w --end -6d
    uv run python -m count_tokens.run --start 2026-01-01T00:00:00 --end start+7d
"""

import argparse
import json
import logging
from datetime import datetime

from .datetime_utils import parse_end_relative_to_start, parse_relative_offset
from .logged_preprocessor_data import LoggedPreprocessorData

from dotenv import load_dotenv
from langfuse import get_client

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
TARGET_OBSERVATION_NAME = (
    "enterprise_knowledge_core.reranker.preprocessor.ColbertPreprocessor.select_chunks"
)


def main():
    start_time, end_time, output = parse_args()
    client = get_client()

    # Get initial page
    paginated_traces = client.api.trace.list(
        name="POST /search",
        page=1,
        limit=10,
        from_timestamp=start_time,
        to_timestamp=end_time,
        order_by="timestamp.desc",
    )
    if paginated_traces.meta.total_pages == 0:
        logger.info("No items found in given time range!")
        return

    # Read all remaining pages
    all_trace_ids: list[str] = []
    all_trace_ids.extend([trace.id for trace in paginated_traces.data])
    for page in range(2, paginated_traces.meta.total_pages + 1):
        paginated_traces = client.api.trace.list(
            name="POST /search",
            page=page,
            limit=10,
            from_timestamp=start_time,
            to_timestamp=end_time,
            order_by="timestamp.desc",
        )
        all_trace_ids.extend([trace.id for trace in paginated_traces.data])
    logger.info(f"Found {len(all_trace_ids)} traces")

    # Get relevant logged data
    logged_data: list[LoggedPreprocessorData] = []
    for trace_id in all_trace_ids:
        trace_with_full_details = client.api.trace.get(trace_id=trace_id)
        for observation in trace_with_full_details.observations:
            if observation.name == TARGET_OBSERVATION_NAME:
                try:
                    attributes = observation.metadata["attributes"]
                    data = LoggedPreprocessorData(
                        trace_id,
                        int(attributes["preprocessor.n_docs"]),
                        int(attributes["preprocessor.n_long_docs"]),
                        int(attributes["preprocessor.n_chunks"]),
                    )
                    logged_data.append(data)
                except Exception as e:
                    logger.error(
                        f"Preprocessor data could not be parsed: {json.dumps(observation.metadata)}"
                    )
                    logger.error(str(e))

    # Write results
    results = [ld.asdict() for ld in logged_data]
    if output is None:
        print(json.dumps(results, indent=2))
    else:
        with open(output, "w") as f:
            json.dump(results, f, indent=2)

    client.shutdown()


def parse_args() -> tuple[datetime, datetime, str | None]:
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
        "-o",
        "--output",
        default=None,
        help="Output file to write the results to",
    )
    args = parser.parse_args()

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

    return start_time, end_time, args.output


if __name__ == "__main__":
    main()
