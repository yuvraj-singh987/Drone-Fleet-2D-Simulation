# ============================================================
# FLEET MANAGER
# ============================================================

from datetime import datetime, timedelta

from charging import ChargingManager
from config import CHARGING_THRESHOLD
from models import Drone


class FleetManager:
    def __init__(self, start_time: datetime):
        self.drones = self._create_initial_fleet(start_time)
        self.charging = ChargingManager(self.drones)

    @staticmethod
    def _create_initial_fleet(start_time):
        def idle(drone_id, battery):
            return Drone(drone_id, (0.0, 0.0), battery, 'idle', available_at=start_time)

        return [
            Drone('D1', (0.0, 0.0), 50.0, 'busy', available_at=start_time + timedelta(minutes=5)),
            idle('D2', 90.0),
            idle('D3', 80.0),
            idle('D4', 70.0),
            idle('D5', 60.0),
            idle('D6', 50.0),
            idle('D7', 40.0),
            idle('D8', 30.0),
            Drone('D9', (0.0, 0.0), 20.0, 'charging', available_at=start_time + timedelta(minutes=40), charge_target=100.0, charge_started_at=start_time, charge_start_battery=20.0),
            Drone('D10', (0.0, 0.0), 10.0, 'charging', available_at=start_time + timedelta(minutes=40), charge_target=100.0, charge_started_at=start_time, charge_start_battery=10.0),
        ]

    def by_status(self, status):
        return [d for d in self.drones if d.status == status]

    def update(self, now):
        for drone in self.drones:
            if drone.status != 'busy' or drone.available_at is None or now < drone.available_at:
                continue

            batch = drone.current_batch
            drone.position = (0.0, 0.0)
            drone.payload = 0.0
            drone.status = 'idle'
            drone.current_batch = None
            drone.route = []
            drone.predicted_arrivals = {}
            drone.mission_started_at = None
            drone.mission_legs = []
            drone.available_at = now
            drone.cycles += 1

            delivered = [p.package_id for p in batch.packages] if batch else []

            print(
                f'{drone.drone_id} mission completed -> IDLE | '
                f'delivered={delivered} | battery={drone.battery:.2f}% | '
                f'cycles={drone.cycles}'
            )

            if drone.battery < CHARGING_THRESHOLD:
                # No waiting-task target is known here yet, so put it into standby charging.
                self.charging.request_charge(drone, now)

        self.charging.update(now)

    def display_status(self):
        print('\n================ FLEET STATUS ================')

        for drone in self.drones:
            available = (
                drone.available_at.strftime('%H:%M:%S')
                if drone.available_at else '-'
            )

            target = (
                f'{drone.charge_target:.2f}%'
                if drone.charge_target is not None else '-'
            )

            print(
                f'{drone.drone_id:>3} | {drone.status:<14} | '
                f'battery={drone.battery:6.2f}% | '
                f'payload={drone.payload:4.2f}kg | '
                f'charge_target={target:>8} | '
                f'available={available}'
            )

        print(
            f'Charging pads: {self.charging.pads_occupied}/3 | '
            f'Charging queue: {list(self.charging.queue)}'
        )
        print('==============================================')
