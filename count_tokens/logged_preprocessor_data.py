import math
from dataclasses import asdict, dataclass

from .constants import (
    CHUNK_OVERLAP_WORDS,
    MAX_WORDS_PER_CHUNK,
    MAX_WORDS_PER_DOC,
    TOKENS_PER_WORD,
)


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
        return math.ceil(
            (n_short_doc_words + n_chunk_words - n_overlap_words) * TOKENS_PER_WORD
        )

    @property
    def prd_ub_n_tokens(self) -> int:
        """Upper bound on the number of tokens produced by the preprocessor (sent to reranker).
        Only one chunk per long document is selected to be sent."""
        return math.ceil(self.n_docs * MAX_WORDS_PER_DOC * TOKENS_PER_WORD)

    def asdict(self) -> dict[str, str | int]:
        result = asdict(self)
        result.update(
            {
                "n_short_docs": self.n_short_docs,
                "total_chunks": self.total_chunks,
                "rcv_ub_n_tokens": self.rcv_ub_n_tokens,
                "prd_ub_n_tokens": self.prd_ub_n_tokens,
            }
        )
        return result
