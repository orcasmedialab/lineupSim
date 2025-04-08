# src/constants.py

# Plate Appearance Outcomes
WALK = "WALK"
HIT_BY_PITCH = "HBP"
STRIKEOUT = "SO"
SINGLE = "1B"
DOUBLE = "2B"
TRIPLE = "3B"
HOME_RUN = "HR"
GROUND_OUT = "GO" # New
FLY_OUT = "FO"    # New
# OUT_IN_PLAY = "OUT" # Removed

# List of possible outcomes for weighted random choice
OUTCOMES = [
    WALK,
    HIT_BY_PITCH,
    STRIKEOUT,
    SINGLE,
    DOUBLE,
    TRIPLE,
    HOME_RUN,
    GROUND_OUT, # New
    FLY_OUT     # New
]

# Bases
FIRST_BASE = 0
SECOND_BASE = 1
THIRD_BASE = 2
HOME_PLATE = 3 # Represents scoring or crossing the plate

# Batter representation for FC/DP logic
BATTER_INDEX = -1