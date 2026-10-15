"""Interactive 2D visualization for the modular drone fleet project.

Run with: python visual_simulation.py

Left-click the map to stage a package. Set weight/deadline in the right panel,
then click DISPATCH BATCH. DEMO + DISPATCH runs a ready-made three-package trip.
The visualization uses the project's existing assignment, routing, battery,
wind and charging modules.
"""

from __future__ import annotations

import contextlib
import io
import math
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pygame

import config
from assignment import AssignmentEngine
from fleet_manager import FleetManager
from models import Package
from package_manager import create_batch
from utils import route_details


# ---------------------------------------------------------------------------
# Visual settings
# ---------------------------------------------------------------------------
WIDTH = 1200
HEIGHT = 760
FPS = 60
SIM_MINUTES_PER_REAL_SECOND = 0.5

BG = (18, 24, 34)
PANEL = (27, 35, 48)
MAP_BG = (21, 31, 43)
GRID = (42, 55, 70)
WHITE = (235, 241, 248)
MUTED = (150, 165, 183)
CYAN = (74, 205, 222)
BLUE = (78, 145, 255)
ORANGE = (255, 166, 70)
GREEN = (70, 210, 140)
YELLOW = (250, 209, 75)
RED = (255, 100, 110)
PURPLE = (180, 130, 255)
DARK = (13, 18, 27)

MAP_RECT = pygame.Rect(20, 70, 755, 670)
SIDEBAR_RECT = pygame.Rect(795, 70, 385, 670)
MAP_CENTER = (MAP_RECT.centerx, MAP_RECT.centery)
PIXELS_PER_METER = 0.26


