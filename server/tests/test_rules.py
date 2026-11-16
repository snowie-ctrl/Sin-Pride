"""prideRules' planning rules against spec §5 and plan decision 22: tables, one row per case."""
from datetime import date, timedelta

import pytest

from conftest import loadModule

rules = loadModule("prideRules")
SUN = date(2026, 11, 15)          # a Sunday
MON, TUE, WED, SAT = (SUN + timedelta(days=n) for n in (1, 2, 3, 6))


@pytest.mark.parametrize("routines,latest,want", [
    ([], None, None),                 # a program with no routines has nothing next
    ([10, 11, 12], None, 10),         # no workouts yet: the first
    ([10, 11, 12], 10, 11),
    ([10, 11, 12], 12, 10),           # wraps round
    ([10, 11, 12], 99, 10),           # that routine is gone: the first
    ([10, 11, 12], 11, 12),           # logging a different routine moves on from the one logged
    ([10], 10, 10),
])
def test_nextUp(routines, latest, want):
    assert rules.nextUp(routines, latest) == want


@pytest.mark.parametrize("today,days,logged,want", [
    (MON, set(), False, None),        # no planned days: "whenever you're ready"
    (MON, {0, 2, 4}, False, MON),     # today counts
    (MON, {0, 2, 4}, True, WED),      # unless a workout is already logged today
    (TUE, {0, 2, 4}, False, WED),
    (SAT, {0, 2, 4}, False, SAT + timedelta(days=2)),   # wraps past Sunday
    (MON, {0}, True, MON + timedelta(days=7)),          # only today planned and already logged: next week
    (SUN, {6}, False, SUN),
])
def test_plannedDay(today, days, logged, want):
    assert rules.plannedDay(today, days, logged) == want


@pytest.mark.parametrize("today,start,want", [
    (WED, "mon", MON), (MON, "mon", MON), (SUN, "mon", SUN - timedelta(days=6)),
    (SUN, "sun", SUN), (SAT, "sun", SUN), (WED, "sun", SUN),
])
def test_weekStartDate(today, start, want):
    assert rules.weekStartDate(today, start) == want


def test_week():
    days = rules.week(WED, "mon", {0, 2, 4}, {MON})
    assert [d["date"] for d in days] == [(MON + timedelta(days=n)).isoformat() for n in range(7)]
    assert [d["weekday"] for d in days] == list(range(7))
    assert [d["done"] for d in days] == [True, False, False, False, False, False, False]
    # Planned only today and later, never a past day with no workout, never a done day.
    assert [d["planned"] for d in days] == [False, False, True, False, True, False, False]


def test_aDoneDayIsNotAlsoPlanned():
    days = rules.week(MON, "mon", {0}, {MON})
    assert days[0]["done"] is True and days[0]["planned"] is False


def test_aSundayWeekStartingOnSunday():
    days = rules.week(SUN, "sun", {6, 0}, set())
    assert days[0]["date"] == SUN.isoformat() and days[0]["weekday"] == 6
    assert [d["weekday"] for d in days] == [6, 0, 1, 2, 3, 4, 5]
    assert days[0]["planned"] is True and days[1]["planned"] is True


def test_aMissedDayIsNeverShownAsPlanned():
    # Monday and Tuesday are planned weekdays that passed with no workout: they show nothing, today still plans.
    days = rules.week(WED, "mon", {0, 1, 2}, set())
    assert [d["planned"] for d in days[:3]] == [False, False, True]
    assert [d["done"] for d in days[:3]] == [False, False, False]
