"""
create_world.py

This script contains the function to procedurally generate the starting
game world, including the map, terrain, nodes (cities/industries), and
the initial track network.
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

    Args:
        size: A tuple (width, height) for the world dimensions.
        seed: An optional integer to seed the random number generator for reproducible worlds.

    Returns:
        A dictionary containing the list of nodes and links.
    """
    if seed is not None:
        random.seed(seed)

    width, height = size
    nodes: Dict[int, Node] = {}
    links: List[Link] = []
    node_id_counter = 0

    # 1. Generate terrain grid (conceptual, for link cost calculation)
    terrain_grid = [
        [random.choice(list(config.TERRAIN_TYPES.keys())) for _ in range(width)]
        for _ in range(height)
    ]

    # 2. Place nodes (cities and industries)
    for y in range(height):
        for x in range(width):
            # Place a city?
            if random.random() < config.CITY_DENSITY:
                name = f"City-{node_id_counter}"
                nodes[node_id_counter] = Node(id=node_id_counter, name=name, pos=(x, y), node_type='city', industry_type='city')
                node_id_counter += 1
                continue # Don't place an industry in the same spot

            # Place an industry?
            if random.random() < config.INDUSTRY_DENSITY:
                terrain_type = terrain_grid[y][x]
                valid_industries = config.TERRAIN_TYPES[terrain_type].get('valid_industries', [])

                # Exclude 'city' type from being placed as an industry here
                valid_industries = [ind for ind in valid_industries if ind != 'city']

                if valid_industries:
                    industry_type = random.choice(valid_industries)
                    name = f"{industry_type.replace('_', ' ').title()}-{node_id_counter}"
                    nodes[node_id_counter] = Node(id=node_id_counter, name=name, pos=(x, y), node_type='industry', industry_type=industry_type)
                    node_id_counter += 1

    if not nodes:
        # Ensure at least two nodes exist to prevent errors
        nodes[0] = Node(id=0, name="Start Town", pos=(width//4, height//2), node_type='city', industry_type='city')
        nodes[1] = Node(id=1, name="First Industry", pos=(width*3//4, height//2), node_type='industry', industry_type='coal_mine')


    # Per user request, the world now starts with no connecting tracks.
    # The player must build the network from scratch.

    return {"nodes": list(nodes.values()), "links": links}

if __name__ == '__main__':
    # Example of how to generate a world
    world_data = create_world(config.WORLD_SIZE, seed=12345)
    print(f"Generated {len(world_data['nodes'])} nodes and {len(world_data['links'])} links using seed 12345.")
    # print(world_data)
