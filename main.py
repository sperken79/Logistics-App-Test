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

        self.create_train_panel_rect = pygame.Rect(self.screen_width // 2 - 150, self.screen_height // 2 - 100, 300, 200)
        self.train_name_input_rect = pygame.Rect(self.create_train_panel_rect.x + 20, self.create_train_panel_rect.y + 60, 260, 30)
        self.train_schedule_input_rect = pygame.Rect(self.create_train_panel_rect.x + 20, self.create_train_panel_rect.y + 120, 260, 30)
        self.submit_train_button_rect = pygame.Rect(self.create_train_panel_rect.centerx - 50, self.create_train_panel_rect.y + 160, 100, 30)

        self.contract_details_panel_rect = pygame.Rect(self.screen_width // 2 - 175, self.screen_height // 2 - 125, 350, 250)
        self.accept_contract_button_rect = pygame.Rect(self.contract_details_panel_rect.x + 40, self.contract_details_panel_rect.y + 200, 100, 30)
        self.decline_contract_button_rect = pygame.Rect(self.contract_details_panel_rect.right - 140, self.contract_details_panel_rect.y + 200, 100, 30)

        self.last_drawn_contracts = {}


    def draw(self, ui_state):
        self.draw_trains_panel(ui_state)
        if ui_state['selected_node']:
            self.draw_node_details_panel(ui_state)
        if ui_state['show_create_train_panel']:
            self.draw_create_train_panel(ui_state)
        if ui_state['selected_contract']:
            self.draw_contract_details_panel(ui_state['selected_contract'])

        # These need to be drawn last to be on top of other panels
        self.draw_clock_controls(ui_state)
        self.draw_top_bar(ui_state)


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

        color = COLOR_BUTTON_HOVER if self.create_train_button_rect.collidepoint(pygame.mouse.get_pos()) else COLOR_BUTTON
        pygame.draw.rect(self.screen, color, self.create_train_button_rect, border_radius=3)
        text_surf = self.font.render("Create Train", True, COLOR_TEXT)
        self.screen.blit(text_surf, text_surf.get_rect(center=self.create_train_button_rect.center))


    def draw_node_details_panel(self, ui_state):
        node = ui_state['selected_node']
        self.draw_panel_background(self.node_panel_rect, f"Node: {node.name}")
        self.last_drawn_contracts.clear()

        # Node Info
        y_offset = 45
        info_texts = [f"Type: {node.node_type}", f"Industry: {node.industry_type or 'N/A'}"]
        for i, text in enumerate(info_texts):
            self.screen.blit(self.font.render(text, True, COLOR_TEXT), (self.node_panel_rect.x + 10, self.node_panel_rect.y + y_offset + i * 20))

        # Contracts section
        contracts_title_surf = self.font.render("Available Contracts:", True, COLOR_TEXT)
        self.screen.blit(contracts_title_surf, (self.node_panel_rect.x + 10, self.node_panel_rect.y + y_offset + 60))

        # Create a clipping area for the scrollable content
        content_rect = pygame.Rect(self.node_panel_rect.x + 5, self.node_panel_rect.y + y_offset + 80, self.node_panel_rect.width - 20, 150)
        clip_surface = self.screen.subsurface(content_rect)
        clip_surface.fill(COLOR_PANEL) # Fill with panel background

        relevant_contracts = [c for c in self.sim.waybill_manager.contracts.values() if (c.origin_id == node.id or c.destination_id == node.id) and c.state == 'offered']

        # Scrollbar logic
        list_height = len(relevant_contracts) * 20
        view_height = content_rect.height
        if list_height > view_height:
            # Draw scrollbar track
            scrollbar_track_rect = pygame.Rect(content_rect.right, content_rect.top, 10, content_rect.height)
            pygame.draw.rect(self.screen, COLOR_INPUT_BOX, scrollbar_track_rect)

            # Draw scrollbar handle
            handle_height = max(10, view_height * (view_height / list_height))
            denominator = list_height - view_height
            if denominator > 0:
                scroll_percentage = min(1, max(0, ui_state['contract_scroll_offset'] / denominator))
                handle_y = scrollbar_track_rect.top + scroll_percentage * (view_height - handle_height)
                scrollbar_handle_rect = pygame.Rect(scrollbar_track_rect.left, handle_y, 10, handle_height)
            else:
                scrollbar_handle_rect = pygame.Rect(scrollbar_track_rect.left, scrollbar_track_rect.top, 10, handle_height)
            pygame.draw.rect(self.screen, COLOR_BUTTON, scrollbar_handle_rect)

        for i, contract in enumerate(relevant_contracts):
            # Apply scroll offset
            y_pos = i * 20 - ui_state['contract_scroll_offset']

            if y_pos < content_rect.height and y_pos > -20: # Simple culling
                if contract.origin_id == node.id:
                    dest_node = self.sim.node_map[contract.destination_id]
                    text = f"To {dest_node.name} ({contract.cargo})"
                else:
                    origin_node = self.sim.node_map[contract.origin_id]
                    text = f"From {origin_node.name} ({contract.cargo})"

                text_surf = self.font.render(text, True, COLOR_TEXT)

                absolute_rect_pos_y = content_rect.y + y_pos
                text_rect = text_surf.get_rect(topleft=(5, y_pos))

                absolute_text_rect = text_rect.move(content_rect.x, content_rect.y)

                if absolute_text_rect.collidepoint(pygame.mouse.get_pos()):
                    pygame.draw.rect(clip_surface, COLOR_BUTTON_HOVER, text_rect)

                clip_surface.blit(text_surf, text_rect)
                self.last_drawn_contracts[i] = (contract, absolute_text_rect)


    def draw_contract_details_panel(self, contract):
        self.draw_panel_background(self.contract_details_panel_rect, f"Contract Details (ID: {contract.id})")
        y_offset = 45
        origin_node = self.sim.node_map[contract.origin_id]
        dest_node = self.sim.node_map[contract.destination_id]

        distance = math.hypot(origin_node.pos[0] - dest_node.pos[0], origin_node.pos[1] - dest_node.pos[1])
        revenue = distance * config.REVENUE_PER_CARLOAD_DISTANCE_UNIT * (contract.remaining_ticks * contract.cars_per_tick)

        info_texts = [
            f"From: {origin_node.name}", f"To: {dest_node.name}", f"Cargo: {contract.cargo}",
            f"Duration: {contract.remaining_ticks} ticks", f"Est. Total Revenue: ${revenue:,.2f}",
        ]
        for i, text in enumerate(info_texts):
            self.screen.blit(self.font.render(text, True, COLOR_TEXT), (self.contract_details_panel_rect.x + 10, self.contract_details_panel_rect.y + y_offset + i * 20))

        pygame.draw.rect(self.screen, COLOR_BUTTON, self.accept_contract_button_rect, border_radius=3)
        self.screen.blit(self.font.render("Accept", True, COLOR_TEXT), self.font.render("Accept", True, COLOR_TEXT).get_rect(center=self.accept_contract_button_rect.center))
        pygame.draw.rect(self.screen, COLOR_BUTTON, self.decline_contract_button_rect, border_radius=3)
        self.screen.blit(self.font.render("Decline", True, COLOR_TEXT), self.font.render("Decline", True, COLOR_TEXT).get_rect(center=self.decline_contract_button_rect.center))

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
        self.screen.blit(self.font.render("Name:", True, COLOR_TEXT), (self.train_name_input_rect.x, self.train_name_input_rect.y - 20))
        self.screen.blit(self.font.render("Schedule (Node IDs, comma-separated):", True, COLOR_TEXT), (self.train_schedule_input_rect.x, self.train_schedule_input_rect.y - 20))
        pygame.draw.rect(self.screen, COLOR_INPUT_BOX, self.train_name_input_rect)
        pygame.draw.rect(self.screen, COLOR_INPUT_BOX, self.train_schedule_input_rect)
        if ui_state['active_input'] == 'name':
            pygame.draw.rect(self.screen, COLOR_INPUT_BOX_ACTIVE, self.train_name_input_rect, 2)
        elif ui_state['active_input'] == 'schedule':
            pygame.draw.rect(self.screen, COLOR_INPUT_BOX_ACTIVE, self.train_schedule_input_rect, 2)
        name_surf = self.font.render(ui_state['train_name_input'], True, COLOR_TEXT)
        schedule_surf = self.font.render(ui_state['train_schedule_input'], True, COLOR_TEXT)
        self.screen.blit(name_surf, (self.train_name_input_rect.x + 5, self.train_name_input_rect.y + 5))
        self.screen.blit(schedule_surf, (self.train_schedule_input_rect.x + 5, self.train_schedule_input_rect.y + 5))
        pygame.draw.rect(self.screen, COLOR_BUTTON, self.submit_train_button_rect, border_radius=3)
        submit_text = self.font.render("Create", True, COLOR_TEXT)
        self.screen.blit(submit_text, submit_text.get_rect(center=self.submit_train_button_rect.center))

    def handle_click(self, pos, ui_state):
        for speed, rect in self.clock_buttons.items():
            if rect.collidepoint(pos): return {"set_speed": speed}
        if self.create_train_button_rect.collidepoint(pos):
            return {"toggle_create_train_panel": True}
        if ui_state['show_create_train_panel']:
            if self.train_name_input_rect.collidepoint(pos): return {"set_active_input": "name"}
            if self.train_schedule_input_rect.collidepoint(pos): return {"set_active_input": "schedule"}
            if self.submit_train_button_rect.collidepoint(pos): return {"submit_create_train": True}
        if ui_state['selected_node'] and self.node_panel_rect.collidepoint(pos):
            for i, (contract, rect) in self.last_drawn_contracts.items():
                if rect.collidepoint(pos):
                    return {"select_contract": contract}
        if ui_state['selected_contract']:
            if self.accept_contract_button_rect.collidepoint(pos): return {"accept_contract": ui_state['selected_contract']}
            if self.decline_contract_button_rect.collidepoint(pos): return {"decline_contract": True}
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

    def _world_to_screen(self, x, y, ui_state):
        zoomed_x = x * ui_state['zoom']
        zoomed_y = y * ui_state['zoom']
        screen_x = int(zoomed_x + ui_state['camera_offset'][0])
        screen_y = int(zoomed_y + ui_state['camera_offset'][1])
        return screen_x, screen_y

    def _screen_to_world(self, x, y, ui_state):
        unpanned_x = x - ui_state['camera_offset'][0]
        unpanned_y = y - ui_state['camera_offset'][1]
        world_x = unpanned_x / ui_state['zoom']
        world_y = unpanned_y / ui_state['zoom']
        return world_x, world_y

    def draw(self, ui_state):
        self.draw_links(ui_state)
        self.draw_nodes(ui_state)
        self.draw_trains(ui_state)

    def draw_links(self, ui_state):
        for link in self.sim.links:
            node1 = self.sim.node_map.get(link.node1_id)
            node2 = self.sim.node_map.get(link.node2_id)
            if node1 and node2:
                start_pos = self._world_to_screen(*node1.pos, ui_state)
                end_pos = self._world_to_screen(*node2.pos, ui_state)
                pygame.draw.line(self.screen, COLOR_LINK, start_pos, end_pos, int(1 * ui_state['zoom']))

    def draw_nodes(self, ui_state):
        for node in self.sim.nodes:
            pos = self._world_to_screen(*node.pos, ui_state)
            radius = int(7 * ui_state['zoom'])
            if radius < 2: radius = 2
            color = COLOR_NODE_CITY if node.node_type == 'city' else COLOR_NODE_INDUSTRY
            if ui_state['build_mode_origin_node'] and ui_state['build_mode_origin_node'].id == node.id:
                 pygame.draw.circle(self.screen, COLOR_SELECTED, pos, radius + 5, 2)
            elif ui_state['selected_node'] and ui_state['selected_node'].id == node.id:
                pygame.draw.circle(self.screen, COLOR_SELECTED, pos, radius + 3, 2)
            pygame.draw.circle(self.screen, color, pos, radius)

    def draw_trains(self, ui_state):
        for train in self.sim.train_manager.trains.values():
            pos = None
            if train.current_location_id is not None:
                node = self.sim.node_map.get(train.current_location_id)
                if node: pos = self._world_to_screen(*node.pos, ui_state)
            elif train.current_link is not None:
                node1 = self.sim.node_map.get(train.current_link[0])
                node2 = self.sim.node_map.get(train.current_link[1])
                if node1 and node2:
                    link_key = (node1.id, node2.id) if (node1.id, node2.id) in self.sim.train_manager.links_map else (node2.id, node1.id)
                    if link_key in self.sim.train_manager.links_map:
                        link_length = self.sim.train_manager.links_map[link_key].length
                        progress = train.progress_on_link / link_length if link_length > 0 else 0
                        x1, y1 = self._world_to_screen(*node1.pos, ui_state)
                        x2, y2 = self._world_to_screen(*node2.pos, ui_state)
                        pos = (int(x1 + (x2 - x1) * progress), int(y1 + (y2 - y1) * progress))
            if pos:
                size = int(8 * ui_state['zoom'])
                if size < 2: size = 2
                pygame.draw.rect(self.screen, COLOR_TRAIN, (pos[0] - size//2, pos[1] - size//2, size, size))

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
            'camera_offset': [self.screen.get_width()//2, self.screen.get_height()//2],
            'zoom': 15.0,
            'is_panning': False,
            'selected_contract': None,
            'contract_scroll_offset': 0,
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
            node_screen_pos = self.renderer._world_to_screen(*node.pos, self.ui_state)
            if math.hypot(screen_pos[0] - node_screen_pos[0], screen_pos[1] - node_screen_pos[1]) < 10:
                return node
        return None

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEWHEEL:
                if self.ui_manager.node_panel_rect.collidepoint(pygame.mouse.get_pos()):
                    self.ui_state['contract_scroll_offset'] -= event.y * 20
                else:
                    self.ui_state['zoom'] *= (1.1 if event.y > 0 else 0.9)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3: self.ui_state['is_panning'] = True
                elif event.button == 1:
                    ui_action = self.ui_manager.handle_click(event.pos, self.ui_state)
                    if ui_action:
                        if 'set_speed' in ui_action: self.ui_state['game_speed'] = ui_action['set_speed']
                        elif 'toggle_create_train_panel' in ui_action: self.ui_state['show_create_train_panel'] = not self.ui_state['show_create_train_panel']
                        elif 'set_active_input' in ui_action: self.ui_state['active_input'] = ui_action['set_active_input']
                        elif 'submit_create_train' in ui_action: self.submit_train()
                        elif 'select_contract' in ui_action: self.ui_state['selected_contract'] = ui_action['select_contract']
                        elif 'accept_contract' in ui_action:
                            self.sim.waybill_manager.accept_contract(ui_action['accept_contract'].id)
                            self.ui_state['selected_contract'] = None
                        elif 'decline_contract' in ui_action: self.ui_state['selected_contract'] = None
                        continue

                    clicked_node = self.get_node_at_pos(event.pos)
                    if clicked_node:
                        if self.ui_state['is_build_mode']: self.handle_build_click(clicked_node)
                        else: self.handle_select_click(clicked_node)
                    else:
                        self.ui_state['selected_node'] = None
                        self.ui_state['active_input'] = None
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3: self.ui_state['is_panning'] = False
            elif event.type == pygame.MOUSEMOTION:
                if self.ui_state['is_panning']:
                    self.ui_state['camera_offset'][0] += event.rel[0]
                    self.ui_state['camera_offset'][1] += event.rel[1]
            elif event.type == pygame.KEYDOWN:
                if self.ui_state['active_input']:
                    key_name = 'train_' + self.ui_state['active_input'] + '_input'
                    if event.key == pygame.K_BACKSPACE: self.ui_state[key_name] = self.ui_state[key_name][:-1]
                    else: self.ui_state[key_name] += event.unicode
                elif event.key == pygame.K_b:
                    self.ui_state['is_build_mode'] = not self.ui_state['is_build_mode']
                    self.ui_state['build_mode_origin_node'] = None

    def submit_train(self):
        name = self.ui_state['train_name_input']
        schedule_str = self.ui_state['train_schedule_input']
        if name and schedule_str:
            try:
                schedule = [int(n.strip()) for n in schedule_str.split(',')]
                self.sim.train_manager.create_train(name, "type_a", schedule)
                self.ui_state['show_create_train_panel'] = False
                self.ui_state['active_input'] = None
                self.ui_state['train_name_input'] = ""
                self.ui_state['train_schedule_input'] = ""
            except ValueError: self.logger.write_line("Error: Invalid schedule format.")
            except Exception as e: self.logger.write_line(f"Error creating train: {e}")

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
        self.ui_state['contract_scroll_offset'] = 0 # Reset scroll on new node selection

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
