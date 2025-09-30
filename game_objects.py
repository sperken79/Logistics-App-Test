"""
game_objects.py

Defines the core data structures for the simulation using dataclasses.
These objects represent the physical and economic components of the game world.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Any

# --- World and Network Objects ---

@dataclass
class Node:
    """Represents a single point on the map, like a city, industry, or junction."""
    id: int
    name: str
    pos: Tuple[int, int]
    node_type: str  # e.g., 'city', 'industry', 'junction'
    industry_type: Optional[str] = None # e.g., 'coal_mine', 'steel_mill'
    capacity: int = 50  # Default yard capacity
    cars_at_node: List['Railcar'] = field(default_factory=list)

@dataclass
class Link:
    """Represents a track connection between two nodes."""
    node1_id: int
    node2_id: int
    length: float
    terrain: str

# --- Economic and Cargo Objects ---

@dataclass
class Railcar:
    """Represents a single railcar."""
    id: int
    current_location_id: Optional[int] # Node ID
    car_type: str = "boxcar"
    state: str = "empty"  # 'empty', 'loading', 'loaded', 'unloading'
    cargo: Optional[str] = None
    destination_id: Optional[int] = None
    waybill: Optional['Waybill'] = None
    ticks_in_state: int = 0

@dataclass
class Waybill:
    """Represents a single, specific shipping order for one railcar."""
    id: int
    origin_id: int
    destination_id: int
    cargo: str
    state: str = "pending" # 'pending', 'in_transit', 'completed'
    railcar_id: Optional[int] = None

@dataclass
class Contract:
    """Represents a long-term shipping agreement between two industries."""
    id: int
    origin_id: int
    destination_id: int
    cargo: str
    cars_per_tick: float # How many carloads this contract generates on average
    remaining_ticks: int
    state: str = "offered" # 'offered', 'active', 'expired'

# --- Player-Managed Objects ---

@dataclass
class Train:
    """Represents a player-defined train with a locomotive and a schedule."""
    id: int
    name: str
    locomotive_type: str
    schedule: List[int] # List of Node IDs to visit in order
    current_location_id: Optional[int] # Node ID where the head of the train is
    cars: List[Railcar] = field(default_factory=list)
    state: str = "idle" # 'idle', 'running', 'switching', 'waiting_for_yard_space'
    path: List[int] = field(default_factory=list) # The detailed path it's following
    path_index: int = 0
    ticks_at_current_node: int = 0
    # For realistic movement
    progress_on_link: float = 0.0
    current_link: Optional[Tuple[int, int]] = None
