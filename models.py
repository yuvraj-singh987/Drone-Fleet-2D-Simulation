# ============================================================
# DATA MODELS
# ============================================================

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class Package:
    package_id: str
    weight: float
    location: Tuple[float, float]
    deadline_at: datetime


@dataclass
class Batch:
    batch_id: str
    packages: List[Package] = field(default_factory=list)

    @property
    def total_weight(self) -> float:
        return sum(p.weight for p in self.packages)


@dataclass
class Drone:
    drone_id: str
    position: Tuple[float, float]
    battery: float
    status: str
    payload: float = 0.0
    cycles: int = 0
    available_at: Optional[datetime] = None
    current_batch: Optional[Batch] = None
    route: List[str] = field(default_factory=list)
    predicted_arrivals: Dict[str, datetime] = field(default_factory=dict)
    mission_started_at: Optional[datetime] = None
    mission_legs: List[dict] = field(default_factory=list)

    # Charging state
    charge_target: Optional[float] = None
    charge_started_at: Optional[datetime] = None
    charge_start_battery: Optional[float] = None
    charge_for_batch: Optional[str] = None

    @property
    def effective_capacity(self) -> float:
        return max(0.0, 100.0 - self.cycles * 0.05)
