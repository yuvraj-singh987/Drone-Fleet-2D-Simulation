# ============================================================
# GENERAL / ROUTE UTILITIES
# ============================================================

import math
from datetime import datetime, timedelta
from typing import Dict, Sequence, Tuple

import config
from models import Package

Point = Tuple[float, float]


def distance(point1: Point, point2: Point) -> float:
    return math.hypot(point2[0] - point1[0], point2[1] - point1[1])


def speed_for_payload(total_payload: float) -> float:
    """
    Payload -> airspeed model:
        0 kg    -> 12 m/s
        2.5 kg  -> 9 m/s

    The linear relationship is a configurable assumption.
    """
    if total_payload < 0:
        raise ValueError("Payload cannot be negative.")
    if total_payload > config.MAX_PAYLOAD:
        raise ValueError("Payload exceeds maximum capacity.")

    ratio = total_payload / config.MAX_PAYLOAD
    return (
        config.CRUISE_SPEED_EMPTY
        + (config.CRUISE_SPEED_FULL - config.CRUISE_SPEED_EMPTY) * ratio
    )


def ground_speed_for_leg(
    start: Point,
    end: Point,
    airspeed: float,
    wind_vector: Point | None = None,
) -> float:
    """
    Calculate the achievable ground speed while staying on the
    desired track, given an airspeed magnitude and a wind vector.

    We solve:
        |ground_velocity - wind| = airspeed

    If the crosswind is too strong to hold the track, the leg is
    treated as infeasible and returns 0.
    """
    leg_distance = distance(start, end)
    if leg_distance <= 1e-12:
        return float("inf")

    wind = wind_vector if wind_vector is not None else config.WIND_VECTOR

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    leg_length = math.hypot(dx, dy)

    ux = dx / leg_length
    uy = dy / leg_length

    wind_parallel = wind[0] * ux + wind[1] * uy
    wind_speed_sq = wind[0] ** 2 + wind[1] ** 2
    wind_perpendicular_sq = max(
        0.0,
        wind_speed_sq - wind_parallel ** 2,
    )

    if wind_perpendicular_sq >= airspeed ** 2:
        return 0.0

    ground_speed = wind_parallel + math.sqrt(
        airspeed ** 2 - wind_perpendicular_sq
    )

    if ground_speed <= 0.0:
        return 0.0

    return ground_speed


def payload_energy_factor(total_payload: float) -> float:
    """Linear extra-energy factor from empty to full payload."""
    ratio = total_payload / config.MAX_PAYLOAD
    return (
        1.0
        + (config.PAYLOAD_ENERGY_FACTOR_FULL - 1.0) * ratio
    )


def battery_required(
    mission_time: float,
    total_payload: float = 0.0,
) -> float:
    """
    Base battery usage depends on flight time.
    Heavy payload adds an extra configurable energy factor.
    """
    return (
        mission_time
        * config.BATTERY_PER_MIN
        * payload_energy_factor(total_payload)
    )


def route_details(
    packages: Sequence[Package],
    start_time: datetime,
) -> dict:
    if not packages:
        return {
            "distance": 0.0,
            "mission_time": 0.0,
            "arrival_times": {},
            "end_time": start_time,
            "speed": speed_for_payload(0.0),
            "battery_required": 0.0,
            "legs": [],
        }

    total_payload = sum(package.weight for package in packages)

    if total_payload > config.MAX_PAYLOAD + 1e-9:
        raise ValueError("Batch payload exceeds drone capacity.")

    airspeed = speed_for_payload(total_payload)
    current = config.BASE
    elapsed_minutes = 0.0
    total_distance = 0.0
    arrival_times: Dict[str, datetime] = {}
    legs = []

    for package in packages:
        leg_distance = distance(current, package.location)
        total_distance += leg_distance

        ground_speed = ground_speed_for_leg(
            current,
            package.location,
            airspeed,
        )

        if leg_distance > 1e-12 and ground_speed <= 0.0:
            return {
                "distance": float("inf"),
                "mission_time": float("inf"),
                "arrival_times": {},
                "end_time": datetime.max,
                "speed": airspeed,
                "battery_required": float("inf"),
                "legs": [],
            }

        leg_time_minutes = (
            0.0
            if leg_distance <= 1e-12
            else leg_distance / ground_speed / 60.0
        )

        elapsed_minutes += leg_time_minutes

        arrival_times[package.package_id] = (
            start_time + timedelta(minutes=elapsed_minutes)
        )

        legs.append({
            "from": current,
            "to": package.location,
            "distance": leg_distance,
            "ground_speed": ground_speed,
            "time_minutes": leg_time_minutes,
            "package_id": package.package_id,
        })

        current = package.location

    return_distance = distance(current, config.BASE)
    total_distance += return_distance

    return_speed = ground_speed_for_leg(
        current,
        config.BASE,
        airspeed,
    )

    if return_distance > 1e-12 and return_speed <= 0.0:
        return {
            "distance": float("inf"),
            "mission_time": float("inf"),
            "arrival_times": {},
            "end_time": datetime.max,
            "speed": airspeed,
            "battery_required": float("inf"),
            "legs": [],
        }

    return_time_minutes = (
        0.0
        if return_distance <= 1e-12
        else return_distance / return_speed / 60.0
    )

    elapsed_minutes += return_time_minutes

    legs.append({
        "from": current,
        "to": config.BASE,
        "distance": return_distance,
        "ground_speed": return_speed,
        "time_minutes": return_time_minutes,
        "package_id": "RETURN",
    })

    battery_used = battery_required(
        elapsed_minutes,
        total_payload,
    )

    return {
        "distance": total_distance,
        "mission_time": elapsed_minutes,
        "arrival_times": arrival_times,
        "end_time": start_time + timedelta(minutes=elapsed_minutes),
        "speed": airspeed,
        "battery_required": battery_used,
        "legs": legs,
    }


def deadlines_feasible(
    packages: Sequence[Package],
    arrival_times: Dict[str, datetime],
) -> bool:
    if not arrival_times and packages:
        return False

    for package in packages:
        if arrival_times[package.package_id] > package.deadline_at:
            return False

    return True
