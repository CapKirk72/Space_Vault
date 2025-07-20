class Position:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Velocity:
    def __init__(self, dx=0.0, dy=0.0, max_speed=0.0):
        self.dx = dx
        self.dy = dy
        self.max_speed = max_speed

class Sprite:
    def __init__(self, surface):
        self.surface = surface
    
    def draw(self, screen, x, y):
        screen.blit(self.surface, (x, y))

# New Rotation component
class Rotation:
    def __init__(self, angle=0.0, speed=0.0):
        """ Initializes the Rotation component.

        Args:
            angle (float): Initial angle in degrees. Defaults to 0.0.
            speed (float): Initial rotational speed in degrees per second. Defaults to 0.0.
        """
        self.angle = angle
        self.speed = speed 

# New Acceleration component
class Acceleration:
    def __init__(self, ax=0.0, ay=0.0):
        self.ax = ax
        self.ay = ay
        # Damping factor could also live here if it varies per entity
        # For now, we'll use a global one from config 

# New Hitbox component
class Hitbox:
    def __init__(self, local_shapes: list[dict]):
        """ Initializes the Hitbox component.

        Args:
            local_shapes (list[dict]): A list of shape definitions relative to the entity's origin.
                                       Each dict should define 'type', 'local_x', 'local_y', 
                                       and shape-specific attributes like 'radius' or 'width'/'height',
                                       and optionally 'local_angle_degrees'.
        """
        self.local_shapes = local_shapes # Loaded from JSON, defining shapes in local space
        self.current_world_shapes = [] # To be populated by HitboxUpdateSystem with transformed shapes 

class PlayerWeapon:
    def __init__(self, placements, bullet_sprite_path, bullet_hitbox_path, speed, damage):
        self.placements = placements  # list of (local_x, local_y) tuples
        self.bullet_sprite_path = bullet_sprite_path
        self.bullet_hitbox_path = bullet_hitbox_path
        self.speed = speed
        self.damage = damage

class Projectile:
    pass  # Tag component for bullets/projectiles 

class Health:
    def __init__(self, max_hp, current_hp=None):
        self.max_hp = max_hp
        self.current_hp = current_hp or max_hp

class Damage:
    def __init__(self, amount):
        self.amount = amount

class FlightPlan:
    def __init__(self, plan_id, waypoints, current_step=0, start_time=0):
        self.plan_id = plan_id
        self.waypoints = waypoints  # List of waypoint dicts
        self.current_step = current_step
        self.start_time = start_time
        self.completed = False

class LevelManager:
    def __init__(self, level_id, events, mob_cache):
        self.level_id = level_id
        self.events = events  # List of level event dicts
        self.game_time = 0.0
        self.spawned_events = set()
        self.mob_cache = mob_cache 

class IsActive:
    def __init__(self, active=False):
        self.active = active

class IsVisible:
    def __init__(self, visible=True):
        self.visible = visible

class AtlasReference:
    def __init__(self, atlas_key, frame=0):
        self.atlas_key = atlas_key  # Key in atlas dict, e.g. 'bullet'
        self.frame = frame  # For animations 