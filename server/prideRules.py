"""
Pride's rules (spec §5), run on the server so the desktop and iOS always agree. Plain functions over plain values, no
Flask and no database, each table-tested in tests/test_rules.py. Milestone 2 has the planning rules (next up, the next
planned day, the week strip); milestone 3 adds suggestions, stalls and records. The stub imports this file too.
Weekdays are 0 = Monday … 6 = Sunday, as date.weekday() and ProgramDays have them.
"""
from datetime import timedelta


def nextUp(routineIds, latestRoutineId):
    """The routine after the latest workout's (by rotation order, wrapping round); the first with no workouts yet
    or when that routine is gone; None when the program has no routines."""
    if not routineIds:
        return None
    if latestRoutineId in routineIds:
        return routineIds[(routineIds.index(latestRoutineId) + 1) % len(routineIds)]
    return routineIds[0]


def plannedDay(today, weekdays, loggedToday):
    """The first planned weekday from today; today counts unless a workout is already logged today. None with no
    planned days. A missed day is never looked at."""
    for offset in range(1 if loggedToday else 0, 8):
        day = today + timedelta(days=offset)
        if day.weekday() in weekdays:
            return day
    return None


def weekStartDate(today, weekStart):
    back = today.weekday() if weekStart == "mon" else (today.weekday() + 1) % 7
    return today - timedelta(days=back)


def week(today, weekStart, weekdays, doneDates):
    """The 7 days of the week holding today (plan decision 22): done from any workout that day; planned only today
    and later, and never on a done day, so a past planned day with no workout shows nothing."""
    first = weekStartDate(today, weekStart)
    days = []
    for n in range(7):
        day = first + timedelta(days=n)
        done = day in doneDates
        days.append({"date": day.isoformat(), "weekday": day.weekday(), "done": done,
                     "planned": not done and day >= today and day.weekday() in weekdays})
    return days
