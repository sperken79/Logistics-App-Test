"""
main.py

This is the main entry point for the freight rail logistics simulation.
It launches the Textual-based user interface.
"""
import math
from typing import List, Optional

import config
import create_world
from managers import EconomyManager, WaybillManager, TrainManager
from game_objects import Node, Link

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
        self.year = config.STARTING_YEAR
        self.logger.write_line("Simulation initialized.")

    def tick(self):
        """Advances the simulation by one time step."""
        self.waybill_manager.update()
        self.train_manager.update()
        self.game_tick += 1
        self.year = config.STARTING_YEAR + (self.game_tick // (config.TICKS_PER_DAY * 365))

    def build_track(self, node1: Node, node2: Node) -> bool:
        """Handles the logic for building a new track between two nodes."""
        for link in self.waybill_manager.links:
            if (link.node1_id == node1.id and link.node2_id == node2.id) or \
               (link.node1_id == node2.id and link.node2_id == node1.id):
                self.logger.write_line(f"Error: Track between {node1.name} and {node2.name} already exists.")
                return False

        distance = math.hypot(node1.pos[0] - node2.pos[0], node1.pos[1] - node2.pos[1])
        cost = distance * config.TRACK_BUILD_COST_PER_UNIT

        if not self.economy_manager.deduct_cost(cost):
            self.logger.write_line(f"Error: Not enough cash to build track. Cost: ${cost:,.2f}")
            return False

        new_link = Link(node1_id=node1.id, node2_id=node2.id, length=distance, terrain="plains")
        self.waybill_manager.links.append(new_link)

        self.train_manager.links_map[(node1.id, node2.id)] = new_link
        self.train_manager.links_map[(node2.id, node1.id)] = new_link
        self.waybill_manager.adjacency_list[node1.id].append((node2.id, distance))
        self.waybill_manager.adjacency_list[node2.id].append((node1.id, distance))

        self.logger.write_line(f"Successfully built track between {node1.name} and {node2.name} for ${cost:,.2f}.")
        return True

    def build_node(self, x: int, y: int, industry_type: str) -> bool:
        """Handles the logic for building a new node on the map."""
        for node in self.nodes:
            if node.pos == (x, y):
                self.logger.write_line(f"Error: Position ({x},{y}) is already occupied.")
                return False

        cost = config.NODE_BUILD_COST
        if not self.economy_manager.deduct_cost(cost):
            self.logger.write_line(f"Error: Not enough cash to build node. Cost: ${cost:,.2f}")
            return False

        new_node_id = self.waybill_manager._node_id_counter
        self.waybill_manager._node_id_counter += 1

        node_type = 'city' if industry_type == 'city' else 'industry'
        name = f"{industry_type.replace('_', ' ').title()}-{new_node_id}"

        new_node = Node(id=new_node_id, name=name, pos=(x, y), node_type=node_type, industry_type=industry_type)

        self.nodes.append(new_node)
        self.waybill_manager.nodes[new_node_id] = new_node
        self.train_manager.nodes[new_node_id] = new_node
        self.waybill_manager.adjacency_list[new_node_id] = []

        self.logger.write_line(f"Successfully built {name} at ({x},{y}) for ${cost:,.2f}.")
        return True

class StatusPanel(Static):
    """A widget to display game status information."""
    cash = reactive(0)
    tick = reactive(0)
    year = reactive(config.STARTING_YEAR)
    contracts = reactive(0)
    build_track_mode_active = reactive(False)
    build_node_mode_active = reactive(False)

    def watch_tick(self, new_tick: int) -> None:
        self.year = config.STARTING_YEAR + (new_tick // (config.TICKS_PER_DAY * 365))

    def render(self) -> str:
        day_of_year = (self.tick // config.TICKS_PER_DAY) % 365 + 1
        mode_status = ""
        if self.build_track_mode_active:
            mode_status = "[BUILD TRACK]"
        elif self.build_node_mode_active:
            mode_status = "[BUILD NODE]"

        return (
            f"Cash: ${self.cash:,.2f} | "
            f"Date: Y{self.year} D{day_of_year} | "
            f"Tick: {self.tick} | "
            f"Contracts Available: {self.contracts} {mode_status}"
        )

class WorldMap(Static):
    """A widget to display the world map."""
    class NodeClicked(Message):
        def __init__(self, node) -> None:
            super().__init__()
            self.node = node

    class MapClicked(Message):
        def __init__(self, x: int, y: int) -> None:
            super().__init__()
            self.x = x
            self.y = y

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
        width, height = self.map_size
        grid = [[' ' for _ in range(width)] for _ in range(height)]
        for link in self.links:
            node1 = self.node_map.get(link.node1_id)
            node2 = self.node_map.get(link.node2_id)
            if node1 and node2:
                self._draw_line(grid, node1.pos[0], node1.pos[1], node2.pos[0], node2.pos[1], '.')
        for node in self.nodes:
            x, y = node.pos
            if 0 <= x < width and 0 <= y < height:
                if node.id == self.selected_node_id:
                    grid[y][x] = '*'
                else:
                    grid[y][x] = 'C' if node.node_type == 'city' else 'I'
        for train in self.trains.values():
            x, y = -1, -1
            if train.current_location_id is not None:
                if train.current_location_id in self.node_map:
                    x, y = self.node_map[train.current_location_id].pos
            elif train.current_link is not None:
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
            if 0 <= x < width and 0 <= y < height and grid[y][x] == ' ':
                grid[y][x] = 'T'
        return "\n".join("".join(row) for row in grid)

    def on_click(self, event) -> None:
        click_x, click_y = event.x, event.y
        for node in self.nodes:
            if node.pos == (click_x, click_y):
                self.post_message(self.NodeClicked(node))
                return
        if self.app.is_build_node_mode:
            self.post_message(self.MapClicked(click_x, click_y))

class BuildNodeScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static("Select Node Type to Build", id="build_node_title")
        yield DataTable(id="build_node_table")
        yield Button("Cancel", id="cancel_build_node")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_column("Type", key="type")
        for industry_type in config.INDUSTRIES.keys():
            table.add_row(industry_type.replace('_', ' ').title(), key=industry_type)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.dismiss(event.row_key.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_build_node":
            self.dismiss(None)

class CreateTrainScreen(Screen):
    def compose(self) -> ComposeResult:
        current_year = self.app.sim.year
        available_locos = []
        for year, locos in config.LOCOMOTIVE_STATS.items():
            if year <= current_year:
                available_locos.extend(locos.keys())
        loco_options = [(loco, loco) for loco in available_locos]
        yield Vertical(
            Static("Create a New Train", id="create_train_title"),
            Input(placeholder="Train Name (e.g., Express-1)", id="train_name"),
            Select(loco_options, prompt="Select Loco Type", id="loco_type"),
            Input(placeholder="Schedule (e.g., 1,5,3)", id="schedule"),
            Horizontal(Button("Create", variant="primary", id="create"), Button("Cancel", id="cancel"), id="buttons"),
            id="create_train_dialog"
        )
    def on_mount(self) -> None:
        self.query_one("#train_name").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            try:
                name = self.query_one("#train_name", Input).value
                loco_type = self.query_one("#loco_type", Select).value
                schedule_str = self.query_one("#schedule", Input).value
                schedule = [int(n.strip()) for n in schedule_str.split(',')]
                if not name or not loco_type or not schedule:
                    return
                self.app.sim.train_manager.create_train(name, loco_type, schedule)
                self.app.pop_screen()
            except ValueError:
                pass
        elif event.button.id == "cancel":
            self.app.pop_screen()

class SimulationApp(App):
    BINDINGS = [
        Binding("enter", "accept_contract", "Accept Contract"),
        Binding("c", "show_create_train_screen", "Create Train"),
        Binding("b", "toggle_build_track_mode", "Build Track"),
        Binding("n", "toggle_build_node_mode", "Build Node"),
    ]

    is_build_track_mode = reactive(False)
    is_build_node_mode = reactive(False)
    build_mode_origin_node = None
    build_node_type_to_build = None
    displayed_contract_ids = set()

    TITLE = "Freight Rail Logistics Simulation"
    CSS_PATH = "main.css"

    def __init__(self):
        super().__init__()
        self.world_size = (80, 24)
        self.sim = None

    def compose(self) -> ComposeResult:
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
        log_panel = self.query_one("#log_panel", Log)
        self.sim = Simulation(size=self.world_size, seed=12345, logger=log_panel)
        map_container = self.query_one("#map_container")
        map_container.query("Static").remove()
        map_container.mount(WorldMap(self.sim.nodes, self.sim.links, self.sim.train_manager.trains, self.world_size))
        self.query_one("#details_panel").border_title = "Details"
        contracts_table = self.query_one("#contracts_table", DataTable)
        contracts_table.cursor_type = "row"
        contracts_table.add_column("ID", key="id")
        contracts_table.add_column("Origin", key="origin")
        contracts_table.add_column("Dest", key="dest")
        contracts_table.add_column("Cargo", key="cargo")
        trains_table = self.query_one("#trains_table", DataTable)
        trains_table.add_column("ID", key="id")
        trains_table.add_column("Name", key="name")
        trains_table.add_column("State", key="state")
        trains_table.add_column("Location", key="location")
        self.set_interval(1.0 / config.TICKS_PER_DAY, self.run_tick)

    def run_tick(self) -> None:
        if self.sim is None:
            return
        self.sim.tick()
        status_panel = self.query_one(StatusPanel)
        status_panel.cash = self.sim.economy_manager.cash
        status_panel.tick = self.sim.game_tick
        offered_contracts = len([c for c in self.sim.waybill_manager.contracts.values() if c.state == 'offered'])
        status_panel.contracts = offered_contracts
        status_panel.build_track_mode_active = self.is_build_track_mode
        status_panel.build_node_mode_active = self.is_build_node_mode
        world_map = self.query_one(WorldMap)
        world_map.trains = self.sim.train_manager.trains.copy()
        world_map.links = self.sim.waybill_manager.links.copy()
        contracts_table = self.query_one("#contracts_table", DataTable)
        offered_contracts_map = {c.id: c for c in self.sim.waybill_manager.contracts.values() if c.state == 'offered'}
        current_offered_ids = set(offered_contracts_map.keys())
        new_contract_ids = current_offered_ids - self.displayed_contract_ids
        for contract_id in new_contract_ids:
            contract = offered_contracts_map[contract_id]
            origin_name = self.sim.waybill_manager.nodes[contract.origin_id].name
            dest_name = self.sim.waybill_manager.nodes[contract.destination_id].name
            contracts_table.add_row(contract.id, origin_name, dest_name, contract.cargo, key=str(contract.id))
        removed_contract_ids = self.displayed_contract_ids - current_offered_ids
        for contract_id in removed_contract_ids:
            contracts_table.remove_row(str(contract_id))
        self.displayed_contract_ids = current_offered_ids
        trains_table = self.query_one("#trains_table", DataTable)
        trains_table.clear()
        for train in self.sim.train_manager.trains.values():
            location = f"Node {train.current_location_id}" if train.current_location_id is not None else "In Transit"
            trains_table.add_row(train.id, train.name, train.state, location)

    def _accept_selected_contract(self) -> None:
        contracts_table = self.query_one("#contracts_table", DataTable)
        if not contracts_table.is_valid_cursor_coord:
            return
        row_key = contracts_table.cursor_row
        row = contracts_table.get_row_by_key(row_key)
        if row:
            contract_id = row[0]
            if self.sim.waybill_manager.accept_contract(contract_id):
                pass

    def action_accept_contract(self) -> None:
        self._accept_selected_contract()

    def action_show_create_train_screen(self) -> None:
        self.push_screen(CreateTrainScreen())

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.control.id == "contracts_table":
            self._accept_selected_contract()

    def on_world_map_map_clicked(self, message: WorldMap.MapClicked) -> None:
        if self.is_build_node_mode and self.build_node_type_to_build:
            if self.sim.build_node(message.x, message.y, self.build_node_type_to_build):
                self.query_one(WorldMap).nodes = self.sim.nodes.copy()
                self.is_build_node_mode = False
                self.build_node_type_to_build = None

    def on_world_map_node_clicked(self, message: WorldMap.NodeClicked) -> None:
        node = message.node
        world_map = self.query_one(WorldMap)
        log_panel = self.query_one("#log_panel", Log)
        if self.is_build_track_mode:
            if self.build_mode_origin_node is None:
                self.build_mode_origin_node = node
                world_map.selected_node_id = node.id
                log_panel.write(f"Start node [b]{node.name}[/b] selected. Click a second node to build track.")
            else:
                origin_node = self.build_mode_origin_node
                destination_node = node
                if self.sim.build_track(origin_node, destination_node):
                    world_map.links = self.sim.waybill_manager.links.copy()
                self.build_mode_origin_node = None
                world_map.selected_node_id = None
        else:
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

    def action_toggle_build_track_mode(self) -> None:
        self.is_build_track_mode = not self.is_build_track_mode
        self.is_build_node_mode = False
        if not self.is_build_track_mode:
            self.build_mode_origin_node = None
            self.query_one(WorldMap).selected_node_id = None

    def action_toggle_build_node_mode(self) -> None:
        if self.is_build_node_mode:
            self.is_build_node_mode = False
            self.build_node_type_to_build = None
        else:
            def on_select_node_type(industry_type: str):
                if industry_type:
                    self.is_build_node_mode = True
                    self.is_build_track_mode = False
                    self.build_node_type_to_build = industry_type
                    self.query_one("#log_panel", Log).write(f"Build Mode Activated: Click on the map to place a new [b]{industry_type}[/b].")
            self.push_screen(BuildNodeScreen(), on_select_node_type)

if __name__ == "__main__":
    app = SimulationApp()
    app.run()
