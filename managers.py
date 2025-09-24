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
import numpy as np
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
        """Adds revenue to the player's cash."""
        if amount > 0:
            self.cash += amount

    def deduct_cost(self, amount: int) -> bool:
        """Deducts a cost from the player's cash. Returns False if unable to afford."""
        if amount > 0:
            if self.cash >= amount:
                self.cash -= amount
                return True
            return False
        return True

# --- Waybill and Contract Manager ---

class WaybillManager:
    """Manages the lifecycle of contracts and waybills, the core of the economy."""
    def __init__(self, nodes: List[Node], links: List[Link], economy_manager: EconomyManager, game_tick: int, logger):
        self.nodes = {node.id: node for node in nodes}
        self.links = links
        self.economy_manager = economy_manager
        self.game_tick = game_tick
        self.logger = logger

        self.contracts: Dict[int, Contract] = {}
        self.waybills: Dict[int, Waybill] = {}

        self._contract_id_counter = 0
        self._waybill_id_counter = 0

        self.adjacency_list = defaultdict(list)
        for link in self.links:
            self.adjacency_list[link.node1_id].append((link.node2_id, link.length))
            self.adjacency_list[link.node2_id].append((link.node1_id, link.length))

    def update(self, train_manager: 'TrainManager'):
        """Primary update loop, called each game tick."""
        self._update_expired_contracts()
        self._try_generate_new_contracts()
        if self.game_tick % config.TICKS_PER_DAY == 0:
            self._generate_waybills_from_active_contracts()
        self._update_waybill_states(train_manager)

    def _update_expired_contracts(self):
        for contract_id in list(self.contracts.keys()):
            contract = self.contracts[contract_id]
            if contract.status == 'offered' and self.game_tick > contract.acceptance_deadline_tick:
                contract.status = 'expired'

    def _try_generate_new_contracts(self):
        if random.random() > config.CONTRACT_OFFER_CHANCE_PER_TICK:
            return
        producers = [n for n in self.nodes.values() if config.INDUSTRIES.get(n.industry_type, {}).get('output')]
        if not producers: return
        origin_node = random.choice(producers)
        cargo = config.INDUSTRIES.get(origin_node.industry_type, {}).get('output')
        consumers = [n for n in self.nodes.values() if cargo in config.INDUSTRIES.get(n.industry_type, {}).get('input', [])]
        if not consumers: return
        destination_node = random.choice(consumers)
        if origin_node.id == destination_node.id: return
        committed_capacity = sum(c.cars_per_month for c in origin_node.active_contracts if c.status == 'active')
        if committed_capacity >= origin_node.base_capacity: return
        self._create_contract_offer(origin_node, destination_node, cargo)

    def _create_contract_offer(self, origin: Node, destination: Node, cargo: str):
        cargo_config = config.COMMODITIES[cargo]
        cars_per_month = random.randint(10, 30)
        new_contract = Contract(
            id=self._contract_id_counter, origin_id=origin.id, destination_id=destination.id, cargo=cargo,
            cars_per_month=cars_per_month, revenue_per_car=cargo_config['base_revenue'],
            deadline_empty_car_hours=cargo_config['deadline_hours'], deadline_loaded_car_hours=cargo_config['deadline_hours'],
            acceptance_deadline_tick=self.game_tick + (config.CONTRACT_ACCEPTANCE_WINDOW_DAYS * config.TICKS_PER_DAY),
            expiration_tick=self.game_tick + (config.CONTRACT_DURATION_MONTHS * config.DAYS_PER_MONTH * config.TICKS_PER_DAY),
            status='offered'
        )
        self.contracts[self._contract_id_counter] = new_contract
        self._contract_id_counter += 1

    def _generate_waybills_from_active_contracts(self):
        day_of_week = (self.game_tick // config.TICKS_PER_DAY) % config.DAYS_PER_WEEK
        for contract in self.contracts.values():
            if contract.status != 'active': continue
            origin_node = self.nodes[contract.origin_id]
            if day_of_week not in origin_node.business_days: continue
            avg_cars_per_day = contract.cars_per_month / len(origin_node.business_days) / (config.DAYS_PER_MONTH / config.DAYS_PER_WEEK)
            variance = avg_cars_per_day * config.DAILY_CAR_GENERATION_VARIANCE
            num_cars_today = max(0, int(np.random.normal(avg_cars_per_day, variance)))
            for _ in range(num_cars_today): self._create_waybill_from_contract(contract)

    def _create_waybill_from_contract(self, contract: Contract):
        creation_tick = self.game_tick
        service_due = creation_tick + contract.deadline_empty_car_hours
        delivery_due = creation_tick + contract.deadline_loaded_car_hours
        new_waybill = Waybill(
            id=self._waybill_id_counter, contract_id=contract.id, origin_id=contract.origin_id, destination_id=contract.destination_id,
            cargo=contract.cargo, creation_tick=creation_tick, service_due_tick=service_due, delivery_due_tick=delivery_due,
        )
        self.waybills[self._waybill_id_counter] = new_waybill
        self._waybill_id_counter += 1

    def _update_waybill_states(self, train_manager: 'TrainManager'):
        """Handles timed state transitions for loading and unloading cars."""
        for car in train_manager.railcars.values():
            if car.waybill and car.waybill.state in ['Loading', 'Unloading']:
                car.ticks_in_state += 1
                if car.waybill.state == 'Loading' and car.ticks_in_state >= config.LOADING_TICKS:
                    car.waybill.state = 'WaitingForPickup'
                    car.ticks_in_state = 0
                elif car.waybill.state == 'Unloading' and car.ticks_in_state >= config.UNLOADING_TICKS:
                    self.complete_waybill(car.waybill, train_manager)
                    car.ticks_in_state = 0

    def complete_waybill(self, waybill: Waybill, train_manager: 'TrainManager'):
        """Finalizes a waybill, calculating revenue and updating service ratings."""
        waybill.state = 'Completed'
        contract = self.contracts.get(waybill.contract_id)
        if contract:
            distance = self._heuristic(waybill.origin_id, waybill.destination_id)
            revenue = contract.revenue_per_car + (distance * config.REVENUE_PER_DISTANCE_UNIT)
            self.economy_manager.add_revenue(revenue)

            origin_node = self.nodes[waybill.origin_id]
            dest_node = self.nodes[waybill.destination_id]
            if self.game_tick <= waybill.delivery_due_tick:
                origin_node.service_rating = min(100, origin_node.service_rating + 1)
                dest_node.service_rating = min(100, dest_node.service_rating + 1)
            else:
                origin_node.service_rating = max(0, origin_node.service_rating - 2)
                dest_node.service_rating = max(0, dest_node.service_rating - 2)

        # Reset the railcar to be available for new tasks
        if waybill.assigned_railcar_id in train_manager.railcars:
            car = train_manager.railcars[waybill.assigned_railcar_id]
            car.waybill = None
            car.state = "empty" # FIX: Reset car state

        if waybill.id in self.waybills:
            del self.waybills[waybill.id]

    def accept_contract(self, contract_id: int) -> bool:
        if contract_id in self.contracts and self.contracts[contract_id].status == 'offered':
            contract = self.contracts[contract_id]
            contract.status = 'active'
            self.nodes[contract.origin_id].active_contracts.append(contract)
            self.nodes[contract.destination_id].active_contracts.append(contract)
            return True
        return False

    def decline_contract(self, contract_id: int) -> bool:
        if contract_id in self.contracts and self.contracts[contract_id].status == 'offered':
            del self.contracts[contract_id]
            return True
        return False

    def find_path(self, start_node_id, end_node_id):
        if start_node_id not in self.nodes or end_node_id not in self.nodes: return None
        open_set = [(0, start_node_id)]
        came_from, g_score, f_score = {}, {}, {}
        g_score = {node_id: float('inf') for node_id in self.nodes}; g_score[start_node_id] = 0
        f_score[start_node_id] = self._heuristic(start_node_id, end_node_id)
        while open_set:
            _, current_id = heapq.heappop(open_set)
            if current_id == end_node_id: return self._reconstruct_path(came_from, current_id)
            for neighbor_id, length in self.adjacency_list[current_id]:
                tentative_g_score = g_score[current_id] + length
                if tentative_g_score < g_score.get(neighbor_id, float('inf')):
                    came_from[neighbor_id] = current_id; g_score[neighbor_id] = tentative_g_score
                    f_score[neighbor_id] = tentative_g_score + self._heuristic(neighbor_id, end_node_id)
                    heapq.heappush(open_set, (f_score[neighbor_id], neighbor_id))
        return None
    def _heuristic(self, n1, n2): return math.hypot(self.nodes[n1].pos[0]-self.nodes[n2].pos[0], self.nodes[n1].pos[1]-self.nodes[n2].pos[1])
    def _reconstruct_path(self, came_from, current):
        path = [current]
        while current in came_from: current = came_from[current]; path.insert(0, current)
        return path

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
        self._railcar_id_counter = 0
        self.railcars: Dict[int, Railcar] = {}

    def create_railcar(self, railcar_type: str, location_id: int) -> Railcar:
        car_config = config.RAILCARS[railcar_type]
        if not self.economy_manager.deduct_cost(car_config['cost']):
            return None
        new_car = Railcar(id=self._railcar_id_counter, railcar_type=railcar_type, current_location_id=location_id)
        self.railcars[self._railcar_id_counter] = new_car
        self._railcar_id_counter += 1
        self.nodes[location_id].cars_at_node.append(new_car)
        return new_car

    def create_train(self, name: str, locomotive_type: str, schedule: List[int]):
        if not schedule: return None
        cost = config.LOCOMOTIVE_STATS[locomotive_type]['cost']
        if not self.economy_manager.deduct_cost(cost): return None
        start_node_id = schedule[0]
        new_train = Train(id=self._train_id_counter, name=name, locomotive_type=locomotive_type, schedule=schedule, current_location_id=start_node_id)

        for _ in range(5):
            car = self.create_railcar('flatcar', start_node_id)
            if car: new_train.cars.append(car)
        for _ in range(5):
            car = self.create_railcar('boxcar', start_node_id)
            if car: new_train.cars.append(car)

        for car in new_train.cars:
            if car in self.nodes[start_node_id].cars_at_node:
                self.nodes[start_node_id].cars_at_node.remove(car)
            car.current_location_id = None

        self.trains[self._train_id_counter] = new_train; self._train_id_counter += 1
        return new_train

    def update(self):
        for train in self.trains.values():
            if train.state == 'idle':
                self._find_and_assign_task(train)
            if train.current_task:
                self._execute_task(train)

    def _find_and_assign_task(self, train: Train):
        for waybill in self.waybill_manager.waybills.values():
            if waybill.state == 'Pending':
                compatible_car = None
                for car in train.cars:
                    if car.state == 'empty' and waybill.cargo in config.RAILCARS[car.railcar_type]['compatible_cargo']:
                        compatible_car = car
                        break
                if compatible_car:
                    train.current_task = waybill
                    waybill.state = 'Servicing'
                    waybill.assigned_train_id = train.id
                    waybill.assigned_railcar_id = compatible_car.id
                    compatible_car.waybill = waybill
                    compatible_car.state = 'in_service'
                    train.state = 'running'
                    return

    def _execute_task(self, train: Train):
        waybill = train.current_task
        if not waybill: train.state = 'idle'; return

        car = self.railcars[waybill.assigned_railcar_id]

        if waybill.state == 'Servicing':
            self._move_train_to_destination(train, waybill.origin_id)
            if train.current_location_id == waybill.origin_id:
                train.cars.remove(car)
                self.nodes[waybill.origin_id].cars_at_node.append(car)
                car.current_location_id = waybill.origin_id
                waybill.state = 'Loading'
        elif waybill.state == 'WaitingForPickup':
            self._move_train_to_destination(train, waybill.origin_id)
            if train.current_location_id == waybill.origin_id:
                self.nodes[waybill.origin_id].cars_at_node.remove(car)
                train.cars.append(car)
                car.current_location_id = None
                waybill.state = 'InTransit'
        elif waybill.state == 'InTransit':
            self._move_train_to_destination(train, waybill.destination_id)
            if train.current_location_id == waybill.destination_id:
                train.cars.remove(car)
                self.nodes[waybill.destination_id].cars_at_node.append(car)
                car.current_location_id = waybill.destination_id
                waybill.state = 'Unloading'
        elif waybill.state == 'Completed':
            train.current_task = None
            train.state = 'idle'

    def _move_train_to_destination(self, train: Train, destination_id: int):
        if train.current_location_id == destination_id: return
        if not train.path or train.path[-1] != destination_id:
            path = self.waybill_manager.find_path(train.current_location_id, destination_id)
            if path and len(path) > 1:
                train.path = path; train.path_index = 0
            else:
                train.state = 'idle'; return

        if train.current_link is None:
            if train.path_index >= len(train.path) -1: return
            start_node = train.path[train.path_index]
            end_node = train.path[train.path_index + 1]
            train.current_link = (start_node, end_node)
            train.progress_on_link = 0
            train.current_location_id = None

        if train.current_link:
            link = self.links_map.get(train.current_link) or self.links_map.get((train.current_link[1], train.current_link[0]))
            if not link:
                train.state = 'idle'; train.current_link = None; return
            train.progress_on_link += 1.0
            if train.progress_on_link >= link.length:
                arrival_node_id = train.current_link[1]
                train.current_location_id = arrival_node_id
                train.current_link = None; train.progress_on_link = 0
                train.path_index += 1
                if arrival_node_id == destination_id:
                    train.path = []; train.path_index = 0
