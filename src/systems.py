import pygame
import math # Added for HitboxUpdateSystem
from .components import Position, Velocity, Sprite, Rotation, Acceleration, Hitbox, PlayerWeapon, Projectile, Health, Damage, FlightPlan, LevelManager, IsActive, IsVisible, AtlasReference
from . import config as cfg
from . import collision_utils # Added for collision utilities
from .hitbox_loader import load_hitbox_from_json
import time  # For timing diagnostics

class InputSystem:
    def __init__(self, world, player_eid):
        self.world = world
        self.player_eid = player_eid
        self.space_pressed = False
    
    def process(self, dt=0):
        keys = pygame.key.get_pressed()
        active = self.world.get(self.player_eid, IsActive)
        visible = self.world.get(self.player_eid, IsVisible)
        if active and not active.active or visible and not visible.visible:
            return
        acceleration = self.world.get(self.player_eid, Acceleration)
        
        if acceleration:
            acceleration.ax = 0.0
            acceleration.ay = 0.0
            
            if keys[pygame.K_a]:
                acceleration.ax = -cfg.PLAYER_ACCELERATION
            if keys[pygame.K_d]:
                acceleration.ax = cfg.PLAYER_ACCELERATION
            if keys[pygame.K_w]:
                acceleration.ay = -cfg.PLAYER_ACCELERATION
            if keys[pygame.K_s]:
                acceleration.ay = cfg.PLAYER_ACCELERATION
        
        # Shooting
        if keys[pygame.K_SPACE]:
            if not self.space_pressed:
                self.space_pressed = True
                weapon = self.world.get(self.player_eid, PlayerWeapon)
                pos = self.world.get(self.player_eid, Position)
                if weapon and pos:
                    for px, py in weapon.placements:
                        bullet_eid = self.world.pool_manager.get('bullet')
                        if bullet_eid is None:
                            continue  # Pool empty, skip
                        bullet_pos = self.world.get(bullet_eid, Position)
                        bullet_pos.x = pos.x + px
                        bullet_pos.y = pos.y + py
                        bullet_vel = self.world.get(bullet_eid, Velocity)
                        bullet_vel.dx = 0
                        bullet_vel.dy = -weapon.speed
                        bullet_damage = self.world.get(bullet_eid, Damage)
                        bullet_damage.amount = weapon.damage
                        # Activate
                        active = self.world.get(bullet_eid, IsActive)
                        active.active = True
                        bullet_sprite = self.world.get(bullet_eid, Sprite)
                        bullet_surface = pygame.image.load(weapon.bullet_sprite_path)
                        bullet_sprite.surface = bullet_surface
                        bullet_hitbox_data = load_hitbox_from_json(weapon.bullet_hitbox_path)
                        if bullet_hitbox_data:
                            self.world.add_component(bullet_eid, Hitbox(bullet_hitbox_data))
                            self.world.add_component(bullet_eid, Projectile())
                            self.world.add_component(bullet_eid, Damage(weapon.damage))
        else:
            self.space_pressed = False

class MovementSystem:
    def __init__(self, world):
        self.world = world
    
    def process(self, dt):
        for entity in self.world.entities:
            active = self.world.get(entity, IsActive)
            visible = self.world.get(entity, IsVisible)
            if active and not active.active:
                continue
            if visible and not visible.visible:
                continue
            velocity = self.world.get(entity, Velocity)
            position = self.world.get(entity, Position)
            acceleration = self.world.get(entity, Acceleration)
            
            if velocity and position:
                if acceleration:
                    velocity.dx += acceleration.ax * dt
                    velocity.dy += acceleration.ay * dt

                    if acceleration.ax == 0:
                        velocity.dx *= (1 - cfg.PLAYER_DAMPING_FACTOR * dt)
                        if abs(velocity.dx) < 1: velocity.dx = 0.0
                    if acceleration.ay == 0:
                        velocity.dy *= (1 - cfg.PLAYER_DAMPING_FACTOR * dt)
                        if abs(velocity.dy) < 1: velocity.dy = 0.0

                    current_speed_sq = velocity.dx**2 + velocity.dy**2
                    if current_speed_sq > velocity.max_speed**2:
                        current_speed = current_speed_sq**0.5
                        scale_factor = velocity.max_speed / current_speed
                        velocity.dx *= scale_factor
                        velocity.dy *= scale_factor
                
                position.x += velocity.dx * dt
                position.y += velocity.dy * dt

