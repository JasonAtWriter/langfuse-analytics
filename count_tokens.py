import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from dotenv import load_dotenv
from langfuse import get_client

load_dotenv()

MAX_WORDS_PER_DOC   = 350
TOKENS_PER_WORD     = 510 / MAX_WORDS_PER_DOC  # 350 words ~= 510 ColBERT tokens
MAX_WORDS_PER_CHUNK = 300
CHUNK_OVERLAP_WORDS = 50


@dataclass
class LoggedPreprocessorData:
    # ID of the trace this data came from, for refernce purposes
    trace_id: str
    # Number of documents received by the preprocessor (returned by search)
    n_docs: int
    # Number of documents which are over the reranker's token limit (n_long_docs <= n_docs)
    n_long_docs: int
    # Number of chunks constructed from the long documents
    n_chunks: int

    @property
    def n_short_docs(self) -> int:
        """Number of short documents (word count less than max words per doc)."""
        return self.n_docs - self.n_long_docs

    @property
    def total_chunks(self) -> int:
        """The total number of chunks to send to the reranker."""
        return self.n_docs + self.n_chunks

    @property
    def rcv_ub_n_tokens(self) -> int:
        """Upper bound on the number of tokens received by the preprocessor (from search)."""
        n_short_doc_words = self.n_short_docs * MAX_WORDS_PER_DOC
        n_chunk_words = self.n_chunks * MAX_WORDS_PER_CHUNK
        n_overlap_words = (self.n_chunks - 1) * CHUNK_OVERLAP_WORDS
        return math.ceil((n_short_doc_words + n_chunk_words - n_overlap_words) * TOKENS_PER_WORD)

    @property
    def prd_ub_n_tokens(self) -> int: 
        """Upper bound on the number of tokens produced by the preprocessor (sent to reranker).
        Only one chunk per long document is selected to be sent."""
        return math.ceil(self.n_docs * MAX_WORDS_PER_DOC * TOKENS_PER_WORD)

    def asdict(self) -> dict[str, str | int]:
        result = asdict(self)
        result.update({
            'n_short_docs': self.n_short_docs,
            'total_chunks': self.total_chunks,
            'rcv_ub_n_tokens': self.rcv_ub_n_tokens,
            'prd_ub_n_tokens': self.prd_ub_n_tokens,
        })
        return result


def main():
    start_time, end_time = parse_args()
    client = get_client()

    # Get initial page
    paginated_traces = client.api.trace.list(
        name='POST /search',
        page=1,
        limit=10,
        from_timestamp=start_time,
        to_timestamp=end_time,
        order_by='timestamp.desc',
    )
    if paginated_traces.meta.total_pages == 0:
        print('No items found in given time range!')
        return

    # Read all remaining pages
    all_trace_ids: list[str] = []
    all_trace_ids.extend([trace.id for trace in paginated_traces.data])
    for page in range(2, paginated_traces.meta.total_pages + 1):
        paginated_traces = client.api.trace.list(
            name='POST /search',
            page=page,
            limit=10,
            from_timestamp=start_time,
            to_timestamp=end_time,
            order_by='timestamp.desc',
        )
        all_trace_ids.extend([trace.id for trace in paginated_traces.data])

    # Get relevant logged data
    logged_data: list[LoggedPreprocessorData] = []
    target_observation_name = 'enterprise_knowledge_core.reranker.preprocessor.ColbertPreprocessor.select_chunks'
    for trace_id in all_trace_ids:
        trace_with_full_details = client.api.trace.get(trace_id=trace_id)
        for observation in trace_with_full_details.observations:
            if observation.name == target_observation_name:
                attributes = observation.metadata['attributes']
                logged_data.append(
                    LoggedPreprocessorData(
                        trace_id,
                        int(attributes['preprocessor.n_docs']),
                        int(attributes['preprocessor.n_long_docs']),
                        int(attributes['preprocessor.n_chunks']),
                    )
                )
    print(json.dumps([ld.asdict() for ld in logged_data], indent=2))

    client.shutdown()


def parse_args() -> tuple[datetime, datetime]:
    parser = argparse.ArgumentParser(
        description='Download search traces in a timeframe, defaults to past hour.'
    )
    parser.add_argument(
        '--start',
        '--from',
        default=(datetime.now() - timedelta(hours=1)).isoformat(),
        help='Start time (ISO 8601 format) to retrieve search traces (inclusive)',
        dest='start',
    )
    parser.add_argument(
        '--end',
        '--until',
        default=datetime.now().isoformat(),
        help='End time (ISO 8601 format) to retrieve search traces (exclusive)',
        dest='end',
    )
    args = parser.parse_args()

    try:
        start_time = datetime.fromisoformat(args.start)
    except Exception as e:
        raise ValueError('Unable to parse start timestamp, must be ISO 8601 format') from e
    try:
        end_time = datetime.fromisoformat(args.end)
    except Exception as e:
        raise ValueError('Unable to parse end timestamp, must be ISO 8601 format') from e

    if start_time > end_time:
        raise ValueError('START must be less than or equal to END')

    return start_time, end_time


if __name__ == '__main__':
    main()

