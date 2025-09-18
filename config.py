"""
config.py

This file holds all game balance variables and configuration settings
for the freight rail logistics simulation.
"""

# World Generation
WORLD_SIZE = (50, 20)  # Width, Height
CITY_DENSITY = 0.1
INDUSTRY_DENSITY = 0.2
TERRAIN_TYPES = {
    "plains": {"cost": 1, "char": "."},
    "hills": {"cost": 3, "char": "n"},
    "mountains": {"cost": 5, "char": "^"},
}

# Economy
STARTING_CASH = 100000
TRACK_BUILD_COST_PER_UNIT = 100
YARD_UPGRADE_COST = 50000
REVENUE_PER_CARLOAD_DISTANCE_UNIT = 5

# Contracts & Waybills
CONTRACT_OFFER_CHANCE = 0.3 # Chance per tick to generate a new contract offer
MIN_CONTRACT_LENGTH = 100 # In game ticks
MAX_CONTRACT_LENGTH = 500 # In game ticks

# Industries & Supply Chains
INDUSTRIES = {
    "coal_mine": {"output": "coal"},
    "iron_ore_mine": {"output": "iron_ore"},
    "steel_mill": {"input": ["coal", "iron_ore"], "output": "steel"},
    "sawmill": {"input": ["logs"], "output": "lumber"},
    "forest": {"output": "logs"},
    "furniture_factory": {"input": ["lumber"], "output": "furniture"},
    "power_plant": {"input": ["coal"], "output": None},
    "tool_factory": {"input": ["steel"], "output": "tools"},
    "city": {"input": ["furniture", "tools"], "output": None}
}

# Train and Railcar
LOCOMOTIVE_STATS = {
    "type_a": {"power": 5, "cost": 10000, "efficiency": 0.8},
    "type_b": {"power": 10, "cost": 25000, "efficiency": 0.6},
}
RAILCAR_CAPACITY = 1 # How many units of cargo a car can hold
RAILCAR_UPKEEP_COST = 10
TRAIN_OPERATING_COST_PER_TICK = 50
TRAIN_SPEED = 1.0  # distance units per game tick

# Simulation
TICKS_PER_DAY = 24
STARTING_YEAR = 1950
GAME_SPEED_SECONDS_PER_TICK = 1.0 # For the UI, not simulation logic
EMPTY_CAR_REPOSITIONING_PRIORITY = -1 # Lower priority for empty cars
MAX_TRAIN_LENGTH = 20 # Max cars a train can have, regardless of loco power
YARD_SWITCHING_TICKS = 5 # Ticks it takes to process a car in a yard
LOADING_TICKS = 3 # Ticks it takes to load/unload a car at an industry
