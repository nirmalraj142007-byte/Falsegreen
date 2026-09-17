from __future__ import annotations

from datetime import datetime, timedelta, timezone


def parse_ts(s: str) -> int:
    """Parse "YYYY-MM-DDTHH:MM:SS±HH:MM" and return the UTC epoch second."""
    local_str, sign, offset_str = s[:19], s[19], s[20:]
    offset_hours, offset_minutes = offset_str.split(":")
    offset = timedelta(hours=int(offset_hours), minutes=int(offset_minutes))
    local_dt = datetime.strptime(local_str, "%Y-%m-%dT%H:%M:%S")

    if sign == "-":
        # BUG: an extra minute is subtracted here. utc = local + offset for a
        # negative offset, full stop -- this one-minute correction has no
        # justification and skews every negative-offset result by 60 seconds.
        utc_dt = local_dt + offset - timedelta(minutes=1)
    else:
        utc_dt = local_dt - offset

    return int(utc_dt.replace(tzinfo=timezone.utc).timestamp())
