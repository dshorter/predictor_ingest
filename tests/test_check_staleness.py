"""Tests for the staleness pager's pure helpers (Sprint 20.4)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_staleness import _age_hours, _fmt_age, due_for_page

NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


class TestAgeHours:
    def test_datetime_with_z_suffix(self):
        assert _age_hours("2026-07-19T06:00:00Z", NOW) == 6.0

    def test_bare_date(self):
        # Dates parse as midnight UTC.
        assert _age_hours("2026-07-18", NOW) == 36.0

    def test_none_and_garbage(self):
        assert _age_hours(None, NOW) is None
        assert _age_hours("", NOW) is None
        assert _age_hours("not-a-date", NOW) is None

    def test_naive_datetime_assumed_utc(self):
        assert _age_hours("2026-07-19T00:00:00", NOW) == 12.0


class TestFmtAge:
    def test_hours_below_two_days(self):
        assert _fmt_age(36.0) == "36h"

    def test_days_at_two_days_and_beyond(self):
        assert _fmt_age(48.0) == "2.0d"
        assert _fmt_age(453.6) == "18.9d"


class TestDueForPage:
    def test_never_paged_is_due(self):
        assert due_for_page({}, "domain:film:docs", 24, NOW)

    def test_recent_page_not_due(self):
        state = {"domain:film:docs": "2026-07-19T00:00:00+00:00"}
        assert not due_for_page(state, "domain:film:docs", 24, NOW)

    def test_old_page_due_again(self):
        state = {"domain:film:docs": "2026-07-18T06:00:00+00:00"}
        assert due_for_page(state, "domain:film:docs", 24, NOW)
