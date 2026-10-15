# ============================================================
# TASK-AWARE CHARGING MANAGER
# ============================================================

from collections import deque
from datetime import datetime, timedelta

from config import CHARGING_RATE, MAX_CHARGING_PADS


class ChargingManager:
    """
    Charging is task-aware.

    A drone is not automatically charged to 100% when a waiting
    task exists. Instead, it can be charged only to:

        mission battery required + safety reserve

    If pads are full, waiting-charge drones are ordered by
    shortest charging time to their target. A higher current
    battery therefore normally gets priority because it becomes
    mission-ready sooner.
    """

    def __init__(self, drones):
        self.drones = drones
        self.queue = deque()
        self.pads_occupied = sum(
            1 for d in drones if d.status == 'charging'
        )

    def _find(self, drone_id):
        return next(
            (d for d in self.drones if d.drone_id == drone_id),
            None,
        )

    def _queue_priority(self, drone):
        target = drone.charge_target or drone.effective_capacity
        missing = max(0.0, target - drone.battery)
        charge_minutes = missing / CHARGING_RATE
        return (charge_minutes, -drone.battery, drone.drone_id)

    def request_charge(self, drone, now, target_battery=None, batch_id=None):
        target = (
            drone.effective_capacity
            if target_battery is None
            else min(target_battery, drone.effective_capacity)
        )

        if drone.battery >= target - 1e-9:
            return False

        # If already charging, update the target instead of adding a duplicate request.
        if drone.status == 'charging':
            # Bring the stored battery value up to the current simulation time
            # before changing the charging target. This lets us shorten or
            # extend an active charge without resetting progress.
            self._update_partial_battery(drone, now)

            drone.charge_target = max(
                drone.battery,
                min(target, drone.effective_capacity)
            )
            drone.charge_for_batch = batch_id

            missing = max(0.0, drone.charge_target - drone.battery)
            drone.charge_started_at = now
            drone.charge_start_battery = drone.battery
            drone.available_at = now + timedelta(
                minutes=missing / CHARGING_RATE
            )

            return True

        if drone.status == 'waiting_charge':
            drone.charge_target = max(
                drone.battery,
                min(target, drone.effective_capacity)
            )
            drone.charge_for_batch = batch_id
            self._resort_queue()
            return True

        if drone.status != 'idle':
            return False

        drone.charge_target = target
        drone.charge_for_batch = batch_id

        if self.pads_occupied < MAX_CHARGING_PADS:
            self._start_charging(drone, now)
        else:
            drone.status = 'waiting_charge'
            if drone.drone_id not in self.queue:
                self.queue.append(drone.drone_id)
            self._resort_queue()
            print(
                f'{drone.drone_id} -> WAITING_CHARGE | '
                f'target={target:.2f}%'
            )

        return True

    def _resort_queue(self):
        ids = list(self.queue)
        ids.sort(
            key=lambda drone_id: self._queue_priority(self._find(drone_id))
        )
        self.queue = deque(ids)

    def _start_charging(self, drone, now):
        drone.status = 'charging'
        drone.charge_started_at = now
        drone.charge_start_battery = drone.battery
        target = min(
            drone.charge_target or drone.effective_capacity,
            drone.effective_capacity
        )
        drone.charge_target = target
        missing = max(0.0, target - drone.battery)
        minutes = missing / CHARGING_RATE
        drone.available_at = now + timedelta(minutes=minutes)
        self.pads_occupied += 1

        print(
            f'{drone.drone_id} -> CHARGING | '
            f'{drone.battery:.2f}% -> {target:.2f}% | '
            f'{minutes:.2f} min'
        )

    def _update_partial_battery(self, drone, now):
        if drone.charge_started_at is None or drone.charge_start_battery is None:
            return

        elapsed = (now - drone.charge_started_at).total_seconds() / 60.0
        target = min(
            drone.charge_target or drone.effective_capacity,
            drone.effective_capacity
        )

        drone.battery = min(
            target,
            drone.charge_start_battery + elapsed * CHARGING_RATE
        )

    def update(self, now):
        # Complete or partially update active charging.
        for drone in self.drones:
            if drone.status != 'charging':
                continue

            self._update_partial_battery(drone, now)

            if drone.available_at is None or now < drone.available_at:
                continue

            target = min(
                drone.charge_target or drone.effective_capacity,
                drone.effective_capacity
            )
            drone.battery = target
            drone.status = 'idle'
            drone.available_at = now
            drone.charge_started_at = None
            drone.charge_start_battery = None
            drone.charge_target = None
            drone.charge_for_batch = None
            self.pads_occupied = max(0, self.pads_occupied - 1)

            print(
                f'{drone.drone_id} charging completed -> IDLE '
                f'({drone.battery:.2f}%)'
            )

        # Fill newly free pads using the shortest-ready-time request.
        self._resort_queue()

        while self.queue and self.pads_occupied < MAX_CHARGING_PADS:
            drone_id = self.queue.popleft()
            drone = self._find(drone_id)

            if drone is None or drone.status != 'waiting_charge':
                continue

            self._start_charging(drone, now)
