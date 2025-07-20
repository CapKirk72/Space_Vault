import pygame
import sys
from src.world import World
from src.components import Position, Velocity, Sprite, Rotation, Acceleration, Hitbox, PlayerWeapon, Health, Damage, FlightPlan, LevelManager, Projectile, IsActive, IsVisible, AtlasReference
from src.systems import (
    InputSystem, MovementSystem, RenderSystem, RotationSystem, BoundarySystem, 
    HitboxUpdateSystem, CollisionSystem, CleanupSystem, FlightSystem, LevelSystem, CullingSystem
)
from src.hitbox_loader import load_hitbox_from_json
# Import config module with alias
import src.config as cfg 
import sqlite3
import json

def load_player_data(player_id=1):
    try:
        conn = sqlite3.connect('GameDB.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Player WHERE Player_ID = ?', (player_id,))
        player_row = cursor.fetchone()
        if not player_row:
            # Insert default player (existing)
            cursor.execute('''
                INSERT INTO Player (Create_Date, Current_Ship_ID, Current_Weapon_ID, Current_Level_ID, Items, Score, Lives, Last_Save_Date)
                VALUES (strftime("%s","now"), 1, 1, 1, "{}", 0, 3, strftime("%s","now"));
            ''')
            conn.commit()
            player_id = cursor.lastrowid
            cursor.execute('SELECT * FROM Player WHERE Player_ID = ?', (player_id,))
            player_row = cursor.fetchone()
        
        ship_id = player_row['Current_Ship_ID']
        cursor.execute('SELECT * FROM Ships WHERE Ship_ID = ?', (ship_id,))
        ship_data = cursor.fetchone()
        if not ship_data:
            # Insert default ship (existing)
            cursor.execute('''
                INSERT INTO Ships (Ship_Level, Ship_Mod, Ship_HP, Ship_Sprite_Path, Ship_Hitbox_Path)
                VALUES (1, "v1", 100, "assets/sprites/Sprite-0001.png", "assets/hitboxes/main_ship_v1.json");
            ''')
            conn.commit()
            ship_id = cursor.lastrowid
            cursor.execute('UPDATE Player SET Current_Ship_ID = ? WHERE Player_ID = ?', (ship_id, player_id))
            conn.commit()
            cursor.execute('SELECT * FROM Ships WHERE Ship_ID = ?', (ship_id,))
            ship_data = cursor.fetchone()
        
        weapon_id = player_row['Current_Weapon_ID']
        cursor.execute('SELECT * FROM Weapons WHERE Weapon_ID = ?', (weapon_id,))
        weapon_row = cursor.fetchone()
        if weapon_row:
            print(f"Loaded weapon {weapon_id} from DB")
            projectile_id = weapon_row['Projectile_ID']
            cursor.execute('SELECT Projectile_Sprite_Path, Projectile_Hitbox_Path, Projectile_Base_Speed, Projectile_Damage FROM Projectiles WHERE Projectile_ID = ?', (projectile_id,))
            proj_data = cursor.fetchone()
            if proj_data:
                print(f"Loaded projectile {projectile_id}: sprite={proj_data['Projectile_Sprite_Path']}, hitbox={proj_data['Projectile_Hitbox_Path']}, speed={proj_data['Projectile_Base_Speed']}")
                cursor.execute('SELECT Placements_JSON FROM WeaponPlacements WHERE Weapon_ID = ? AND Sprite_Path = ?', (weapon_id, ship_data['Ship_Sprite_Path']))
                placement_row = cursor.fetchone()
                placements = []
                if placement_row and placement_row['Placements_JSON']:
                    import json
                    data = json.loads(placement_row['Placements_JSON'])
                    placements = [(d['local_x'], d['local_y']) for d in data]
                    print(f"Loaded {len(placements)} placements for weapon {weapon_id} on sprite {ship_data['Ship_Sprite_Path']}")
                db_data = {'ship_data': ship_data, 'weapon_data': {'placements': placements, 'bullet_sprite_path': proj_data['Projectile_Sprite_Path'], 'bullet_hitbox_path': proj_data['Projectile_Hitbox_Path'], 'speed': proj_data['Projectile_Base_Speed'] or 300, 'damage': proj_data['Projectile_Damage'] or 10}}
            else:
                print(f"No projectile data for ID {projectile_id}")
                db_data = {'ship_data': ship_data, 'weapon_data': {}}
        else:
            print(f"No weapon data for ID {weapon_id}")
            db_data = {'ship_data': ship_data, 'weapon_data': {}}
        # mobs
        # Load mob data
        cursor.execute('SELECT * FROM Mobs LIMIT 1')  # Get first mob for now
        mob_data = cursor.fetchone()
        if not mob_data:
            # Insert default mob if missing
            cursor.execute("INSERT INTO Mobs (Mob_Name, Mob_Level, Mob_HP, Mob_Sprite_Path) VALUES ('Basic Enemy', 1, 30, 'assets/sprites/mob_0001.png')")
            conn.commit()
            mob_id = cursor.lastrowid
            cursor.execute('SELECT * FROM Mobs WHERE Mob_ID = ?', (mob_id,))
            mob_data = cursor.fetchone()
        
        db_data['mob_data'] = mob_data
        conn.close()
        return db_data
    except Exception as e:
        print(f"DB error: {e}. Falling back to defaults.")
        return {'ship_data': {'Ship_Sprite_Path': 'assets/sprites/Sprite-0001.png', 'Ship_Hitbox_Path': 'assets/hitboxes/main_ship_v1.json', 'Ship_HP': 100}, 'weapon_data': {'placements': [], 'bullet_sprite_path': 'assets/sprites/basic_bullet_0001.png', 'bullet_hitbox_path': 'assets/hitboxes/basic_bullet_v1.json', 'speed': 300, 'damage': 10}, 'mob_data': {'Mob_HP': 30, 'Mob_Sprite_Path': 'assets/sprites/mob_0001.png'}}