class RotationSystem:
    def __init__(self, world):
        self.world = world

    def process(self, dt):
        for entity in self.world.entities:
            active = self.world.get(entity, IsActive)
            visible = self.world.get(entity, IsVisible)
            if active and not active.active:
                continue
            if visible and not visible.visible:
                continue
            rotation = self.world.get(entity, Rotation)
            if rotation:
                rotation.angle += rotation.speed * dt
                rotation.angle %= 360

class BoundarySystem:
    def __init__(self, world):
        self.world = world

    def process(self, dt):
        screen_width = cfg.SCREEN_WIDTH
        screen_height = cfg.SCREEN_HEIGHT

        for entity in self.world.entities:
            active = self.world.get(entity, IsActive)
            visible = self.world.get(entity, IsVisible)
            if active and not active.active:
                continue
            if visible and not visible.visible:
                continue
            position = self.world.get(entity, Position)
            velocity = self.world.get(entity, Velocity)
            sprite_comp = self.world.get(entity, Sprite)
            projectile_tag = self.world.get(entity, Projectile)

            # Skip boundary constraints for projectiles
            if projectile_tag:
                continue

            if position and sprite_comp:
                sprite_rect = sprite_comp.surface.get_rect()
                half_size_x = sprite_rect.width / 2
                half_size_y = sprite_rect.height / 2

                if position.x - half_size_x < 0:
                    position.x = half_size_x
                    if velocity: velocity.dx = max(0, velocity.dx)
                elif position.x + half_size_x > screen_width:
                    position.x = screen_width - half_size_x
                    if velocity: velocity.dx = min(0, velocity.dx)

                if position.y - half_size_y < 0:
                    position.y = half_size_y
                    if velocity: velocity.dy = max(0, velocity.dy)
                elif position.y + half_size_y > screen_height:
                    position.y = screen_height - half_size_y
                    if velocity: velocity.dy = min(0, velocity.dy)
            elif position:
                if position.x < 0: position.x = 0
                elif position.x > screen_width: position.x = screen_width
                if position.y < 0: position.y = 0
                elif position.y > screen_height: position.y = screen_height

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
            active = self.world.get(entity, IsActive)
            visible = self.world.get(entity, IsVisible)
            if active and not active.active:
                continue
            if visible and not visible.visible:
                continue
            
            atlas_ref = self.world.get(entity, AtlasReference)
            position = self.world.get(entity, Position)
            rotation = self.world.get(entity, Rotation)
            
            if atlas_ref and position:
                surface_to_draw = self.world.atlas[atlas_ref.atlas_key]
                if rotation:
                    surface_to_draw = pygame.transform.rotate(surface_to_draw, rotation.angle)
                self._draw_centered(surface_to_draw, (position.x, position.y))
        
        pygame.display.flip() 

# New Hitbox Update System
class HitboxUpdateSystem:
    def __init__(self, world):
        self.world = world

    def process(self, dt):
        for entity in self.world.entities:
            active = self.world.get(entity, IsActive)
            visible = self.world.get(entity, IsVisible)
            if active and not active.active:
                continue
            if visible and not visible.visible:
                continue
            pos = self.world.get(entity, Position)
            rot = self.world.get(entity, Rotation)
            hitbox_comp = self.world.get(entity, Hitbox)

            if pos and hitbox_comp: # Rotation is optional for the hitbox itself, but used if present for entity
                entity_angle_degrees = rot.angle if rot else 0.0
                entity_angle_rad = math.radians(entity_angle_degrees)
                cos_entity_angle = math.cos(entity_angle_rad)
                sin_entity_angle = math.sin(entity_angle_rad)

                hitbox_comp.current_world_shapes = [] # Clear previous frame's world shapes

                for local_shape_def in hitbox_comp.local_shapes:
                    # Get local offset and optional local rotation of the shape
                    local_x = local_shape_def.get('local_x', 0.0)
                    local_y = local_shape_def.get('local_y', 0.0)
                    shape_local_angle_degrees = local_shape_def.get('local_angle_degrees', 0.0)

                    # Step 1: Rotate the local offset by the entity's rotation
                    rotated_offset_x = local_x * cos_entity_angle - local_y * sin_entity_angle
                    rotated_offset_y = local_x * sin_entity_angle + local_y * cos_entity_angle

                    # Step 2: Calculate the world center of the sub-shape
                    shape_world_center_x = pos.x + rotated_offset_x
                    shape_world_center_y = pos.y + rotated_offset_y

                    # Step 3: Calculate the final world angle of the sub-shape
                    shape_world_angle_degrees = entity_angle_degrees + shape_local_angle_degrees

                    transformed_shape = {
                        'type': local_shape_def['type'],
                        'world_center_x': shape_world_center_x,
                        'world_center_y': shape_world_center_y,
                        # Store original dimensions for clarity
                        **{k: v for k, v in local_shape_def.items() if k not in ['type', 'local_x', 'local_y', 'local_angle_degrees']}
                    }

                    if transformed_shape['type'] == 'square':
                        transformed_shape['world_angle_degrees'] = shape_world_angle_degrees
                        # Calculate and store world vertices for squares for easier collision checks
                        transformed_shape['world_vertices'] = collision_utils.get_square_vertices(
                            shape_world_center_x,
                            shape_world_center_y,
                            local_shape_def['width'],
                            local_shape_def['height'],
                            shape_world_angle_degrees
                        )
                    elif transformed_shape['type'] == 'circle':
                        # Circles don't have a meaningful 'world_angle_degrees' for collision in this context
                        # Their radius remains the same regardless of rotation
                        pass 
                        
                    hitbox_comp.current_world_shapes.append(transformed_shape)

