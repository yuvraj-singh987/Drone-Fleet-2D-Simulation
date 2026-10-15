# ============================================================
# CONFIGURATION
# ============================================================

MAX_DRONES = 10
MAX_PAYLOAD = 2.5

# Payload-dependent airspeed model.
# These are modeling assumptions because the PS does not
# provide the exact payload-speed equation.
CRUISE_SPEED_EMPTY = 12.0   # m/s at 0 kg
CRUISE_SPEED_FULL = 9.0     # m/s at 2.5 kg

ENDURANCE_MIN = 25.0
CHARGING_TIME = 40.0
CHARGING_RATE = 100.0 / CHARGING_TIME
BATTERY_PER_MIN = 100.0 / ENDURANCE_MIN

# Heavy payload also increases energy use per minute.
# 1.00 = empty-load multiplier, 1.20 = full-load multiplier.
# This is a configurable modeling assumption.
PAYLOAD_ENERGY_FACTOR_FULL = 1.20

MAX_CHARGING_PADS = 3
CHARGING_THRESHOLD = 20.0
SAFETY_RESERVE = 10.0

BATTERY_DEGRADATION_PER_CYCLE = 0.05

MAX_EXACT_ROUTE_PACKAGES = 7

BASE = (0.0, 0.0)

# Wind vector in world coordinates (m/s).
# Example: (3, 0) = 3 m/s wind toward +X.
# Set to (0, 0) for calm air.
WIND_VECTOR = (0.0, 0.0)
