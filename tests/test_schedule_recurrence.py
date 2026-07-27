from datetime import date, time

from firelaw_api.schedule_recurrence import generate_visit_starts


def test_generate_monthly_visits_preserves_anchor_day_across_short_months():
    visits = generate_visit_starts(
        start_date=date(2026, 1, 31),
        preferred_start_time=time(9, 30),
        frequency="monthly",
        interval=1,
        end_date=date(2026, 4, 30),
    )

    assert [visit.isoformat() for visit in visits[:4]] == [
        "2026-01-31T09:30:00+08:00",
        "2026-02-28T09:30:00+08:00",
        "2026-03-31T09:30:00+08:00",
        "2026-04-30T09:30:00+08:00",
    ]


def test_generate_weekly_and_semiannual_visits_respect_generation_window():
    weekly = generate_visit_starts(
        start_date=date(2026, 8, 1),
        preferred_start_time=time(8, 0),
        frequency="weekly",
        interval=2,
        end_date=date(2026, 8, 31),
    )
    semiannual = generate_visit_starts(
        start_date=date(2026, 8, 1),
        preferred_start_time=time(9, 0),
        frequency="semiannual",
        interval=1,
        end_date=date(2027, 8, 1),
    )

    assert [visit.date().isoformat() for visit in weekly] == ["2026-08-01", "2026-08-15", "2026-08-29"]
    assert [visit.date().isoformat() for visit in semiannual] == ["2026-08-01", "2027-02-01", "2027-08-01"]


def test_generate_visits_defaults_to_eighteen_month_window():
    visits = generate_visit_starts(
        start_date=date(2026, 1, 1),
        preferred_start_time=time(9, 0),
        frequency="quarterly",
        interval=1,
        end_date=None,
    )

    assert visits[0].isoformat() == "2026-01-01T09:00:00+08:00"
    assert visits[-1].date().isoformat() == "2027-07-01"
