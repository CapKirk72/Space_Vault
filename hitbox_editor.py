import pygame
import sys
import os
import json
import tkinter as tk
from tkinter import filedialog
from collections import deque
import sqlite3

# Constants
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
BACKGROUND_COLOR = (40, 40, 40)
GRID_COLOR = (60, 60, 60)
SQUARE_COLOR = (255, 0, 0, 128)  # Semi-transparent red
SELECTED_COLOR = (0, 255, 0, 128)  # Semi-transparent green for selected
HANDLE_COLOR = (255, 255, 255)
HANDLE_SIZE = 8
GRID_SIZE = 10
SNAP_SIZE = GRID_SIZE / 32  # Even finer
DEFAULT_SPRITE_DIR = 'assets/sprites'
DEFAULT_HITBOX_DIR = 'assets/hitboxes'
MAX_UNDO = 20
SIZE_STEP = GRID_SIZE / 4
MIN_SIZE = GRID_SIZE / 8

os.makedirs(DEFAULT_SPRITE_DIR, exist_ok=True)
os.makedirs(DEFAULT_HITBOX_DIR, exist_ok=True)

class Square:
    def __init__(self, x, y, width, height):
        self.x = x  # Local to sprite center
        self.y = y
        self.width = width
        self.height = height

    def to_json(self):
        return {'type': 'square', 'local_x': self.x, 'local_y': self.y, 'width': self.width, 'height': self.height}

    def contains_point(self, px, py, offset_x, offset_y, scale):
        world_x = offset_x + self.x * scale
        world_y = offset_y + self.y * scale
        half_w = (self.width * scale) / 2
        half_h = (self.height * scale) / 2
        return abs(px - world_x) <= half_w and abs(py - world_y) <= half_h

    def get_corner(self, px, py, offset_x, offset_y, scale):
        world_x = offset_x + self.x * scale
        world_y = offset_y + self.y * scale
        half_w = (self.width * scale) / 2
        half_h = (self.height * scale) / 2
        corners = [
            (world_x - half_w, world_y - half_h, 'top_left'),
            (world_x + half_w, world_y - half_h, 'top_right'),
            (world_x + half_w, world_y + half_h, 'bottom_right'),
            (world_x - half_w, world_y + half_h, 'bottom_left')
        ]
        for cx, cy, corner in corners:
            if abs(px - cx) < HANDLE_SIZE and abs(py - cy) < HANDLE_SIZE:
                return corner
        return None

    def draw(self, screen, offset_x, offset_y, scale, selected=False):
        color = SELECTED_COLOR if selected else SQUARE_COLOR
        world_x = offset_x + self.x * scale
        world_y = offset_y + self.y * scale
        scaled_w = self.width * scale
        scaled_h = self.height * scale
        rect = pygame.Rect(world_x - scaled_w/2, world_y - scaled_h/2, scaled_w, scaled_h)
        pygame.draw.rect(screen, color, rect, 0)
        pygame.draw.rect(screen, (255, 255, 255), rect, 2)
        if selected:
            # Draw resize handles
            half_w = scaled_w / 2
            half_h = scaled_h / 2
            handles = [
                (world_x - half_w, world_y - half_h),
                (world_x + half_w, world_y - half_h),
                (world_x + half_w, world_y + half_h),
                (world_x - half_w, world_y + half_h)
            ]
            for hx, hy in handles:
                pygame.draw.circle(screen, HANDLE_COLOR, (int(hx), int(hy)), HANDLE_SIZE // 2)

class Placement:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def to_json(self):
        return {'type': 'placement', 'local_x': self.x, 'local_y': self.y}

    def contains_point(self, px, py, offset_x, offset_y, scale):
        world_x = offset_x + self.x * scale
        world_y = offset_y + self.y * scale
        half = 8  # Fixed half-size for selection
        return abs(px - world_x) <= half and abs(py - world_y) <= half

    def draw(self, screen, offset_x, offset_y, scale, selected=False):
        world_x = int(offset_x + self.x * scale)
        world_y = int(offset_y + self.y * scale)
        size = 16  # Fixed screen size
        half = size // 2
        color = (0, 0, 255) if not selected else (0, 255, 0)
        rect = pygame.Rect(world_x - half, world_y - half, size, size)
        pygame.draw.rect(screen, color, rect)
        # Crosshair
        pygame.draw.line(screen, (255, 255, 0), (world_x - half, world_y), (world_x + half, world_y), 2)
        pygame.draw.line(screen, (255, 255, 0), (world_x, world_y - half), (world_x, world_y + half), 2)

class HitboxEditor:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Hitbox Editor - Modern Edition')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Arial', 24, bold=True)
        self.small_font = pygame.font.SysFont('Arial', 16)

        # State
        self.sprite = None
        self.sprite_path = ''
        self.placements = {}  # {weapon_id: [Placement, ...]}
        self.squares = []
        self.selected = None
        self.dragging = False
        self.resizing = None  # None or corner name
        self.drag_start = (0, 0)
        self.drag_start_pos = (0, 0)
        self.drag_start_size = (0, 0)
        self.offset_x = SCREEN_WIDTH // 2
        self.offset_y = SCREEN_HEIGHT // 2
        self.scale = 1.0
        self.undo_stack = deque(maxlen=MAX_UNDO)
        self.redo_stack = []
        self.save_state()  # Initial state
        self.copied = None
        self.selected_object = None  # 'square' or 'placement'
        self.selected_type = None
        self.weapon_id_for_new = None
        self.show_dropdown = False
        self.dropdown_options = []
        self.pending_add_placement = False

        # Toolbar
        self.toolbar_height = 50
        self.buttons = [
            ('Load Sprite', self.load_sprite),
            ('Load Hitbox', self.load_hitbox),
            ('Save Hitbox', self.save_hitbox),
            ('Add Square', self.add_square_mode),
            ('Select Weapon', self.select_weapon),
            ('Add Placement', self.add_placement),
            ('Save Placements', self.save_placements),
            ('Delete', self.delete_selected),
            ('Undo', self.undo),
            ('Redo', self.redo),
            ('Zoom In', lambda: self.zoom(0.1)),
            ('Zoom Out', lambda: self.zoom(-0.1))
        ]
        self.button_width = SCREEN_WIDTH // len(self.buttons)

        self.holding_button = None
        self.hold_start = 0
        self.last_hold_time = 0
        self.hold_initial_delay = 200  # ms
        self.hold_repeat_rate = 50    # ms

    def save_state(self):
        state = {'squares': [s.__dict__.copy() for s in self.squares], 'placements': {wid: [p.__dict__.copy() for p in pts] for wid, pts in self.placements.items()}}
        self.undo_stack.append(state)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.undo_stack[-1])
            state = self.undo_stack.pop()
            self.squares = [Square(**d) for d in state['squares']]
            self.placements = {wid: [Placement(**d) for d in ps] for wid, ps in state['placements']}

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.redo_stack[-1])
            state = self.redo_stack.pop()
            self.squares = [Square(**d) for d in state['squares']]
            self.placements = {wid: [Placement(**d) for d in ps] for wid, ps in state['placements']}

    def zoom(self, delta):
        self.scale = max(0.1, min(10, self.scale + delta))

    def add_square_mode(self):
        local_x = 0  # Center
        local_y = 0
        new_square = Square(local_x, local_y, GRID_SIZE * 4, GRID_SIZE * 4)  # Larger default
        self.squares.append(new_square)
        self.selected = new_square
        self.selected_type = 'square'
        self.save_state()

    def select_weapon(self):
        weapons = self.query_weapons()
        if not weapons: return
        self.show_dropdown = True
        self.dropdown_options = weapons
        self.dropdown_pos = (self.button_width * 4, self.toolbar_height)  # Adjust index if needed

    def add_placement(self):
        if self.weapon_id_for_new is None:
            self.select_weapon()
            self.pending_add_placement = True
            return
        new_p = Placement(0, 0)
        self.placements.setdefault(self.weapon_id_for_new, []).append(new_p)
        self.selected_object = new_p
        self.selected_type = 'placement'
        self.save_state()

    def save_placements(self):
        self.save_placements_to_db()
        print('Saved placements to DB')

    def query_weapons(self):
        try:
            conn = sqlite3.connect('GameDB.db')  # Adjust path if needed
            cursor = conn.cursor()
            cursor.execute('SELECT Weapon_ID, Weapon_Name FROM Weapons')
            return cursor.fetchall()
        except Exception as e:
            print(f'DB query error: {e}')
            return []

    def file_dialog_subprocess(self, mode, initial_dir, file_types, default_ext=''):
        import tempfile
        temp_script = tempfile.NamedTemporaryFile(delete=False, suffix='.py')
        script_content = f'''
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
if '{mode}' == 'open':
    path = filedialog.askopenfilename(initialdir='{initial_dir}', filetypes={file_types})
else:
    path = filedialog.asksaveasfilename(initialdir='{initial_dir}', filetypes={file_types}, defaultextension='{default_ext}')
print(path)
'''
        temp_script.write(script_content.encode('utf-8'))
        temp_script.close()
        try:
            import subprocess
            result = subprocess.run([sys.executable, temp_script.name], capture_output=True, text=True)
            path = result.stdout.strip()
            if path:
                return path
            else:
                print('File selection cancelled or failed.')
                return None
        except Exception as e:
            print(f'Error with file dialog subprocess: {e}')
            return None
        finally:
            os.unlink(temp_script.name)

    def load_sprite(self):
        file_types = [('Images', '*.png *.jpg *.jpeg *.bmp *.gif')]
        path = self.file_dialog_subprocess('open', DEFAULT_SPRITE_DIR, file_types)
        if path:
            try:
                self.sprite = pygame.image.load(path)
                self.sprite_path = os.path.basename(path)
                # Load placements if they exist
                placements_path = path.replace('.png', '_placements.json')
                if os.path.exists(placements_path):
                    with open(placements_path, 'r') as f:
                        self.placements = json.load(f)
                        print(f'Loaded {len(self.placements)} placements from {placements_path}')
                self.load_placements_from_db()
            except Exception as e:
                print(f'Error loading sprite: {e}')

    def load_hitbox(self):
        file_types = [('JSON', '*.json')]
        path = self.file_dialog_subprocess('open', DEFAULT_HITBOX_DIR, file_types)
        if path:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                self.squares = []
                for d in data:
                    if d['type'] == 'square':
                        self.squares.append(Square(d['local_x'], d['local_y'], d['width'], d['height']))
                self.save_state()
            except Exception as e:
                print(f'Error loading hitbox: {e}')

    def save_hitbox(self):
        file_types = [('JSON', '*.json')]
        path = self.file_dialog_subprocess('save', DEFAULT_HITBOX_DIR, file_types, '.json')
        if path:
            try:
                data = [s.to_json() for s in self.squares]
                with open(path, 'w') as f:
                    json.dump(data, f, indent=4)
                # Save placements to a separate file
                placements_data = {wid: [{'local_x': p.x, 'local_y': p.y} for p in pts] for wid, pts in self.placements.items()}
                with open(path.replace('.json', '_placements.json'), 'w') as f:
                    json.dump(placements_data, f, indent=4)
                    print(f'Saved placements to {path.replace(".json", "_placements.json")}')
                self.save_placements_to_db()
            except Exception as e:
                print(f'Error saving hitbox: {e}')

    def delete_selected(self):
        if self.selected_object:
            if self.selected_type == 'placement':
                for wid, pts in self.placements.items():
                    if self.selected_object in pts:
                        pts.remove(self.selected_object)
                        break
                self.selected_object = None
                self.selected_type = None
            else: # Square
                self.squares.remove(self.selected_object)
                self.selected = None
                self.selected_type = None
            self.save_state()

    def draw_toolbar(self):
        pygame.draw.rect(self.screen, (30, 30, 30), (0, 0, SCREEN_WIDTH, self.toolbar_height))
        for i, (text, action) in enumerate(self.buttons):
            btn_rect = pygame.Rect(i * self.button_width, 0, self.button_width, self.toolbar_height)
            pygame.draw.rect(self.screen, (50, 50, 50), btn_rect)
            label = self.small_font.render(text, True, (255, 255, 255))
            self.screen.blit(label, (btn_rect.centerx - label.get_width()//2, btn_rect.centery - label.get_height()//2))
            if text == 'Add Weapon':
                # Draw down arrow
                arrow_points = [(btn_rect.right - 20, btn_rect.centery - 5), (btn_rect.right - 10, btn_rect.centery - 5), (btn_rect.right - 15, btn_rect.centery + 5)]
                pygame.draw.polygon(self.screen, (255, 255, 255), arrow_points)

    def handle_toolbar_click(self, pos):
        if pos[1] < self.toolbar_height:
            idx = pos[0] // self.button_width
            if idx < len(self.buttons):
                self.buttons[idx][1]()
                return idx  # Return index instead of True
        return -1

    def snap_to_grid(self, val):
        return round(val / SNAP_SIZE) * SNAP_SIZE

    def check_weapon_assignment(self, weapon_id):
        conn = sqlite3.connect('GameDB.db')
        cursor = conn.cursor()
        cursor.execute('SELECT Sprite_Path FROM WeaponPlacements WHERE Weapon_ID = ?', (weapon_id,))
        existing = cursor.fetchone()
        conn.close()
        return existing and existing[0] != self.sprite_path

    def save_placements_to_db(self):
        conn = sqlite3.connect('GameDB.db')
        cursor = conn.cursor()
        for wid in self.placements:
            # Delete existing row for this weapon/sprite
            cursor.execute('DELETE FROM WeaponPlacements WHERE Weapon_ID = ? AND Sprite_Path = ?', (wid, self.sprite_path))
            # Serialize placements to JSON
            json_data = json.dumps([{'local_x': p.x, 'local_y': p.y} for p in self.placements.get(wid, [])])
            # Insert new row
            cursor.execute('INSERT INTO WeaponPlacements (Weapon_ID, Sprite_Path, Placements_JSON) VALUES (?, ?, ?)', (wid, self.sprite_path, json_data))
        conn.commit()
        conn.close()

    def load_placements_from_db(self):
        conn = sqlite3.connect('GameDB.db')
        cursor = conn.cursor()
        cursor.execute('SELECT Weapon_ID, Placements_JSON FROM WeaponPlacements WHERE Sprite_Path = ?', (self.sprite_path,))
        rows = cursor.fetchall()
        self.placements = {}
        for wid, json_str in rows:
            if json_str:
                data = json.loads(json_str)
                self.placements[wid] = [Placement(d['local_x'], d['local_y']) for d in data]
        conn.close()

    def load_existing_placements(self, weapon_id):
        conn = sqlite3.connect('GameDB.db')
        cursor = conn.cursor()
        cursor.execute('SELECT Placements_JSON FROM WeaponPlacements WHERE Weapon_ID = ? AND Sprite_Path = ?', (weapon_id, self.sprite_path))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            data = json.loads(row[0])
            return [Placement(d['local_x'], d['local_y']) for d in data]
        return []

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 2:  # Middle click for pan
                        self.dragging = 'pan'
                        self.drag_start = event.pos
                    btn_idx = self.handle_toolbar_click(event.pos)
                    if btn_idx != -1:
                        btn_text = self.buttons[btn_idx][0]
                        if btn_text in ['Zoom In', 'Zoom Out']:
                            self.holding_button = btn_text
                            self.hold_start = pygame.time.get_ticks()
                            self.last_hold_time = self.hold_start
                        continue
                    mx, my = event.pos
                    self.selected_object = next((s for s in reversed(self.squares) if s.contains_point(mx, my, self.offset_x, self.offset_y, self.scale)), None)
                    if self.selected_object:
                        self.selected_type = 'square'
                            self.dragging = True
                        self.drag_start = (mx, my)
                        self.drag_start_pos = (self.selected_object.x, self.selected_object.y)
                        self.drag_start_size = (self.selected_object.width, self.selected_object.height)
                    else:
                        for wid, ps in self.placements.items():
                            for p in reversed(ps):
                                if p.contains_point(mx, my, self.offset_x, self.offset_y, self.scale):
                                    self.selected_object = p
                                    self.selected_type = 'placement'
                                    self.dragging = True
                                    self.drag_start = (mx, my)
                                    self.drag_start_pos = (self.selected_object.x, self.selected_object.y)
                                    break
                            if self.selected_object: break
                    if self.show_dropdown:
                        for i, (wid, wname) in enumerate(self.dropdown_options):
                            rect = pygame.Rect(self.dropdown_pos[0], self.dropdown_pos[1] + i*40, 200, 30)
                            if rect.collidepoint(event.pos):
                                self.weapon_id_for_new = wid
                                self.placements[wid] = self.load_existing_placements(wid) or []
                                self.show_dropdown = False
                                if self.pending_add_placement:
                                    self.pending_add_placement = False
                                    self.add_placement()
                                break
                    if self.weapon_id_for_new is not None:
                        self.weapon_id_for_new = None # Reset for next click

                elif event.type == pygame.MOUSEBUTTONUP:
                    self.dragging = False
                    self.resizing = None
                    self.holding_button = None
                    was_dragging = self.dragging
                    self.dragging = False
                    if self.selected_object:
                        self.save_state()
                        print('Ended drag/resize')
                    if was_dragging and self.selected_object:
                                self.save_state()

                elif event.type == pygame.MOUSEMOTION:
                    if self.dragging == 'pan':
                        dx = event.pos[0] - self.drag_start[0]
                        dy = event.pos[1] - self.drag_start[1]
                        self.offset_x += dx
                        self.offset_y += dy
                        self.drag_start = event.pos
                    elif self.dragging and self.selected_object and not self.show_dropdown:
                        dx = (event.pos[0] - self.drag_start[0]) / self.scale
                        dy = (event.pos[1] - self.drag_start[1]) / self.scale
                        min_size = MIN_SIZE
                        if self.resizing == 'top_left':
                            self.selected_object.x = self.snap_to_grid(self.drag_start_pos[0] + dx / 2)
                            self.selected_object.y = self.snap_to_grid(self.drag_start_pos[1] + dy / 2)
                            self.selected_object.width = self.snap_to_grid(max(min_size, self.drag_start_size[0] - dx))
                            self.selected_object.height = self.snap_to_grid(max(min_size, self.drag_start_size[1] - dy))
                        elif self.resizing == 'top_right':
                            self.selected_object.x = self.snap_to_grid(self.drag_start_pos[0] + dx / 2)
                            self.selected_object.y = self.snap_to_grid(self.drag_start_pos[1] + dy / 2)
                            self.selected_object.width = self.snap_to_grid(max(min_size, self.drag_start_size[0] + dx))
                            self.selected_object.height = self.snap_to_grid(max(min_size, self.drag_start_size[1] - dy))
                        elif self.resizing == 'bottom_right':
                            self.selected_object.x = self.snap_to_grid(self.drag_start_pos[0] + dx / 2)
                            self.selected_object.y = self.snap_to_grid(self.drag_start_pos[1] + dy / 2)
                            self.selected_object.width = self.snap_to_grid(max(min_size, self.drag_start_size[0] + dx))
                            self.selected_object.height = self.snap_to_grid(max(min_size, self.drag_start_size[1] + dy))
                        elif self.resizing == 'bottom_left':
                            self.selected_object.x = self.snap_to_grid(self.drag_start_pos[0] + dx / 2)
                            self.selected_object.y = self.snap_to_grid(self.drag_start_pos[1] + dy / 2)
                            self.selected_object.width = self.snap_to_grid(max(min_size, self.drag_start_size[0] - dx))
                            self.selected_object.height = self.snap_to_grid(max(min_size, self.drag_start_size[1] + dy))
                        self.selected_object.x = self.snap_to_grid(self.drag_start_pos[0] + dx)
                        self.selected_object.y = self.snap_to_grid(self.drag_start_pos[1] + dy)
                        print('Dragging to:', self.selected_object.x, self.selected_object.y)
                    elif self.dragging and self.selected_type == 'placement':
                        dx = (event.pos[0] - self.drag_start[0]) / self.scale
                        dy = (event.pos[1] - self.drag_start[1]) / self.scale
                        self.selected_object.x = self.snap_to_grid(self.drag_start_pos[0] + dx)
                        self.selected_object.y = self.snap_to_grid(self.drag_start_pos[1] + dy)
                        print('Dragging placement to', (self.selected_object.x, self.selected_object.y))

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DELETE and self.selected_object:
                        self.delete_selected()
                    elif event.key == pygame.K_z and (event.mod & pygame.KMOD_CTRL):
                        self.undo()
                    elif event.key == pygame.K_y and (event.mod & pygame.KMOD_CTRL):
                        self.redo()
                    elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                        if self.selected_object:
                            self.selected_object.width = self.snap_to_grid(self.selected_object.width + SIZE_STEP)
                            self.selected_object.height = self.snap_to_grid(self.selected_object.height + SIZE_STEP)
                            self.save_state()
                    elif event.key == pygame.K_MINUS:
                        if self.selected_object:
                            self.selected_object.width = max(MIN_SIZE, self.snap_to_grid(self.selected_object.width - SIZE_STEP))
                            self.selected_object.height = max(MIN_SIZE, self.snap_to_grid(self.selected_object.height - SIZE_STEP))
                            self.save_state()
                    elif (event.key == pygame.K_c and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META))) and self.selected_object:
                        self.copied = self.selected_object.__dict__.copy()
                        print('Copied square')
                    elif (event.key == pygame.K_v and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META))) and self.copied:
                        new_data = self.copied.copy()
                        new_data['x'] += GRID_SIZE  # Offset to right
                        new_square = Square(**new_data)
                        self.squares.append(new_square)
                        self.selected = new_square
                        self.selected_type = 'square'
                        self.save_state()
                        print('Pasted square')
                    if event.key == pygame.K_DELETE and self.selected_object:
                        self.delete_selected()
                    if self.show_dropdown:
                        if event.key == pygame.K_ESCAPE:
                            self.show_dropdown = False
                            self.dropdown_options = []
                            print('Exited dropdown')
                        elif event.key == pygame.K_DOWN:
                            self.dropdown_pos = (self.dropdown_pos[0], self.dropdown_pos[1] + 40)
                            if self.dropdown_pos[1] + 40 * len(self.dropdown_options) > SCREEN_HEIGHT - self.toolbar_height:
                                self.dropdown_pos = (self.dropdown_pos[0], SCREEN_HEIGHT - self.toolbar_height - 40 * len(self.dropdown_options))
                        elif event.key == pygame.K_UP:
                            self.dropdown_pos = (self.dropdown_pos[0], self.dropdown_pos[1] - 40)
                            if self.dropdown_pos[1] < self.toolbar_height:
                                self.dropdown_pos = (self.dropdown_pos[0], self.toolbar_height)
                        elif event.key == pygame.K_ENTER:
                            if self.dropdown_options:
                                self.weapon_id_for_new = self.dropdown_options[self.dropdown_pos[1] // 40][0]
                                self.placements[self.weapon_id_for_new] = self.load_existing_placements(self.weapon_id_for_new)
                                self.show_dropdown = False
                                self.dropdown_options = []
                                self.dropdown_pos = (self.button_width * 4, self.toolbar_height)
                                print('Selected weapon:', self.weapon_id_for_new)
                        elif event.key == pygame.K_LEFT:
                            self.dropdown_pos = (self.dropdown_pos[0], self.dropdown_pos[1] - 40)
                            if self.dropdown_pos[1] < self.toolbar_height:
                                self.dropdown_pos = (self.dropdown_pos[0], SCREEN_HEIGHT - self.toolbar_height - 40 * len(self.dropdown_options))
                        elif event.key == pygame.K_RIGHT:
                            self.dropdown_pos = (self.dropdown_pos[0], self.dropdown_pos[1] + 40)
                            if self.dropdown_pos[1] + 40 * len(self.dropdown_options) > SCREEN_HEIGHT - self.toolbar_height:
                                self.dropdown_pos = (self.dropdown_pos[0], self.toolbar_height)
                        elif event.key == pygame.K_ESCAPE:
                            self.show_dropdown = False
                            self.dropdown_options = []
                            print('Exited dropdown')
                    elif self.selected_object:
                        if event.key == pygame.K_LEFT:
                            self.selected_object.x = self.snap_to_grid(self.selected_object.x - SNAP_SIZE)
                        elif event.key == pygame.K_RIGHT:
                            self.selected_object.x = self.snap_to_grid(self.selected_object.x + SNAP_SIZE)
                        elif event.key == pygame.K_UP:
                            self.selected_object.y = self.snap_to_grid(self.selected_object.y - SNAP_SIZE)
                        elif event.key == pygame.K_DOWN:
                            self.selected_object.y = self.snap_to_grid(self.selected_object.y + SNAP_SIZE)
                        self.save_state()
                        print('Moved placement to', (self.selected_object.x, self.selected_object.y))

            self.screen.fill(BACKGROUND_COLOR)
            # Draw grid (zoomed and panned)
            for x in range(0, SCREEN_WIDTH, int(GRID_SIZE * self.scale)):
                pygame.draw.line(self.screen, GRID_COLOR, (x + self.offset_x % (GRID_SIZE * self.scale), 0), (x + self.offset_x % (GRID_SIZE * self.scale), SCREEN_HEIGHT))
            for y in range(0, SCREEN_HEIGHT, int(GRID_SIZE * self.scale)):
                pygame.draw.line(self.screen, GRID_COLOR, (0, y + self.offset_y % (GRID_SIZE * self.scale)), (SCREEN_WIDTH, y + self.offset_y % (GRID_SIZE * self.scale)))

            # Draw sprite
            if self.sprite:
                scaled = pygame.transform.scale(self.sprite, (int(self.sprite.get_width() * self.scale), int(self.sprite.get_height() * self.scale)))
                rect = scaled.get_rect(center=(self.offset_x, self.offset_y))
                self.screen.blit(scaled, rect)

            # Draw squares
            for s in self.squares:
                s.draw(self.screen, self.offset_x, self.offset_y, self.scale, s == self.selected)

            # Draw placements
            for weapon_id, placements in self.placements.items():
                for p in placements:
                    selected = (p == self.selected_object)
                    p.draw(self.screen, self.offset_x, self.offset_y, self.scale, selected)

            self.draw_toolbar()

            if self.show_dropdown:
                dropdown_x, dropdown_y = self.dropdown_pos
                for i, (wid, wname) in enumerate(self.dropdown_options):
                    rect = pygame.Rect(dropdown_x, dropdown_y + i*40, 200, 30)
                    pygame.draw.rect(self.screen, (200, 200, 200), rect)
                    label = self.small_font.render(wname, True, (0, 0, 0))
                    self.screen.blit(label, (rect.centerx - label.get_width()//2, rect.centery - label.get_height()//2))

            pygame.display.flip()
            self.clock.tick(60)

            current_time = pygame.time.get_ticks()
            if self.holding_button:
                if current_time - self.hold_start > self.hold_initial_delay:
                    if current_time - self.last_hold_time > self.hold_repeat_rate:
                        if self.holding_button == 'Zoom In':
                            self.zoom(0.1)
                        elif self.holding_button == 'Zoom Out':
                            self.zoom(-0.1)
                        self.last_hold_time = current_time

            mouse_pos = pygame.mouse.get_pos()
            if self.holding_button and mouse_pos[1] >= self.toolbar_height:
                self.holding_button = None

        pygame.quit()
        sys.exit()

if __name__ == '__main__':
    editor = HitboxEditor()
    editor.run() 