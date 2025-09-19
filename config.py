"""
config.py

This file holds all game balance variables and configuration settings
for the freight rail logistics simulation.
"""

# World Generation
WORLD_SIZE = (80, 24)  # Default world size
CITY_DENSITY = 0.01
INDUSTRY_DENSITY = 0.02
TERRAIN_TYPES = {
    "plains": {
        "cost": 1,
        "char": ".",
        "valid_industries": ["forest", "city", "sawmill", "furniture_factory", "power_plant", "grain_elevator", "food_processor"]
    },
    "hills": {
        "cost": 3,
        "char": "n",
        "valid_industries": ["forest", "coal_mine", "steel_mill", "tool_factory"]
    },
    "mountains": {
        "cost": 5,
        "char": "^",
        "valid_industries": ["iron_ore_mine", "coal_mine"]
    },
}

# Economy
STARTING_CASH = 100000
TRACK_BUILD_COST_PER_UNIT = 100
NODE_BUILD_COST = 75000
YARD_UPGRADE_COST = 50000
REVENUE_PER_CARLOAD_DISTANCE_UNIT = 5

# Contracts & Waybills
CONTRACT_OFFER_CHANCE = 0.3
MIN_CONTRACT_LENGTH = 100
MAX_CONTRACT_LENGTH = 500

# Industries & Supply Chains
INDUSTRIES = {
    # Mines
    "coal_mine": {"output": "coal"},
    "iron_ore_mine": {"output": "iron_ore"},
    # Processing
    "steel_mill": {"input": ["coal", "iron_ore"], "output": "steel"},
    "sawmill": {"input": ["logs"], "output": "lumber"},
    "food_processor": {"input": ["grain"], "output": "food"},
    # Raw Materials
    "forest": {"output": "logs"},
    "grain_elevator": {"output": "grain"},
    # Manufacturing
    "furniture_factory": {"input": ["lumber"], "output": "furniture"},
    "tool_factory": {"input": ["steel"], "output": "tools"},
    # Consumers
    "power_plant": {"input": ["coal"], "output": None},
    "city": {"input": ["furniture", "tools", "food"], "output": None}
}

# Train and Railcar
LOCOMOTIVE_STATS = {
    1950: {
        "type_a": {"power": 5, "cost": 10000, "efficiency": 0.8},
        "type_b": {"power": 10, "cost": 25000, "efficiency": 0.6},
    },
    1960: {
        "type_c_diesel": {"power": 15, "cost": 50000, "efficiency": 0.9},
    }
}
RAILCAR_CAPACITY = 1
RAILCAR_UPKEEP_COST = 10
TRAIN_OPERATING_COST_PER_TICK = 50
TRAIN_SPEED = 4.0  # distance units per game tick
MAX_TRAIN_LENGTH = 20
YARD_SWITCHING_TICKS = 5
LOADING_TICKS = 3

# Simulation
TICKS_PER_DAY = 24
STARTING_YEAR = 1950
GAME_SPEED_SECONDS_PER_TICK = 1.0
EMPTY_CAR_REPOSITIONING_PRIORITY = -1
