import pygame
import sys
from src.world import World
from src.components import Position, Velocity, Sprite, Rotation
from src.systems import InputSystem, MovementSystem, RenderSystem, RotationSystem
# Import config module with alias
import src.config as cfg 

def main():
    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT))
    # Use config alias for window caption
    pygame.display.set_caption(cfg.WINDOW_CAPTION)
    clock = pygame.time.Clock()
    
    # Create world
    world = World()
    
    # Create player entity
    player_eid = world.add_entity()
    player_surface = pygame.Surface((20, 20))
    player_surface.fill((255, 0, 150))
    
    # Use config alias for initial player position (centered)
    player_initial_x = cfg.SCREEN_WIDTH // 2
    player_initial_y = cfg.SCREEN_HEIGHT // 2
    world.add_component(player_eid, Position(player_initial_x, player_initial_y))
    world.add_component(player_eid, Velocity(0, 0))
    world.add_component(player_eid, Sprite(player_surface))
    
    # Add systems
    world.add_system(InputSystem(world, player_eid))
    world.add_system(MovementSystem(world))
    world.add_system(RotationSystem(world))
    world.add_system(RenderSystem(world, screen))
    
    # Game loop
    running = True
    while running:
        # Use config alias
        dt = clock.tick(cfg.TARGET_FPS) / 1000.0
        
        # Process events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        # Update world
        world.update(dt)
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main() 