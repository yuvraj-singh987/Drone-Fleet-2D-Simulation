DRONE FLEET MANAGEMENT - 2D SIMULATION
======================================

Install the one extra visual dependency:
    python -m pip install -r requirements.txt

Run the graphical simulation:
    python visual_simulation.py

Controls:
- Click on the map: add a package at that coordinate.
- Weight and deadline boxes: click a field and type a number.
- DEMO + DISPATCH: loads three example packages and dispatches them.
- DISPATCH BATCH: dispatches all staged packages as one batch.
- CLEAR PENDING: removes staged packages.
- PAUSE / RESUME or Space: pause/resume simulated time.
- WIND button or W: cycles through calm wind and two wind vectors.
- RESET SIMULATION or R: resets the drone fleet and packages.
- Esc: close the window.

Time is simulated, not real wall-clock time. One real second advances the
simulation by approximately 0.5 simulated minutes. Flight paths are animated
from the planned per-leg times. Changing wind affects new routes; currently
flying drones keep the route/time plan calculated when they were dispatched.

The existing main.py terminal interface is retained. Use it as before with:
    python main.py

Model assumptions are documented in config.py. The payload-speed relation,
full-load energy multiplier, and safety reserve are configurable assumptions,
not exact physical data supplied by the problem statement.
