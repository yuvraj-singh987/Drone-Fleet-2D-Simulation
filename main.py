# ============================================================
# DRONE FLEET MANAGEMENT SYSTEM
# MODULAR + MULTI-PACKAGE + TASK-AWARE CHARGING
# ============================================================

from datetime import datetime, timedelta

from assignment import AssignmentEngine
from fleet_manager import FleetManager
from models import Package
from package_manager import create_batch


def read_package(number, now):
    print(f'\n--- Package {number} ---')

    package_id = input(
        'Package ID (Enter for automatic): '
    ).strip() or f'P{number}'

    weight = float(input('Weight (kg): '))
    deadline_minutes = float(input('Deadline from now (minutes): '))
    x = float(input('Drop X: '))
    y = float(input('Drop Y: '))

    return Package(
        package_id=package_id,
        weight=weight,
        location=(x, y),
        deadline_at=now + timedelta(minutes=deadline_minutes),
    )


def main():
    sim_time = datetime.now()
    fleet = FleetManager(sim_time)
    assignment = AssignmentEngine(fleet)

    batch_counter = 1

    print('\n===============================================')
    print('       MODULAR DRONE DELIVERY SYSTEM')
    print('===============================================')
    print('Multiple packages can be carried in one batch.')
    print('Total payload must be <= 2.5 kg.')
    print('For <= 7 packages, all delivery orders are tested.')
    print('Charging is task-aware and need not reach 100%.')

    while True:
        print(f'\nSimulation time: {sim_time.strftime("%H:%M:%S")}')

        fleet.update(sim_time)
        assignment.process_waiting_queue(sim_time)
        fleet.display_status()

        try:
            number_of_packages = int(
                input('\nHow many packages in this batch? ')
            )
        except ValueError:
            print('Please enter an integer.')
            continue

        if number_of_packages <= 0:
            print('Number of packages must be positive.')
            continue

        packages = []
        try:
            for i in range(1, number_of_packages + 1):
                packages.append(read_package(i, sim_time))
        except ValueError:
            print('Invalid numeric input. Batch cancelled.')
            continue

        batch, route, message = create_batch(
            f'B{batch_counter}',
            packages,
            sim_time,
        )

        if batch is None:
            print(f'\nBatch rejected: {message}')
        else:
            print('\nCandidate batch created successfully.')
            print(f'Total payload: {batch.total_weight:.2f} kg')
            print(
                'Selected route: BASE -> '
                + ' -> '.join(p.package_id for p in route['order'])
                + ' -> BASE'
            )
            assignment.submit_batch(batch, sim_time)

        fleet.display_status()

        try:
            advance = float(
                input('\nAdvance simulation by how many minutes? ')
            )
        except ValueError:
            print('Invalid time. Keeping current simulation time.')
            advance = 0.0

        sim_time += timedelta(minutes=max(0.0, advance))

        fleet.update(sim_time)
        assignment.process_waiting_queue(sim_time)
        fleet.display_status()

        again = input('\nAdd another batch? (yes/no): ').strip().lower()
        if again == 'no':
            print('\nSystem stopped accepting new batches.')
            print(
                'Batches still waiting: '
                + str(len(assignment.waiting_batches))
            )
            break

        batch_counter += 1


if __name__ == '__main__':
    main()
