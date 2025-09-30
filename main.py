import pygame
import sys
import math
import config
import create_world
from managers import EconomyManager, WaybillManager, TrainManager
from game_objects import Node, Link

# --- Constants ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
MAP_WIDTH = 960
MAP_HEIGHT = 720
SIDE_PANEL_WIDTH = SCREEN_WIDTH - MAP_WIDTH
BG_COLOR = (240, 240, 240) # Light grey
MAP_BG_COLOR = (200, 200, 200) # Slightly darker grey for the map area
CITY_COLOR = (0, 0, 255) # Blue
INDUSTRY_COLOR = (255, 0, 0) # Red
LINK_COLOR = (100, 100, 100) # Dark Grey
NODE_RADIUS = 8
SELECTED_NODE_COLOR = (255, 255, 0) # Yellow
TEXT_COLOR = (10, 10, 10) # Black
HEADER_COLOR = (50, 50, 50) # Dark Grey
TRAIN_COLOR = (255, 165, 0) # Orange
TRAIN_RADIUS = 5

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
        self.logger.write_line("Simulation initialized.")

    def tick(self):
        """Advances the simulation by one time step."""
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

class GameLogger:
    """A simple logger that prints to the console."""
    def write_line(self, message):
        print(message)

def draw_text(surface, text, pos, font, color=TEXT_COLOR):
    """Helper function to draw text on a surface."""
    text_surface = font.render(text, True, color)
    surface.blit(text_surface, pos)

