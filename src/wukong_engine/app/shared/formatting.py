"""Formatting of durations, sizes and counts for people to read."""

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
BYTES_PER_UNIT = 1024
COUNT_UNITS = ((1_000_000_000, 'B'), (1_000_000, 'M'))  # Largest first


def format_duration(seconds: float) -> str:
    """Format a duration for people to read, with the precision that matters at its scale.

    Args:
        seconds: Duration in seconds.

    Returns:
        The duration as milliseconds (``12ms``), seconds with a decimal (``3.2s``), minutes and seconds (``4m 05s``)
        or hours and minutes (``2h 03m``).
    """
    if seconds < 1:
        return f'{seconds * 1000:.0f}ms'
    if seconds < SECONDS_PER_MINUTE:
        return f'{seconds:.1f}s'
    if seconds < SECONDS_PER_HOUR:
        minutes, rest = divmod(round(seconds), SECONDS_PER_MINUTE)
        return f'{minutes}m {rest:02d}s'
    hours, rest = divmod(round(seconds), SECONDS_PER_HOUR)
    return f'{hours}h {rest // SECONDS_PER_MINUTE:02d}m'


def format_size(size: int) -> str:
    """Format a size in bytes for people to read.

    Args:
        size: Size in bytes.

    Returns:
        The size in the largest binary unit that keeps it at least 1, with a decimal above bytes (``1.2 MB``).
    """
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < BYTES_PER_UNIT or unit == 'GB':
            return f'{size} B' if unit == 'B' else f'{value:.1f} {unit}'
        value /= BYTES_PER_UNIT
    raise AssertionError  # Unreachable: the loop returns at its last unit


def format_count(count: int) -> str:
    """Format a count for people to read, shortening it from a million up.

    Args:
        count: Count to format.

    Returns:
        The count in millions or billions with two decimals (``12.35 M``, ``1.20 B``), or in full with thousands
        separators below a million (``987,654``).
    """
    for scale, unit in COUNT_UNITS:
        if abs(count) >= scale:
            return f'{count / scale:.2f} {unit}'
    return f'{count:,}'
