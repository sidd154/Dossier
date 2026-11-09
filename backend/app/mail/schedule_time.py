"""Pure next-run calculation for mail schedules.

Kept free of database access so it can be exhaustively tested across timezones,
weekdays, and month lengths.
"""

import calendar
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.mail.models import MailFrequency, MailSchedule


def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def compute_next_run(
    *,
    frequency: MailFrequency,
    time_of_day: time,
    weekday: int | None,
    day_of_month: int | None,
    timezone: str,
    after: datetime | None = None,
) -> datetime:
    """Return the next occurrence as an aware UTC datetime."""
    tz = ZoneInfo(timezone)
    reference = after or datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    local = reference.astimezone(tz)

    def at(day: date) -> datetime:
        return datetime.combine(day, time_of_day, tzinfo=tz)

    if frequency == MailFrequency.DAILY:
        candidate = at(local.date())
        if candidate <= local:
            candidate = at(local.date() + timedelta(days=1))
    elif frequency == MailFrequency.WEEKLY:
        target = weekday if weekday is not None else local.weekday()
        offset = (target - local.weekday()) % 7
        candidate = at(local.date() + timedelta(days=offset))
        if candidate <= local:
            candidate = at(local.date() + timedelta(days=offset + 7))
    else:
        target_day = day_of_month or local.day
        year, month = local.year, local.month
        candidate = at(date(year, month, min(target_day, _days_in_month(year, month))))
        if candidate <= local:
            month += 1
            if month == 13:
                month = 1
                year += 1
            candidate = at(
                date(year, month, min(target_day, _days_in_month(year, month)))
            )

    return candidate.astimezone(UTC)


def next_run_for_schedule(
    schedule: MailSchedule, *, after: datetime | None = None
) -> datetime:
    """Adapter from a MailSchedule row to the pure calculator."""
    return compute_next_run(
        frequency=schedule.frequency,
        time_of_day=schedule.time_of_day,
        weekday=schedule.weekday,
        day_of_month=schedule.day_of_month,
        timezone=schedule.timezone,
        after=after,
    )
