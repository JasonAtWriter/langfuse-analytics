import re
from datetime import datetime, timedelta


def parse_relative_offset(value: str) -> timedelta | None:
    """Parse a relative offset like -1w, -3d, -6h, -30m into a (negative) timedelta.

    Returns None if the value does not match the expected format.
    Only whole-number increments are accepted.
    """
    match = re.fullmatch(r"^-(\d+)(w|d|h|m)$", value)
    if not match:
        return None
    n = int(match.group(1))
    unit = match.group(2)
    unit_map = {"w": "weeks", "d": "days", "h": "hours", "m": "minutes"}
    return -timedelta(**{unit_map[unit]: n})


def split_time_range(
    start: datetime, end: datetime, n_chunks: int
) -> list[tuple[datetime, datetime]]:
    """Split [start, end) into n_chunks equal sub-intervals."""
    chunk_size = (end - start) / n_chunks
    boundaries = [start + chunk_size * i for i in range(n_chunks)] + [end]
    return list(zip(boundaries[:-1], boundaries[1:]))


def parse_end_relative_to_start(value: str, start: datetime) -> datetime | None:
    """Parse an end time expressed relative to start, e.g. start+1w, start+3d.

    Returns None if the value does not match the expected format.
    Only whole-number increments are accepted.
    """
    match = re.fullmatch(r"^start\+(\d+)(w|d|h|m)$", value)
    if not match:
        return None
    n = int(match.group(1))
    unit = match.group(2)
    unit_map = {"w": "weeks", "d": "days", "h": "hours", "m": "minutes"}
    return start + timedelta(**{unit_map[unit]: n})
