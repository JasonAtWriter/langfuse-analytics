from datetime import datetime, timedelta

from count_tokens.datetime_utils import (
    parse_end_relative_to_start,
    parse_relative_offset,
)


class TestParseRelativeOffset:
    def test_weeks(self):
        assert parse_relative_offset("-1w") == timedelta(weeks=-1)

    def test_days(self):
        assert parse_relative_offset("-3d") == timedelta(days=-3)

    def test_hours(self):
        assert parse_relative_offset("-6h") == timedelta(hours=-6)

    def test_minutes(self):
        assert parse_relative_offset("-30m") == timedelta(minutes=-30)

    def test_float_rejected(self):
        assert parse_relative_offset("-0.5h") is None

    def test_no_minus(self):
        assert parse_relative_offset("1h") is None

    def test_word(self):
        assert parse_relative_offset("now") is None

    def test_unknown_unit(self):
        assert parse_relative_offset("-1x") is None


class TestParseEndRelativeToStart:
    START = datetime(2026, 1, 1, 12, 0, 0)

    def test_weeks(self):
        assert parse_end_relative_to_start(
            "start+1w", self.START
        ) == self.START + timedelta(weeks=1)

    def test_days(self):
        assert parse_end_relative_to_start(
            "start+3d", self.START
        ) == self.START + timedelta(days=3)

    def test_hours(self):
        assert parse_end_relative_to_start(
            "start+6h", self.START
        ) == self.START + timedelta(hours=6)

    def test_minutes(self):
        assert parse_end_relative_to_start(
            "start+30m", self.START
        ) == self.START + timedelta(minutes=30)

    def test_float_rejected(self):
        assert parse_end_relative_to_start("start+0.5d", self.START) is None

    def test_relative_offset_not_matched(self):
        assert parse_end_relative_to_start("-1d", self.START) is None
