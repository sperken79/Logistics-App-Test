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
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# --- Logging Setup ---
class PrintLogger:
    def write_line(self, message): print(message)
    def write(self, message): print(message, end='')

class Simulation:
    """A non-UI class to hold the core simulation state and managers."""
    def __init__(self, size, seed, logger):
        self.logger = logger
        self.logger.write_line("Initializing simulation...")
        self.game_tick = 0
        world_data = create_world.create_world(size, seed)
        self.nodes = world_data['nodes']
        self.links = world_data['links']
        self.node_map = {node.id: node for node in self.nodes}

        self.economy_manager = EconomyManager(config.STARTING_CASH)
        # Pass the game_tick to the manager
        self.waybill_manager = WaybillManager(self.nodes, self.links, self.economy_manager, self.game_tick, self.logger)
        self.train_manager = TrainManager(self.nodes, self.links, self.waybill_manager, self.economy_manager, self.logger)
        self.logger.write_line("Simulation initialized.")

    def tick(self):
        self.game_tick += 1
        # Pass the current tick to the managers that need it
        self.waybill_manager.game_tick = self.game_tick
        self.waybill_manager.update(self.train_manager)
        self.train_manager.update()

    def build_track(self, node1: Node, node2: Node) -> bool:
        # Same as before
        for link in self.waybill_manager.links:
            if (link.node1_id == node1.id and link.node2_id == node2.id) or \
               (link.node1_id == node2.id and link.node2_id == node1.id):
                return False
        distance = math.hypot(node1.pos[0] - node2.pos[0], node1.pos[1] - node2.pos[1])
        cost = distance * config.TRACK_BUILD_COST_PER_UNIT
        if not self.economy_manager.deduct_cost(cost):
            return False
        new_link = Link(node1_id=node1.id, node2_id=node2.id, length=distance, terrain="plains")
        self.waybill_manager.links.append(new_link)
        self.train_manager.links_map[(node1.id, node2.id)] = new_link
        self.train_manager.links_map[(node2.id, node1.id)] = new_link
        self.waybill_manager.adjacency_list[node1.id].append((node2.id, distance))
        self.waybill_manager.adjacency_list[node2.id].append((node1.id, distance))
        return True

