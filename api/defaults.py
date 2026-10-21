"""Single source of truth for the default analysis window.

Water year runs Oct 1 - Sep 30. The default window starts at WY1986 (1985-10-01)
and ends on the last day of the most recent *complete* water year, resolved at
call time so a long-running server rolls over on its own each Oct 1.
"""

from __future__ import annotations

from datetime import date

DEFAULT_START = date(1985, 10, 1)


def _today() -> date:
    return date.today()


def last_complete_water_year_end(today: date | None = None) -> date:
    """Sep 30 closing the latest complete water year as of ``today``.

    On or after Oct 1 of year Y the water year that ended Sep 30 of Y is complete;
    before that (including Sep 30 itself) the last complete one ended in Y-1.
    """
    today = today or _today()
    year = today.year if today >= date(today.year, 10, 1) else today.year - 1
    return date(year, 9, 30)


def default_window(today: date | None = None) -> tuple[date, date]:
    return DEFAULT_START, last_complete_water_year_end(today)
