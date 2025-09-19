"""
managers.py

This file contains the core manager classes that run the simulation.
- EconomyManager: Handles player finances.
- WaybillManager: Manages contracts, waybills, and car routing (pathfinding).
- TrainManager: Manages train creation, movement, and operations.
"""

import heapq
import random
import math
from collections import defaultdict
from typing import List, Dict, Optional, Tuple, Set

import config
from game_objects import Node, Link, Railcar, Waybill, Contract, Train

# --- Economy Manager ---

class EconomyManager:
    """Tracks player cash and provides simple methods for transactions."""
    def __init__(self, starting_cash: int):
        self.cash = starting_cash

    def add_revenue(self, amount: int):
        if amount > 0:
            self.cash += amount

    def deduct_cost(self, amount: int) -> bool:
        if amount > 0:
            if self.cash >= amount:
                self.cash -= amount
                return True
            return False
        return True

# --- Waybill and Contract Manager ---

class WaybillManager:
    """Manages contracts, waybills, and finds optimal paths for railcars."""
    def __init__(self, nodes: List[Node], links: List[Link], economy_manager: EconomyManager, logger):
        self.nodes = {node.id: node for node in nodes}
        self.links = links
        self.economy_manager = economy_manager
        self.logger = logger
        self.contracts: Dict[int, Contract] = {}
        self.active_waybills: Dict[int, Waybill] = {}
        self.completed_waybills: List[Waybill] = []
        self._contract_id_counter = 0
        self._waybill_id_counter = 0
        self._railcar_id_counter = 0
        self._node_id_counter = len(nodes)
        self.railcars: Dict[int, Railcar] = {}

        self.adjacency_list = defaultdict(list)
        for link in self.links:
            self.adjacency_list[link.node1_id].append((link.node2_id, link.length))
            self.adjacency_list[link.node2_id].append((link.node1_id, link.length))

    def _get_producing_industries(self) -> List[Node]:
        return [node for node in self.nodes.values() if node.industry_type and config.INDUSTRIES[node.industry_type].get('output')]

    def _get_consuming_industries(self, cargo: str) -> List[Node]:
        return [node for node in self.nodes.values() if node.industry_type and cargo in config.INDUSTRIES[node.industry_type].get('input', [])]

    def find_path(self, start_node_id: int, end_node_id: int) -> Optional[List[int]]:
        if start_node_id not in self.nodes or end_node_id not in self.nodes:
            return None
        open_set = [(0, start_node_id)]
        came_from = {}
        g_score = {node_id: float('inf') for node_id in self.nodes}
        g_score[start_node_id] = 0
        f_score = {node_id: float('inf') for node_id in self.nodes}
        f_score[start_node_id] = self._heuristic(start_node_id, end_node_id)
        while open_set:
            _, current_id = heapq.heappop(open_set)
            if current_id == end_node_id:
                return self._reconstruct_path(came_from, current_id)
            for neighbor_id, length in self.adjacency_list[current_id]:
                tentative_g_score = g_score[current_id] + length
                if tentative_g_score < g_score[neighbor_id]:
                    came_from[neighbor_id] = current_id
                    g_score[neighbor_id] = tentative_g_score
                    f_score[neighbor_id] = tentative_g_score + self._heuristic(neighbor_id, end_node_id)
                    heapq.heappush(open_set, (f_score[neighbor_id], neighbor_id))
        return None

    def _heuristic(self, node1_id: int, node2_id: int) -> float:
        pos1 = self.nodes[node1_id].pos
        pos2 = self.nodes[node2_id].pos
        return math.hypot(pos1[0] - pos2[0], pos1[1] - pos2[1])

    def _reconstruct_path(self, came_from: Dict[int, int], current_id: int) -> List[int]:
        path = [current_id]
        while current_id in came_from:
            current_id = came_from[current_id]
            path.insert(0, current_id)
        return path

    def get_path_distance(self, path: List[int]) -> float:
        distance = 0.0
        for i in range(len(path) - 1):
            node1_id = path[i]
            node2_id = path[i+1]
            for neighbor_id, length in self.adjacency_list[node1_id]:
                if neighbor_id == node2_id:
                    distance += length
                    break
        return distance

    def update(self):
        for node in self.nodes.values():
            for car in node.cars_at_node:
                if car.state in ['loading', 'unloading']:
                    car.ticks_in_state += 1
                    if car.ticks_in_state >= config.LOADING_TICKS:
                        if car.state == 'loading':
                            car.state = 'loaded'
                            self.logger.write_line(f"Car {car.id} finished loading with {car.cargo} at Node {node.id}.")
                        elif car.state == 'unloading':
                            car.state = 'empty'
                            if car.waybill:
                                self.complete_waybill(car.waybill.id)
                            self.logger.write_line(f"Car {car.id} finished unloading at Node {node.id}.")
                        car.ticks_in_state = 0
        for contract_id in list(self.contracts.keys()):
            contract = self.contracts[contract_id]
            if contract.state == 'active':
                contract.remaining_ticks -= 1
                if contract.remaining_ticks <= 0:
                    contract.state = 'expired'
                elif random.random() < contract.cars_per_tick:
                    self._create_waybill_from_contract(contract)
        if random.random() < config.CONTRACT_OFFER_CHANCE:
            producers = self._get_producing_industries()
            if producers:
                origin_node = random.choice(producers)
                cargo = config.INDUSTRIES[origin_node.industry_type]['output']
                consumers = self._get_consuming_industries(cargo)
                if consumers:
                    destination_node = random.choice(consumers)
                    if self.find_path(origin_node.id, destination_node.id):
                        self._create_contract_offer(origin_node.id, destination_node.id, cargo)

    def _create_contract_offer(self, origin_id, dest_id, cargo):
        new_contract = Contract(id=self._contract_id_counter, origin_id=origin_id, destination_id=dest_id, cargo=cargo, cars_per_tick=0.1, remaining_ticks=random.randint(config.MIN_CONTRACT_LENGTH, config.MAX_CONTRACT_LENGTH), state='offered')
        self.contracts[self._contract_id_counter] = new_contract
        self._contract_id_counter += 1

    def accept_contract(self, contract_id: int) -> bool:
        if contract_id in self.contracts and self.contracts[contract_id].state == 'offered':
            self.contracts[contract_id].state = 'active'
            self.logger.write_line(f"Contract {contract_id} accepted!")
            return True
        return False

    def _create_waybill_from_contract(self, contract: Contract):
        car_to_use = None
        for car in self.nodes[contract.origin_id].cars_at_node:
            if car.state == "empty":
                car_to_use = car
                break
        if not car_to_use:
            car_to_use = self.create_railcar(contract.origin_id)
        new_waybill = Waybill(id=self._waybill_id_counter, origin_id=contract.origin_id, destination_id=contract.destination_id, cargo=contract.cargo, state="pending", railcar_id=car_to_use.id)
        self.active_waybills[self._waybill_id_counter] = new_waybill
        self._waybill_id_counter += 1
        car_to_use.waybill = new_waybill
        car_to_use.state = "loading"
        car_to_use.cargo = contract.cargo
        car_to_use.destination_id = contract.destination_id

    def create_railcar(self, location_id: int) -> Railcar:
        new_car = Railcar(id=self._railcar_id_counter, current_location_id=location_id)
        self.railcars[self._railcar_id_counter] = new_car
        self.nodes[location_id].cars_at_node.append(new_car)
        self._railcar_id_counter += 1
        self.economy_manager.deduct_cost(config.RAILCAR_UPKEEP_COST * 10)
        return new_car

    def complete_waybill(self, waybill_id: int):
        if waybill_id in self.active_waybills:
            waybill = self.active_waybills.pop(waybill_id)
            waybill.state = "completed"
            path = self.find_path(waybill.origin_id, waybill.destination_id)
            if path:
                path_dist = self.get_path_distance(path)
                revenue = path_dist * config.REVENUE_PER_CARLOAD_DISTANCE_UNIT
                self.economy_manager.add_revenue(revenue)
            car = self.railcars.get(waybill.railcar_id)
            if car:
                car.state = "empty"
                car.cargo = None
                car.destination_id = None
                car.waybill = None
            self.completed_waybills.append(waybill)

