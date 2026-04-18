# ============================================================
# src/utils/helpers.py — Shared Helper Functions
# ============================================================
# Small, reusable utilities used across the project.
# ============================================================

import datetime
import re


def format_duration_since(start: datetime.datetime, now: datetime.datetime) -> str:
    """
    Return a human-readable duration string between two datetimes.
    Example: "2 months 1 week 3 days 5 hours and 12 minutes"
    """
    year_diff = now.year - start.year
    months = year_diff * 12 + now.month - start.month

    comparison_start = start.replace(year=now.year, month=now.month)
    if now < comparison_start:
        months -= 1

    def add_months(dt, count):
        month = dt.month - 1 + count
        year = dt.year + month // 12
        month = month % 12 + 1
        day = min(
            dt.day,
            [31, 29 if (year % 400 == 0 or (year % 100 != 0 and year % 4 == 0)) else 28,
             31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
        )
        return dt.replace(year=year, month=month, day=day)

    month_anchor = add_months(start, months)
    remainder = now - month_anchor

    weeks   = remainder.days // 7
    days    = remainder.days % 7
    hours   = remainder.seconds // 3600
    minutes = (remainder.seconds % 3600) // 60

    # Build parts from largest to smallest
    parts = []
    if months > 0:
        parts.extend([
            f"{months} month{'s' if months != 1 else ''}",
            f"{weeks} week{'s' if weeks != 1 else ''}",
            f"{days} day{'s' if days != 1 else ''}",
            f"{hours} hour{'s' if hours != 1 else ''}",
            f"{minutes} minute{'s' if minutes != 1 else ''}",
        ])
    elif weeks > 0:
        parts.extend([
            f"{weeks} week{'s' if weeks != 1 else ''}",
            f"{days} day{'s' if days != 1 else ''}",
            f"{hours} hour{'s' if hours != 1 else ''}",
            f"{minutes} minute{'s' if minutes != 1 else ''}",
        ])
    elif days > 0:
        parts.extend([
            f"{days} day{'s' if days != 1 else ''}",
            f"{hours} hour{'s' if hours != 1 else ''}",
            f"{minutes} minute{'s' if minutes != 1 else ''}",
        ])
    elif hours > 0:
        parts.extend([
            f"{hours} hour{'s' if hours != 1 else ''}",
            f"{minutes} minute{'s' if minutes != 1 else ''}",
        ])
    else:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    # Drop zero-value parts and add "and" before the last one
    visible = [p for p in parts if not p.startswith("0 ")]
    if len(visible) > 1 and visible[-1].endswith("minute"):
        visible[-1] = "and " + visible[-1]
    return " ".join(visible)


def create_progress_bar(current: int, target: int, length: int = 10) -> str:
    """Return a text-based progress bar like ████░░░░░░"""
    if target == 0:
        return "█" * length
    progress = min(current / target, 1.0)
    filled = int(progress * length)
    empty  = length - filled
    return "█" * filled + "░" * empty


# Regex for detecting custom & unicode emoji in messages
EMOJI_PATTERN = re.compile(
    r'<:\w+:\d+>|<a:\w+:\d+>'
    r'|[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF'
    r'\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]'
)