class UIManager:
    """Handles drawing and interaction for all UI elements."""
    def __init__(self, screen, font, sim):
        self.screen = screen
        self.font = font
        self.sim = sim
        self.screen_width, self.screen_height = screen.get_size()

        # Define UI element rectangles
        self.trains_panel_rect = pygame.Rect(10, 50, 250, 200)
        self.waybills_panel_rect = pygame.Rect(10, self.trains_panel_rect.bottom + 10, 250, 200)
        self.node_panel_rect = pygame.Rect(self.screen_width - 260, 50, 250, 350)
        self.create_train_button_rect = pygame.Rect(10, self.waybills_panel_rect.bottom + 10, 250, 40)

        self.clock_buttons = {
            "pause": pygame.Rect(10, 10, 35, 30), "1x": pygame.Rect(55, 10, 35, 30),
            "2x": pygame.Rect(100, 10, 35, 30), "5x": pygame.Rect(145, 10, 35, 30),
            "10x": pygame.Rect(190, 10, 35, 30), "20x": pygame.Rect(235, 10, 35, 30),
            "50x": pygame.Rect(280, 10, 35, 30),
        }

        self.create_train_panel_rect = pygame.Rect(self.screen_width // 2 - 150, self.screen_height // 2 - 100, 300, 200)
        self.train_name_input_rect = pygame.Rect(self.create_train_panel_rect.x + 20, self.create_train_panel_rect.y + 60, 260, 30)
        self.train_schedule_input_rect = pygame.Rect(self.create_train_panel_rect.x + 20, self.create_train_panel_rect.y + 120, 260, 30)
        self.submit_train_button_rect = pygame.Rect(self.create_train_panel_rect.centerx - 50, self.create_train_panel_rect.y + 160, 100, 30)

        self.contract_details_panel_rect = pygame.Rect(self.screen_width // 2 - 200, self.screen_height // 2 - 150, 400, 300)
        self.accept_contract_button_rect = pygame.Rect(self.contract_details_panel_rect.x + 50, self.contract_details_panel_rect.bottom - 50, 100, 30)
        self.decline_contract_button_rect = pygame.Rect(self.contract_details_panel_rect.right - 150, self.contract_details_panel_rect.bottom - 50, 100, 30)

        self.create_train_close_button_rect = pygame.Rect(self.create_train_panel_rect.right - 25, self.create_train_panel_rect.top + 5, 20, 20)
        self.contract_details_close_button_rect = pygame.Rect(self.contract_details_panel_rect.right - 25, self.contract_details_panel_rect.top + 5, 20, 20)

        self.last_drawn_contracts = {}

    def draw(self, ui_state):
        self.draw_trains_panel(ui_state)
        self.draw_waybills_panel(ui_state)
        if ui_state['selected_node']:
            self.draw_node_details_panel(ui_state)
        if ui_state['show_create_train_panel']:
            self.draw_create_train_panel(ui_state)
        if ui_state['selected_contract']:
            self.draw_contract_details_panel(ui_state['selected_contract'])

        self.draw_clock_controls(ui_state)
        self.draw_top_bar(ui_state)

    def draw_panel_background(self, rect, title):
        pygame.draw.rect(self.screen, COLOR_PANEL, rect, border_radius=5)
        pygame.draw.rect(self.screen, COLOR_SELECTED, rect, width=1, border_radius=5)
        title_surf = self.font.render(title, True, COLOR_TEXT)
        self.screen.blit(title_surf, (rect.x + 10, rect.y + 10))
        pygame.draw.line(self.screen, COLOR_TEXT, (rect.x + 5, rect.y + 35), (rect.right - 5, rect.y + 35))

    def draw_close_button(self, rect):
        mouse_pos = pygame.mouse.get_pos()
        color = COLOR_BUTTON_HOVER if rect.collidepoint(mouse_pos) else COLOR_BUTTON
        pygame.draw.rect(self.screen, color, rect, border_radius=3)
        text_surf = self.font.render("X", True, COLOR_TEXT)
        self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))

    def draw_trains_panel(self, ui_state):
        self.draw_panel_background(self.trains_panel_rect, "Trains")
        y_offset = 45
        for i, train in enumerate(self.sim.train_manager.trains.values()):
            task_info = f" ({train.current_task.id})" if train.current_task else ""
            text = f"{train.name} ({train.state}{task_info})"
            train_surf = self.font.render(text, True, COLOR_TEXT)
            self.screen.blit(train_surf, (self.trains_panel_rect.x + 10, self.trains_panel_rect.y + y_offset + i * 20))

        color = COLOR_BUTTON_HOVER if self.create_train_button_rect.collidepoint(pygame.mouse.get_pos()) else COLOR_BUTTON
        pygame.draw.rect(self.screen, color, self.create_train_button_rect, border_radius=3)
        text_surf = self.font.render("Create Train", True, COLOR_TEXT)
        self.screen.blit(text_surf, text_surf.get_rect(center=self.create_train_button_rect.center))

    def draw_waybills_panel(self, ui_state):
        self.draw_panel_background(self.waybills_panel_rect, "Active Waybills")
        y_offset = 45
        for i, waybill in enumerate(list(self.sim.waybill_manager.waybills.values())[:8]): # Limit to 8 for display
            text = f"#{waybill.id}: {waybill.cargo} ({waybill.state})"
            waybill_surf = self.font.render(text, True, COLOR_TEXT)
            self.screen.blit(waybill_surf, (self.waybills_panel_rect.x + 10, self.waybills_panel_rect.y + y_offset + i * 20))

    def draw_node_details_panel(self, ui_state):
        node = ui_state['selected_node']
        self.draw_panel_background(self.node_panel_rect, f"Node: {node.name}")
        self.last_drawn_contracts.clear()

        y_offset = 45
        # Display new industry info
        day_str = ", ".join([DAY_NAMES[d] for d in node.business_days])
        info_texts = [
            f"Industry: {node.industry_type or 'N/A'}",
            f"Capacity: {node.base_capacity} cars/month",
            f"Service Rating: {node.service_rating:.1f}%",
            f"Business Days: {day_str}"
        ]
        for i, text in enumerate(info_texts):
            self.screen.blit(self.font.render(text, True, COLOR_TEXT), (self.node_panel_rect.x + 10, self.node_panel_rect.y + y_offset + i * 20))

        # Display offered contracts from this node
        contracts_y_start = self.node_panel_rect.y + y_offset + len(info_texts) * 20 + 10
        contracts_title_surf = self.font.render("Contract Offers:", True, COLOR_TEXT)
        self.screen.blit(contracts_title_surf, (self.node_panel_rect.x + 10, contracts_y_start))

        content_rect = pygame.Rect(self.node_panel_rect.x + 5, contracts_y_start + 20, self.node_panel_rect.width - 10, 150)
        # No clipping for simplicity now

        relevant_contracts = [c for c in self.sim.waybill_manager.contracts.values() if c.origin_id == node.id and c.status == 'offered']

        for i, contract in enumerate(relevant_contracts):
            dest_node = self.sim.node_map[contract.destination_id]
            text = f"To {dest_node.name} ({contract.cargo})"
            text_surf = self.font.render(text, True, COLOR_TEXT)
            text_rect = text_surf.get_rect(topleft=(content_rect.x + 5, content_rect.y + i * 20))
            if text_rect.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(self.screen, COLOR_BUTTON_HOVER, text_rect)
            self.screen.blit(text_surf, text_rect)
            self.last_drawn_contracts[i] = (contract, text_rect)

    def draw_contract_details_panel(self, contract):
        self.draw_panel_background(self.contract_details_panel_rect, f"Contract Offer #{contract.id}")
        self.draw_close_button(self.contract_details_close_button_rect)
        y_offset = 45
        origin_node = self.sim.node_map[contract.origin_id]
        dest_node = self.sim.node_map[contract.destination_id]
        distance = self.sim.waybill_manager._heuristic(contract.origin_id, contract.destination_id)
        total_revenue = contract.revenue_per_car + (distance * config.REVENUE_PER_DISTANCE_UNIT)

        info_texts = [
            f"From: {origin_node.name}",
            f"To: {dest_node.name}",
            f"Cargo: {contract.cargo}",
            f"Shipment Rate: {contract.cars_per_month} cars/month",
            f"Revenue per Car: ${total_revenue:,.2f} (base + distance)",
            f"Empty Car Deadline: {contract.deadline_empty_car_hours} hours",
            f"Loaded Car Deadline: {contract.deadline_loaded_car_hours} hours",
            f"Expires in: {(contract.acceptance_deadline_tick - self.sim.game_tick) // config.TICKS_PER_DAY} days"
        ]
        for i, text in enumerate(info_texts):
            self.screen.blit(self.font.render(text, True, COLOR_TEXT), (self.contract_details_panel_rect.x + 10, self.contract_details_panel_rect.y + y_offset + i * 25))

        pygame.draw.rect(self.screen, COLOR_BUTTON, self.accept_contract_button_rect, border_radius=3)
        self.screen.blit(self.font.render("Accept", True, COLOR_TEXT), self.font.render("Accept", True, COLOR_TEXT).get_rect(center=self.accept_contract_button_rect.center))
        pygame.draw.rect(self.screen, COLOR_BUTTON, self.decline_contract_button_rect, border_radius=3)
        self.screen.blit(self.font.render("Decline", True, COLOR_TEXT), self.font.render("Decline", True, COLOR_TEXT).get_rect(center=self.decline_contract_button_rect.center))

    def draw_clock_controls(self, ui_state):
        # same as before
        mouse_pos = pygame.mouse.get_pos()
        for speed, rect in self.clock_buttons.items():
            color = COLOR_BUTTON_HOVER if rect.collidepoint(mouse_pos) else COLOR_BUTTON
            if ui_state['game_speed'] == speed: color = COLOR_SELECTED
            pygame.draw.rect(self.screen, color, rect, border_radius=3)
            text_surf = self.font.render(speed.upper(), True, COLOR_TEXT)
            self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))

    def draw_create_train_panel(self, ui_state):
        # same as before
        self.draw_panel_background(self.create_train_panel_rect, "Create New Train")
        self.draw_close_button(self.create_train_close_button_rect)
        self.screen.blit(self.font.render("Name:", True, COLOR_TEXT), (self.train_name_input_rect.x, self.train_name_input_rect.y - 20))
        self.screen.blit(self.font.render("Schedule (Node IDs):", True, COLOR_TEXT), (self.train_schedule_input_rect.x, self.train_schedule_input_rect.y - 20))
        pygame.draw.rect(self.screen, COLOR_INPUT_BOX, self.train_name_input_rect)
        pygame.draw.rect(self.screen, COLOR_INPUT_BOX, self.train_schedule_input_rect)
        name_surf = self.font.render(ui_state['train_name_input'], True, COLOR_TEXT)
        schedule_surf = self.font.render(ui_state['train_schedule_input'], True, COLOR_TEXT)
        self.screen.blit(name_surf, (self.train_name_input_rect.x + 5, self.train_name_input_rect.y + 5))
        self.screen.blit(schedule_surf, (self.train_schedule_input_rect.x + 5, self.train_schedule_input_rect.y + 5))
        pygame.draw.rect(self.screen, COLOR_BUTTON, self.submit_train_button_rect, border_radius=3)
        self.screen.blit(self.font.render("Create", True, COLOR_TEXT), self.font.render("Create", True, COLOR_TEXT).get_rect(center=self.submit_train_button_rect.center))

    def handle_click(self, pos, ui_state):
        # same as before
        for speed, rect in self.clock_buttons.items():
            if rect.collidepoint(pos): return {"set_speed": speed}
        if self.create_train_button_rect.collidepoint(pos):
            return {"toggle_create_train_panel": True}
        if ui_state['show_create_train_panel']:
            if self.create_train_close_button_rect.collidepoint(pos): return {"close_create_train_panel": True}
            if self.train_name_input_rect.collidepoint(pos): return {"set_active_input": "name"}
            if self.train_schedule_input_rect.collidepoint(pos): return {"set_active_input": "schedule"}
            if self.submit_train_button_rect.collidepoint(pos): return {"submit_create_train": True}
        if ui_state['selected_node'] and self.node_panel_rect.collidepoint(pos):
            for i, (contract, rect) in self.last_drawn_contracts.items():
                if rect.collidepoint(pos): return {"select_contract": contract}
        if ui_state['selected_contract']:
            if self.contract_details_close_button_rect.collidepoint(pos): return {"close_contract_details": True}
            if self.accept_contract_button_rect.collidepoint(pos): return {"accept_contract": ui_state['selected_contract']}
            if self.decline_contract_button_rect.collidepoint(pos): return {"decline_contract": ui_state['selected_contract']}
        return None

    def draw_top_bar(self, ui_state):
        # same as before
        cash = self.sim.economy_manager.cash; tick = self.sim.game_tick
        year = config.STARTING_YEAR + (tick // (config.TICKS_PER_DAY * config.DAYS_PER_YEAR))
        day_of_year = (tick // config.TICKS_PER_DAY) % config.DAYS_PER_YEAR + 1
        hour = tick % config.TICKS_PER_DAY
        status_text = f"Cash: ${cash:,.2f} | Date: Y{year} D{day_of_year} H{hour:02d}"
        build_mode_status = " | BUILD MODE (B)" if ui_state['is_build_mode'] else ""
        text_surface = self.font.render(status_text + build_mode_status, True, COLOR_TEXT)
        self.screen.blit(text_surface, (325, 18))

class Renderer:
    # same as before
    def __init__(self, screen, font, sim, world_size):
        self.screen, self.font, self.sim = screen, font, sim
        self.world_width, self.world_height = world_size
        self.screen_width, self.screen_height = screen.get_size()
    def _world_to_screen(self, x, y, ui_state):
        base_x = x * (self.screen_width / self.world_width); base_y = y * (self.screen_height / self.world_height)
        zoomed_x = base_x * ui_state['zoom']; zoomed_y = base_y * ui_state['zoom']
        return int(zoomed_x + ui_state['camera_offset'][0]), int(zoomed_y + ui_state['camera_offset'][1])
    def draw(self, ui_state):
        self.draw_links(ui_state); self.draw_nodes(ui_state); self.draw_trains(ui_state)
    def draw_links(self, ui_state):
        for link in self.sim.links:
            n1, n2 = self.sim.node_map.get(link.node1_id), self.sim.node_map.get(link.node2_id)
            if n1 and n2:
                start, end = self._world_to_screen(*n1.pos, ui_state), self._world_to_screen(*n2.pos, ui_state)
                pygame.draw.line(self.screen, COLOR_LINK, start, end, max(1, int(1 * ui_state['zoom'])))
    def get_node_radius(self, zoom): return max(3, int(4 * zoom))
    def draw_nodes(self, ui_state):
        for node in self.sim.nodes:
            pos = self._world_to_screen(*node.pos, ui_state); radius = self.get_node_radius(ui_state['zoom'])
            color = COLOR_NODE_CITY if node.node_type == 'city' else COLOR_NODE_INDUSTRY
            if ui_state.get('build_mode_origin_node') and ui_state['build_mode_origin_node'].id == node.id:
                pygame.draw.circle(self.screen, COLOR_SELECTED, pos, radius + 4, 2)
            elif ui_state.get('selected_node') and ui_state['selected_node'].id == node.id:
                pygame.draw.circle(self.screen, COLOR_SELECTED, pos, radius + 2, 2)
            pygame.draw.circle(self.screen, color, pos, radius)
    def draw_trains(self, ui_state):
        for train in self.sim.train_manager.trains.values():
            pos = None
            if train.current_location_id is not None:
                if node := self.sim.node_map.get(train.current_location_id): pos = self._world_to_screen(*node.pos, ui_state)
            elif train.current_link is not None:
                n1, n2 = self.sim.node_map.get(train.current_link[0]), self.sim.node_map.get(train.current_link[1])
                if n1 and n2:
                    link = self.sim.train_manager.links_map.get(train.current_link) or self.sim.train_manager.links_map.get((train.current_link[1], train.current_link[0]))
                    if link:
                        progress = train.progress_on_link / link.length if link.length > 0 else 0
                        x1, y1 = self._world_to_screen(*n1.pos, ui_state); x2, y2 = self._world_to_screen(*n2.pos, ui_state)
                        pos = (int(x1 + (x2 - x1) * progress), int(y1 + (y2 - y1) * progress))
            if pos:
                size = max(4, int(8 * ui_state['zoom']))
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
            'is_build_mode': False, 'build_mode_origin_node': None, 'selected_node': None,
            'game_speed': "1x", 'show_create_train_panel': False, 'active_input': None,
            'train_name_input': "", 'train_schedule_input': "", 'camera_offset': [0,0],
            'zoom': 1.0, 'is_panning': False, 'selected_contract': None, 'contract_scroll_offset': 0,
        }
        self.tick_timer = 0
        self.speed_multipliers = {"pause": 0, "1x": 1, "2x": 2, "5x": 5, "10x": 10, "20x": 20, "50x": 50}

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)
        pygame.quit(); sys.exit()

    def get_node_at_pos(self, screen_pos):
        for node in reversed(self.sim.nodes):
            node_screen_pos = self.renderer._world_to_screen(*node.pos, self.ui_state)
            radius = self.renderer.get_node_radius(self.ui_state['zoom'])
            if math.hypot(screen_pos[0] - node_screen_pos[0], screen_pos[1] - node_screen_pos[1]) < radius:
                return node
        return None

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: self.running = False
            elif event.type == pygame.MOUSEWHEEL:
                if self.ui_manager.node_panel_rect.collidepoint(pygame.mouse.get_pos()):
                    self.ui_state['contract_scroll_offset'] -= event.y * 20
                else:
                    self.ui_state['zoom'] *= 1.1 if event.y > 0 else 0.9
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3: self.ui_state['is_panning'] = True
                elif event.button == 1:
                    ui_action = self.ui_manager.handle_click(event.pos, self.ui_state)
                    if ui_action:
                        action_map = {
                            "set_speed": lambda: self.ui_state.update(game_speed=ui_action['set_speed']),
                            "toggle_create_train_panel": lambda: self.ui_state.update(show_create_train_panel=not self.ui_state['show_create_train_panel']),
                            "close_create_train_panel": lambda: self.ui_state.update(show_create_train_panel=False),
                            "set_active_input": lambda: self.ui_state.update(active_input=ui_action['set_active_input']),
                            "submit_create_train": self.submit_train,
                            "select_contract": lambda: self.ui_state.update(selected_contract=ui_action['select_contract']),
                            "accept_contract": lambda: (self.sim.waybill_manager.accept_contract(ui_action['accept_contract'].id), self.ui_state.update(selected_contract=None)),
                            "decline_contract": lambda: (self.sim.waybill_manager.decline_contract(ui_action['decline_contract'].id), self.ui_state.update(selected_contract=None)),
                            "close_contract_details": lambda: self.ui_state.update(selected_contract=None)
                        }
                        action_key = list(ui_action.keys())[0]
                        if action_key in action_map:
                            action_map[action_key]()
                            continue

                    clicked_node = self.get_node_at_pos(event.pos)
                    self.ui_state['selected_node'] = clicked_node
                    if not clicked_node: self.ui_state['active_input'] = None
                    elif self.ui_state['is_build_mode']: self.handle_build_click(clicked_node)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3: self.ui_state['is_panning'] = False
            elif event.type == pygame.MOUSEMOTION:
                if self.ui_state['is_panning']:
                    self.ui_state['camera_offset'][0] += event.rel[0]; self.ui_state['camera_offset'][1] += event.rel[1]
            elif event.type == pygame.KEYDOWN:
                if self.ui_state['active_input']:
                    key_name = f"train_{self.ui_state['active_input']}_input"
                    if event.key == pygame.K_BACKSPACE: self.ui_state[key_name] = self.ui_state[key_name][:-1]
                    else: self.ui_state[key_name] += event.unicode
                elif event.key == pygame.K_b:
                    self.ui_state['is_build_mode'] = not self.ui_state['is_build_mode']; self.ui_state['build_mode_origin_node'] = None

    def submit_train(self):
        name, schedule_str = self.ui_state['train_name_input'], self.ui_state['train_schedule_input']
        if name and schedule_str:
            try:
                schedule = [int(n.strip()) for n in schedule_str.split(',')]
                self.sim.train_manager.create_train(name, "type_a", schedule)
                self.ui_state.update(show_create_train_panel=False, active_input=None, train_name_input="", train_schedule_input="")
            except (ValueError, Exception) as e: self.logger.write_line(f"Error creating train: {e}")

    def handle_build_click(self, clicked_node):
        if not self.ui_state.get('build_mode_origin_node'): self.ui_state['build_mode_origin_node'] = clicked_node
        else:
            if self.ui_state['build_mode_origin_node'].id != clicked_node.id:
                self.sim.build_track(self.ui_state['build_mode_origin_node'], clicked_node)
            self.ui_state['build_mode_origin_node'] = None

    def update(self):
        delta_time = self.clock.get_time() / 1000.0
        multiplier = self.speed_multipliers.get(self.ui_state['game_speed'], 0)
        if multiplier == 0: return
        ticks_per_second = multiplier
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
