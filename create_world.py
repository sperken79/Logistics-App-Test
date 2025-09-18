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

def create_world(size: Tuple[int, int]) -> Dict:
    """
    Generates the game world.

    Args:
        size: A tuple (width, height) for the world dimensions.

    Returns:
        A dictionary containing the list of nodes and links.
    """
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
                industry_type = random.choice(list(config.INDUSTRIES.keys()))
                # Avoid placing a city industry type manually
                if industry_type == 'city':
                    continue
                name = f"{industry_type.replace('_', ' ').title()}-{node_id_counter}"
                nodes[node_id_counter] = Node(id=node_id_counter, name=name, pos=(x, y), node_type='industry', industry_type=industry_type)
                node_id_counter += 1

    if not nodes:
        # Ensure at least two nodes exist to prevent errors
        nodes[0] = Node(id=0, name="Start Town", pos=(width//4, height//2), node_type='city', industry_type='city')
        nodes[1] = Node(id=1, name="First Industry", pos=(width*3//4, height//2), node_type='industry', industry_type='coal_mine')


    # 3. Connect nodes with a minimum spanning tree (Prim's algorithm)
    # to ensure all nodes are connected.
    all_node_ids = list(nodes.keys())
    random.shuffle(all_node_ids)

    connected_nodes: Set[int] = {all_node_ids[0]}
    edges_to_consider = []

    # Add initial edges from the starting node
    for other_node_id in all_node_ids[1:]:
        dist = math.hypot(nodes[all_node_ids[0]].pos[0] - nodes[other_node_id].pos[0],
                          nodes[all_node_ids[0]].pos[1] - nodes[other_node_id].pos[1])
        edges_to_consider.append((dist, all_node_ids[0], other_node_id))

    edges_to_consider.sort()

    while edges_to_consider and len(connected_nodes) < len(all_node_ids):
        dist, u_id, v_id = edges_to_consider.pop(0)

        if v_id not in connected_nodes:
            connected_nodes.add(v_id)

            # Calculate terrain cost (simplified)
            mid_x = int((nodes[u_id].pos[0] + nodes[v_id].pos[0]) / 2)
            mid_y = int((nodes[u_id].pos[1] + nodes[v_id].pos[1]) / 2)
            terrain_type = terrain_grid[mid_y][mid_x]
            terrain_cost = config.TERRAIN_TYPES[terrain_type]['cost']

            length = dist * terrain_cost

            links.append(Link(node1_id=u_id, node2_id=v_id, length=length, terrain=terrain_type))

            # Add new edges from the newly connected node
            for other_node_id in all_node_ids:
                if other_node_id not in connected_nodes:
                    new_dist = math.hypot(nodes[v_id].pos[0] - nodes[other_node_id].pos[0],
                                          nodes[v_id].pos[1] - nodes[other_node_id].pos[1])
                    edges_to_consider.append((new_dist, v_id, other_node_id))
            edges_to_consider.sort()

    # 4. (Optional) Add a few extra links to create cycles
    for _ in range(len(nodes) // 4):
        u_id, v_id = random.sample(all_node_ids, 2)

        # Check if link already exists
        is_existing = False
        for link in links:
            if (link.node1_id == u_id and link.node2_id == v_id) or \
               (link.node1_id == v_id and link.node2_id == u_id):
                is_existing = True
                break

        if not is_existing:
            dist = math.hypot(nodes[u_id].pos[0] - nodes[v_id].pos[0],
                              nodes[u_id].pos[1] - nodes[v_id].pos[1])
            mid_x = int((nodes[u_id].pos[0] + nodes[v_id].pos[0]) / 2)
            mid_y = int((nodes[u_id].pos[1] + nodes[v_id].pos[1]) / 2)
            terrain_type = terrain_grid[mid_y][mid_x]
            terrain_cost = config.TERRAIN_TYPES[terrain_type]['cost']
            length = dist * terrain_cost

            links.append(Link(node1_id=u_id, node2_id=v_id, length=length, terrain=terrain_type))


    return {"nodes": list(nodes.values()), "links": links}

if __name__ == '__main__':
    # Example of how to generate a world
    world_data = create_world(config.WORLD_SIZE)
    print(f"Generated {len(world_data['nodes'])} nodes and {len(world_data['links'])} links.")
    # print(world_data)
