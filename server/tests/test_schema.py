"""schema.sql against spec §3: every table, the house engine, no SET/ENUM/JSON, word CHECKs in step with
prideCatalog, the foreign keys that keep history whole, the indexes and the limits."""
import pathlib
import re

from conftest import loadModule

SCHEMA = (pathlib.Path(__file__).resolve().parent.parent / "schema.sql").read_text(encoding="utf-8")
TABLES = {"Users", "Devices", "Sessions", "LoginKeys", "Profiles", "UserEquipment", "Exercises", "ExerciseMuscles",
          "ExerciseEquipment", "ExerciseSteps", "ExercisePictures", "CatalogVersion", "Programs", "ProgramDays",
          "Routines", "RoutineItems", "Workouts", "WorkoutExercises", "WorkoutSets", "Suggestions"}


def block(table):
    return re.search(rf"CREATE TABLE {table} \((.*?)\n\)", SCHEMA, re.S).group(1)


def checkWords(table, column):
    found = re.search(rf"CHECK \((?:{column} IS NULL OR )?{column} IN \(([^)]*)\)\)", block(table))
    assert found, (table, column)
    return tuple(re.findall(r"'([^']*)'", found.group(1)))


def test_everyTableOfTheSpecIsThere():
    assert set(re.findall(r"CREATE TABLE (\w+)", SCHEMA)) == TABLES


def test_everyTableUsesTheHouseEngineAndCollation():
    tails = re.findall(r"CREATE TABLE \w+ \((?:.*?)\n\)(.*?);", SCHEMA, re.S)
    assert len(tails) == len(TABLES)
    for tail in tails:
        assert tail.strip() == "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci"


def test_noSetEnumOrJsonColumns():
    body = "\n".join(line for line in SCHEMA.splitlines() if not line.startswith("--"))
    assert not re.search(r"\b(SET|ENUM)\s*\(|\bJSON\b", body)


def test_nothingIsAlteredOrDropped():
    assert not re.search(r"\b(ALTER|DROP)\s+TABLE\b", SCHEMA)


def test_theWordChecksMatchPrideCatalog():
    c = loadModule("prideCatalog")
    assert checkWords("Exercises", "Measure") == c.MEASURES
    assert checkWords("Exercises", "Region") == c.REGIONS
    assert checkWords("Exercises", "Level") == c.LEVELS
    assert checkWords("Exercises", "Category") == c.CATEGORIES
    assert checkWords("ExerciseMuscles", "Muscle") == c.MUSCLES
    assert checkWords("ExerciseMuscles", "Role") == c.ROLES
    assert checkWords("ExerciseEquipment", "Equipment") == c.EQUIPMENT
    assert checkWords("UserEquipment", "Equipment") == c.EQUIPMENT


def test_theProfilesWordsAreTheSpecs():
    assert checkWords("Profiles", "Units") == ("lb", "kg")
    assert checkWords("Profiles", "Goal") == ("strength", "muscle", "general")
    assert checkWords("Profiles", "WeekStart") == ("mon", "sun")
    assert checkWords("Profiles", "IntroState") == ("pending", "done", "skipped")
    assert checkWords("Suggestions", "Kind") == ("increase", "stall")
    assert checkWords("Suggestions", "State") == ("open", "accepted", "dismissed", "withdrawn")


def test_aSignUpsProfileHasTheSpecsDefaults():
    profile = block("Profiles")
    for column in ("Units VARCHAR(2) NOT NULL DEFAULT 'lb'", "Goal VARCHAR(8) NOT NULL DEFAULT 'general'",
                   "DaysPerWeek TINYINT NOT NULL DEFAULT 3", "UpperIncrement DECIMAL(5,2) NOT NULL DEFAULT 5.00",
                   "LowerIncrement DECIMAL(5,2) NOT NULL DEFAULT 10.00", "WeekStart VARCHAR(3) NOT NULL DEFAULT 'mon'",
                   "IntroState VARCHAR(7) NOT NULL DEFAULT 'pending'"):
        assert column in profile, column


