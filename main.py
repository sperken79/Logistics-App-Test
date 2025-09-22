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
COLOR_PANEL = (50, 50, 80)
COLOR_BUTTON = (80, 80, 110)
COLOR_BUTTON_HOVER = (110, 110, 140)
COLOR_INPUT_BOX = (20, 20, 30)
COLOR_INPUT_BOX_ACTIVE = (200, 200, 220)


# --- Logging Setup ---
class PrintLogger:
    def write_line(self, message):
        print(message)
    def write(self, message):
        print(message, end='')

class Simulation:
    """A non-UI class to hold the core simulation state and managers."""
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
        self.waybill_manager.update()
        self.train_manager.update()
        self.game_tick += 1

    def build_track(self, node1: Node, node2: Node) -> bool:
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

class UIManager:
    """Handles drawing and interaction for all UI elements."""
    def __init__(self, screen, font, sim):
        self.screen = screen
        self.font = font
        self.sim = sim
        self.screen_width, self.screen_height = screen.get_size()

        # Define UI element rectangles
        self.trains_panel_rect = pygame.Rect(10, 50, 250, 250)
        self.node_panel_rect = pygame.Rect(self.screen_width - 260, 50, 250, 300)
        self.create_train_button_rect = pygame.Rect(10, self.trains_panel_rect.bottom + 10, 250, 40)

        self.clock_buttons = {
            "pause": pygame.Rect(10, 10, 40, 30),
            "1x": pygame.Rect(60, 10, 40, 30),
            "2x": pygame.Rect(110, 10, 40, 30),
            "5x": pygame.Rect(160, 10, 40, 30),
        }

        # Create Train Panel elements
        self.create_train_panel_rect = pygame.Rect(self.screen_width // 2 - 150, self.screen_height // 2 - 100, 300, 200)
        self.train_name_input_rect = pygame.Rect(self.create_train_panel_rect.x + 20, self.create_train_panel_rect.y + 60, 260, 30)
        self.train_schedule_input_rect = pygame.Rect(self.create_train_panel_rect.x + 20, self.create_train_panel_rect.y + 120, 260, 30)
        self.submit_train_button_rect = pygame.Rect(self.create_train_panel_rect.centerx - 50, self.create_train_panel_rect.y + 160, 100, 30)


    def draw(self, ui_state):
        """Draw all UI panels and buttons."""
        self.draw_trains_panel(ui_state)
        if ui_state['selected_node']:
            self.draw_node_details_panel(ui_state['selected_node'])
        self.draw_clock_controls(ui_state)
        self.draw_top_bar(ui_state)
        if ui_state['show_create_train_panel']:
            self.draw_create_train_panel(ui_state)

    def draw_panel_background(self, rect, title):
        pygame.draw.rect(self.screen, COLOR_PANEL, rect, border_radius=5)
        pygame.draw.rect(self.screen, COLOR_SELECTED, rect, width=1, border_radius=5)
        title_surf = self.font.render(title, True, COLOR_TEXT)
        self.screen.blit(title_surf, (rect.x + 10, rect.y + 10))
        pygame.draw.line(self.screen, COLOR_TEXT, (rect.x + 5, rect.y + 35), (rect.right - 5, rect.y + 35))

    def draw_trains_panel(self, ui_state):
        self.draw_panel_background(self.trains_panel_rect, "Trains")
        y_offset = 45
        for i, train in enumerate(self.sim.train_manager.trains.values()):
            text = f"{train.name} ({train.state})"
            train_surf = self.font.render(text, True, COLOR_TEXT)
            self.screen.blit(train_surf, (self.trains_panel_rect.x + 10, self.trains_panel_rect.y + y_offset + i * 20))

        # Draw Create Train button
        color = COLOR_BUTTON_HOVER if self.create_train_button_rect.collidepoint(pygame.mouse.get_pos()) else COLOR_BUTTON
        pygame.draw.rect(self.screen, color, self.create_train_button_rect, border_radius=3)
        text_surf = self.font.render("Create Train", True, COLOR_TEXT)
        self.screen.blit(text_surf, text_surf.get_rect(center=self.create_train_button_rect.center))


    def draw_node_details_panel(self, node):
        self.draw_panel_background(self.node_panel_rect, f"Node: {node.name}")
        y_offset = 45
        info_texts = [f"Type: {node.node_type}", f"Industry: {node.industry_type or 'N/A'}"]
        for i, text in enumerate(info_texts):
            self.screen.blit(self.font.render(text, True, COLOR_TEXT), (self.node_panel_rect.x + 10, self.node_panel_rect.y + y_offset + i * 20))

        contracts_title_surf = self.font.render("Available Contracts:", True, COLOR_TEXT)
        self.screen.blit(contracts_title_surf, (self.node_panel_rect.x + 10, self.node_panel_rect.y + y_offset + 60))
        contract_y_offset = y_offset + 80

        origin_contracts = [c for c in self.sim.waybill_manager.contracts.values() if c.origin_id == node.id and c.state == 'offered']
        for i, contract in enumerate(origin_contracts):
            dest_node = self.sim.node_map[contract.destination_id]
            text = f"To {dest_node.name} ({contract.cargo})"
            self.screen.blit(self.font.render(text, True, COLOR_TEXT), (self.node_panel_rect.x + 10, self.node_panel_rect.y + contract_y_offset + i * 20))

    def draw_clock_controls(self, ui_state):
        mouse_pos = pygame.mouse.get_pos()
        for speed, rect in self.clock_buttons.items():
            color = COLOR_BUTTON_HOVER if rect.collidepoint(mouse_pos) else COLOR_BUTTON
            if ui_state['game_speed'] == speed: color = COLOR_SELECTED
            pygame.draw.rect(self.screen, color, rect, border_radius=3)
            text_surf = self.font.render(speed.upper(), True, COLOR_TEXT)
            self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))

    def draw_create_train_panel(self, ui_state):
        self.draw_panel_background(self.create_train_panel_rect, "Create New Train")

        # Labels
        self.screen.blit(self.font.render("Name:", True, COLOR_TEXT), (self.train_name_input_rect.x, self.train_name_input_rect.y - 20))
        self.screen.blit(self.font.render("Schedule (Node IDs, comma-separated):", True, COLOR_TEXT), (self.train_schedule_input_rect.x, self.train_schedule_input_rect.y - 20))

        # Input boxes
        pygame.draw.rect(self.screen, COLOR_INPUT_BOX, self.train_name_input_rect)
        pygame.draw.rect(self.screen, COLOR_INPUT_BOX, self.train_schedule_input_rect)

        # Active box highlight
        if ui_state['active_input'] == 'name':
            pygame.draw.rect(self.screen, COLOR_INPUT_BOX_ACTIVE, self.train_name_input_rect, 2)
        elif ui_state['active_input'] == 'schedule':
            pygame.draw.rect(self.screen, COLOR_INPUT_BOX_ACTIVE, self.train_schedule_input_rect, 2)

        # Input text
        name_surf = self.font.render(ui_state['train_name_input'], True, COLOR_TEXT)
        schedule_surf = self.font.render(ui_state['train_schedule_input'], True, COLOR_TEXT)
        self.screen.blit(name_surf, (self.train_name_input_rect.x + 5, self.train_name_input_rect.y + 5))
        self.screen.blit(schedule_surf, (self.train_schedule_input_rect.x + 5, self.train_schedule_input_rect.y + 5))

        # Submit button
        pygame.draw.rect(self.screen, COLOR_BUTTON, self.submit_train_button_rect, border_radius=3)
        submit_text = self.font.render("Create", True, COLOR_TEXT)
        self.screen.blit(submit_text, submit_text.get_rect(center=self.submit_train_button_rect.center))


    def handle_click(self, pos, ui_state):
        """Check for clicks on UI elements and return an action if found."""
        for speed, rect in self.clock_buttons.items():
            if rect.collidepoint(pos):
                return {"set_speed": speed}

        if self.create_train_button_rect.collidepoint(pos):
            return {"toggle_create_train_panel": True}

        if ui_state['show_create_train_panel']:
            if self.train_name_input_rect.collidepoint(pos):
                return {"set_active_input": "name"}
            if self.train_schedule_input_rect.collidepoint(pos):
                return {"set_active_input": "schedule"}
            if self.submit_train_button_rect.collidepoint(pos):
                return {"submit_create_train": True}

        return None

    def draw_top_bar(self, ui_state):
        cash = self.sim.economy_manager.cash
        tick = self.sim.game_tick
        year = config.STARTING_YEAR + (tick // (config.TICKS_PER_DAY * 365))
        day_of_year = (tick // config.TICKS_PER_DAY) % 365 + 1
        status_text = f"Cash: ${cash:,.2f} | Date: Y{year} D{day_of_year}"
        build_mode_status = " | BUILD MODE (B)" if ui_state['is_build_mode'] else ""
        text_surface = self.font.render(status_text + build_mode_status, True, COLOR_TEXT)
        self.screen.blit(text_surface, (220, 18))

class Renderer:
    """Handles all drawing of the game world (nodes, links, trains)."""
    def __init__(self, screen, font, sim, world_size):
        self.screen = screen
        self.font = font
        self.sim = sim
        self.world_width, self.world_height = world_size
        self.screen_width, self.screen_height = screen.get_size()
        self.padding = 40

    def _world_to_screen(self, x, y):
        screen_x = int(self.padding + x * (self.screen_width - 2 * self.padding) / self.world_width)
        screen_y = int(self.padding + y * (self.screen_height - 2 * self.padding) / self.world_height)
        return screen_x, screen_y

    def draw(self, ui_state):
        self.draw_links()
        self.draw_nodes(ui_state)
        self.draw_trains()

    def draw_links(self):
        for link in self.sim.links:
            node1 = self.sim.node_map.get(link.node1_id)
            node2 = self.sim.node_map.get(link.node2_id)
            if node1 and node2:
                start_pos = self._world_to_screen(*node1.pos)
                end_pos = self._world_to_screen(*node2.pos)
                pygame.draw.line(self.screen, COLOR_LINK, start_pos, end_pos, 1)

    def draw_nodes(self, ui_state):
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
        for train in self.sim.train_manager.trains.values():
            pos = None
            if train.current_location_id is not None:
                node = self.sim.node_map.get(train.current_location_id)
                if node: pos = self._world_to_screen(*node.pos)
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

class Game:
    """The main class for the Pygame application."""
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
        self.ui_manager = UIManager(self.screen, self.font, self.sim)

        self.ui_state = {
            'is_build_mode': False,
            'build_mode_origin_node': None,
            'selected_node': None,
            'game_speed': "1x",
            'show_create_train_panel': False,
            'active_input': None,
            'train_name_input': "",
            'train_schedule_input': "",
        }
        self.tick_timer = 0
        self.speed_multipliers = {"pause": 0, "1x": 1, "2x": 2, "5x": 5}

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)
        pygame.quit()
        sys.exit()

    def get_node_at_pos(self, screen_pos):
        for node in self.sim.nodes:
            node_screen_pos = self.renderer._world_to_screen(*node.pos)
            if math.hypot(screen_pos[0] - node_screen_pos[0], screen_pos[1] - node_screen_pos[1]) < 10:
                return node
        return None

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if self.ui_state['active_input']:
                    if event.key == pygame.K_BACKSPACE:
                        self.ui_state[self.ui_state['active_input'] + '_input'] = self.ui_state[self.ui_state['active_input'] + '_input'][:-1]
                    else:
                        self.ui_state[self.ui_state['active_input'] + '_input'] += event.unicode
                elif event.key == pygame.K_b:
                    self.ui_state['is_build_mode'] = not self.ui_state['is_build_mode']
                    self.ui_state['build_mode_origin_node'] = None
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    ui_action = self.ui_manager.handle_click(event.pos, self.ui_state)
                    if ui_action:
                        if 'set_speed' in ui_action: self.ui_state['game_speed'] = ui_action['set_speed']
                        elif 'toggle_create_train_panel' in ui_action: self.ui_state['show_create_train_panel'] = not self.ui_state['show_create_train_panel']
                        elif 'set_active_input' in ui_action: self.ui_state['active_input'] = ui_action['set_active_input']
                        elif 'submit_create_train' in ui_action: self.submit_train()
                        continue

                    clicked_node = self.get_node_at_pos(event.pos)
                    if clicked_node:
                        if self.ui_state['is_build_mode']: self.handle_build_click(clicked_node)
                        else: self.handle_select_click(clicked_node)
                    else:
                        self.ui_state['selected_node'] = None
                        self.ui_state['active_input'] = None # Deselect input box

    def submit_train(self):
        name = self.ui_state['train_name_input']
        schedule_str = self.ui_state['train_schedule_input']
        if name and schedule_str:
            try:
                schedule = [int(n.strip()) for n in schedule_str.split(',')]
                # For simplicity, using a default loco type. Could be an input later.
                self.sim.train_manager.create_train(name, "type_a", schedule)
                # Reset and close panel
                self.ui_state['show_create_train_panel'] = False
                self.ui_state['active_input'] = None
                self.ui_state['train_name_input'] = ""
                self.ui_state['train_schedule_input'] = ""
            except ValueError:
                self.logger.write_line("Error: Invalid schedule format. Must be comma-separated numbers.")
            except Exception as e:
                self.logger.write_line(f"Error creating train: {e}")


    def handle_build_click(self, clicked_node):
        if not clicked_node:
            self.ui_state['build_mode_origin_node'] = None
            return
        if not self.ui_state['build_mode_origin_node']:
            self.ui_state['build_mode_origin_node'] = clicked_node
        else:
            origin_node = self.ui_state['build_mode_origin_node']
            if origin_node.id != clicked_node.id:
                self.sim.build_track(origin_node, clicked_node)
            self.ui_state['build_mode_origin_node'] = None

    def handle_select_click(self, clicked_node):
        self.ui_state['selected_node'] = clicked_node

    def update(self):
        delta_time = self.clock.get_time() / 1000.0
        multiplier = self.speed_multipliers.get(self.ui_state['game_speed'], 0)
        if multiplier == 0: return

        ticks_per_second = config.TICKS_PER_DAY * multiplier
        if ticks_per_second <= 0: return

        self.tick_timer += delta_time
        time_per_tick = 1.0 / ticks_per_second
        while self.tick_timer >= time_per_tick:
            self.sim.tick()
            self.tick_timer -= time_per_tick

    def render(self):
        self.screen.fill(COLOR_BACKGROUND)
        self.renderer.draw(self.ui_state)
        self.ui_manager.draw(self.ui_state)
        pygame.display.flip()

if __name__ == "__main__":
    game = Game()
    game.run()