class DroneFleet2DSimulation:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Drone Fleet Management — 2D Simulation")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("segoeui", 17)
        self.small_font = pygame.font.SysFont("segoeui", 14)
        self.tiny_font = pygame.font.SysFont("segoeui", 12)
        self.bold_font = pygame.font.SysFont("segoeui", 18, bold=True)
        self.title_font = pygame.font.SysFont("segoeui", 24, bold=True)

        self.weight_text = "0.8"
        self.deadline_text = "20"
        self.active_field: Optional[str] = None
        self.paused = False
        self.running = True
        self.wind_index = 0
        self.wind_options = [
            (0.0, 0.0),
            (4.0, 0.0),
            (-3.0, 2.0),
        ]
        config.WIND_VECTOR = self.wind_options[self.wind_index]

        self.message = "Click the map to add packages, or start with DEMO + DISPATCH."
        self.message_until = 0.0
        self.events: List[str] = []
        self.package_counter = 1
        self.batch_counter = 1
        self.pending_packages: List[Package] = []
        self.all_packages: Dict[str, Package] = {}
        self.package_states: Dict[str, str] = {}

        self._make_buttons()
        self._reset_simulation_state()
        self.log("Simulation ready. Space = pause/resume; W = change wind.")

    def _make_buttons(self) -> None:
        self.weight_box = pygame.Rect(815, 119, 150, 31)
        self.deadline_box = pygame.Rect(990, 119, 165, 31)
        self.buttons = {
            "demo": pygame.Rect(815, 164, 340, 36),
            "dispatch": pygame.Rect(815, 208, 165, 34),
            "clear": pygame.Rect(990, 208, 165, 34),
            "pause": pygame.Rect(815, 250, 165, 34),
            "wind": pygame.Rect(990, 250, 165, 34),
            "reset": pygame.Rect(815, 292, 340, 32),
        }

    def _reset_simulation_state(self) -> None:
        self.sim_time = datetime.now().replace(microsecond=0)
        self.fleet = FleetManager(self.sim_time)
        self.assignment = AssignmentEngine(self.fleet)
        self.pending_packages.clear()
        self.all_packages.clear()
        self.package_states.clear()
        self.package_counter = 1
        self.batch_counter = 1
        self.events = []
        self.paused = False

    # ------------------------------------------------------------------
    # Logging / helpers
    # ------------------------------------------------------------------
    def log(self, message: str) -> None:
        clean = message.strip()
        if not clean:
            return
        stamp = self.sim_time.strftime("%H:%M:%S")
        self.events.append(f"{stamp}  {clean}")
        self.events = self.events[-6:]

    def set_message(self, text: str, seconds: float = 4.0) -> None:
        self.message = text
        self.message_until = pygame.time.get_ticks() / 1000.0 + seconds

    def capture(self, callback):
        """Run existing project logic and surface useful status lines in the UI."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = callback()
        useful = (
            "mission completed",
            "charging completed",
            "-> CHARGING",
            "WAITING_CHARGE",
            "WAITING QUEUE",
            "REJECTED",
            "REMOVED",
            "removed from waiting queue",
        )
        for raw in buffer.getvalue().splitlines():
            line = raw.strip()
            if line and any(term.lower() in line.lower() for term in useful):
                self.log(line)
        return result

    def world_to_screen(self, point: Tuple[float, float]) -> Tuple[int, int]:
        x = int(MAP_CENTER[0] + point[0] * PIXELS_PER_METER)
        y = int(MAP_CENTER[1] - point[1] * PIXELS_PER_METER)
        return x, y

    def screen_to_world(self, point: Tuple[int, int]) -> Tuple[float, float]:
        wx = (point[0] - MAP_CENTER[0]) / PIXELS_PER_METER
        wy = (MAP_CENTER[1] - point[1]) / PIXELS_PER_METER
        # Round map-click coordinates to the nearest 10 metres.
        return round(wx / 10) * 10.0, round(wy / 10) * 10.0

    # ------------------------------------------------------------------
    # Package actions
    # ------------------------------------------------------------------
    def add_package_at(self, screen_point: Tuple[int, int]) -> None:
        try:
            weight = float(self.weight_text)
            deadline = float(self.deadline_text)
        except ValueError:
            self.set_message("Weight and deadline must be numbers.")
            return

        if weight <= 0 or deadline <= 0:
            self.set_message("Weight and deadline must both be positive.")
            return

        location = self.screen_to_world(screen_point)
        package = Package(
            package_id=f"P{self.package_counter}",
            weight=weight,
            location=location,
            deadline_at=self.sim_time + timedelta(minutes=deadline),
        )
        self.package_counter += 1
        self.pending_packages.append(package)
        self.all_packages[package.package_id] = package
        self.package_states[package.package_id] = "pending"
        self.log(f"{package.package_id} staged ({weight:.2f} kg)")
        self.set_message(
            f"Added {package.package_id} at ({location[0]:.0f}, {location[1]:.0f}) m."
        )

    def load_demo_batch(self) -> None:
        if self.pending_packages:
            self.set_message("Dispatch or clear pending packages before loading the demo.")
            return

        specifications = [
            ("P", 0.8, (650.0, 100.0), 20.0),
            ("P", 0.6, (-500.0, 450.0), 28.0),
            ("P", 0.5, (200.0, -700.0), 40.0),
        ]
        for _, weight, location, deadline_min in specifications:
            package = Package(
                package_id=f"P{self.package_counter}",
                weight=weight,
                location=location,
                deadline_at=self.sim_time + timedelta(minutes=deadline_min),
            )
            self.package_counter += 1
            self.pending_packages.append(package)
            self.all_packages[package.package_id] = package
            self.package_states[package.package_id] = "pending"

        self.log("Demo batch loaded: 3 packages, 1.90 kg total.")
        self.dispatch_pending()

    def dispatch_pending(self) -> None:
        if not self.pending_packages:
            self.set_message("No pending packages. Click the map or load the demo batch.")
            return

        batch_id = f"B{self.batch_counter}"
        batch, route, message = create_batch(
            batch_id,
            list(self.pending_packages),
            self.sim_time,
        )
        if batch is None:
            self.set_message(f"Batch not dispatchable: {message}", 6.0)
            self.log(f"{batch_id} not created: {message}")
            return

        waiting_before = len(self.assignment.waiting_batches)
        assigned_now = self.capture(
            lambda: self.assignment.submit_batch(batch, self.sim_time)
        )
        entered_queue = len(self.assignment.waiting_batches) > waiting_before

        if assigned_now or entered_queue:
            for package in batch.packages:
                self.package_states[package.package_id] = (
                    "in flight" if assigned_now else "waiting"
                )
            order_text = " → ".join(p.package_id for p in route["order"])
            self.log(
                f"{batch_id} accepted | route {order_text} | "
                f"{batch.total_weight:.2f} kg"
            )
            self.pending_packages.clear()
            self.batch_counter += 1
            if assigned_now:
                self.set_message(f"{batch_id} assigned. Watch the drone follow its route.")
            else:
                self.set_message(f"{batch_id} queued; the system is preparing a feasible drone.")
        else:
            self.set_message(
                "No drone can currently/future-feasibly take this batch. Packages kept pending.",
                6.0,
            )

    def clear_pending(self) -> None:
        for package in self.pending_packages:
            self.all_packages.pop(package.package_id, None)
            self.package_states.pop(package.package_id, None)
        self.pending_packages.clear()
        self.set_message("Pending packages cleared.")

    def toggle_wind(self) -> None:
        self.wind_index = (self.wind_index + 1) % len(self.wind_options)
        config.WIND_VECTOR = self.wind_options[self.wind_index]
        wx, wy = config.WIND_VECTOR
        self.log(f"Wind changed to ({wx:.1f}, {wy:.1f}) m/s; applies to new routes.")
        self.set_message(f"Wind = ({wx:.1f}, {wy:.1f}) m/s for new routes.")

    # ------------------------------------------------------------------
    # Simulation clock and route position
    # ------------------------------------------------------------------
    def update_package_states(self) -> None:
        # Update packages on active drones using each planned arrival timestamp.
        for drone in self.fleet.drones:
            batch = drone.current_batch
            if batch is None:
                continue
            for package in batch.packages:
                arrival = drone.predicted_arrivals.get(package.package_id)
                if arrival and self.sim_time >= arrival:
                    self.package_states[package.package_id] = "delivered"
                else:
                    self.package_states[package.package_id] = "in flight"

        # Waiting batches have not started flying yet.
        for batch in self.assignment.waiting_batches:
            for package in batch.packages:
                self.package_states[package.package_id] = "waiting"

    def update(self, dt_seconds: float) -> None:
        if self.paused:
            return

        self.sim_time += timedelta(
            minutes=dt_seconds * SIM_MINUTES_PER_REAL_SECOND
        )
        self.update_package_states()
        self.capture(
            lambda: self.assignment.process_waiting_queue(self.sim_time)
        )
        self.update_package_states()

    def drone_world_position(self, drone) -> Tuple[float, float]:
        if drone.status != "busy" or not drone.mission_legs or drone.mission_started_at is None:
            return (0.0, 0.0)

        elapsed = max(
            0.0,
            (self.sim_time - drone.mission_started_at).total_seconds() / 60.0,
        )

        for leg in drone.mission_legs:
            duration = max(0.0, float(leg.get("time_minutes", 0.0)))
            start = leg["from"]
            end = leg["to"]
            if duration <= 1e-12:
                continue
            if elapsed <= duration:
                fraction = max(0.0, min(1.0, elapsed / duration))
                return (
                    start[0] + (end[0] - start[0]) * fraction,
                    start[1] + (end[1] - start[1]) * fraction,
                )
            elapsed -= duration

        return (0.0, 0.0)

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def draw_text(self, text, position, color=WHITE, font=None) -> None:
        font = font or self.font
        image = font.render(str(text), True, color)
        self.screen.blit(image, position)

    def draw_button(self, key: str, label: str, color=(54, 69, 88)) -> None:
        rect = self.buttons[key]
        pygame.draw.rect(self.screen, color, rect, border_radius=7)
        pygame.draw.rect(self.screen, (88, 108, 132), rect, 1, border_radius=7)
        text = self.bold_font.render(label, True, WHITE)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _draw_grid(self) -> None:
        pygame.draw.rect(self.screen, MAP_BG, MAP_RECT, border_radius=10)
        pygame.draw.rect(self.screen, (54, 69, 87), MAP_RECT, 1, border_radius=10)

        # Lines every 200 m.
        half_x = MAP_RECT.width / (2 * PIXELS_PER_METER)
        half_y = MAP_RECT.height / (2 * PIXELS_PER_METER)
        x_limit = int(math.ceil(half_x / 200) * 200)
        y_limit = int(math.ceil(half_y / 200) * 200)

        for wx in range(-x_limit, x_limit + 1, 200):
            sx, _ = self.world_to_screen((wx, 0))
            if MAP_RECT.left < sx < MAP_RECT.right:
                pygame.draw.line(self.screen, GRID, (sx, MAP_RECT.top), (sx, MAP_RECT.bottom), 1)
                if wx != 0:
                    self.draw_text(str(wx), (sx + 3, MAP_RECT.top + 5), MUTED, self.tiny_font)

        for wy in range(-y_limit, y_limit + 1, 200):
            _, sy = self.world_to_screen((0, wy))
            if MAP_RECT.top < sy < MAP_RECT.bottom:
                pygame.draw.line(self.screen, GRID, (MAP_RECT.left, sy), (MAP_RECT.right, sy), 1)
                if wy != 0:
                    self.draw_text(str(wy), (MAP_RECT.left + 4, sy + 3), MUTED, self.tiny_font)

        base = self.world_to_screen((0.0, 0.0))
        pygame.draw.line(self.screen, (93, 116, 143), (MAP_RECT.left, base[1]), (MAP_RECT.right, base[1]), 2)
        pygame.draw.line(self.screen, (93, 116, 143), (base[0], MAP_RECT.top), (base[0], MAP_RECT.bottom), 2)
        pygame.draw.circle(self.screen, (65, 84, 108), base, 24, 2)
        pygame.draw.circle(self.screen, CYAN, base, 10)
        pygame.draw.circle(self.screen, DARK, base, 4)
        self.draw_text("BASE", (base[0] + 16, base[1] - 28), WHITE, self.bold_font)
        self.draw_text("Click anywhere in the map to add a package", (MAP_RECT.left + 13, MAP_RECT.top + 13), MUTED, self.small_font)

        # Wind arrow. This is only a legend, not a world-location marker.
        wx, wy = config.WIND_VECTOR
        origin = (MAP_RECT.left + 55, MAP_RECT.top + 66)
        mag = math.hypot(wx, wy)
        if mag > 0:
            direction = (wx / mag, -wy / mag)
            end = (int(origin[0] + direction[0] * 35), int(origin[1] + direction[1] * 35))
            pygame.draw.line(self.screen, ORANGE, origin, end, 3)
            angle = math.atan2(end[1] - origin[1], end[0] - origin[0])
            for offset in (-2.5, 2.5):
                p = (int(end[0] - 10 * math.cos(angle + offset)), int(end[1] - 10 * math.sin(angle + offset)))
                pygame.draw.line(self.screen, ORANGE, end, p, 3)
        self.draw_text(f"Wind ({wx:.1f}, {wy:.1f}) m/s", (MAP_RECT.left + 13, MAP_RECT.top + 82), ORANGE, self.small_font)

    def _draw_route_for_drone(self, drone) -> None:
        if drone.status != "busy" or not drone.mission_legs:
            return
        points = [drone.mission_legs[0]["from"]]
        points.extend(leg["to"] for leg in drone.mission_legs)
        pixels = [self.world_to_screen(point) for point in points]
        if len(pixels) > 1:
            pygame.draw.lines(self.screen, (48, 129, 150), False, pixels, 2)
            for p in pixels[1:-1]:
                pygame.draw.circle(self.screen, (55, 148, 165), p, 3)

    def _draw_packages(self) -> None:
        colors = {
            "pending": YELLOW,
            "waiting": PURPLE,
            "in flight": CYAN,
            "delivered": GREEN,
        }
        for package_id, package in self.all_packages.items():
            point = self.world_to_screen(package.location)
            state = self.package_states.get(package_id, "pending")
            color = colors.get(state, YELLOW)
            radius = 8 if state != "delivered" else 6
            pygame.draw.circle(self.screen, color, point, radius)
            pygame.draw.circle(self.screen, DARK, point, radius, 2)
            label = f"{package_id} {package.weight:.1f}kg"
            self.draw_text(label, (point[0] + 10, point[1] - 16), color, self.small_font)

    def _charging_visual_positions(self):
        base = self.world_to_screen((0, 0))
        slots = [
            (base[0] + 37, base[1] + 34),
            (base[0] + 73, base[1] + 34),
            (base[0] + 109, base[1] + 34),
        ]
        charging = [d for d in self.fleet.drones if d.status == "charging"]
        waiting = [d for d in self.fleet.drones if d.status == "waiting_charge"]
        for i, drone in enumerate(charging):
            pos = slots[i % len(slots)]
            pygame.draw.rect(self.screen, GREEN, pygame.Rect(pos[0] - 12, pos[1] - 10, 24, 20), border_radius=4)
            self.draw_text(drone.drone_id, (pos[0] - 13, pos[1] + 12), GREEN, self.tiny_font)
        for i, drone in enumerate(waiting):
            pos = (base[0] + 38 + (i % 3) * 36, base[1] + 75 + (i // 3) * 26)
            pygame.draw.circle(self.screen, PURPLE, pos, 8)
            self.draw_text(drone.drone_id, (pos[0] - 13, pos[1] + 9), PURPLE, self.tiny_font)
        self.draw_text("Charging pads", (base[0] + 34, base[1] + 6), MUTED, self.tiny_font)

    def _draw_drones(self) -> None:
        # Draw the selected route first so drone icons stay visible above it.
        for drone in self.fleet.drones:
            self._draw_route_for_drone(drone)

        self._charging_visual_positions()
        base_px = self.world_to_screen((0, 0))
        idle_list = [d for d in self.fleet.drones if d.status == "idle"]
        idle_offsets = [(-25, -29), (0, -34), (25, -29), (-35, 0), (35, 0), (-25, 29), (0, 34), (25, 29)]
        idle_offset_map = {d.drone_id: idle_offsets[i % len(idle_offsets)] for i, d in enumerate(idle_list)}

        status_colors = {
            "idle": BLUE,
            "busy": ORANGE,
            "charging": GREEN,
            "waiting_charge": PURPLE,
        }
        for drone in self.fleet.drones:
            if drone.status == "busy":
                world = self.drone_world_position(drone)
                point = self.world_to_screen(world)
            elif drone.status == "idle":
                dx, dy = idle_offset_map.get(drone.drone_id, (0, 0))
                point = (base_px[0] + dx, base_px[1] + dy)
            else:
                # Their icons are drawn at pad / charge queue locations above.
                continue

            color = status_colors.get(drone.status, WHITE)
            pygame.draw.circle(self.screen, DARK, point, 13)
            pygame.draw.circle(self.screen, color, point, 10)
            pygame.draw.circle(self.screen, WHITE, point, 10, 1)
            label = self.small_font.render(drone.drone_id, True, DARK)
            self.screen.blit(label, label.get_rect(center=point))
            if drone.status == "busy":
                pygame.draw.circle(self.screen, ORANGE, point, 15, 1)

    def _draw_sidebar(self) -> None:
        pygame.draw.rect(self.screen, PANEL, SIDEBAR_RECT, border_radius=10)
        pygame.draw.rect(self.screen, (54, 69, 87), SIDEBAR_RECT, 1, border_radius=10)
        x = SIDEBAR_RECT.left + 18

        self.draw_text("CONTROLS", (x, 84), WHITE, self.bold_font)
        self.draw_text("Weight (kg)", (x, 101), MUTED, self.small_font)
        self.draw_text("Deadline (min)", (x + 175, 101), MUTED, self.small_font)

        for name, rect, value in (
            ("weight", self.weight_box, self.weight_text),
            ("deadline", self.deadline_box, self.deadline_text),
        ):
            active = self.active_field == name
            pygame.draw.rect(self.screen, (38, 52, 69) if not active else (45, 72, 90), rect, border_radius=5)
            pygame.draw.rect(self.screen, CYAN if active else (75, 91, 111), rect, 2 if active else 1, border_radius=5)
            self.draw_text(value, (rect.x + 9, rect.y + 6), WHITE, self.font)

        self.draw_button("demo", "DEMO + DISPATCH", (47, 104, 116))
        self.draw_button("dispatch", "DISPATCH BATCH", (50, 111, 82))
        self.draw_button("clear", "CLEAR PENDING", (83, 70, 78))
        self.draw_button("pause", "RESUME" if self.paused else "PAUSE", (70, 83, 106))
        wx, wy = config.WIND_VECTOR
        self.draw_button("wind", f"WIND {wx:.0f}, {wy:.0f}  (W)", (107, 83, 54))
        self.draw_button("reset", "RESET SIMULATION  (R)", (65, 73, 90))

        now_text = self.sim_time.strftime("%H:%M:%S")
        self.draw_text(f"SIM TIME  {now_text}", (x, 334), CYAN, self.bold_font)
        speed_text = f"Time scale: {SIM_MINUTES_PER_REAL_SECOND:.1f} sim min / real sec"
        self.draw_text(speed_text, (x, 357), MUTED, self.tiny_font)

        # Fleet counts.
        counts = {status: len(self.fleet.by_status(status)) for status in ("idle", "busy", "charging", "waiting_charge")}
        summary = (
            f"Idle {counts['idle']}   Busy {counts['busy']}   "
            f"Charging {counts['charging']}/3   Queue {counts['waiting_charge']}"
        )
        self.draw_text(summary, (x, 378), WHITE, self.small_font)
        self.draw_text(f"Delivery batches waiting: {len(self.assignment.waiting_batches)}", (x, 399), MUTED, self.small_font)

        # Drone table, with battery bars.
        self.draw_text("FLEET STATUS", (x, 427), WHITE, self.bold_font)
        status_colors = {
            "idle": BLUE,
            "busy": ORANGE,
            "charging": GREEN,
            "waiting_charge": PURPLE,
        }
        start_y = 451
        for idx, drone in enumerate(self.fleet.drones):
            y = start_y + idx * 18
            col = status_colors.get(drone.status, MUTED)
            pygame.draw.circle(self.screen, col, (x + 5, y + 7), 4)
            self.draw_text(drone.drone_id, (x + 16, y - 2), WHITE, self.small_font)
            state = drone.status.replace("waiting_charge", "wait charge")
            self.draw_text(state, (x + 50, y - 2), col, self.tiny_font)
            # Battery bar.
            bar = pygame.Rect(x + 158, y + 1, 100, 9)
            pygame.draw.rect(self.screen, (48, 59, 73), bar, border_radius=4)
            fill = bar.copy()
            fill.width = int(bar.width * max(0.0, min(1.0, drone.battery / 100.0)))
            if fill.width > 0:
                battery_color = GREEN if drone.battery >= 40 else (YELLOW if drone.battery >= 20 else RED)
                pygame.draw.rect(self.screen, battery_color, fill, border_radius=4)
            self.draw_text(f"{drone.battery:.0f}%", (x + 269, y - 3), WHITE, self.tiny_font)

        # Message strip and event log.
        pygame.draw.line(self.screen, (65, 80, 98), (x, 634), (SIDEBAR_RECT.right - 16, 634), 1)
        now_ticks = pygame.time.get_ticks() / 1000.0
        if self.message and now_ticks <= self.message_until:
            self.draw_text(self.message[:52], (x, 639), YELLOW, self.tiny_font)
        else:
            self.draw_text("Recent events:", (x, 639), MUTED, self.tiny_font)
        for i, event in enumerate(self.events[-3:]):
            self.draw_text(event[:52], (x, 659 + i * 17), MUTED, self.tiny_font)

    def _draw_pending_counter(self) -> None:
        total = sum(p.weight for p in self.pending_packages)
        text = f"Pending to dispatch: {len(self.pending_packages)} package(s), {total:.2f} kg"
        self.draw_text(text, (MAP_RECT.left + 13, MAP_RECT.bottom - 27), YELLOW, self.small_font)

    def draw(self) -> None:
        self.screen.fill(BG)
        self.draw_text("DRONE FLEET MANAGEMENT", (20, 16), WHITE, self.title_font)
        self.draw_text("2D LIVE SIMULATION", (395, 23), CYAN, self.bold_font)
        self.draw_text("Pygame • route • wind • battery • deadlines • charging", (650, 25), MUTED, self.tiny_font)

        self._draw_grid()
        self._draw_drones()
        self._draw_packages()
        self._draw_pending_counter()
        self._draw_sidebar()

        if self.paused:
            shade = pygame.Surface((MAP_RECT.width, MAP_RECT.height), pygame.SRCALPHA)
            shade.fill((5, 10, 18, 95))
            self.screen.blit(shade, MAP_RECT.topleft)
            label = self.title_font.render("PAUSED", True, WHITE)
            self.screen.blit(label, label.get_rect(center=MAP_RECT.center))

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Input / main loop
    # ------------------------------------------------------------------
    def handle_click(self, pos: Tuple[int, int]) -> None:
        if self.weight_box.collidepoint(pos):
            self.active_field = "weight"
            self.weight_text = ""
            return
        if self.deadline_box.collidepoint(pos):
            self.active_field = "deadline"
            self.deadline_text = ""
            return

        for key, rect in self.buttons.items():
            if rect.collidepoint(pos):
                self.active_field = None
                if key == "demo":
                    self.load_demo_batch()
                elif key == "dispatch":
                    self.dispatch_pending()
                elif key == "clear":
                    self.clear_pending()
                elif key == "pause":
                    self.paused = not self.paused
                    self.set_message("Simulation paused." if self.paused else "Simulation resumed.")
                elif key == "wind":
                    self.toggle_wind()
                elif key == "reset":
                    self._reset_simulation_state()
                    self.set_message("Simulation reset.")
                    self.log("Simulation reset.")
                return

        if MAP_RECT.collidepoint(pos):
            self.active_field = None
            self.add_package_at(pos)
        else:
            self.active_field = None

    def handle_text_input(self, text: str) -> None:
        if self.active_field is None:
            return
        if self.active_field == "weight":
            self.weight_text += text
        elif self.active_field == "deadline":
            self.deadline_text += text

    def handle_keydown(self, event) -> None:
        if event.key == pygame.K_ESCAPE:
            self.running = False
        elif event.key == pygame.K_SPACE:
            self.paused = not self.paused
            self.set_message("Simulation paused." if self.paused else "Simulation resumed.")
        elif event.key == pygame.K_w:
            self.toggle_wind()
        elif event.key == pygame.K_r:
            self._reset_simulation_state()
            self.set_message("Simulation reset.")
            self.log("Simulation reset.")
        elif event.key == pygame.K_BACKSPACE and self.active_field:
            if self.active_field == "weight":
                self.weight_text = self.weight_text[:-1]
            else:
                self.deadline_text = self.deadline_text[:-1]
        elif event.key == pygame.K_RETURN:
            self.active_field = None

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                elif event.type == pygame.TEXTINPUT:
                    self.handle_text_input(event.text)
                elif event.type == pygame.KEYDOWN:
                    self.handle_keydown(event)

            self.update(dt)
            self.draw()

        pygame.quit()


def main() -> None:
    try:
        app = DroneFleet2DSimulation()
        app.run()
    except pygame.error as exc:
        print(f"Could not start Pygame display: {exc}", file=sys.stderr)
        print("Check that you are running this on your desktop, not a headless terminal.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
