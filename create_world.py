"""
create_world.py

This script contains the function to procedurally generate the starting
game world, including the map and nodes (cities/industries).
"""

import random
import math
from typing import List, Tuple, Dict, Set

import config
from game_objects import Node, Link

from typing import Optional

def create_world(size: Tuple[int, int], seed: Optional[int] = None) -> Dict:
    """
    Generates the game world.
    """
    if seed is not None:
        random.seed(seed)

    width, height = size
    nodes: Dict[int, Node] = {}
    links: List[Link] = []
    node_id_counter = 0

    # 1. Generate terrain grid (conceptual, for industry placement)
    # For now, we'll just have plains, hills, and mountains
    terrain_types = ["plains", "hills", "mountains"]
    terrain_grid = [
        [random.choice(terrain_types) for _ in range(width)]
        for _ in range(height)
    ]

    # 2. Place nodes (cities and industries)
    for y in range(height):
        for x in range(width):
            terrain_type = terrain_grid[y][x]

            # Place a city?
            if 'city' in config.TERRAIN_VALID_INDUSTRIES[terrain_type] and random.random() < config.CITY_DENSITY:
                city_config = config.INDUSTRIES['city']
                nodes[node_id_counter] = Node(
                    id=node_id_counter, name=f"City-{node_id_counter}", pos=(x, y),
                    node_type='city', industry_type='city',
                    industry_category=city_config['category'],
                    base_capacity=city_config['capacity_cars_per_month'],
                    business_days=city_config['business_days']
                )
                node_id_counter += 1
                continue

            # Place an industry?
            if random.random() < config.INDUSTRY_DENSITY:
                valid_industries = [
                    ind for ind in config.TERRAIN_VALID_INDUSTRIES[terrain_type] if ind != 'city'
                ]
                if valid_industries:
                    industry_key = random.choice(valid_industries)
                    industry_config = config.INDUSTRIES[industry_key]
                    nodes[node_id_counter] = Node(
                        id=node_id_counter, name=f"{industry_config['name']}-{node_id_counter}", pos=(x, y),
                        node_type='industry', industry_type=industry_key,
                        industry_category=industry_config['category'],
                        base_capacity=industry_config['capacity_cars_per_month'],
                        business_days=industry_config['business_days']
                    )
                    node_id_counter += 1

    if not nodes:
        # Ensure at least two nodes exist to prevent errors
        nodes[0] = Node(id=0, name="Start Town", pos=(width//4, height//2), node_type='city', industry_type='city')
        nodes[1] = Node(id=1, name="First Forest", pos=(width*3//4, height//2), node_type='industry', industry_type='forest')

    # Link generation at start is disabled as per user request.

    return {"nodes": list(nodes.values()), "links": links}

if __name__ == '__main__':
    world_data = create_world(config.WORLD_SIZE, seed=12345)
    print(f"Generated {len(world_data['nodes'])} nodes and {len(world_data['links'])} links using seed 12345.")