def main():
    """Main function to run the Pygame-based UI."""
    pygame.init()

    # --- Setup fonts ---
    font_s = pygame.font.SysFont(None, 24)
    font_m = pygame.font.SysFont(None, 32)
    font_l = pygame.font.SysFont(None, 48)

    # --- Setup the screen and clock ---
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Freight Rail Logistics Simulation")
    clock = pygame.time.Clock()

    # --- Initialize Simulation ---
    # We'll use a dummy logger for now.
    # In the future, we could integrate this with a proper in-game console.
    logger = GameLogger()
    sim = Simulation(size=(MAP_WIDTH, MAP_HEIGHT), seed=12345, logger=logger)

    is_build_mode = False
    build_mode_origin_node = None
    selected_node_for_details = None

    running = True
    while running:
        # --- Event Handling ---
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_b:
                    is_build_mode = not is_build_mode
                    build_mode_origin_node = None # Reset on mode toggle
                    logger.write_line(f"Build mode {'ACTIVATED' if is_build_mode else 'DEACTIVATED'}.")

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: # Left click
                if is_build_mode:
                    clicked_node = None
                    for node in sim.nodes:
                        if pygame.math.Vector2(node.pos).distance_to(mouse_pos) < NODE_RADIUS:
                            clicked_node = node
                            break

                    if clicked_node:
                        if build_mode_origin_node is None:
                            build_mode_origin_node = clicked_node
                        else:
                            if build_mode_origin_node != clicked_node:
                                sim.build_track(build_mode_origin_node, clicked_node)
                                build_mode_origin_node = None # Reset after building
                            else:
                                # Deselect if clicking the same node again
                                build_mode_origin_node = None
                else: # Not in build mode, handle selecting for details
                    clicked_node = None
                    for node in sim.nodes:
                        if pygame.math.Vector2(node.pos).distance_to(mouse_pos) < NODE_RADIUS:
                            clicked_node = node
                            break
                    selected_node_for_details = clicked_node

        # --- Simulation Tick ---
        sim.tick()

        # --- Drawing ---
        screen.fill(BG_COLOR)

        # Draw Map Area
        map_rect = pygame.Rect(0, 0, MAP_WIDTH, MAP_HEIGHT)
        pygame.draw.rect(screen, MAP_BG_COLOR, map_rect)

        # Draw Side Panel Area
        side_panel_rect = pygame.Rect(MAP_WIDTH, 0, SIDE_PANEL_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(screen, BG_COLOR, side_panel_rect)

        # --- Draw Game World ---
        node_map = {node.id: node for node in sim.nodes}

        # Draw links
        for link in sim.links:
            node1 = node_map.get(link.node1_id)
            node2 = node_map.get(link.node2_id)
            if node1 and node2:
                pygame.draw.line(screen, LINK_COLOR, node1.pos, node2.pos, 2)

        # Draw nodes
        for node in sim.nodes:
            color = CITY_COLOR if node.node_type == 'city' else INDUSTRY_COLOR
            # Highlight the selected node for building
            if build_mode_origin_node and node.id == build_mode_origin_node.id:
                color = SELECTED_NODE_COLOR
            pygame.draw.circle(screen, color, node.pos, NODE_RADIUS)

        # Draw line from selected node to mouse in build mode
        if is_build_mode and build_mode_origin_node:
            pygame.draw.line(screen, LINK_COLOR, build_mode_origin_node.pos, mouse_pos, 2)

        # Draw trains
        for train in sim.train_manager.trains.values():
            pos = None
            if train.current_location_id is not None:
                if train.current_location_id in node_map:
                    pos = node_map[train.current_location_id].pos
            elif train.current_link is not None:
                node1 = node_map.get(train.current_link[0])
                node2 = node_map.get(train.current_link[1])
                if node1 and node2:
                    link_key = (node1.id, node2.id) if (node1.id, node2.id) in sim.train_manager.links_map else (node2.id, node1.id)
                    if link_key in sim.train_manager.links_map:
                        link_length = sim.train_manager.links_map[link_key].length
                        progress = train.progress_on_link / link_length if link_length > 0 else 0

                        x1, y1 = node1.pos
                        x2, y2 = node2.pos
                        x = int(x1 + (x2 - x1) * progress)
                        y = int(y1 + (y2 - y1) * progress)
                        pos = (x, y)

            if pos:
                pygame.draw.circle(screen, TRAIN_COLOR, pos, TRAIN_RADIUS)


        # --- Draw Side Panel UI ---
        panel_x = MAP_WIDTH + 10
        y_offset = 10

        # Title
        draw_text(screen, "Status", (panel_x, y_offset), font_l, color=HEADER_COLOR)
        y_offset += 50

        # Stats
        cash_text = f"Cash: ${sim.economy_manager.cash:,.2f}"
        draw_text(screen, cash_text, (panel_x, y_offset), font_m)
        y_offset += 30

        year = config.STARTING_YEAR + (sim.game_tick // (config.TICKS_PER_DAY * 365))
        day_of_year = (sim.game_tick // config.TICKS_PER_DAY) % 365 + 1
        date_text = f"Date: Y{year} D{day_of_year}"
        draw_text(screen, date_text, (panel_x, y_offset), font_s)
        y_offset += 25

        build_mode_text = f"Build Mode: {'ON' if is_build_mode else 'OFF'} (B)"
        draw_text(screen, build_mode_text, (panel_x, y_offset), font_s, color=(0, 150, 0) if is_build_mode else TEXT_COLOR)
        y_offset += 40

        # Node Details
        draw_text(screen, "Node Details", (panel_x, y_offset), font_m, color=HEADER_COLOR)
        y_offset += 35
        if selected_node_for_details:
            node = selected_node_for_details
            draw_text(screen, f"Name: {node.name}", (panel_x, y_offset), font_s)
            y_offset += 20
            draw_text(screen, f"Type: {node.node_type.title()}", (panel_x, y_offset), font_s)
            y_offset += 20
            if node.industry_type:
                industry_name = node.industry_type.replace('_', ' ').title()
                draw_text(screen, f"Industry: {industry_name}", (panel_x, y_offset), font_s)
                y_offset += 20
        else:
            draw_text(screen, "Click on a node to see details.", (panel_x, y_offset), font_s)


        # --- Update the display ---
        pygame.display.flip()

        # --- Cap the frame rate ---
        clock.tick(30) # 30 frames per second

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()