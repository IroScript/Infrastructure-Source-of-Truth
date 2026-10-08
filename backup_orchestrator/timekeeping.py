"""Monotonic Timekeeping & Asia/Dhaka Filename Formatting (Sections 43, 56)."""
from __future__ import annotations

import datetime
import secrets
import time
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python < 3.9 fallback if ever needed
    from datetime import timezone, timedelta
    class ZoneInfo:  # type: ignore
        def __init__(self, key: str):
            self.key = key
        def utcoffset(self, dt):
            return timedelta(hours=6)
        def tzname(self, dt):
            return "BDT"
        def dst(self, dt):
            return timedelta(0)


class Clock:
    """Abstract clock interface providing monotonic and timezone-aware wall time."""

    def monotonic(self) -> float:
        raise NotImplementedError

    def now_bdt(self) -> datetime.datetime:
        raise NotImplementedError


class RealClock(Clock):
    """Production clock using OS monotonic clock and Asia/Dhaka wall clock."""

    def __init__(self, tz_name: str = "Asia/Dhaka"):
        self.tz = ZoneInfo(tz_name)

    def monotonic(self) -> float:
        return time.monotonic()

    def now_bdt(self) -> datetime.datetime:
        return datetime.datetime.now(self.tz)


class InjectableClock(Clock):
    """Deterministic injectable clock for testing boundaries without sleeping real time."""

    def __init__(self, initial_mono: float = 1000.0, initial_wall_bdt: Optional[datetime.datetime] = None):
        self._mono = initial_mono
        self.tz = ZoneInfo("Asia/Dhaka")
        self._wall = initial_wall_bdt or datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=self.tz)

    def monotonic(self) -> float:
        return self._mono

    def now_bdt(self) -> datetime.datetime:
        return self._wall

    def advance(self, seconds: float) -> None:
        self._mono += seconds
        self._wall += datetime.timedelta(seconds=seconds)

    def set_monotonic(self, mono: float) -> None:
        self._mono = mono


def generate_backup_filename(project_slug: str, clock: Clock, unique_suffix: Optional[str] = None) -> str:
    """
    Generates compliant backup filename:
    <ProjectSlug>__YYYY-MM-DD__HH-mm-ss__BDT[__<unique>].zip
    """
    dt = clock.now_bdt()
    time_str = dt.strftime("%Y-%m-%d__%H-%M-%S__BDT")
    if not unique_suffix:
        unique_suffix = secrets.token_hex(4)
    return f"{project_slug}__{time_str}__{unique_suffix}.zip"
