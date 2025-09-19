"""
main.py

This is the main entry point for the freight rail logistics simulation.
It launches the Textual-based user interface.
"""

from typing import List
import math

import config
import create_world
from managers import EconomyManager, WaybillManager, TrainManager
from game_objects import Node

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, DataTable, Input, Button, Log, Select
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from rich.text import Text
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

    def build_track(self, node1: Node, node2: Node) -> bool:
        """Handles the logic for building a new track between two nodes."""
        # 1. Check for existing link
        for link in self.waybill_manager.links:
            if (link.node1_id == node1.id and link.node2_id == node2.id) or \
               (link.node1_id == node2.id and link.node2_id == node1.id):
                self.logger.write_line(f"Error: Track between {node1.name} and {node2.name} already exists.")
                return False

        # 2. Calculate distance and cost (simplified cost model)
        distance = math.hypot(node1.pos[0] - node2.pos[0], node1.pos[1] - node2.pos[1])
        cost = distance * config.TRACK_BUILD_COST_PER_UNIT

        # 3. Check affordability and deduct cost
        if not self.economy_manager.deduct_cost(cost):
            self.logger.write_line(f"Error: Not enough cash to build track. Cost: ${cost:,.2f}")
            return False

        # 4. Create and add the new link
        new_link = Link(node1_id=node1.id, node2_id=node2.id, length=distance, terrain="plains")
        self.waybill_manager.links.append(new_link)

        # 5. Update graphs for pathfinding
        self.train_manager.links_map[(node1.id, node2.id)] = new_link
        self.train_manager.links_map[(node2.id, node1.id)] = new_link
        self.waybill_manager.adjacency_list[node1.id].append((node2.id, distance))
        self.waybill_manager.adjacency_list[node2.id].append((node1.id, distance))

        self.logger.write_line(f"Successfully built track between {node1.name} and {node2.name} for ${cost:,.2f}.")
        return True

