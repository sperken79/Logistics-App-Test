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
from textual.widgets import Header, Footer, Static, DataTable, Input, Button
from textual.reactive import reactive
from textual.containers import ScrollableContainer, Horizontal, Vertical

class Simulation:
    """
    A non-UI class to hold the core simulation state and managers.
    This is now separate from the UI App class.
    """
    def __init__(self, size, seed):
        print("Initializing simulation...")
        world_data = create_world.create_world(size, seed)
        self.nodes = world_data['nodes']
        self.links = world_data['links']

        self.economy_manager = EconomyManager(config.STARTING_CASH)
        self.waybill_manager = WaybillManager(self.nodes, self.links, self.economy_manager)
        self.train_manager = TrainManager(self.nodes, self.links, self.waybill_manager, self.economy_manager)

        self.game_tick = 0
        print("Simulation initialized.")

    def tick(self):
        """Advances the simulation by one time step."""
        print(f"\n--- Advancing Tick {self.game_tick} ---")
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

    def __init__(self, nodes, links, size, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nodes = nodes
        self.links = links
        self.map_size = size

    def render(self) -> str:
        """Render the map as a string."""
        width, height = self.map_size
        # Create a blank grid
        grid = [[' ' for _ in range(width)] for _ in range(height)]

        # Place nodes on the grid
        for node in self.nodes:
            x, y = node.pos
            if 0 <= x < width and 0 <= y < height:
                char = '?'
                if node.node_type == 'city':
                    char = 'C'
                elif node.node_type == 'industry':
                    char = 'I'
                grid[y][x] = char

        # Convert grid to a single string
        return "\n".join("".join(row) for row in grid)

class CreateTrainScreen(Screen):
    """A modal screen for creating a new train."""
    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Create a New Train", id="create_train_title"),
            Input(placeholder="Train Name (e.g., Express-1)", id="train_name"),
            Input(placeholder="Loco Type (e.g., type_a)", id="loco_type"),
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
                loco_type = self.query_one("#loco_type", Input).value
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
        # For now, hardcode the world settings. We'll add a setup screen later.
        self.world_size = (80, 24)
        self.sim = Simulation(size=self.world_size, seed=12345)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield StatusPanel(id="status_panel")
        yield ScrollableContainer(WorldMap(self.sim.nodes, self.sim.links, self.world_size), id="map_container")
        with Horizontal(id="data_tables"):
            yield DataTable(id="contracts_table")
            yield DataTable(id="trains_table")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
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
        self.sim.tick()

        # Update Status Panel
        status_panel = self.query_one(StatusPanel)
        status_panel.cash = self.sim.economy_manager.cash
        status_panel.tick = self.sim.game_tick
        offered_contracts = len([c for c in self.sim.waybill_manager.contracts.values() if c.state == 'offered'])
        status_panel.contracts = offered_contracts

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
        if not contracts_table.is_valid_cursor_coord:
            return

        row_key = contracts_table.cursor_row
        row = contracts_table.get_row_by_key(row_key)
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
