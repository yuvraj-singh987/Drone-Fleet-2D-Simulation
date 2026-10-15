# ============================================================
# ASSIGNMENT ENGINE
# ============================================================

from collections import deque
from datetime import datetime

from config import SAFETY_RESERVE
from package_manager import find_best_feasible_route


class AssignmentEngine:
    def __init__(self, fleet_manager):
        self.fleet = fleet_manager
        self.waiting_batches = deque()

    def _route_for_drone(self, drone, batch, start_time):
        route = find_best_feasible_route(batch.packages, start_time)
        if route is None:
            return False, None

        required = route['battery_required'] + SAFETY_RESERVE
        if drone.battery < required - 1e-9:
            return False, route

        return True, route

    def _future_candidate(self, drone, batch, now):
        # For charging drones, available_at means target battery will be reached.
        if drone.status == 'charging' and drone.available_at:
            start = drone.available_at
            battery = drone.charge_target or drone.effective_capacity
            route = find_best_feasible_route(batch.packages, start)
            if route is None:
                return None
            required = route['battery_required'] + SAFETY_RESERVE
            if battery < required - 1e-9:
                return None
            return start, route

        if drone.status == 'busy' and drone.available_at:
            start = drone.available_at
            route = find_best_feasible_route(batch.packages, start)
            if route is None:
                return None
            required = route['battery_required'] + SAFETY_RESERVE
            if drone.battery < required - 1e-9:
                # Busy drone may need a future charge; charging is handled after it returns.
                return None
            return start, route

        return None

    def _assign_first_feasible_idle(self, batch, now):
        # Deterministic first-feasible policy: D1, D2, D3...
        for drone in self.fleet.drones:
            if drone.status != 'idle':
                continue

            ok, route = self._route_for_drone(drone, batch, now)
            if not ok:
                continue

            drone.status = 'busy'
            drone.payload = batch.total_weight
            drone.current_batch = batch
            drone.route = [p.package_id for p in route['order']]
            drone.predicted_arrivals = route['arrival_times']
            drone.mission_started_at = now
            # Freeze the planned leg times so the visual simulator can
            # animate this mission consistently even if wind is changed later.
            drone.mission_legs = list(route.get('legs', []))
            drone.available_at = route['end_time']

            drone.battery -= route['battery_required']

            # This is a batch route from the base in this model.
            drone.position = (0.0, 0.0)

            self._print_assignment(drone, batch, route)
            return drone

        return None

    def _ensure_charging_for_batch(self, batch, now):
        """
        Ask suitable non-busy drones to charge only to the
        battery level required by this waiting batch + reserve.

        For drones already charging, their target can be adjusted.
        For idle low-battery drones, a charging request is created.
        """

        # The exact route is evaluated from the base for a task-ready drone.
        route = find_best_feasible_route(batch.packages, now)
        if route is None:
            return

        target = route['battery_required'] + SAFETY_RESERVE

        for drone in self.fleet.drones:
            if drone.status not in {'idle', 'charging', 'waiting_charge'}:
                continue

            if drone.battery >= target - 1e-9:
                continue

            # Only start charging if this drone could use the target battery for the batch.
            # The charging manager handles pad availability and queue priority.
            self.fleet.charging.request_charge(
                drone,
                now,
                target_battery=target,
                batch_id=batch.batch_id,
            )

    def _any_drone_can_eventually_take(self, batch, now):
        # Current idle drone.
        for drone in self.fleet.drones:
            if drone.status == 'idle':
                ok, _ = self._route_for_drone(drone, batch, now)
                if ok:
                    return True

        # Busy/charging future drones.
        for drone in self.fleet.drones:
            future = self._future_candidate(drone, batch, now)
            if future is not None:
                return True

        # A low-battery idle/charging drone may become feasible by partial charging.
        route = find_best_feasible_route(batch.packages, now)
        if route is not None:
            target = route['battery_required'] + SAFETY_RESERVE
            for drone in self.fleet.drones:
                if drone.status in {'idle', 'charging', 'waiting_charge'} and drone.effective_capacity >= target:
                    return True

        return False

    def submit_batch(self, batch, now):
        self.fleet.update(now)

        if not self._any_drone_can_eventually_take(batch, now):
            print(
                f'Batch {batch.batch_id} REJECTED: no drone can become '
                f'feasible before all deadlines.'
            )
            return False

        drone = self._assign_first_feasible_idle(batch, now)
        if drone is not None:
            return True

        self.waiting_batches.append(batch)

        print(
            f'Batch {batch.batch_id} -> WAITING QUEUE '
            f'(no feasible idle drone right now).'
        )

        # Immediately plan task-aware partial charging.
        self._ensure_charging_for_batch(batch, now)
        return False

    def process_waiting_queue(self, now):
        self.fleet.update(now)

        count = len(self.waiting_batches)
        for _ in range(count):
            batch = self.waiting_batches.popleft()

            if not self._any_drone_can_eventually_take(batch, now):
                print(
                    f'Batch {batch.batch_id} REMOVED: deadline is '
                    f'no longer achievable.'
                )
                continue

            drone = self._assign_first_feasible_idle(batch, now)

            if drone is None:
                self.waiting_batches.append(batch)
                self._ensure_charging_for_batch(batch, now)
            else:
                print(
                    f'Batch {batch.batch_id} removed from waiting queue.'
                )

        print(
            f'Waiting batches: {len(self.waiting_batches)}'
        )

    @staticmethod
    def _print_assignment(drone, batch, route):
        print('\n================ ASSIGNMENT ================')
        print(f'Drone            : {drone.drone_id}')
        print(f'Batch            : {batch.batch_id}')
        print(f'Total payload    : {batch.total_weight:.2f} kg')
        print(
            'Route             : BASE -> '
            + ' -> '.join(drone.route)
            + ' -> BASE'
        )
        print(f'Speed             : {route["speed"]:.2f} m/s')
        print(f'Total distance    : {route["distance"]:.2f} m')
        print(f'Mission time     : {route["mission_time"]:.2f} min')
        print(
            f'Battery used     : '
            f'{route["battery_required"]:.2f}%'
        )
        print(f'Remaining battery: {drone.battery:.2f}%')

        print('Delivery order and deadlines:')
        for package in route['order']:
            arrival = route['arrival_times'][package.package_id]
            print(
                f'  {package.package_id}: arrival={arrival.strftime("%H:%M:%S")} | '
                f'deadline={package.deadline_at.strftime("%H:%M:%S")}'
            )

        print('============================================')
