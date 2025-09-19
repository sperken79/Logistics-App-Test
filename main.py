"""
main.py

This is the main entry point for the freight rail logistics simulation.
It launches the Textual-based user interface.
"""

from typing import List

import config
import create_world
from managers import EconomyManager, WaybillManager, TrainManager

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, DataTable, Input, Button, Log, Select
from textual.reactive import reactive
from textual.containers import ScrollableContainer, Horizontal, Vertical

class Simulation:
    """
    A non-UI class to hold the core simulation state and managers.
    This is now separate from the UI App class.
    """
    def __init__(self, size, seed, logger):
        self.logger = logger
        self.logger.write_line("Initializing simulation...")
        world_data = create_world.create_world(size, seed)
        self.nodes = world_data['nodes']
        self.links = world_data['links']

        self.economy_manager = EconomyManager(config.STARTING_CASH)
        self.waybill_manager = WaybillManager(self.nodes, self.links, self.economy_manager, self.logger)
        self.train_manager = TrainManager(self.nodes, self.links, self.waybill_manager, self.economy_manager, self.logger)

        self.game_tick = 0
        self.logger.write_line("Simulation initialized.")

    def tick(self):
        """Advances the simulation by one time step."""
        # self.logger.write_line(f"--- Advancing Tick {self.game_tick} ---") # This gets too spammy
        self.waybill_manager.update()
        self.train_manager.update()
        self.game_tick += 1

