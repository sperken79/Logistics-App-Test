"""
main.py

This is the main entry point for the freight rail logistics simulation.
It launches the Pygame-based user interface.
"""

import math
import sys
import logging

import pygame

import config
import create_world
from managers import EconomyManager, WaybillManager, TrainManager
from game_objects import Node, Link

# --- Color Definitions ---
COLOR_BACKGROUND = (20, 20, 40)
COLOR_NODE_CITY = (200, 200, 200)
COLOR_NODE_INDUSTRY = (150, 100, 50)
COLOR_LINK = (100, 100, 100)
COLOR_TRAIN = (255, 0, 0)
COLOR_TEXT = (255, 255, 255)
COLOR_SELECTED = (255, 255, 0)


# --- Logging Setup ---
class PrintLogger:
    def write_line(self, message):
        print(message)
    def write(self, message):
        print(message, end='')

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
        self.node_map = {node.id: node for node in self.nodes}

        self.economy_manager = EconomyManager(config.STARTING_CASH)
        self.waybill_manager = WaybillManager(self.nodes, self.links, self.economy_manager, self.logger)
        self.train_manager = TrainManager(self.nodes, self.links, self.waybill_manager, self.economy_manager, self.logger)

        self.game_tick = 0
        self.logger.write_line("Simulation initialized.")

    def tick(self):
        """Advances the simulation by one time step."""
        self.waybill_manager.update()
        self.train_manager.update()
        self.game_tick += 1

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