class StatusPanel(Static):
    """A widget to display game status information."""
    cash = reactive(0)
    tick = reactive(0)
    year = reactive(config.STARTING_YEAR)
    contracts = reactive(0)
    build_mode_active = reactive(False)

    def watch_tick(self, new_tick: int) -> None:
        self.year = config.STARTING_YEAR + (new_tick // (config.TICKS_PER_DAY * 365))

    def render(self) -> str:
        day_of_year = (self.tick // config.TICKS_PER_DAY) % 365 + 1
        build_mode_status = "[BUILD MODE]" if self.build_mode_active else ""
        return (
            f"Cash: ${self.cash:,.2f} | "
            f"Date: Y{self.year} D{day_of_year} | "
            f"Tick: {self.tick} | "
            f"Contracts Available: {self.contracts} {build_mode_status}"
        )

class WorldMap(Static):
    """A widget to display the world map."""

    class NodeClicked(Message):
        """Custom message to broadcast when a node is clicked."""
        def __init__(self, node) -> None:
            super().__init__()
            self.node = node

    nodes = reactive(list)
    trains = reactive(dict)
    links = reactive(list)
    selected_node_id = reactive(None)

    def __init__(self, nodes, links, trains, size, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nodes = nodes
        self.links = links
        self.trains = trains
        self.map_size = size
        self.node_map = {node.id: node for node in nodes}

    def _draw_line(self, grid, x1, y1, x2, y2, char):
        """Draws a line on the grid using Bresenham's algorithm."""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        while True:
            if 0 <= y1 < len(grid) and 0 <= x1 < len(grid[0]) and grid[y1][x1] == ' ':
                grid[y1][x1] = char
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy

    def render(self) -> str:
        """Render the map as a string."""
        width, height = self.map_size
        grid = [[' ' for _ in range(width)] for _ in range(height)]

        # Draw links first so nodes are drawn on top
        for link in self.links:
            node1 = self.node_map.get(link.node1_id)
            node2 = self.node_map.get(link.node2_id)
            if node1 and node2:
                self._draw_line(grid, node1.pos[0], node1.pos[1], node2.pos[0], node2.pos[1], '.')

        # Place nodes
        for node in self.nodes:
            x, y = node.pos
            if 0 <= x < width and 0 <= y < height:
                if node.id == self.selected_node_id:
                    grid[y][x] = '*'  # Highlight selected node
                else:
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

    def on_click(self, event) -> None:
        """Handle clicks on the map."""
        # For now, we allow clicking to see details regardless of build mode.
        # This might change when we implement track building.
        click_x, click_y = event.x, event.y
        for node in self.nodes:
            if node.pos == (click_x, click_y):
                self.post_message(self.NodeClicked(node))
                break

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
        Binding("enter", "accept_contract", "Accept Contract"),
        Binding("c", "show_create_train_screen", "Create Train"),
        Binding("b", "toggle_build_mode", "Build Track"),
    ]

    is_build_mode = reactive(False)
    build_mode_origin_node = None

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
        yield ScrollableContainer(Static(id="world_map"), id="map_container")
        with Horizontal(id="data_tables"):
            yield DataTable(id="contracts_table")
            yield DataTable(id="trains_table")
        with Horizontal(id="bottom_panels"):
            yield Log(id="log_panel", max_lines=200)
            yield Static("Click a node for details.", id="details_panel")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        log_panel = self.query_one("#log_panel", Log)
        self.sim = Simulation(size=self.world_size, seed=12345, logger=log_panel)

        # Now that sim is created, populate the map
        map_container = self.query_one("#map_container")
        map_container.query("Static").remove()
        map_container.mount(WorldMap(self.sim.nodes, self.sim.links, self.sim.train_manager.trains, self.world_size))

        # Give the details panel a border
        self.query_one("#details_panel").border_title = "Details"

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
        status_panel.build_mode_active = self.is_build_mode

        # Update World Map
        world_map = self.query_one(WorldMap)
        world_map.trains = self.sim.train_manager.trains.copy()
        world_map.links = self.sim.waybill_manager.links.copy()

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

    def on_world_map_node_clicked(self, message: WorldMap.NodeClicked) -> None:
        """Handle a node being clicked on the map."""
        node = message.node
        world_map = self.query_one(WorldMap)
        log_panel = self.query_one("#log_panel", Log)

        if self.is_build_mode:
            if self.build_mode_origin_node is None:
                self.build_mode_origin_node = node
                world_map.selected_node_id = node.id
                log_panel.write(f"Start node [b]{node.name}[/b] selected. Click a second node to build track.")
            else:
                origin_node = self.build_mode_origin_node
                destination_node = node

                if self.sim.build_track(origin_node, destination_node):
                    # If build is successful, refresh the map instantly
                    world_map.links = self.sim.waybill_manager.links.copy()

                # Reset for the next build action
                self.build_mode_origin_node = None
                world_map.selected_node_id = None
        else:
            # If not in build mode, just show details
            details_panel = self.query_one("#details_panel", Static)
            content = Text.from_markup(f"[b]Node {node.id}: {node.name}[/b]\n")
            content.append(f"Type: {node.node_type.title()}\n")
            if node.industry_type:
                content.append(f"Industry: {node.industry_type.replace('_', ' ').title()}\n")
            content.append(f"Yard Capacity: {len(node.cars_at_node)} / {node.capacity}\n\n")

            content.append("[u]Cars at this location:[/u]\n")
            if not node.cars_at_node:
                content.append("None")
            else:
                for car in node.cars_at_node:
                    waybill_info = f"to Node {car.destination_id}" if car.waybill else "no waybill"
                    content.append(f" - Car {car.id}: {car.state}, Cargo: {car.cargo or 'None'}, {waybill_info}\n")
            details_panel.update(content)

    def action_toggle_build_mode(self) -> None:
        """Toggles track building mode."""
        self.is_build_mode = not self.is_build_mode
        # Clear any selection when toggling build mode
        if not self.is_build_mode:
            self.build_mode_origin_node = None
            self.query_one(WorldMap).selected_node_id = None

if __name__ == "__main__":
    app = SimulationApp()
    app.run()
