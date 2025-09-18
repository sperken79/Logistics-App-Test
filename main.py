"""
main.py

This is the main entry point for the freight rail logistics simulation.
It contains the Simulation class that coordinates the managers and the
interactive text-based UI for player interaction.
"""

import time
import sys
from typing import List

import config
import create_world
from managers import EconomyManager, WaybillManager, TrainManager

class Simulation:
    """
    The main class that orchestrates the entire simulation,
    including the game loop and user command processing.
    """
    def __init__(self):
        print("Initializing simulation...")
        world_data = create_world.create_world(config.WORLD_SIZE)
        self.nodes = world_data['nodes']
        self.links = world_data['links']

        self.economy_manager = EconomyManager(config.STARTING_CASH)
        self.waybill_manager = WaybillManager(self.nodes, self.links, self.economy_manager)
        self.train_manager = TrainManager(self.nodes, self.links, self.waybill_manager, self.economy_manager)

        self.game_tick = 0
        self.is_running = True
        print("Simulation initialized. Type 'help' for a list of commands.")

    def tick(self):
        """Advances the simulation by one time step."""
        print(f"\n--- Advancing Tick {self.game_tick} ---")
        self.waybill_manager.update()
        self.train_manager.update()
        self.game_tick += 1

    def run(self):
        """Starts the main game loop and command processor."""
        while self.is_running:
            try:
                command = input("\n> ").strip().lower().split()
                if not command:
                    continue

                cmd = command[0]
                args = command[1:]

                command_map = {
                    'help': self.cmd_help,
                    'quit': self.cmd_quit,
                    'next': self.cmd_next,
                    'status': self.cmd_status,
                    'nodes': self.cmd_nodes,
                    'node': self.cmd_node_details,
                    'contracts': self.cmd_contracts,
                    'accept': self.cmd_accept_contract,
                    'trains': self.cmd_trains,
                    'train': self.cmd_train_details,
                    'create': self.cmd_create,
                }

                if cmd in command_map:
                    command_map[cmd](args)
                else:
                    print("Unknown command. Type 'help' for a list of commands.")

            except (EOFError, KeyboardInterrupt):
                self.is_running = False
                print("\nExiting simulation.")
            except Exception as e:
                print(f"An error occurred: {e}", file=sys.stderr)

    # --- Command Functions ---

    def cmd_help(self, args: List[str]):
        """Prints a list of available commands."""
        print("--- Available Commands ---")
        print("help                      - Show this help message.")
        print("quit                      - Exit the simulation.")
        print("next [N]                  - Advance the simulation by N ticks (default 1).")
        print("status                    - Display current cash and game time.")
        print("nodes                     - List all nodes (cities, industries).")
        print("node <id>                 - View details for a specific node.")
        print("contracts                 - List all available contract offers.")
        print("accept <id>               - Accept a contract offer.")
        print("trains                    - List all your trains.")
        print("train <id>                - View details for a specific train.")
        print("create train <name> <type> <schedule> - Create a new train (e.g., create train Express A 1,2,3).")

    def cmd_quit(self, args: List[str]):
        """Exits the simulation."""
        self.is_running = False
        print("Exiting simulation.")

    def cmd_next(self, args: List[str]):
        """Advances the simulation by N ticks."""
        ticks_to_advance = 1
        if args and args[0].isdigit():
            ticks_to_advance = int(args[0])

        for _ in range(ticks_to_advance):
            if self.is_running:
                self.tick()
                time.sleep(config.GAME_SPEED_SECONDS_PER_TICK)

    def cmd_status(self, args: List[str]):
        """Displays general game status."""
        print(f"--- Game Status ---")
        print(f"Current Tick: {self.game_tick}")
        print(f"Current Year: {config.STARTING_YEAR + (self.game_tick // (config.TICKS_PER_DAY * 365))}")
        print(f"Player Cash: ${self.economy_manager.cash:,.2f}")
        print(f"Active Waybills: {len(self.waybill_manager.active_waybills)}")
        print(f"Offered Contracts: {len([c for c in self.waybill_manager.contracts.values() if c.state == 'offered'])}")

    def cmd_nodes(self, args: List[str]):
        """Lists all nodes."""
        print("--- Nodes ---")
        for node in self.nodes:
            print(f"ID {node.id}: {node.name} ({node.node_type}) at {node.pos}")

    def cmd_node_details(self, args: List[str]):
        """Shows details for a specific node."""
        if not args or not args[0].isdigit():
            print("Usage: node <id>")
            return
        node_id = int(args[0])
        node = self.waybill_manager.nodes.get(node_id)
        if not node:
            print(f"Node with ID {node_id} not found.")
            return

        print(f"--- Node {node.id}: {node.name} ---")
        print(f"Type: {node.node_type}, Industry: {node.industry_type}")
        print(f"Position: {node.pos}")
        print("Cars at this node:")
        if not node.cars_at_node:
            print("  None")
        for car in node.cars_at_node:
            waybill_info = f"to Node {car.destination_id}" if car.waybill else "no waybill"
            print(f"  - Car {car.id}: {car.state}, Cargo: {car.cargo or 'None'}, {waybill_info}")

    def cmd_contracts(self, args: List[str]):
        """Lists offered contracts."""
        print("--- Offered Contracts ---")
        offers = [c for c in self.waybill_manager.contracts.values() if c.state == 'offered']
        if not offers:
            print("No new contract offers at this time.")
            return
        for contract in offers:
            origin = self.waybill_manager.nodes[contract.origin_id].name
            dest = self.waybill_manager.nodes[contract.destination_id].name
            print(f"ID {contract.id}: Ship {contract.cargo} from {origin} to {dest} ({contract.remaining_ticks} ticks remaining)")

    def cmd_accept_contract(self, args: List[str]):
        """Accepts a contract."""
        if not args or not args[0].isdigit():
            print("Usage: accept <id>")
            return
        contract_id = int(args[0])
        if self.waybill_manager.accept_contract(contract_id):
            print(f"Successfully accepted contract {contract_id}.")
        else:
            print(f"Could not accept contract {contract_id}. Is it a valid offer?")

    def cmd_trains(self, args: List[str]):
        """Lists all trains."""
        print("--- Trains ---")
        if not self.train_manager.trains:
            print("You have no trains. Use 'create train' to build one.")
            return
        for train in self.train_manager.trains.values():
            print(f"ID {train.id}: {train.name} ({train.locomotive_type}) at Node {train.current_location_id}, State: {train.state}, Cars: {len(train.cars)}")

    def cmd_train_details(self, args: List[str]):
        """Shows details for a specific train."""
        if not args or not args[0].isdigit():
            print("Usage: train <id>")
            return
        train_id = int(args[0])
        train = self.train_manager.trains.get(train_id)
        if not train:
            print(f"Train with ID {train_id} not found.")
            return

        print(f"--- Train {train.id}: {train.name} ---")
        print(f"Locomotive: {train.locomotive_type}, State: {train.state}")
        print(f"Location: Node {train.current_location_id}")
        schedule_names = [self.waybill_manager.nodes[nid].name for nid in train.schedule]
        print(f"Schedule: {' -> '.join(schedule_names)}")
        print("Cars:")
        if not train.cars:
            print("  None")
        for car in train.cars:
            print(f"  - Car {car.id}: carrying {car.cargo} to Node {car.destination_id}")

    def cmd_create(self, args: List[str]):
        """Handles creation commands, e.g., 'create train'."""
        if not args:
            print("Usage: create train <name> <type> <schedule>")
            return

        if args[0] == 'train':
            if len(args) < 4:
                print("Usage: create train <name> <type> <schedule_node_ids>")
                print("Example: create train Express-1 type_a 1,5,3")
                return

            name = args[1]
            loco_type = args[2]
            try:
                schedule_ids = [int(n) for n in args[3].split(',')]
            except ValueError:
                print("Error: Schedule must be a comma-separated list of node IDs (e.g., 1,5,3).")
                return

            # Validate node IDs
            for node_id in schedule_ids:
                if node_id not in self.waybill_manager.nodes:
                    print(f"Error: Node ID {node_id} in schedule does not exist.")
                    return

            self.train_manager.create_train(name, loco_type, schedule_ids)
        else:
            print(f"Unknown create command: '{args[0]}'. Try 'create train'.")


if __name__ == "__main__":
    sim = Simulation()
    sim.run()