class StatusPanel(Static):
    """A widget to display game status information."""
    cash = reactive(0)
    tick = reactive(0)
    year = reactive(config.STARTING_YEAR)
    contracts = reactive(0)

    def watch_tick(self, new_tick: int) -> None:
        self.year = config.STARTING_YEAR + (new_tick // (config.TICKS_PER_DAY * 365))

    def render(self) -> str:
        day_of_year = (self.tick // config.TICKS_PER_DAY) % 365 + 1
        return (
            f"Cash: ${self.cash:,.2f} | "
            f"Date: Y{self.year} D{day_of_year} | "
            f"Tick: {self.tick} | "
            f"Contracts Available: {self.contracts}"
        )

class WorldMap(Static):
    """A widget to display the world map."""

    nodes = reactive(list)
    trains = reactive(dict)

    def __init__(self, nodes, links, trains, size, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nodes = nodes
        self.links = links
        self.trains = trains
        self.map_size = size
        self.node_map = {node.id: node for node in nodes}

    def render(self) -> str:
        """Render the map as a string."""
        width, height = self.map_size
        grid = [[' ' for _ in range(width)] for _ in range(height)]

        # Place nodes
        for node in self.nodes:
            x, y = node.pos
            if 0 <= x < width and 0 <= y < height:
                grid[y][x] = 'C' if node.node_type == 'city' else 'I'

        # Place trains
        for train in self.trains.values():
            x, y = -1, -1
            if train.current_location_id is not None:
                if train.current_location_id in self.node_map:
                    x, y = self.node_map[train.current_location_id].pos
            elif train.current_link is not None:
                # Interpolate position on link
                node1 = self.node_map.get(train.current_link[0])
                node2 = self.node_map.get(train.current_link[1])
                if node1 and node2:
                    link_key = (node1.id, node2.id) if (node1.id, node2.id) in self.app.sim.train_manager.links_map else (node2.id, node1.id)
                    if link_key in self.app.sim.train_manager.links_map:
                        link_length = self.app.sim.train_manager.links_map[link_key].length
                        progress = train.progress_on_link / link_length if link_length > 0 else 0

                        x1, y1 = node1.pos
                        x2, y2 = node2.pos
                        x = int(x1 + (x2 - x1) * progress)
                        y = int(y1 + (y2 - y1) * progress)

            if 0 <= x < width and 0 <= y < height:
                # Prevent train icon from overwriting a node icon
                if grid[y][x] == ' ':
                    grid[y][x] = 'T'

        return "\n".join("".join(row) for row in grid)

class CreateTrainScreen(Screen):
    """A modal screen for creating a new train."""
    def compose(self) -> ComposeResult:
        loco_options = [(loco, loco) for loco in config.LOCOMOTIVE_STATS.keys()]
        yield Vertical(
            Static("Create a New Train", id="create_train_title"),
            Input(placeholder="Train Name (e.g., Express-1)", id="train_name"),
            Select(loco_options, prompt="Select Loco Type", id="loco_type"),
            Input(placeholder="Schedule (e.g., 1,5,3)", id="schedule"),
            Horizontal(
                Button("Create", variant="primary", id="create"),
                Button("Cancel", id="cancel"),
                id="buttons"
            ),
            id="create_train_dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            try:
                name = self.query_one("#train_name", Input).value
                loco_type = self.query_one("#loco_type", Select).value
                schedule_str = self.query_one("#schedule", Input).value
                schedule = [int(n.strip()) for n in schedule_str.split(',')]

                # Basic validation
                if not name or not loco_type or not schedule:
                    # Could add a popup/notification later
                    return

                self.app.sim.train_manager.create_train(name, loco_type, schedule)
                self.app.pop_screen()

            except ValueError:
                # Handle error if schedule is not valid integers
                # Could add a popup/notification later
                pass
        elif event.button.id == "cancel":
            self.app.pop_screen()


class SimulationApp(App):
    """The main Textual application for the simulation."""

    BINDINGS = [
        ("enter", "accept_contract", "Accept Contract"),
        ("c", "show_create_train_screen", "Create Train"),
    ]

    TITLE = "Freight Rail Logistics Simulation"
    CSS_PATH = "main.css" # We can add styling later

    def __init__(self):
        super().__init__()
        self.world_size = (80, 24)
        # The simulation is now initialized in on_mount, after the logger is available
        self.sim = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield StatusPanel(id="status_panel")
        # The map and tables will be populated after the simulation is created
        yield ScrollableContainer(Static(id="world_map"), id="map_container")
        with Horizontal(id="data_tables"):
            yield DataTable(id="contracts_table")
            yield DataTable(id="trains_table")
        yield Log(id="log_panel", max_lines=100)
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        log_panel = self.query_one(Log)
        self.sim = Simulation(size=self.world_size, seed=12345, logger=log_panel)

        # Now that sim is created, populate the map
        map_container = self.query_one("#map_container")
        # We have to remove the placeholder static widget first
        map_container.query("Static").remove()
        map_container.mount(WorldMap(self.sim.nodes, self.sim.links, self.sim.train_manager.trains, self.world_size))

        # Setup Contracts Table
        contracts_table = self.query_one("#contracts_table", DataTable)
        contracts_table.cursor_type = "row"
        contracts_table.add_column("ID", key="id")
        contracts_table.add_column("Origin", key="origin")
        contracts_table.add_column("Dest", key="dest")
        contracts_table.add_column("Cargo", key="cargo")

        # Setup Trains Table
        trains_table = self.query_one("#trains_table", DataTable)
        trains_table.add_column("ID", key="id")
        trains_table.add_column("Name", key="name")
        trains_table.add_column("State", key="state")
        trains_table.add_column("Location", key="location")

        self.set_interval(1.0 / config.TICKS_PER_DAY, self.run_tick)

    def run_tick(self) -> None:
        """Run one tick of the simulation and update the UI."""
        if self.sim is None:
            return
        self.sim.tick()

        # Update Status Panel
        status_panel = self.query_one(StatusPanel)
        status_panel.cash = self.sim.economy_manager.cash
        status_panel.tick = self.sim.game_tick
        offered_contracts = len([c for c in self.sim.waybill_manager.contracts.values() if c.state == 'offered'])
        status_panel.contracts = offered_contracts

        # Update World Map
        world_map = self.query_one(WorldMap)
        world_map.trains = self.sim.train_manager.trains.copy()

        # Update Contracts Table
        contracts_table = self.query_one("#contracts_table", DataTable)
        contracts_table.clear()
        for contract in self.sim.waybill_manager.contracts.values():
            if contract.state == 'offered':
                origin_name = self.sim.waybill_manager.nodes[contract.origin_id].name
                dest_name = self.sim.waybill_manager.nodes[contract.destination_id].name
                contracts_table.add_row(contract.id, origin_name, dest_name, contract.cargo)

        # Update Trains Table
        trains_table = self.query_one("#trains_table", DataTable)
        trains_table.clear()
        for train in self.sim.train_manager.trains.values():
            location = f"Node {train.current_location_id}" if train.current_location_id is not None else "In Transit"
            trains_table.add_row(train.id, train.name, train.state, location)

    def _accept_selected_contract(self) -> None:
        """Accepts the currently selected contract in the DataTable."""
        contracts_table = self.query_one("#contracts_table", DataTable)
        if not contracts_table.is_valid_coordinate(contracts_table.cursor_coordinate):
            return

        row_index = contracts_table.cursor_row
        if row_index >= 0 and row_index < contracts_table.row_count:
            row = contracts_table.get_row_at(row_index)
            if row:
                contract_id = row[0]
                if self.sim.waybill_manager.accept_contract(contract_id):
                    # The UI will update on the next tick automatically
                    pass

    def action_accept_contract(self) -> None:
        """Called when the user presses the 'enter' key."""
        self._accept_selected_contract()

    def action_show_create_train_screen(self) -> None:
        """Pushes the CreateTrainScreen onto the view."""
        self.push_screen(CreateTrainScreen())

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Called when a user clicks a row in a DataTable."""
        if event.control.id == "contracts_table":
            self._accept_selected_contract()

if __name__ == "__main__":
    app = SimulationApp()
    app.run()