def save_player_data(player_id=1, updates=None):
    try:
        conn = sqlite3.connect('GameDB.db')
        cursor = conn.cursor()
        if updates:
            set_clause = ', '.join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [player_id]
            cursor.execute(f'UPDATE Player SET {set_clause}, Last_Save_Date = strftime("%s","now") WHERE Player_ID = ?', values)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Save error: {e}")

def load_level_data(level=1):
    try:
        conn = sqlite3.connect('GameDB.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Load level events using the new Level column
        cursor.execute('SELECT * FROM Levels WHERE Level = ? ORDER BY Event_Start', (level,))
        events = cursor.fetchall()
        
        # Load flight plans used in this level
        flight_plans = {}
        for event in events:
            if event['Flight_Plan_ID']:
                plan_id = event['Flight_Plan_ID']
                if plan_id not in flight_plans:
                    cursor.execute('SELECT * FROM Waypoints WHERE Flight_Plan_ID = ? ORDER BY Waypoint_Step', (plan_id,))
                    waypoints = cursor.fetchall()
                    flight_plans[plan_id] = [dict(wp) for wp in waypoints]
        
        # Cache mob data for all unique Mob_IDs in events
        mob_ids = set(event['Mob_ID'] for event in events if event['Mob_ID'])
        mob_cache = {}
        for mob_id in mob_ids:
            cursor.execute('SELECT * FROM Mobs WHERE Mob_ID = ?', (mob_id,))
            mob_data = cursor.fetchone()
            if mob_data:
                mob_cache[mob_id] = dict(mob_data)
        
        conn.close()
        return {'events': [dict(e) for e in events], 'flight_plans': flight_plans, 'mob_cache': mob_cache}
    except Exception as e:
        print(f"Error loading level data: {e}")
        return {'events': [], 'flight_plans': {}, 'mob_cache': {}}

def main():
    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT))
    # Use config alias for window caption
    pygame.display.set_caption(cfg.WINDOW_CAPTION)
    clock = pygame.time.Clock()
    
    # Initialize atlas
    atlas_surface = pygame.image.load('assets/atlas.png')  # Assume a single atlas PNG
    with open(cfg.ATLAS_JSON_PATH, 'r') as f:
        atlas_data = json.load(f)
    atlas = {}
    for key, data in atlas_data.items():
        rect = data['rect']
        atlas[key] = atlas_surface.subsurface(rect)
    
    # Create world
    world = World()
    world.atlas = atlas  # Store in world for access
    
    # Register bullet pool
    def create_bullet(eid):
        world.add_component(eid, Position(0, -100))  # Off-screen
        world.add_component(eid, Velocity(0, 0))
        world.add_component(eid, AtlasReference('bullet'))
        world.add_component(eid, Projectile())
        world.add_component(eid, Damage(10))  # Default
        world.add_component(eid, IsActive(False))
        world.add_component(eid, IsVisible(False))
    
    def reset_bullet(eid):
        pos = world.get(eid, Position)
        if pos:
            pos.x = 0
            pos.y = -100
        vel = world.get(eid, Velocity)
        if vel:
            vel.dx = 0
            vel.dy = 0
    
    world.pool_manager.register_pool('bullet', 500, create_bullet, reset_bullet)
    print("Registered bullet pool with 500 entities")
    
    # Register mob pool
    def create_mob(eid):
        world.add_component(eid, Position(0, -100))
        world.add_component(eid, Velocity(0, 0))
        world.add_component(eid, AtlasReference('mob'))
        world.add_component(eid, Health(30))  # Default
        mob_hitbox_data = load_hitbox_from_json('assets/hitboxes/mob_01_v1.json')
        if mob_hitbox_data:
            world.add_component(eid, Hitbox(mob_hitbox_data))
        world.add_component(eid, IsActive(False))
        world.add_component(eid, IsVisible(False))
    
    def reset_mob(eid):
        pos = world.get(eid, Position)
        if pos:
            pos.x = 0
            pos.y = -100
        vel = world.get(eid, Velocity)
        if vel:
            vel.dx = 0
            vel.dy = 0
        # Remove FlightPlan and Health if present
        if world.get(eid, FlightPlan):
            world.components[FlightPlan].pop(eid, None)
        if world.get(eid, Health):
            world.components[Health].pop(eid, None)
    
    world.pool_manager.register_pool('mob', 50, create_mob, reset_mob)
    print("Registered mob pool with 50 entities")
    
    db_data = load_player_data()
    ship_data = db_data['ship_data']
    
    # Create player entity
    player_eid = world.add_entity()
    player_surface = pygame.image.load(ship_data['Ship_Sprite_Path'])
    
    # Use config alias for initial player position (centered)
    player_initial_x = cfg.SCREEN_WIDTH // 2
    player_initial_y = cfg.SCREEN_HEIGHT // 2
    world.add_component(player_eid, Position(player_initial_x, player_initial_y))
    # Initialize Velocity with max_speed from config
    world.add_component(player_eid, Velocity(max_speed=cfg.PLAYER_MAX_SPEED))
    world.add_component(player_eid, Sprite(player_surface))
    # Add Acceleration component to the player
    world.add_component(player_eid, Acceleration())
    
    # Load player hitbox
    player_hitbox_path = ship_data['Ship_Hitbox_Path']
    player_hitbox_data = load_hitbox_from_json(player_hitbox_path)
    if player_hitbox_data:
        world.add_component(player_eid, Hitbox(player_hitbox_data))
    else:
        print('Warning: Player hitbox not loaded')

    # Add PlayerWeapon if available
    if 'weapon_data' in db_data and db_data['weapon_data']:
        wd = db_data['weapon_data']
        world.add_component(player_eid, PlayerWeapon(wd['placements'], wd['bullet_sprite_path'], wd['bullet_hitbox_path'], wd['speed'], wd['damage']))
        print(f"Player weapon damage: {wd['damage']}")

    # Add player health
    player_hp = ship_data['Ship_HP']
    world.add_component(player_eid, Health(player_hp))
    print(f"Player health: {player_hp} HP")

    # Load level data and create level manager
    level_data = load_level_data(1)  # Load level 1
    level_manager_eid = world.add_entity()
    world.add_component(level_manager_eid, LevelManager(1, level_data['events'], level_data['mob_cache']))
    print(f"Loaded level 1 with {len(level_data['events'])} events")
    
    # Store flight plans globally for spawning (could be improved)
    world.flight_plans = level_data['flight_plans']

    # Add systems (Order matters for some systems, e.g., HitboxUpdate before Collision)
    world.add_system(InputSystem(world, player_eid))
    world.add_system(MovementSystem(world))
    world.add_system(CullingSystem(world))  # Add after Movement
    world.add_system(FlightSystem(world))  # Add after MovementSystem
    world.add_system(RotationSystem(world))
    # HitboxUpdateSystem should run after movement/rotation but before collision detection
    world.add_system(HitboxUpdateSystem(world))
    world.add_system(CollisionSystem(world)) 
    world.add_system(BoundarySystem(world)) # Boundary system might use hitboxes later, or just position
    world.add_system(CleanupSystem(world))  # Add after Boundary to clean up off-screen
    world.add_system(LevelSystem(world))  # Add before RenderSystem
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
    
    # On quit, e.g., save score=100, level=2
    save_player_data(1, {'Score': 100, 'Current_Level_ID': 2})

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main() 
