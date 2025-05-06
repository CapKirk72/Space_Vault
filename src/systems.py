import pygame
from .components import Position, Velocity, Sprite, Rotation
from . import config as cfg

class InputSystem:
    def __init__(self, world, player_eid):
        self.world = world
        self.player_eid = player_eid
    
    def process(self, dt=0):
        keys = pygame.key.get_pressed()
        velocity = self.world.get(self.player_eid, Velocity)
        
        if velocity:
            velocity.dx = 0
            velocity.dy = 0
            
            if keys[pygame.K_a]:
                velocity.dx = -cfg.PLAYER_SPEED
            if keys[pygame.K_d]:
                velocity.dx = cfg.PLAYER_SPEED
            if keys[pygame.K_w]:
                velocity.dy = -cfg.PLAYER_SPEED
            if keys[pygame.K_s]:
                velocity.dy = cfg.PLAYER_SPEED

class MovementSystem:
    def __init__(self, world):
        self.world = world
    
    def process(self, dt):
        for entity in self.world.entities:
            velocity = self.world.get(entity, Velocity)
            position = self.world.get(entity, Position)
            
            if velocity and position:
                position.x += velocity.dx * dt
                position.y += velocity.dy * dt

class RotationSystem:
    def __init__(self, world):
        self.world = world

    def process(self, dt):
        for entity in self.world.entities:
            rotation = self.world.get(entity, Rotation)
            if rotation:
                rotation.angle += rotation.speed * dt
                rotation.angle %= 360

class RenderSystem:
    def __init__(self, world, screen):
        self.world = world
        self.screen = screen

    def _draw_centered(self, surface, center_pos):
        """Helper to draw a surface centered at a given position."""
        rect = surface.get_rect(center=center_pos)
        self.screen.blit(surface, rect.topleft)
    
    def process(self, dt=0):
        self.screen.fill(cfg.BACKGROUND_COLOR if hasattr(cfg, 'BACKGROUND_COLOR') else (0, 0, 0))
        
        for entity in self.world.entities:
            sprite = self.world.get(entity, Sprite)
            position = self.world.get(entity, Position)
            rotation = self.world.get(entity, Rotation)
            
            if sprite and position:
                # Determine the surface to draw (original or rotated)
                surface_to_draw = sprite.surface
                if rotation:
                    surface_to_draw = pygame.transform.rotate(sprite.surface, rotation.angle)
                
                # Use the helper method to draw it centered
                self._draw_centered(surface_to_draw, (position.x, position.y))
        
        pygame.display.flip() 