-- Pride part 1: every table prideDB needs (spec §3), created at once so no later milestone alters one. Milestone 1
-- uses the accounts, the profile row a sign-up makes, and the catalog. The owner runs it once at rollout
-- (milestone 4) with: sudo mysql prideDB < schema.sql
-- Multi-valued facts live in child tables; single-valued words are VARCHAR with a CHECK whose list is prideCatalog's.
-- No CHECK names a column whose foreign key cascades or sets null: MySQL refuses that.

-- ---- Accounts (as Gluttony's) ----

CREATE TABLE Users (
  UserID INT NOT NULL AUTO_INCREMENT,
  Username VARCHAR(32) NOT NULL,
  PasswordHash VARCHAR(255) NOT NULL,
  CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (UserID),
  UNIQUE KEY ux_users_username (Username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- A device that signs in by itself. Its last sign-in is read from its newest session.
CREATE TABLE Devices (
  Fingerprint VARCHAR(255) NOT NULL,
  UserID INT NOT NULL,
  PRIMARY KEY (Fingerprint),
  KEY ix_devices_user (UserID),
  CONSTRAINT fk_devices_user FOREIGN KEY (UserID) REFERENCES Users (UserID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE Sessions (
  Token CHAR(64) NOT NULL,
  UserID INT NOT NULL,
  DeviceFingerprint VARCHAR(255) NOT NULL,
  ExpiresAt DATETIME NOT NULL,
  PRIMARY KEY (Token),
  KEY ix_sessions_user (UserID),
  CONSTRAINT fk_sessions_user FOREIGN KEY (UserID) REFERENCES Users (UserID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- The owner inserts a row by hand for each friend: INSERT INTO LoginKeys (KeyValue) VALUES ('<a long random key>');
CREATE TABLE LoginKeys (
  KeyValue VARCHAR(64) NOT NULL,
  Used TINYINT(1) NOT NULL DEFAULT 0,
  UsedBy INT NULL,
  CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (KeyValue),
  CONSTRAINT fk_loginkeys_user FOREIGN KEY (UsedBy) REFERENCES Users (UserID) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---- Profile: sign-up makes the row with the intro pending; the increments are in the profile's units ----

CREATE TABLE Profiles (
  UserID INT NOT NULL,
  Units VARCHAR(2) NOT NULL DEFAULT 'lb',
  Goal VARCHAR(8) NOT NULL DEFAULT 'general',
  DaysPerWeek TINYINT NOT NULL DEFAULT 3,
  UpperIncrement DECIMAL(5,2) NOT NULL DEFAULT 5.00,
  LowerIncrement DECIMAL(5,2) NOT NULL DEFAULT 10.00,
  WeekStart VARCHAR(3) NOT NULL DEFAULT 'mon',
  IntroState VARCHAR(7) NOT NULL DEFAULT 'pending',
  PRIMARY KEY (UserID),
  CONSTRAINT ck_profiles_units CHECK (Units IN ('lb', 'kg')),
  CONSTRAINT ck_profiles_goal CHECK (Goal IN ('strength', 'muscle', 'general')),
  CONSTRAINT ck_profiles_days CHECK (DaysPerWeek BETWEEN 2 AND 6),
  CONSTRAINT ck_profiles_upper CHECK (UpperIncrement > 0 AND UpperIncrement <= 100),
  CONSTRAINT ck_profiles_lower CHECK (LowerIncrement > 0 AND LowerIncrement <= 100),
  CONSTRAINT ck_profiles_weekstart CHECK (WeekStart IN ('mon', 'sun')),
  CONSTRAINT ck_profiles_intro CHECK (IntroState IN ('pending', 'done', 'skipped')),
  CONSTRAINT fk_profiles_user FOREIGN KEY (UserID) REFERENCES Users (UserID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE UserEquipment (
  UserID INT NOT NULL,
  Equipment VARCHAR(12) NOT NULL,
  PRIMARY KEY (UserID, Equipment),
  CONSTRAINT ck_userequipment_word CHECK (Equipment IN ('barbell', 'dumbbell', 'kettlebell', 'machine', 'cable', 'bands', 'bodyweight', 'bench', 'pull-up bar', 'other')),
  CONSTRAINT fk_userequipment_user FOREIGN KEY (UserID) REFERENCES Users (UserID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---- Catalog: imported rows have no owner; a person's own exercise names them. Rows are hidden, never deleted ----

CREATE TABLE Exercises (
  ExerciseID INT NOT NULL AUTO_INCREMENT,
  Source VARCHAR(40) NOT NULL,
  SourceKey VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  Licence VARCHAR(80) NULL,
  Name VARCHAR(120) NOT NULL,
  Category VARCHAR(21) NULL,
  Level VARCHAR(12) NULL,
  Measure VARCHAR(13) NOT NULL,
  Region VARCHAR(5) NOT NULL,
  OwnerUserID INT NULL,
  ContentHash CHAR(40) NULL,
  RemovedAt DATETIME NULL,
  UpdatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (ExerciseID),
  UNIQUE KEY ux_exercises_source (Source, SourceKey),
  KEY ix_exercises_owner (OwnerUserID),
  CONSTRAINT ck_exercises_category CHECK (Category IS NULL OR Category IN ('strength', 'stretching', 'plyometrics', 'strongman', 'powerlifting', 'cardio', 'olympic weightlifting')),
  CONSTRAINT ck_exercises_level CHECK (Level IS NULL OR Level IN ('beginner', 'intermediate', 'expert')),
  CONSTRAINT ck_exercises_measure CHECK (Measure IN ('weight_reps', 'reps', 'time', 'distance_time')),
  CONSTRAINT ck_exercises_region CHECK (Region IN ('upper', 'lower', 'full')),
  CONSTRAINT fk_exercises_owner FOREIGN KEY (OwnerUserID) REFERENCES Users (UserID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ExerciseMuscles (
  ExerciseID INT NOT NULL,
  Muscle VARCHAR(12) NOT NULL,
  Role VARCHAR(9) NOT NULL,
  PRIMARY KEY (ExerciseID, Muscle),
  CONSTRAINT ck_exercisemuscles_muscle CHECK (Muscle IN ('abdominals', 'abductors', 'adductors', 'biceps', 'calves', 'chest', 'forearms', 'glutes', 'hamstrings', 'lats', 'lower back', 'middle back', 'neck', 'quadriceps', 'shoulders', 'traps', 'triceps')),
  CONSTRAINT ck_exercisemuscles_role CHECK (Role IN ('primary', 'secondary')),
  CONSTRAINT fk_exercisemuscles_exercise FOREIGN KEY (ExerciseID) REFERENCES Exercises (ExerciseID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ExerciseEquipment (
  ExerciseID INT NOT NULL,
  Equipment VARCHAR(12) NOT NULL,
  PRIMARY KEY (ExerciseID, Equipment),
  CONSTRAINT ck_exerciseequipment_word CHECK (Equipment IN ('barbell', 'dumbbell', 'kettlebell', 'machine', 'cable', 'bands', 'bodyweight', 'bench', 'pull-up bar', 'other')),
  CONSTRAINT fk_exerciseequipment_exercise FOREIGN KEY (ExerciseID) REFERENCES Exercises (ExerciseID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ExerciseSteps (
  ExerciseID INT NOT NULL,
  StepNo TINYINT NOT NULL,
  Text VARCHAR(1000) NOT NULL,
  PRIMARY KEY (ExerciseID, StepNo),
  CONSTRAINT ck_exercisesteps_no CHECK (StepNo BETWEEN 1 AND 50),
  CONSTRAINT fk_exercisesteps_exercise FOREIGN KEY (ExerciseID) REFERENCES Exercises (ExerciseID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Path is the picture's name under appFiles/pride/exercises (prideCatalog.PICTURE_NAME).
CREATE TABLE ExercisePictures (
  ExerciseID INT NOT NULL,
  Idx TINYINT NOT NULL,
  Path VARCHAR(40) NOT NULL,
  PRIMARY KEY (ExerciseID, Idx),
  CONSTRAINT ck_exercisepictures_idx CHECK (Idx BETWEEN 0 AND 9),
  CONSTRAINT fk_exercisepictures_exercise FOREIGN KEY (ExerciseID) REFERENCES Exercises (ExerciseID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- One row: the hash of the catalog as the last import left it. The app compares it before refreshing its copy.
CREATE TABLE CatalogVersion (
  Id TINYINT NOT NULL,
  Version CHAR(40) NOT NULL,
  UpdatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (Id),
  CONSTRAINT ck_catalogversion_one CHECK (Id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---- Programs (milestone 2): at most one active program per person, which the server enforces ----

CREATE TABLE Programs (
  ProgramID INT NOT NULL AUTO_INCREMENT,
  UserID INT NOT NULL,
  Title VARCHAR(60) NOT NULL,
  IsActive TINYINT(1) NOT NULL DEFAULT 0,
  StarterKey VARCHAR(40) NULL,
  CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UpdatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (ProgramID),
  KEY ix_programs_user (UserID),
  CONSTRAINT fk_programs_user FOREIGN KEY (UserID) REFERENCES Users (UserID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- The planned weekdays, 0 = Monday. It can be empty.
CREATE TABLE ProgramDays (
  ProgramID INT NOT NULL,
  Weekday TINYINT NOT NULL,
  PRIMARY KEY (ProgramID, Weekday),
  CONSTRAINT ck_programdays_weekday CHECK (Weekday BETWEEN 0 AND 6),
  CONSTRAINT fk_programdays_program FOREIGN KEY (ProgramID) REFERENCES Programs (ProgramID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE Routines (
  RoutineID INT NOT NULL AUTO_INCREMENT,
  ProgramID INT NOT NULL,
  Title VARCHAR(60) NOT NULL,
  OrderIndex INT NOT NULL,
  PRIMARY KEY (RoutineID),
  KEY ix_routines_program (ProgramID, OrderIndex),
  CONSTRAINT fk_routines_program FOREIGN KEY (ProgramID) REFERENCES Programs (ProgramID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE RoutineItems (
  ItemID INT NOT NULL AUTO_INCREMENT,
  RoutineID INT NOT NULL,
  ExerciseID INT NOT NULL,
  OrderIndex INT NOT NULL,
  Sets TINYINT NOT NULL DEFAULT 3,
  RepsMin TINYINT NULL,
  RepsMax TINYINT NULL,
  TargetWeight DECIMAL(6,2) NULL,
  TargetUnit VARCHAR(2) NULL,
  TargetSeconds INT NULL,
  TargetDistance DECIMAL(7,2) NULL,
  DistanceUnit VARCHAR(2) NULL,
  RestSeconds SMALLINT NULL,
  Note VARCHAR(1000) NULL,
  PRIMARY KEY (ItemID),
  KEY ix_routineitems_routine (RoutineID, OrderIndex),
  CONSTRAINT ck_routineitems_sets CHECK (Sets BETWEEN 1 AND 20),
  CONSTRAINT ck_routineitems_repsmin CHECK (RepsMin IS NULL OR RepsMin BETWEEN 1 AND 100),
  CONSTRAINT ck_routineitems_repsmax CHECK (RepsMax IS NULL OR RepsMax BETWEEN 1 AND 100),
  CONSTRAINT ck_routineitems_range CHECK (RepsMin IS NULL OR RepsMax IS NULL OR RepsMin <= RepsMax),
  CONSTRAINT ck_routineitems_weight CHECK (TargetWeight IS NULL OR TargetWeight BETWEEN 0 AND 2000),
  CONSTRAINT ck_routineitems_unit CHECK (TargetUnit IS NULL OR TargetUnit IN ('lb', 'kg')),
  CONSTRAINT ck_routineitems_seconds CHECK (TargetSeconds IS NULL OR TargetSeconds BETWEEN 1 AND 36000),
  CONSTRAINT ck_routineitems_distance CHECK (TargetDistance IS NULL OR TargetDistance BETWEEN 0 AND 1000),
  CONSTRAINT ck_routineitems_distanceunit CHECK (DistanceUnit IS NULL OR DistanceUnit IN ('km', 'mi', 'm')),
  CONSTRAINT ck_routineitems_rest CHECK (RestSeconds IS NULL OR RestSeconds BETWEEN 0 AND 3600),
  CONSTRAINT fk_routineitems_routine FOREIGN KEY (RoutineID) REFERENCES Routines (RoutineID) ON DELETE CASCADE,
  CONSTRAINT fk_routineitems_exercise FOREIGN KEY (ExerciseID) REFERENCES Exercises (ExerciseID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---- Workouts (milestone 3): sets keep the number and unit as entered; history outlives the plan ----

CREATE TABLE Workouts (
  WorkoutID INT NOT NULL AUTO_INCREMENT,
  UserID INT NOT NULL,
  ClientID CHAR(36) NOT NULL,
  PerformedOn DATE NOT NULL,
  StartedAt DATETIME NULL,
  EndedAt DATETIME NULL,
  ProgramID INT NULL,
  RoutineID INT NULL,
  Note VARCHAR(1000) NULL,
  CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UpdatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (WorkoutID),
  UNIQUE KEY ux_workouts_client (ClientID),
  KEY ix_workouts_user_day (UserID, PerformedOn),
  CONSTRAINT fk_workouts_user FOREIGN KEY (UserID) REFERENCES Users (UserID) ON DELETE CASCADE,
  CONSTRAINT fk_workouts_program FOREIGN KEY (ProgramID) REFERENCES Programs (ProgramID) ON DELETE SET NULL,
  CONSTRAINT fk_workouts_routine FOREIGN KEY (RoutineID) REFERENCES Routines (RoutineID) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE WorkoutExercises (
  WorkoutExerciseID INT NOT NULL AUTO_INCREMENT,
  WorkoutID INT NOT NULL,
  ExerciseID INT NOT NULL,
  OrderIndex INT NOT NULL,
  ItemID INT NULL,
  Note VARCHAR(1000) NULL,
  PRIMARY KEY (WorkoutExerciseID),
  KEY ix_workoutexercises_workout (WorkoutID, OrderIndex),
  KEY ix_workoutexercises_exercise (ExerciseID),
  CONSTRAINT fk_workoutexercises_workout FOREIGN KEY (WorkoutID) REFERENCES Workouts (WorkoutID) ON DELETE CASCADE,
  CONSTRAINT fk_workoutexercises_item FOREIGN KEY (ItemID) REFERENCES RoutineItems (ItemID) ON DELETE SET NULL,
  CONSTRAINT fk_workoutexercises_exercise FOREIGN KEY (ExerciseID) REFERENCES Exercises (ExerciseID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE WorkoutSets (
  WorkoutExerciseID INT NOT NULL,
  SetNo TINYINT NOT NULL,
  IsWarmup TINYINT(1) NOT NULL DEFAULT 0,
  Weight DECIMAL(6,2) NULL,
  WeightUnit VARCHAR(2) NULL,
  Reps SMALLINT NULL,
  Seconds INT NULL,
  Distance DECIMAL(7,2) NULL,
  DistanceUnit VARCHAR(2) NULL,
  PRIMARY KEY (WorkoutExerciseID, SetNo),
  CONSTRAINT ck_workoutsets_no CHECK (SetNo BETWEEN 1 AND 20),
  CONSTRAINT ck_workoutsets_weight CHECK (Weight IS NULL OR Weight BETWEEN 0 AND 2000),
  CONSTRAINT ck_workoutsets_unit CHECK (WeightUnit IS NULL OR WeightUnit IN ('lb', 'kg')),
  CONSTRAINT ck_workoutsets_reps CHECK (Reps IS NULL OR Reps BETWEEN 0 AND 1000),
  CONSTRAINT ck_workoutsets_seconds CHECK (Seconds IS NULL OR Seconds BETWEEN 1 AND 36000),
  CONSTRAINT ck_workoutsets_distance CHECK (Distance IS NULL OR Distance BETWEEN 0 AND 1000),
  CONSTRAINT ck_workoutsets_distanceunit CHECK (DistanceUnit IS NULL OR DistanceUnit IN ('km', 'mi', 'm')),
  CONSTRAINT fk_workoutsets_exercise FOREIGN KEY (WorkoutExerciseID) REFERENCES WorkoutExercises (WorkoutExerciseID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---- Suggestions (milestone 3): at most one open per item, which the rules enforce ----

CREATE TABLE Suggestions (
  SuggestionID INT NOT NULL AUTO_INCREMENT,
  UserID INT NOT NULL,
  ItemID INT NOT NULL,
  Kind VARCHAR(8) NOT NULL,
  ProposedWeight DECIMAL(6,2) NULL,
  ProposedUnit VARCHAR(2) NULL,
  ProposedRepsMin TINYINT NULL,
  ProposedRepsMax TINYINT NULL,
  ProposedSeconds INT NULL,
  BasedOnWorkoutID INT NULL,
  State VARCHAR(9) NOT NULL DEFAULT 'open',
  CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (SuggestionID),
  KEY ix_suggestions_item_state (ItemID, State),
  CONSTRAINT ck_suggestions_kind CHECK (Kind IN ('increase', 'stall')),
  CONSTRAINT ck_suggestions_unit CHECK (ProposedUnit IS NULL OR ProposedUnit IN ('lb', 'kg')),
  CONSTRAINT ck_suggestions_state CHECK (State IN ('open', 'accepted', 'dismissed', 'withdrawn')),
  CONSTRAINT fk_suggestions_user FOREIGN KEY (UserID) REFERENCES Users (UserID) ON DELETE CASCADE,
  CONSTRAINT fk_suggestions_item FOREIGN KEY (ItemID) REFERENCES RoutineItems (ItemID) ON DELETE CASCADE,
  CONSTRAINT fk_suggestions_workout FOREIGN KEY (BasedOnWorkoutID) REFERENCES Workouts (WorkoutID) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
