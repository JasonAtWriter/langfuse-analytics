"""Async helpers for fetching trace data from LangFuse."""

import asyncio
import json
import logging
from datetime import datetime

from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from .logged_preprocessor_data import LoggedPreprocessorData

logger = logging.getLogger(__name__)

TARGET_OBSERVATION_NAME = (
    "enterprise_knowledge_core.reranker.preprocessor.ColbertPreprocessor.select_chunks"
)


def _parse_int_attribute(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return int(json.loads(value)["intValue"])


async def fetch_traces_in_window(
    async_trace_client,
    start_time: datetime,
    end_time: datetime,
    concurrency: int = 10,
    page_limit: int = 50,
) -> list[LoggedPreprocessorData]:
    """Fetch and parse all preprocessor trace data in [start_time, end_time).

    Paginates through all matching traces, then concurrently fetches full
    details for each trace ID, bounded by `concurrency` simultaneous requests.
    """
    # Phase 1: collect all trace IDs in window
    page = await async_trace_client.list(
        name="POST /search",
        page=1,
        limit=page_limit,
        from_timestamp=start_time,
        to_timestamp=end_time,
        order_by="timestamp.desc",
    )
    if page.meta.total_pages == 0:
        return []

    all_trace_ids: list[str] = [t.id for t in page.data]
    for page_num in range(2, page.meta.total_pages + 1):
        page = await async_trace_client.list(
            name="POST /search",
            page=page_num,
            limit=page_limit,
            from_timestamp=start_time,
            to_timestamp=end_time,
            order_by="timestamp.desc",
        )
        all_trace_ids.extend(t.id for t in page.data)

    logger.info(
        f"Window {start_time.isoformat()} → {end_time.isoformat()}: "
        f"found {len(all_trace_ids)} traces"
    )

    # Phase 2: fetch each trace concurrently, bounded by semaphore
    sem = asyncio.Semaphore(concurrency)

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=1, max=30),
        reraise=True,
    )
    async def get_one(trace_id: str) -> LoggedPreprocessorData | None:
        async with sem:
            trace = await async_trace_client.get(trace_id=trace_id)
        for obs in trace.observations:
            if obs.name == TARGET_OBSERVATION_NAME:
                try:
                    attrs = obs.metadata["attributes"]
                    return LoggedPreprocessorData(
                        trace_id,
                        _parse_int_attribute(attrs["preprocessor.n_docs"]),
                        _parse_int_attribute(attrs["preprocessor.n_long_docs"]),
                        _parse_int_attribute(attrs["preprocessor.n_chunks"]),
                    )
                except Exception as e:
                    logger.error(
                        f"Preprocessor data could not be parsed: {json.dumps(obs.metadata)}"
                    )
                    logger.error(str(e))
        return None

    results = await asyncio.gather(
        *[get_one(tid) for tid in all_trace_ids], return_exceptions=True
    )
    data: list[LoggedPreprocessorData] = []
    for tid, result in zip(all_trace_ids, results):
        if isinstance(result, BaseException):
            logger.error(f"Failed to fetch trace {tid}: {result}")
        elif result is not None:
            data.append(result)
    return data