class Renderer:
    """Handles all drawing to the screen."""
    def __init__(self, screen, font, sim, world_size):
        self.screen = screen
        self.font = font
        self.sim = sim
        self.world_width, self.world_height = world_size
        self.screen_width, self.screen_height = screen.get_size()
        self.padding = 40 # Increased padding

    def _world_to_screen(self, x, y):
        """Converts world coordinates to screen coordinates."""
        screen_x = int(self.padding + x * (self.screen_width - 2 * self.padding) / self.world_width)
        screen_y = int(self.padding + y * (self.screen_height - 2 * self.padding) / self.world_height)
        return screen_x, screen_y

    def draw(self, ui_state):
        """Draw the entire game state."""
        self.screen.fill(COLOR_BACKGROUND)
        self.draw_links()
        self.draw_nodes(ui_state)
        self.draw_trains()
        self.draw_status_text(ui_state)
        pygame.display.flip()

    def draw_links(self):
        """Draws the rail links."""
        for link in self.sim.links:
            node1 = self.sim.node_map.get(link.node1_id)
            node2 = self.sim.node_map.get(link.node2_id)
            if node1 and node2:
                start_pos = self._world_to_screen(*node1.pos)
                end_pos = self._world_to_screen(*node2.pos)
                pygame.draw.line(self.screen, COLOR_LINK, start_pos, end_pos, 1)

    def draw_nodes(self, ui_state):
        """Draws the nodes (cities and industries)."""
        for node in self.sim.nodes:
            pos = self._world_to_screen(*node.pos)
            color = COLOR_NODE_CITY if node.node_type == 'city' else COLOR_NODE_INDUSTRY
            radius = 7

            if ui_state['build_mode_origin_node'] and ui_state['build_mode_origin_node'].id == node.id:
                 pygame.draw.circle(self.screen, COLOR_SELECTED, pos, radius + 5, 2)
            elif ui_state['selected_node'] and ui_state['selected_node'].id == node.id:
                pygame.draw.circle(self.screen, COLOR_SELECTED, pos, radius + 3, 2)

            pygame.draw.circle(self.screen, color, pos, radius)

    def draw_trains(self):
        """Draws the trains on the map."""
        for train in self.sim.train_manager.trains.values():
            pos = None
            if train.current_location_id is not None:
                node = self.sim.node_map.get(train.current_location_id)
                if node:
                    pos = self._world_to_screen(*node.pos)
            elif train.current_link is not None:
                node1 = self.sim.node_map.get(train.current_link[0])
                node2 = self.sim.node_map.get(train.current_link[1])
                if node1 and node2:
                    link_key = (node1.id, node2.id) if (node1.id, node2.id) in self.sim.train_manager.links_map else (node2.id, node1.id)
                    if link_key in self.sim.train_manager.links_map:
                        link_length = self.sim.train_manager.links_map[link_key].length
                        progress = train.progress_on_link / link_length if link_length > 0 else 0

                        x1, y1 = self._world_to_screen(*node1.pos)
                        x2, y2 = self._world_to_screen(*node2.pos)

                        pos = (int(x1 + (x2 - x1) * progress), int(y1 + (y2 - y1) * progress))

            if pos:
                pygame.draw.rect(self.screen, COLOR_TRAIN, (pos[0] - 4, pos[1] - 4, 8, 8))

    def draw_status_text(self, ui_state):
        """Draws cash, date, and other status info."""
        cash = self.sim.economy_manager.cash
        tick = self.sim.game_tick
        year = config.STARTING_YEAR + (tick // (config.TICKS_PER_DAY * 365))
        day_of_year = (tick // config.TICKS_PER_DAY) % 365 + 1

        status_text = f"Cash: ${cash:,.2f} | Date: Y{year} D{day_of_year}"
        build_mode_status = " | BUILD MODE (B)" if ui_state['is_build_mode'] else ""

        text_surface = self.font.render(status_text + build_mode_status, True, COLOR_TEXT)
        self.screen.blit(text_surface, (10, 10))


class Game:
    """
    The main class for the Pygame application. It handles the game loop,
    rendering, and user input.
    """
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1280, 720))
        pygame.display.set_caption("Freight Rail Logistics Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 24)
        self.running = True

        self.logger = PrintLogger()
        self.sim = Simulation(size=config.WORLD_SIZE, seed=12345, logger=self.logger)
        self.renderer = Renderer(self.screen, self.font, self.sim, config.WORLD_SIZE)

        self.ui_state = {
            'is_build_mode': False,
            'build_mode_origin_node': None,
            'selected_node': None,
        }
        self.tick_timer = 0
        self.ticks_per_second = config.TICKS_PER_DAY

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)
        pygame.quit()
        sys.exit()

    def get_node_at_pos(self, screen_pos):
        """Check if a screen position collides with any node."""
        for node in self.sim.nodes:
            node_screen_pos = self.renderer._world_to_screen(*node.pos)
            distance = math.hypot(screen_pos[0] - node_screen_pos[0], screen_pos[1] - node_screen_pos[1])
            if distance < 10: # Click radius
                return node
        return None

    def handle_events(self):
        """Process Pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_b:
                    self.ui_state['is_build_mode'] = not self.ui_state['is_build_mode']
                    self.ui_state['build_mode_origin_node'] = None # Reset on toggle
                    self.logger.write_line(f"Build mode {'activated' if self.ui_state['is_build_mode'] else 'deactivated'}.")

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    clicked_node = self.get_node_at_pos(event.pos)
                    if self.ui_state['is_build_mode']:
                        self.handle_build_click(clicked_node)
                    else:
                        self.handle_select_click(clicked_node)

    def handle_build_click(self, clicked_node):
        """Handle a click event in build mode."""
        if not clicked_node:
            self.ui_state['build_mode_origin_node'] = None
            return

        if not self.ui_state['build_mode_origin_node']:
            self.ui_state['build_mode_origin_node'] = clicked_node
            self.logger.write_line(f"Build mode: Start node {clicked_node.name} selected.")
        else:
            origin_node = self.ui_state['build_mode_origin_node']
            if origin_node.id != clicked_node.id:
                self.logger.write_line(f"Attempting to build track from {origin_node.name} to {clicked_node.name}.")
                self.sim.build_track(origin_node, clicked_node)
            # Reset after attempting to build
            self.ui_state['build_mode_origin_node'] = None

    def handle_select_click(self, clicked_node):
        """Handle a click event in select mode."""
        self.ui_state['selected_node'] = clicked_node
        if clicked_node:
            self.logger.write_line(f"Selected node: {clicked_node.name} (ID: {clicked_node.id})")
            # Log more details
            self.logger.write_line(f"  Type: {clicked_node.node_type}, Industry: {clicked_node.industry_type}")
            self.logger.write_line(f"  Cars at node: {len(clicked_node.cars_at_node)}")
        else:
            self.logger.write_line("No node selected.")


    def update(self):
        """Update game state based on a timer."""
        self.tick_timer += self.clock.get_time() / 1000.0
        while self.tick_timer > 1.0 / self.ticks_per_second:
            self.sim.tick()
            self.tick_timer -= 1.0 / self.ticks_per_second

    def render(self):
        """Draw everything to the screen."""
        self.renderer.draw(self.ui_state)


if __name__ == "__main__":
    game = Game()
    game.run()