def test_aPersonGoesWithEverythingTheirs():
    for table in ("Devices", "Sessions", "Profiles", "UserEquipment", "Programs", "Workouts", "Suggestions", "Exercises"):
        assert "REFERENCES Users (UserID) ON DELETE CASCADE" in block(table), table
    assert "REFERENCES Users (UserID) ON DELETE SET NULL" in block("LoginKeys")


def test_historyOutlivesThePlan():
    workouts = block("Workouts")
    assert "REFERENCES Programs (ProgramID) ON DELETE SET NULL" in workouts
    assert "REFERENCES Routines (RoutineID) ON DELETE SET NULL" in workouts
    assert "REFERENCES RoutineItems (ItemID) ON DELETE SET NULL" in block("WorkoutExercises")
    assert "REFERENCES Workouts (WorkoutID) ON DELETE SET NULL" in block("Suggestions")
    # A logged exercise is only ever hidden: nothing cascades from Exercises into history.
    logged = [line for line in block("WorkoutExercises").splitlines() if "REFERENCES Exercises" in line]
    assert logged and "ON DELETE" not in logged[0]


def test_theSpecsIndexesAndKeysAreThere():
    assert "KEY ix_workouts_user_day (UserID, PerformedOn)" in block("Workouts")
    assert "UNIQUE KEY ux_workouts_client (ClientID)" in block("Workouts")
    assert "ClientID CHAR(36) NOT NULL" in block("Workouts")
    assert "KEY ix_workoutexercises_exercise (ExerciseID)" in block("WorkoutExercises")
    assert "KEY ix_suggestions_item_state (ItemID, State)" in block("Suggestions")
    assert "KEY ix_sessions_user (UserID)" in block("Sessions")
    assert "KEY ix_exercises_owner (OwnerUserID)" in block("Exercises")
    assert "UNIQUE KEY ux_exercises_source (Source, SourceKey)" in block("Exercises")
    assert "UNIQUE KEY ux_users_username (Username)" in block("Users")
    assert "Token CHAR(64) NOT NULL" in block("Sessions")


def test_sourceKeysAreComparedExactly():
    """Upstream ids are exact identifiers: two differing only in case must stay two exercises."""
    assert "SourceKey VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL," in block("Exercises")


def test_theSpecsLimitsAreInTheColumns():
    items = block("RoutineItems")
    for check in ("CHECK (Sets BETWEEN 1 AND 20)", "CHECK (RepsMin IS NULL OR RepsMin BETWEEN 1 AND 100)",
                  "CHECK (RepsMax IS NULL OR RepsMax BETWEEN 1 AND 100)",
                  "CHECK (RepsMin IS NULL OR RepsMax IS NULL OR RepsMin <= RepsMax)",
                  "CHECK (TargetWeight IS NULL OR TargetWeight BETWEEN 0 AND 2000)",
                  "CHECK (TargetSeconds IS NULL OR TargetSeconds BETWEEN 1 AND 36000)"):
        assert check in items, check
    sets = block("WorkoutSets")
    assert "CHECK (SetNo BETWEEN 1 AND 20)" in sets
    assert "CHECK (Weight IS NULL OR Weight BETWEEN 0 AND 2000)" in sets
    assert "CHECK (Seconds IS NULL OR Seconds BETWEEN 1 AND 36000)" in sets
    for table in ("RoutineItems", "Workouts", "WorkoutExercises"):
        assert "Note VARCHAR(1000) NULL" in block(table), table
    assert "CHECK (DaysPerWeek BETWEEN 2 AND 6)" in block("Profiles")
    assert "CHECK (Weekday BETWEEN 0 AND 6)" in block("ProgramDays")
    assert "CHECK (Id = 1)" in block("CatalogVersion")


def test_noCheckTouchesAColumnAForeignKeyActsOn():
    """MySQL refuses a CHECK on a column whose foreign key has ON DELETE CASCADE or SET NULL."""
    for table in TABLES:
        text = block(table)
        acted = set(re.findall(r"FOREIGN KEY \((\w+)\) REFERENCES \w+ \(\w+\) ON DELETE", text))
        for check in re.findall(r"CHECK \((.*)\)", text):
            for column in acted:
                assert not re.search(rf"\b{column}\b", check), (table, column)