# New Collision System (Basic Placeholder)
class CollisionSystem:
    def __init__(self, world):
        self.world = world
        self.collision_pairs = set() # To store pairs that have collided this frame (entity1_id, entity2_id)

    def process(self, dt):
        start_time = time.perf_counter()
        self.collision_pairs.clear()
        
        # Broad-phase: Build grid of entities with hitboxes
        GRID_SIZE = 100  # Cell size
        grid_width = (cfg.SCREEN_WIDTH // GRID_SIZE) + 1
        grid_height = (cfg.SCREEN_HEIGHT // GRID_SIZE) + 1
        grid = [[[] for _ in range(grid_height)] for _ in range(grid_width)]
        entity_to_cell = {}
        
        for entity in list(self.world.entities):
            active = self.world.get(entity, IsActive)
            visible = self.world.get(entity, IsVisible)
            if active and not active.active:
                continue
            if visible and not visible.visible:
                continue
            if self.world.get(entity, Hitbox) and self.world.get(entity, Position):
                pos = self.world.get(entity, Position)
                cell_x = int(pos.x // GRID_SIZE)
                cell_y = int(pos.y // GRID_SIZE)
                if 0 <= cell_x < grid_width and 0 <= cell_y < grid_height:
                    grid[cell_x][cell_y].append(entity)
                    entity_to_cell[entity] = (cell_x, cell_y)
        
        # Check pairs in same or adjacent cells
        checked_pairs = set()
        for cx in range(grid_width):
            for cy in range(grid_height):
                cell_entities = grid[cx][cy]
                # Check within cell
                for i in range(len(cell_entities)):
                    for j in range(i + 1, len(cell_entities)):
                        pair = tuple(sorted((cell_entities[i], cell_entities[j])))
                        checked_pairs.add(pair)
                # Check adjacent cells (right and below to avoid doubles)
                for dx, dy in [(0,1), (1,0), (1,1)]:
                    ax, ay = cx + dx, cy + dy
                    if ax < grid_width and ay < grid_height:
                        for e1 in cell_entities:
                            for e2 in grid[ax][ay]:
                                pair = tuple(sorted((e1, e2)))
                                checked_pairs.add(pair)
        
        # Narrow-phase on potential pairs
        for entity1, entity2 in checked_pairs:
            # Check if entities still exist
            if entity1 not in self.world.entities or entity2 not in self.world.entities:
                continue
            
            hitbox1_comp = self.world.get(entity1, Hitbox)
            hitbox2_comp = self.world.get(entity2, Hitbox)
            
            if not hitbox1_comp or not hitbox2_comp:
                continue
            
            if not hitbox1_comp.current_world_shapes or not hitbox2_comp.current_world_shapes:
                continue
            
            collided_this_pair = False
            for shape1_world in hitbox1_comp.current_world_shapes:
                if collided_this_pair: break
                for shape2_world in hitbox2_comp.current_world_shapes:
                    if collided_this_pair: break
                    
                    type1 = shape1_world['type']
                    type2 = shape2_world['type']
                    
                    if type1 == 'circle' and type2 == 'circle':
                        if collision_utils.check_circle_circle_collision(
                            shape1_world['world_center_x'], shape1_world['world_center_y'], shape1_world['radius'],
                            shape2_world['world_center_x'], shape2_world['world_center_y'], shape2_world['radius']
                        ):
                            collided_this_pair = True
                    elif type1 == 'square' and type2 == 'square':
                        if collision_utils.check_square_square_collision(
                            shape1_world['world_vertices'], shape2_world['world_vertices']
                        ):
                            collided_this_pair = True
                    elif type1 == 'circle' and type2 == 'square':
                        if collision_utils.check_circle_square_collision(
                            shape1_world['world_center_x'], shape1_world['world_center_y'], shape1_world['radius'],
                            shape2_world['world_vertices']
                        ):
                            collided_this_pair = True
                    elif type1 == 'square' and type2 == 'circle':
                         if collision_utils.check_circle_square_collision(
                            shape2_world['world_center_x'], shape2_world['world_center_y'], shape2_world['radius'],
                            shape1_world['world_vertices'] # Order matters for the util function
                        ):
                            collided_this_pair = True
                    # Add more combinations if other shape types are introduced

            if collided_this_pair:
                # Check for projectile vs health entity collision
                damage1 = self.world.get(entity1, Damage)
                damage2 = self.world.get(entity2, Damage)
                health1 = self.world.get(entity1, Health)
                health2 = self.world.get(entity2, Health)
                
                # Apply damage: projectile hits health entity
                if damage1 and health2:
                    health2.current_hp -= damage1.amount
                    print(f"Entity {entity1} hit entity {entity2} for {damage1.amount} damage! Health: {health2.current_hp}/{health2.max_hp}")
                    self.world.remove_entity(entity1)  # Remove projectile
                    if health2.current_hp <= 0:
                        print(f"Entity {entity2} destroyed!")
                        self.world.remove_entity(entity2)
                elif damage2 and health1:
                    health1.current_hp -= damage2.amount
                    print(f"Entity {entity2} hit entity {entity1} for {damage2.amount} damage! Health: {health1.current_hp}/{health1.max_hp}")
                    self.world.remove_entity(entity2)  # Remove projectile
                    if health1.current_hp <= 0:
                        print(f"Entity {entity1} destroyed!")
                        self.world.remove_entity(entity1)
                
                # Store the pair (order doesn't matter, so store consistently e.g., smaller_id first)
                pair = tuple(sorted((entity1, entity2)))
                self.collision_pairs.add(pair)
                # For now, just print. Later, this could trigger events or component changes.
                # For example, you might add a "CollidedWith" component to the entities. 
        end_time = time.perf_counter()
        print(f"Collision system took {end_time - start_time:.6f} seconds")

class CullingSystem:
    def __init__(self, world):
        self.world = world

    def process(self, dt):
        screen_w = cfg.SCREEN_WIDTH
        screen_h = cfg.SCREEN_HEIGHT
        buffer = cfg.CAMERA_BUFFER
        for entity in list(self.world.entities):
            pos = self.world.get(entity, Position)
            visible_comp = self.world.get(entity, IsVisible)
            if pos and visible_comp:
                visible_comp.visible = (pos.x > -buffer and pos.x < screen_w + buffer and
                                        pos.y > -buffer and pos.y < screen_h + buffer)

class CleanupSystem:
    def __init__(self, world):
        self.world = world

    def process(self, dt):
        for entity in list(self.world.entities):
            active = self.world.get(entity, IsActive)
            visible = self.world.get(entity, IsVisible)
            if active and not active.active:
                continue
            if visible and not visible.visible:
                continue
            projectile_tag = self.world.get(entity, Projectile)
            pos = self.world.get(entity, Position)
            flight_plan = self.world.get(entity, FlightPlan)
            if projectile_tag and pos:
                if pos.y < 0 or pos.y > cfg.SCREEN_HEIGHT or pos.x < 0 or pos.x > cfg.SCREEN_WIDTH:
                    self.world.pool_manager.return_to_pool('bullet', entity)
                    print(f"Returned off-screen projectile {entity} to pool")
            elif flight_plan and flight_plan.completed and pos:
                if pos.y > cfg.SCREEN_HEIGHT + 50:
                    self.world.pool_manager.return_to_pool('mob', entity)
                    print(f"Returned completed off-screen mob {entity} to pool")

class FlightSystem:
    def __init__(self, world):
        self.world = world

    def process(self, dt):
        import time
        current_time = time.time()
        
        for entity in list(self.world.entities):  # Use list() to create a copy
            active = self.world.get(entity, IsActive)
            visible = self.world.get(entity, IsVisible)
            if active and not active.active:
                continue
            if visible and not visible.visible:
                continue
            flight_plan = self.world.get(entity, FlightPlan)
            pos = self.world.get(entity, Position)
            vel = self.world.get(entity, Velocity)
            
            if flight_plan and pos and vel and not flight_plan.completed:
                # Check if we should move to next waypoint
                time_since_start = current_time - flight_plan.start_time
                
                if flight_plan.current_step < len(flight_plan.waypoints):
                    current_wp = flight_plan.waypoints[flight_plan.current_step]
                    
                    # Check if it's time for this waypoint
                    if time_since_start >= current_wp.get('Waypoint_Time_Offset', 0):
                        target_x = current_wp['X']
                        target_y = current_wp['Y']
                        speed = current_wp.get('Speed', 100)
                        
                        # Calculate direction to target
                        dx = target_x - pos.x
                        dy = target_y - pos.y
                        distance = (dx*dx + dy*dy)**0.5
                        
                        if distance > 5:  # Still moving toward waypoint
                            vel.dx = (dx / distance) * speed
                            vel.dy = (dy / distance) * speed
                        else:  # Reached waypoint
                            pos.x = target_x
                            pos.y = target_y
                            vel.dx = 0
                            vel.dy = 0
                            
                            # Execute waypoint action
                            action = current_wp.get('Action', 'move')
                            if action == 'exit':
                                self.world.remove_entity(entity)
                                continue
                            elif action == 'fire':
                                # TODO: Implement mob firing
                                pass
                            
                            # Move to next waypoint
                            flight_plan.current_step += 1
                            
                            if flight_plan.current_step >= len(flight_plan.waypoints):
                                flight_plan.completed = True
                                vel.dx = 0
                                vel.dy = 0
                                # Check if off-screen to return to pool
                                if pos.y > cfg.SCREEN_HEIGHT + 50:
                                    self.world.pool_manager.return_to_pool('mob', entity)
                                    print(f"Returned completed mob {entity} to pool")

class LevelSystem:
    def __init__(self, world):
        self.world = world

    def process(self, dt):
        import time
        current_time = time.time()
        
        for entity in list(self.world.entities):  # Use list() to create a copy
            level_mgr = self.world.get(entity, LevelManager)
            if level_mgr:
                level_mgr.game_time += dt
                
                # Check for events to spawn
                for event in level_mgr.events:
                    event_key = f"{event['Level']}_{event['Event_Start']}"
                    if (level_mgr.game_time >= event['Event_Start'] and 
                        event_key not in level_mgr.spawned_events):
                        
                        if event['Event'] == 'spawn_mob':
                            self.spawn_mob(event)
                            level_mgr.spawned_events.add(event_key)
                            print(f"Spawned mob at t={level_mgr.game_time:.1f}s")

    def spawn_mob(self, event):
        from .hitbox_loader import load_hitbox_from_json
        import pygame
        
        # Get mob data
        mob_id = event['Mob_ID']
        flight_plan_id = event['Flight_Plan_ID']
        
        # Query mob data (could be cached)
        import sqlite3
        conn = sqlite3.connect('GameDB.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Mobs WHERE Mob_ID = ?', (mob_id,))
        mob_data = cursor.fetchone()
        conn.close()
        
        if not mob_data:
            print(f"Mob {mob_id} not found!")
            return
        
        # Create mob entity from pool
        mob_eid = self.world.pool_manager.get('mob')
        if mob_eid is None:
            print(f"Mob pool empty, skipping spawn")
            return
        
        # Configure position from first waypoint
        if flight_plan_id in self.world.flight_plans:
            waypoints = self.world.flight_plans[flight_plan_id]
            if waypoints:
                first_wp = waypoints[0]
                spawn_x = first_wp['X']
                spawn_y = first_wp['Y']
            else:
                spawn_x, spawn_y = 400, -50
        else:
            spawn_x, spawn_y = 400, -50
        
        pos = self.world.get(mob_eid, Position)
        pos.x = spawn_x
        pos.y = spawn_y
        
        vel = self.world.get(mob_eid, Velocity)
        vel.dx = 0
        vel.dy = 0
        
        # AtlasReference already set in pool create
        
        # Health from cache
        self.world.add_component(mob_eid, Health(mob_data['Mob_HP']))
        
        # Add flight plan
        import time
        flight_plan = FlightPlan(flight_plan_id, self.world.flight_plans[flight_plan_id], 0, time.time())
        self.world.add_component(mob_eid, flight_plan)
        
        # Add hitbox (assuming same for all mobs for now)
        # Removed - now in pool create
        
        # Activate
        active = self.world.get(mob_eid, IsActive)
        active.active = True
        visible = self.world.get(mob_eid, IsVisible)
        visible.visible = True  # Assuming IsVisible has 'visible' attr
        
        print(f"Spawned mob {mob_id} with flight plan {flight_plan_id} at ({spawn_x}, {spawn_y})") 