# --- Train Manager ---

class TrainManager:
    """Manages the fleet of trains, their movement, and their interaction with cargo."""
    def __init__(self, nodes: List[Node], links: List[Link], waybill_manager: WaybillManager, economy_manager: EconomyManager, logger):
        self.nodes = {node.id: node for node in nodes}
        self.links_map = {(l.node1_id, l.node2_id): l for l in links}
        self.links_map.update({(l.node2_id, l.node1_id): l for l in links})
        self.waybill_manager = waybill_manager
        self.economy_manager = economy_manager
        self.logger = logger
        self.trains: Dict[int, Train] = {}
        self._train_id_counter = 0

    def _get_loco_stats(self, loco_type: str) -> Optional[dict]:
        for decade, locos in config.LOCOMOTIVE_STATS.items():
            if loco_type in locos:
                return locos[loco_type]
        return None

    def create_train(self, name: str, locomotive_type: str, schedule: List[int]):
        if not schedule:
            self.logger.write_line("Error: Cannot create a train with an empty schedule.")
            return None
        loco_stats = self._get_loco_stats(locomotive_type)
        if not loco_stats:
            self.logger.write_line(f"Error: Unknown or unavailable locomotive type '{locomotive_type}'.")
            return None
        cost = loco_stats['cost']
        if not self.economy_manager.deduct_cost(cost):
            self.logger.write_line("Error: Not enough cash to build this locomotive.")
            return None
        start_node_id = schedule[0]
        new_train = Train(id=self._train_id_counter, name=name, locomotive_type=locomotive_type, schedule=schedule, current_location_id=start_node_id)
        self.trains[self._train_id_counter] = new_train
        self._train_id_counter += 1
        self.logger.write_line(f"Train '{name}' created at Node {start_node_id}.")
        return new_train

    def update(self):
        for train in self.trains.values():
            if train.state == 'idle':
                if train.current_location_id is not None and self._has_work(train):
                    train.state = 'running'
            elif train.state == 'running':
                self.economy_manager.deduct_cost(config.TRAIN_OPERATING_COST_PER_TICK)
                self._move_train(train)
            elif train.state == 'switching':
                train.ticks_at_current_node += 1
                if train.ticks_at_current_node >= config.YARD_SWITCHING_TICKS:
                    self._process_switching_at_node(train)
                    if train.state == 'switching':
                        train.ticks_at_current_node = 0
                        if self._has_work(train):
                            train.state = 'running'
                        else:
                            train.state = 'idle'
            elif train.state == 'waiting_for_yard_space':
                self.logger.write_line(f"Train '{train.name}' is waiting for yard space at Node {train.current_location_id}.")
                self._process_switching_at_node(train)

    def _has_work(self, train: Train) -> bool:
        if train.current_location_id is None:
            return False
        try:
            current_schedule_index = train.schedule.index(train.current_location_id)
        except (ValueError, TypeError):
            return False
        num_stops = len(train.schedule)
        if num_stops < 2: return False
        future_stops = set()
        for i in range(1, num_stops):
            future_index = (current_schedule_index + i) % num_stops
            future_stops.add(train.schedule[future_index])
        for car in train.cars:
            if car.destination_id in future_stops:
                return True
        node = self.nodes[train.current_location_id]
        loco_stats = self._get_loco_stats(train.locomotive_type)
        loco_power = loco_stats['power'] if loco_stats else 0
        if len(train.cars) < loco_power and len(train.cars) < config.MAX_TRAIN_LENGTH:
            for car in node.cars_at_node:
                if car.state == 'loaded' and car.destination_id in future_stops:
                    return True
        return False

    def _find_next_schedule_target(self, train: Train) -> int:
        current_schedule_index = train.schedule.index(train.current_location_id)
        next_schedule_index = (current_schedule_index + 1) % len(train.schedule)
        return train.schedule[next_schedule_index]

    def _move_train(self, train: Train):
        if train.current_link is None:
            if train.current_location_id is None:
                self.logger.write_line(f"Error: Train {train.name} is running but has no location or link. Setting to idle.")
                train.state = 'idle'
                return
            if not train.path or train.path_index >= len(train.path) - 1:
                target_node_id = self._find_next_schedule_target(train)
                path = self.waybill_manager.find_path(train.current_location_id, target_node_id)
                if path and len(path) > 1:
                    train.path = path
                    train.path_index = 0
                else:
                    train.state = 'idle'
                    return
            start_node = train.path[train.path_index]
            end_node = train.path[train.path_index + 1]
            train.current_link = (start_node, end_node)
            train.progress_on_link = 0
            train.current_location_id = None
            self.logger.write_line(f"Train '{train.name}' departing Node {start_node} for Node {end_node}.")
        if train.current_link:
            link_key = train.current_link
            if link_key not in self.links_map:
                link_key = (train.current_link[1], train.current_link[0])
            if link_key in self.links_map:
                link = self.links_map[link_key]
                train.progress_on_link += config.TRAIN_SPEED
                if train.progress_on_link >= link.length:
                    arrival_node_id = train.current_link[1]
                    train.current_location_id = arrival_node_id
                    train.current_link = None
                    train.progress_on_link = 0
                    train.path_index += 1
                    self.logger.write_line(f"Train '{train.name}' arrived at Node {arrival_node_id}.")
                    if arrival_node_id in train.schedule:
                        train.state = 'switching'
                        train.path = []
                        train.path_index = 0
            else:
                self.logger.write_line(f"Error: Could not find link {train.current_link} for train {train.name}")
                train.state = 'idle'

    def _process_switching_at_node(self, train: Train):
        if train.current_location_id is None: return
        node = self.nodes[train.current_location_id]
        loco_stats = self._get_loco_stats(train.locomotive_type)
        loco_power = loco_stats['power'] if loco_stats else 0
        self.logger.write_line(f"Train '{train.name}' switching at Node {node.id} ({node.name}).")
        cars_to_drop = [car for car in train.cars if car.destination_id == node.id]
        if len(node.cars_at_node) + len(cars_to_drop) > node.capacity:
            self.logger.write_line(f"  - Yard at {node.name} is full! Train '{train.name}' must wait.")
            train.state = 'waiting_for_yard_space'
            return
        if train.state == 'waiting_for_yard_space':
            train.state = 'switching'
        for car in cars_to_drop:
            train.cars.remove(car)
            node.cars_at_node.append(car)
            car.current_location_id = node.id
            car.state = 'unloading'
            car.ticks_in_state = 0
            self.logger.write_line(f"  - Dropped off car {car.id} with {car.cargo} at {node.name}. Now unloading.")
        cars_to_pickup = []
        current_schedule_idx = train.schedule.index(node.id)
        future_stops = {train.schedule[(current_schedule_idx + i) % len(train.schedule)] for i in range(1, len(train.schedule))}
        for car in node.cars_at_node:
            if len(train.cars) >= loco_power or len(train.cars) >= config.MAX_TRAIN_LENGTH:
                break
            if car.state == 'loaded' and car.destination_id in future_stops:
                cars_to_pickup.append(car)
        for car in cars_to_pickup:
            node.cars_at_node.remove(car)
            train.cars.append(car)
            car.current_location_id = None
            self.logger.write_line(f"  + Picked up car {car.id} with {car.cargo} for Node {car.destination_id}.")
