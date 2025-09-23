"""
config.py

This file holds all game balance variables and configuration settings
for the freight rail logistics simulation.
"""

# --- Calendar & Time ---
TICKS_PER_DAY = 24
DAYS_PER_WEEK = 7
DAYS_PER_MONTH = 30
DAYS_PER_YEAR = 365
STARTING_YEAR = 1950

# --- World Generation ---
WORLD_SIZE = (50, 20)
CITY_DENSITY = 0.1
INDUSTRY_DENSITY = 0.2

# --- Economy ---
STARTING_CASH = 250000
TRACK_BUILD_COST_PER_UNIT = 100
# Revenue is now calculated per-contract based on commodity and distance
# See COMMODITIES for base values.

# --- Commodities ---
# Defines properties for each type of cargo.
# base_revenue: Base payment for a single carload delivery.
# deadline_hours: Time limit for each stage of delivery (empty + loaded).
COMMODITIES = {
    "logs": {
        "name": "Logs",
        "base_revenue": 300,
        "deadline_hours": 168 # 7 days
    },
    "lumber": {
        "name": "Lumber",
        "base_revenue": 450,
        "deadline_hours": 120 # 5 days
    },
    "furniture": {
        "name": "Furniture",
        "base_revenue": 700,
        "deadline_hours": 72 # 3 days
    },
}

# --- Industries & Supply Chains ---
# A simple, linear supply chain to start.
# capacity_cars_per_month: The total number of carloads this industry can support.
# business_days: A list of integers from 0 (Monday) to 6 (Sunday).
INDUSTRIES = {
    "forest": {
        "name": "Forest",
        "category": "forest",
        "output": "logs",
        "capacity_cars_per_month": 80,
        "business_days": [0, 1, 2, 3, 4] # Mon-Fri
    },
    "sawmill": {
        "name": "Sawmill",
        "category": "forest",
        "input": ["logs"],
        "output": "lumber",
        "capacity_cars_per_month": 60,
        "business_days": [0, 1, 2, 3, 4] # Mon-Fri
    },
    "furniture_factory": {
        "name": "Furniture Factory",
        "category": "manufacturing",
        "input": ["lumber"],
        "output": "furniture",
        "capacity_cars_per_month": 40,
        "business_days": [0, 1, 2, 3, 4, 5] # Mon-Sat
    },
    "city": {
        "name": "City",
        "category": "city",
        "input": ["furniture"],
        "capacity_cars_per_month": 100,
        "business_days": [0, 1, 2, 3, 4, 5, 6] # Every day
    }
}

# List of valid industries for each terrain type during world generation
TERRAIN_VALID_INDUSTRIES = {
    "plains": ["city", "furniture_factory", "sawmill"],
    "hills": ["forest", "sawmill"],
    "mountains": ["forest"],
}


# --- Train and Railcar ---
LOCOMOTIVE_STATS = {
    "type_a": {"power": 10, "cost": 10000},
    "type_b": {"power": 20, "cost": 25000},
}
# Defines railcar types and which commodities they can carry.
RAILCARS = {
    "flatcar": {
        "name": "Flatcar",
        "compatible_cargo": ["logs", "lumber"],
        "cost": 1000
    },
    "boxcar": {
        "name": "Boxcar",
        "compatible_cargo": ["furniture"],
        "cost": 1200
    }
}
MAX_TRAIN_LENGTH = 25 # Max cars a train can have

# --- Simulation Parameters ---
# How often the game tries to generate new contract offers
CONTRACT_OFFER_CHANCE_PER_TICK = 0.1
# How long a contract offer is valid for
CONTRACT_ACCEPTANCE_WINDOW_DAYS = 30
# How long an accepted contract lasts
CONTRACT_DURATION_MONTHS = 36 # 3 years
# Variance for daily car generation from contracts
DAILY_CAR_GENERATION_VARIANCE = 0.3 # 30%
# Time it takes to load/unload a car at an industry
LOADING_TICKS = 12 # 12 hours
UNLOADING_TICKS = 12 # 12 hours
