from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from app.mail.models import MailFrequency
from app.mail.schedule_time import compute_next_run


def _dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def _run(frequency, *, at=time(9, 0), weekday=None, day_of_month=None, timezone="UTC", after):
    return compute_next_run(
        frequency=frequency,
        time_of_day=at,
        weekday=weekday,
        day_of_month=day_of_month,
        timezone=timezone,
        after=after,
    )


def test_daily_later_today() -> None:
    assert _run(
        MailFrequency.DAILY, after=_dt(2026, 1, 5, 8)
    ) == _dt(2026, 1, 5, 9)


def test_daily_rolls_to_tomorrow() -> None:
    assert _run(
        MailFrequency.DAILY, after=_dt(2026, 1, 5, 10)
    ) == _dt(2026, 1, 6, 9)


def test_daily_equal_time_rolls_to_tomorrow() -> None:
    assert _run(
        MailFrequency.DAILY, after=_dt(2026, 1, 5, 9)
    ) == _dt(2026, 1, 6, 9)


def test_weekly_same_day_later_in_week() -> None:
    # 2026-01-05 is a Monday (weekday 0).
    assert _run(
        MailFrequency.WEEKLY, weekday=2, after=_dt(2026, 1, 5, 10)
    ) == _dt(2026, 1, 7, 9)


def test_weekly_same_day_passed_rolls_a_week() -> None:
    assert _run(
        MailFrequency.WEEKLY, weekday=0, after=_dt(2026, 1, 5, 10)
    ) == _dt(2026, 1, 12, 9)


def test_monthly_clamps_to_short_month() -> None:
    # 2026 is not a leap year, so 31 January rolls to 28 February.
    assert _run(
        MailFrequency.MONTHLY, day_of_month=31, after=_dt(2026, 1, 31, 10)
    ) == _dt(2026, 2, 28, 9)


def test_monthly_rolls_into_next_year() -> None:
    assert _run(
        MailFrequency.MONTHLY, day_of_month=5, after=_dt(2026, 12, 6, 10)
    ) == _dt(2027, 1, 5, 9)


def test_timezone_is_respected() -> None:
    result = _run(
        MailFrequency.DAILY,
        at=time(9, 0),
        timezone="Asia/Kolkata",
        after=_dt(2026, 1, 5, 0, 0),
    )
    assert result == _dt(2026, 1, 5, 3, 30)


def test_dst_transition_stays_in_the_future() -> None:
    after = _dt(2026, 3, 28, 12)
    result = _run(
        MailFrequency.DAILY,
        at=time(2, 30),
        timezone="Europe/London",
        after=after,
    )
    assert result > after
    assert result.utcoffset() is not None
    assert result.utcoffset().total_seconds() == 0


def test_result_is_utc() -> None:
    result = _run(
        MailFrequency.DAILY,
        timezone="America/New_York",
        after=_dt(2026, 1, 5, 0),
    )
    assert result.tzinfo == UTC


def test_local_hour_matches_request() -> None:
    result = _run(
        MailFrequency.DAILY,
        at=time(18, 30),
        timezone="Europe/London",
        after=_dt(2026, 6, 1, 0),
    )
    assert result.astimezone(ZoneInfo("Europe/London")).hour == 18
    assert result.astimezone(ZoneInfo("Europe/London")).minute == 30
