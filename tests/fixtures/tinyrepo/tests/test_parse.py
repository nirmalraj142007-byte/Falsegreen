from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tinyrepo.parse import parse_ts


def _expected_utc_epoch(local_str: str, hours: int, minutes: int) -> int:
    local_dt = datetime.strptime(local_str, "%Y-%m-%dT%H:%M:%S")
    utc_dt = local_dt - timedelta(hours=hours, minutes=minutes)
    return int(utc_dt.replace(tzinfo=timezone.utc).timestamp())


def test_positive_offset_five_thirty() -> None:
    assert parse_ts("2024-03-01T12:00:00+05:30") == _expected_utc_epoch(
        "2024-03-01T12:00:00", 5, 30
    )


def test_zero_offset() -> None:
    assert parse_ts("2024-06-15T00:00:00+00:00") == _expected_utc_epoch(
        "2024-06-15T00:00:00", 0, 0
    )


def test_positive_offset_nine_hours() -> None:
    assert parse_ts("2023-12-31T23:59:59+09:00") == _expected_utc_epoch(
        "2023-12-31T23:59:59", 9, 0
    )
