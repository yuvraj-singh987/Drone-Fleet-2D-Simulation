# ============================================================
# PACKAGE / BATCH MANAGEMENT
# ============================================================

from datetime import datetime
from itertools import permutations
from typing import List, Optional, Sequence, Tuple

from config import MAX_EXACT_ROUTE_PACKAGES, MAX_PAYLOAD
from models import Batch, Package
from utils import deadlines_feasible, route_details


def validate_packages(packages: Sequence[Package]) -> Tuple[bool, str]:
    if not packages:
        return False, 'Batch must contain at least one package.'

    for package in packages:
        if package.weight <= 0:
            return False, f'{package.package_id}: weight must be positive.'
        if package.weight > MAX_PAYLOAD:
            return False, (
                f'{package.package_id}: weight {package.weight:.2f} kg '
                f'exceeds maximum payload {MAX_PAYLOAD:.2f} kg.'
            )

    total = sum(p.weight for p in packages)
    if total > MAX_PAYLOAD + 1e-9:
        return False, (
            f'Total batch weight {total:.2f} kg exceeds '
            f'maximum payload {MAX_PAYLOAD:.2f} kg.'
        )

    return True, 'OK'


def _exact_best_route(packages: Sequence[Package], start_time: datetime) -> Optional[dict]:
    best = None

    for order in permutations(packages):
        details = route_details(order, start_time)

        if not deadlines_feasible(order, details['arrival_times']):
            continue

        if best is None or details['mission_time'] < best['mission_time']:
            best = {'order': list(order), **details}

    return best


def _greedy_route(packages: Sequence[Package], start_time: datetime) -> Optional[dict]:
    order = sorted(packages, key=lambda p: (p.deadline_at, p.package_id))
    details = route_details(order, start_time)

    if not deadlines_feasible(order, details['arrival_times']):
        return None

    return {'order': order, **details}


def find_best_feasible_route(packages: Sequence[Package], start_time: datetime) -> Optional[dict]:
    valid, _ = validate_packages(packages)
    if not valid:
        return None

    if len(packages) <= MAX_EXACT_ROUTE_PACKAGES:
        return _exact_best_route(packages, start_time)

    return _greedy_route(packages, start_time)


def create_batch(batch_id: str, packages: Sequence[Package], start_time: datetime):
    valid, message = validate_packages(packages)
    if not valid:
        return None, None, message

    batch = Batch(batch_id=batch_id, packages=list(packages))
    route = find_best_feasible_route(batch.packages, start_time)

    if route is None:
        return None, None, 'No delivery order can satisfy all package deadlines.'

    return batch, route, 'OK'
