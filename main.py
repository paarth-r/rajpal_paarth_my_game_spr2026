'''
Main file responsible for game loop including input, update, and draw methods.
'''

import pygame as pg
import sys
import json
import os
from os import path
from settings import *
from sprites import *
from utils import *
from inventory import Inventory, ITEM_DEFS, EQUIPMENT_SLOTS

vec = pg.math.Vector2


class Game:
    def __init__(self):
        pg.init()
        # Window and viewport stay fixed; SCALE only zooms (perceived size)
        self.display = pg.display.set_mode((WIDTH, HEIGHT))
        self.screen = pg.Surface((WIDTH, HEIGHT))
        pg.display.set_caption(TITLE)
        self.clock = pg.time.Clock()
        self.running = True
        self.playing = True

    def load_data(self):
        self.game_dir = path.dirname(__file__)
        self.img_dir = path.join(self.game_dir, 'images')
        self.levels_dir = path.join(self.game_dir, 'levels')
        self.saves_dir = path.join(self.game_dir, 'saves')
        self.active_save_path = path.join(self.saves_dir, 'active_world.txt')
        self.wall_img = pg.image.load(path.join(self.img_dir, 'wall_art.png')).convert_alpha()
        self.level_order = ['level1.txt', 'level2.txt', 'level3.txt']
        self.current_level_name = self.level_order[0]
        self.current_save_name = None
        self.save_path = None
        self.mob_states_by_level = {}
        self.init_save_system()
        self._load_world_state_from_save()
        self.load_level(self.current_level_name, create_player=True)

    def is_walkable(self, col, row):
        """True if (col, row) is in bounds, not a wall, and not occupied by a mob or player (current or sliding-to)."""
        if row < 0 or row >= len(self.map.data):
            return False
        if col < 0 or col >= len(self.map.data[0]):
            return False
        tile = self.map.data[row][col]
        if tile == '1':
            return False
        if tile == 'N' and not self.level_exit_open:
            return False
        if (self.player.tile_x, self.player.tile_y) == (col, row):
            return False
        if self.player.slide_to_tile is not None and self.player.slide_to_tile == (col, row):
            return False
        for mob in self.all_mobs:
            if (mob.tile_x, mob.tile_y) == (col, row):
                return False
        return True

    def new(self):
        self.load_data()
        self._initialize_player_inventory()
        self.inventory_open = False
        self.manual_target = None
        # Inventory UI state
        self.inv_slot_rects = []    # built each frame: list of (pg.Rect, source, index)
        self.inv_dragging = None    # (source, index, item_id, count) while dragging
        self.inv_drag_offset = (0, 0)
        self.inv_selected = None    # (source, index) for click-highlight
        self.pause_menu_open = False
        self.pause_save_btn_rect = None
        self.pause_quit_title_btn_rect = None
        self.pause_resume_btn_rect = None
        self.title_start_btn_rect = None
        self.title_new_world_btn_rect = None
        self.title_quit_btn_rect = None
        self.respawn_button_rect = None
        self.state = 'intro'
        self.run()

    def init_save_system(self):
        """Set up saves folder and choose active world save."""
        os.makedirs(self.saves_dir, exist_ok=True)
        legacy_save = path.join(self.game_dir, 'save_inventory.json')
        legacy_target = path.join(self.saves_dir, 'world_001.json')
        if path.exists(legacy_save) and not path.exists(legacy_target):
            try:
                with open(legacy_save, 'r') as src:
                    payload = json.load(src)
                with open(legacy_target, 'w') as dst:
                    json.dump(payload, dst, indent=2)
            except Exception:
                pass
        saves = sorted([f for f in os.listdir(self.saves_dir) if f.endswith('.json')])
        active = None
        if path.exists(self.active_save_path):
            try:
                with open(self.active_save_path, 'r') as f:
                    name = f.read().strip()
                if name in saves:
                    active = name
            except Exception:
                active = None
        if active is None:
            if saves:
                active = saves[0]
            else:
                active = 'world_001.json'
        self.set_active_world(active)

    def set_active_world(self, save_name):
        self.current_save_name = save_name
        self.save_path = path.join(self.saves_dir, save_name)
        try:
            with open(self.active_save_path, 'w') as f:
                f.write(save_name)
        except Exception:
            pass

    def _initialize_player_inventory(self):
        """Load active world inventory or create default new-world inventory."""
        self.inventory = Inventory(INVENTORY_SLOTS, HOTBAR_SLOTS)
        loaded = self.load_inventory_state()
        if loaded:
            return
        self.inventory.add_item('gold_coin', 5)
        self.inventory.add_item('health_potion', 2)
        # Starting gear: gladius + legionnaire armor set (equip directly)
        self.inventory.equipment['weapon'] = 'gladius'
        self.inventory.equipment['head'] = 'legion_helm'
        self.inventory.equipment['chest'] = 'legion_cuirass'
        self.inventory.equipment['boots'] = 'legion_boots'
        self.save_inventory_state()

    def _load_world_state_from_save(self):
        """Load world-level state from save (current level + mobs)."""
        if not path.exists(self.save_path):
            return
        try:
            with open(self.save_path, 'r') as f:
                payload = json.load(f)
            level_name = payload.get('current_level')
            if level_name in self.level_order:
                self.current_level_name = level_name
            mob_states = payload.get('mob_states', {})
            if isinstance(mob_states, dict):
                self.mob_states_by_level = mob_states
        except Exception:
            pass

    def create_new_world(self):
        """Create a new save world and start from fresh defaults."""
        saves = [f for f in os.listdir(self.saves_dir) if f.endswith('.json')]
        nums = []
        for s in saves:
            if s.startswith('world_') and s.endswith('.json'):
                stem = s[len('world_'):-len('.json')]
                if stem.isdigit():
                    nums.append(int(stem))
        next_num = (max(nums) + 1) if nums else 1
        new_name = f"world_{next_num:03d}.json"
        self.set_active_world(new_name)
        self.current_level_name = self.level_order[0]
        self.mob_states_by_level = {}
        self.load_level(self.current_level_name, create_player=True)
        self._initialize_player_inventory()
        self.pause_menu_open = False
        self.inventory_open = False
        self.inv_dragging = None
        self.inv_selected = None
        self.manual_target = None
        self.state = 'playing'

    def load_level(self, level_name, create_player=False):
        """Build map/entities for a level; keep player instance when transitioning."""
        self.current_level_name = level_name
        level_path = path.join(self.levels_dir, level_name)
        self.map = Map(level_path)
        self.map_img = pg.Surface((self.map.width, self.map.height))
        self.map_img.fill(FLOOR_COLOR)
        self.map_rect = self.map_img.get_rect()
        self.all_sprites = pg.sprite.Group()
        self.all_walls = pg.sprite.Group()
        self.all_mobs = pg.sprite.Group()
        self.all_drops = pg.sprite.Group()
        self.checkpoint_tile = None
        self.level_exit_tiles = []
        self.level_return_tiles = []
        player_spawn = None
        default_mob_spawns = []

        for row, tiles in enumerate(self.map.data):
            for col, tile in enumerate(tiles):
                if tile == '1':
                    Wall(self, col, row)
                elif tile == 'P':
                    player_spawn = (col, row)
                    if self.checkpoint_tile is None:
                        self.checkpoint_tile = (col, row)
                elif tile == 'K':
                    self.checkpoint_tile = (col, row)
                elif tile == 'N':
                    self.level_exit_tiles.append((col, row))
                elif tile == 'R':
                    self.level_return_tiles.append((col, row))
                elif tile == 'M':
                    default_mob_spawns.append((col, row))

        if self.checkpoint_tile is None and player_spawn is not None:
            self.checkpoint_tile = player_spawn
        if player_spawn is None:
            player_spawn = self.checkpoint_tile if self.checkpoint_tile else (1, 1)

        if create_player or not hasattr(self, 'player') or self.player is None:
            self.player = Player(self, player_spawn[0], player_spawn[1])
        else:
            self.all_sprites.add(self.player)
            self.player.clear_move_queue()
            self.player.move_state = 'idle'
            self.player.slide_to_tile = None
            self.player.tile_x, self.player.tile_y = self.checkpoint_tile if self.checkpoint_tile else player_spawn
            self.player.pos = vec(self.player.tile_x * TILESIZE + TILESIZE / 2, self.player.tile_y * TILESIZE + TILESIZE / 2)
            self.player.hit_rect.center = self.player.pos
            self.player.rect.center = self.player.hit_rect.center

        saved_mobs = self.mob_states_by_level.get(level_name)
        if isinstance(saved_mobs, list):
            for m in saved_mobs:
                tx = int(m.get('tile_x', 0))
                ty = int(m.get('tile_y', 0))
                mob_type = m.get('mob_type', 'statue')
                health = int(m.get('health', MOB_HP))
                if health <= 0:
                    continue
                mob = Mob(self, tx, ty, mob_type=mob_type)
                mob.health = max(1, health)
                if m.get('state') in ('inactive', 'idle', 'walk', 'attack'):
                    mob.state = m.get('state')
        else:
            for col, row in default_mob_spawns:
                Mob(self, col, row)

        self.level_exit_open = len([m for m in self.all_mobs if getattr(m, 'state', None) != 'dead']) == 0
        self.camera = Camera(self.map.width, self.map.height)
        self.manual_target = None

    def run(self):
        while self.running:
            self.dt = self.clock.tick(FPS) / 1000
            self.events()
            if self.state == 'intro':
                self.draw_intro()
            elif self.state == 'death':
                self.draw_death()
            else:
                if not self.inventory_open and not self.pause_menu_open:
                    self.update()
                self.draw()

    def events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.save_inventory_state()
                if self.playing:
                    self.playing = False
                self.running = False
            if event.type == pg.KEYDOWN:
                if self.state == 'intro':
                    if event.key == pg.K_RETURN:
                        self.state = 'playing'
                    if event.key == pg.K_n:
                        self.create_new_world()
                    continue
                if self.state == 'death':
                    continue
                if self.state != 'playing':
                    continue
                if event.key == pg.K_ESCAPE:
                    if self.pause_menu_open:
                        self.pause_menu_open = False
                    else:
                        self.pause_menu_open = True
                        self.inventory_open = False
                        self.inv_dragging = None
                        self.inv_selected = None
                    continue
                if self.pause_menu_open:
                    continue
                if self.inventory_open:
                    if event.key in (INVENTORY_KEY, CHARACTER_KEY, pg.K_ESCAPE):
                        self.inventory_open = False
                        self.inv_dragging = None
                        self.inv_selected = None
                    continue
                if event.key in (INVENTORY_KEY, CHARACTER_KEY):
                    self.inventory_open = True
                    continue
                if pg.K_1 <= event.key <= pg.K_8:
                    self.inventory.selected_hotbar_index = event.key - pg.K_1
                    continue
                if event.key == pg.K_SPACE:
                    self.player.attack()
                if event.key == pg.K_f:
                    self.use_selected_item()
                if event.key == pg.K_DELETE or event.key == pg.K_BACKSPACE:
                    self.player.clear_move_queue()
                # Hold keys to queue moves (path preview); executes at speed
                if event.key == pg.K_w:
                    self.player.queue_move(0, -1)
                if event.key == pg.K_s:
                    self.player.queue_move(0, 1)
                if event.key == pg.K_a:
                    self.player.queue_move(-1, 0)
                if event.key == pg.K_d:
                    self.player.queue_move(1, 0)
            if self.inventory_open and self.state == 'playing':
                if event.type == pg.MOUSEBUTTONDOWN:
                    self._inv_mouse_down(event)
                    continue
                if event.type == pg.MOUSEBUTTONUP:
                    self._inv_mouse_up(event)
                    continue
            if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                if self.state == 'intro':
                    if self.title_start_btn_rect and self.title_start_btn_rect.collidepoint(event.pos):
                        self.state = 'playing'
                    elif self.title_new_world_btn_rect and self.title_new_world_btn_rect.collidepoint(event.pos):
                        self.create_new_world()
                    elif self.title_quit_btn_rect and self.title_quit_btn_rect.collidepoint(event.pos):
                        self.save_inventory_state()
                        self.running = False
                    continue
                if self.state == 'death':
                    if self.respawn_button_rect and self.respawn_button_rect.collidepoint(event.pos):
                        self.respawn_player()
                    continue
                if self.state == 'playing' and self.pause_menu_open:
                    if self.pause_save_btn_rect and self.pause_save_btn_rect.collidepoint(event.pos):
                        self.save_inventory_state()
                    elif self.pause_quit_title_btn_rect and self.pause_quit_title_btn_rect.collidepoint(event.pos):
                        self.save_inventory_state()
                        self.pause_menu_open = False
                        self.inventory_open = False
                        self.state = 'intro'
                    elif self.pause_resume_btn_rect and self.pause_resume_btn_rect.collidepoint(event.pos):
                        self.pause_menu_open = False
                    continue
                if self.state != 'playing' or self.inventory_open:
                    continue
                self._handle_click_target(event.pos)

    def quit(self):
        pass

    def save_inventory_state(self):
        """Persist inventory, player health, current level, and per-level mob states."""
        try:
            self.mob_states_by_level[self.current_level_name] = self._snapshot_current_level_mobs()
            slots = []
            for slot in self.inventory.slots:
                if slot is None:
                    slots.append(None)
                else:
                    slots.append([slot[0], slot[1]])
            payload = {
                'slots': slots,
                'equipment': dict(self.inventory.equipment),
                'selected_hotbar_index': int(self.inventory.selected_hotbar_index),
                'player_health': int(self.player.health),
                'current_level': self.current_level_name,
                'mob_states': self.mob_states_by_level,
            }
            with open(self.save_path, 'w') as f:
                json.dump(payload, f, indent=2)
            return True
        except Exception:
            return False

    def _snapshot_current_level_mobs(self):
        """Serialize current level's non-dead mobs."""
        result = []
        for mob in self.all_mobs:
            if getattr(mob, 'state', None) == 'dead' or mob.health <= 0:
                continue
            result.append({
                'tile_x': int(mob.tile_x),
                'tile_y': int(mob.tile_y),
                'health': int(mob.health),
                'state': mob.state,
                'mob_type': getattr(mob, 'mob_type', 'statue'),
            })
        return result

    def load_inventory_state(self):
        """Load inventory state from disk. Returns True if loaded successfully."""
        if not path.exists(self.save_path):
            return False
        try:
            with open(self.save_path, 'r') as f:
                payload = json.load(f)
            slots = payload.get('slots', [])
            for i in range(min(len(slots), self.inventory.num_slots)):
                s = slots[i]
                if s is None:
                    self.inventory.slots[i] = None
                    continue
                if not isinstance(s, list) or len(s) != 2:
                    continue
                item_id, count = s
                if item_id in ITEM_DEFS and isinstance(count, int) and count > 0:
                    self.inventory.slots[i] = (item_id, count)
            eq = payload.get('equipment', {})
            for slot_name in EQUIPMENT_SLOTS:
                item_id = eq.get(slot_name)
                if item_id in ITEM_DEFS:
                    self.inventory.equipment[slot_name] = item_id
                else:
                    self.inventory.equipment[slot_name] = None
            idx = int(payload.get('selected_hotbar_index', 0))
            self.inventory.selected_hotbar_index = max(0, min(self.inventory.hotbar_size - 1, idx))
            saved_hp = payload.get('player_health')
            if isinstance(saved_hp, int):
                max_hp = self.player.get_effective_max_health()
                self.player.health = max(0, min(saved_hp, max_hp))
            return True
        except Exception:
            return False

    def update(self):
        self.all_sprites.update()
        if self.player.health <= 0:
            self.state = 'death'
            self.inventory_open = False
            self.inv_dragging = None
            self.inv_selected = None
            return
        live_mobs = [m for m in self.all_mobs if getattr(m, 'state', None) != 'dead' and m.health > 0]
        if not self.level_exit_open and len(live_mobs) == 0:
            self.level_exit_open = True
        # Keep manual target valid
        if self.manual_target is not None:
            if (not self.manual_target.alive()) or getattr(self.manual_target, 'state', None) == 'dead':
                self.manual_target = None
        # Player attack: auto-target one attackable entity within range (regardless of facing)
        if self.player.attacking and not self.player.attack_hit_dealt:
            best = self._get_best_attack_target()
            if best is not None:
                best.hurt(self.player.get_effective_damage())
                self.player.attack_hit_dealt = True
        player_tile = (self.player.tile_x, self.player.tile_y)
        if player_tile in self.level_return_tiles:
            self.go_to_prev_level()
            return
        if self.level_exit_open and player_tile in self.level_exit_tiles:
            self.go_to_next_level()
            return
        self.camera.update(self.player)

    def draw(self):
        self.screen.fill(BGCOLOR)
        # Draw zoomed view: small world window scaled up to fill (WIDTH, HEIGHT)
        cam = self.camera.camera
        view_w, view_h = int(cam.width), int(cam.height)
        if view_w > 0 and view_h > 0:
            view_surf = pg.Surface((view_w, view_h))
            view_surf.fill(BGCOLOR)
            view_surf.blit(self.map_img, (-cam.x, -cam.y))
            # Grid: tile boundaries in world coords, drawn on view
            for wx in range(0, self.map.width + 1, TILESIZE):
                sx = wx - cam.x
                if -1 < sx < view_w + 1:
                    pg.draw.line(view_surf, GRID_COLOR, (sx, 0), (sx, view_h))
            for wy in range(0, self.map.height + 1, TILESIZE):
                sy = wy - cam.y
                if -1 < sy < view_h + 1:
                    pg.draw.line(view_surf, GRID_COLOR, (0, sy), (view_w, sy))
            scaled_map = pg.transform.scale(view_surf, (WIDTH, HEIGHT))
            self.screen.blit(scaled_map, (0, 0))
        # Checkpoint tile marker
        if self.checkpoint_tile is not None:
            cp_rect = pg.Rect(self.checkpoint_tile[0] * TILESIZE, self.checkpoint_tile[1] * TILESIZE, TILESIZE, TILESIZE)
            cp_screen = self.camera.apply_rect(cp_rect)
            pg.draw.rect(self.screen, (60, 120, 220), cp_screen)
            pg.draw.rect(self.screen, WHITE, cp_screen, 2)
        # Forward exits: locked looks like wall; unlocked becomes purple doorway.
        for ex_tile in self.level_exit_tiles:
            ex_rect = pg.Rect(ex_tile[0] * TILESIZE, ex_tile[1] * TILESIZE, TILESIZE, TILESIZE)
            ex_screen = self.camera.apply_rect(ex_rect)
            if self.level_exit_open:
                pg.draw.rect(self.screen, (145, 60, 210), ex_screen)
                pg.draw.rect(self.screen, WHITE, ex_screen, 2)
            else:
                wall_scaled = pg.transform.scale(self.wall_img, (ex_screen.width, ex_screen.height))
                self.screen.blit(wall_scaled, ex_screen)
        # Return exits are always open (teal doorway).
        for ret_tile in self.level_return_tiles:
            rt_rect = pg.Rect(ret_tile[0] * TILESIZE, ret_tile[1] * TILESIZE, TILESIZE, TILESIZE)
            rt_screen = self.camera.apply_rect(rt_rect)
            pg.draw.rect(self.screen, (40, 170, 170), rt_screen)
            pg.draw.rect(self.screen, WHITE, rt_screen, 2)
        # Draw path preview: outlined tiles for queued moves
        path_tiles = self.player.get_path_tiles()
        path_rect = pg.Rect(0, 0, TILESIZE, TILESIZE)
        for (tx, ty) in path_tiles:
            path_rect.x = tx * TILESIZE
            path_rect.y = ty * TILESIZE
            screen_rect = self.camera.apply_rect(path_rect)
            pg.draw.rect(self.screen, PATH_TILE_OUTLINE_COLOR, screen_rect, PATH_TILE_OUTLINE_WIDTH)

        # Outline each mob's current tile so it's clear which block they occupy
        for mob in self.all_mobs:
            path_rect.x = mob.tile_x * TILESIZE
            path_rect.y = mob.tile_y * TILESIZE
            screen_rect = self.camera.apply_rect(path_rect)
            pg.draw.rect(self.screen, PATH_TILE_OUTLINE_COLOR, screen_rect, PATH_TILE_OUTLINE_WIDTH)
        # Stable draw order (by y then x) to prevent flicker
        sprites_sorted = sorted(self.all_sprites, key=lambda s: (s.rect.centery, s.rect.centerx))
        for sprite in sprites_sorted:
            if sprite.image is None or sprite.rect.width <= 0 or sprite.rect.height <= 0:
                continue
            dest = self.camera.apply(sprite)
            if dest.width <= 0 or dest.height <= 0:
                continue
            scaled_img = pg.transform.scale(sprite.image, (dest.width, dest.height))
            self.screen.blit(scaled_img, dest)
            # HP bar above any sprite with .health and .max_health (or use default max)
            if hasattr(sprite, 'health'):
                max_hp = getattr(sprite, 'max_health', PLAYER_MAX_HEALTH)
                bar_w = HP_BAR_WIDTH
                bar_h = HP_BAR_HEIGHT
                bar_x = dest.centerx - bar_w // 2
                bar_y = dest.y + HP_BAR_OFFSET
                self.screen.fill(HP_BAR_BG, (bar_x, bar_y, bar_w, bar_h))
                if max_hp > 0:
                    fill_w = max(1, int(bar_w * sprite.health / max_hp))
                    self.screen.fill(HP_BAR_FG, (bar_x, bar_y, fill_w, bar_h))
        # Target selector: shows manual target, or current auto-target if no manual one.
        selected_target = self._get_best_attack_target()
        if selected_target is not None and selected_target.alive() and getattr(selected_target, 'state', None) != 'dead':
            target_rect = self.camera.apply(selected_target).inflate(8, 8)
            px, py = self.player.hit_rect.centerx, self.player.hit_rect.centery
            mx, my = selected_target.hit_rect.centerx, selected_target.hit_rect.centery
            d_sq = (px - mx) ** 2 + (py - my) ** 2
            in_range = d_sq <= PLAYER_ATTACK_RANGE * PLAYER_ATTACK_RANGE
            outline_color = GREEN if in_range else RED
            pg.draw.rect(self.screen, outline_color, target_rect, 2)
        # Mob attack range overlays only (player overlay removed)
        overlay = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        path_rect = pg.Rect(0, 0, TILESIZE, TILESIZE)
        for mob in self.all_mobs:
            if getattr(mob, 'state', None) == 'dead':
                continue
            if getattr(mob, 'state', None) == 'inactive':
                continue
            mx, my = mob.hit_rect.centerx, mob.hit_rect.centery
            mr = MOB_ATTACK_RANGE
            for tx in range(self.map.tilewidth):
                for ty in range(self.map.tileheight):
                    cx = tx * TILESIZE + TILESIZE / 2
                    cy = ty * TILESIZE + TILESIZE / 2
                    if (mx - cx) ** 2 + (my - cy) ** 2 <= mr * mr:
                        path_rect.x = tx * TILESIZE
                        path_rect.y = ty * TILESIZE
                        screen_rect = self.camera.apply_rect(path_rect)
                        overlay.fill(MOB_ATTACK_OVERLAY, screen_rect)
        self.screen.blit(overlay, (0, 0))
        self.draw_hud()
        self.draw_hotbar()
        if self.inventory_open:
            self.draw_inventory()
        if self.pause_menu_open:
            self.draw_pause_menu()
        self.display.blit(self.screen, (0, 0))
        pg.display.flip()

    def draw_death(self):
        """Death screen shown before respawning."""
        self.screen.fill((10, 0, 0))
        title_font = pg.font.Font(pg.font.match_font('arial'), 64)
        msg_font = pg.font.Font(pg.font.match_font('arial'), 24)
        btn_font = pg.font.Font(pg.font.match_font('arial'), 28)
        title = title_font.render("You Died", True, RED)
        msg = msg_font.render("The dungeon has claimed you... for now.", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 120)))
        self.screen.blit(msg, msg.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60)))
        btn_w, btn_h = 240, 60
        btn_x = WIDTH // 2 - btn_w // 2
        btn_y = HEIGHT // 2 + 20
        self.respawn_button_rect = pg.Rect(btn_x, btn_y, btn_w, btn_h)
        mouse_over = self.respawn_button_rect.collidepoint(pg.mouse.get_pos())
        btn_color = (160, 30, 30) if mouse_over else (120, 20, 20)
        pg.draw.rect(self.screen, btn_color, self.respawn_button_rect)
        pg.draw.rect(self.screen, WHITE, self.respawn_button_rect, 2)
        btn_text = btn_font.render("Respawn", True, WHITE)
        self.screen.blit(btn_text, btn_text.get_rect(center=self.respawn_button_rect.center))
        self.display.blit(self.screen, (0, 0))
        pg.display.flip()

    def draw_pause_menu(self):
        """ESC pause menu with save options."""
        overlay = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        title_font = pg.font.Font(pg.font.match_font('arial'), 48)
        btn_font = pg.font.Font(pg.font.match_font('arial'), 24)
        title = title_font.render("Paused", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 140)))

        btn_w, btn_h = 320, 56
        x = WIDTH // 2 - btn_w // 2
        y0 = HEIGHT // 2 - 50
        self.pause_save_btn_rect = pg.Rect(x, y0, btn_w, btn_h)
        self.pause_quit_title_btn_rect = pg.Rect(x, y0 + 72, btn_w, btn_h)
        self.pause_resume_btn_rect = pg.Rect(x, y0 + 144, btn_w, btn_h)
        for rect, text in (
            (self.pause_save_btn_rect, "Save Game"),
            (self.pause_quit_title_btn_rect, "Save & Quit to Title"),
            (self.pause_resume_btn_rect, "Resume"),
        ):
            hover = rect.collidepoint(pg.mouse.get_pos())
            color = (80, 80, 80) if hover else (55, 55, 55)
            pg.draw.rect(self.screen, color, rect)
            pg.draw.rect(self.screen, WHITE, rect, 2)
            surf = btn_font.render(text, True, WHITE)
            self.screen.blit(surf, surf.get_rect(center=rect.center))

    def respawn_player(self):
        """Respawn player at checkpoint and return to gameplay."""
        if self.checkpoint_tile is None:
            self.checkpoint_tile = (self.player.tile_x, self.player.tile_y)
        cx, cy = self.checkpoint_tile
        self.player.clear_move_queue()
        self.player.move_state = 'idle'
        self.player.slide_from = None
        self.player.slide_to = None
        self.player.slide_to_tile = None
        self.player.attacking = False
        self.player.attack_hit_dealt = False
        self.player.tile_x, self.player.tile_y = cx, cy
        self.player.pos = vec(cx * TILESIZE + TILESIZE / 2, cy * TILESIZE + TILESIZE / 2)
        self.player.hit_rect.center = self.player.pos
        self.player.rect.center = self.player.hit_rect.center
        self.player.max_health = self.player.get_effective_max_health()
        self.player.health = self.player.max_health
        self.manual_target = None
        self.state = 'playing'

    def go_to_next_level(self):
        """Transition through unlocked exit to the next level file."""
        try:
            idx = self.level_order.index(self.current_level_name)
        except ValueError:
            idx = 0
        if idx + 1 >= len(self.level_order):
            return
        self.mob_states_by_level[self.current_level_name] = self._snapshot_current_level_mobs()
        next_level = self.level_order[idx + 1]
        self.load_level(next_level, create_player=False)
        # Ensure camera and gameplay continue cleanly on transition.
        self.pause_menu_open = False
        self.inventory_open = False
        self.inv_dragging = None
        self.inv_selected = None
        self.manual_target = None
        self.camera.update(self.player)
        self.save_inventory_state()

    def go_to_prev_level(self):
        """Transition through return exit to previous level."""
        try:
            idx = self.level_order.index(self.current_level_name)
        except ValueError:
            idx = 0
        if idx <= 0:
            return
        self.mob_states_by_level[self.current_level_name] = self._snapshot_current_level_mobs()
        prev_level = self.level_order[idx - 1]
        self.load_level(prev_level, create_player=False)
        self.pause_menu_open = False
        self.inventory_open = False
        self.inv_dragging = None
        self.inv_selected = None
        self.manual_target = None
        self.camera.update(self.player)
        self.save_inventory_state()

    def draw_intro(self):
        """Menu-style title screen with interactive buttons."""
        self.screen.fill((8, 8, 12))
        panel_w, panel_h = 620, 540
        panel_x = (WIDTH - panel_w) // 2
        panel_y = (HEIGHT - panel_h) // 2
        pg.draw.rect(self.screen, (25, 25, 35), (panel_x, panel_y, panel_w, panel_h))
        pg.draw.rect(self.screen, GOLD, (panel_x, panel_y, panel_w, panel_h), 2)

        font_title = pg.font.Font(pg.font.match_font('arial'), 72)
        font_tag = pg.font.Font(pg.font.match_font('arial'), 24)
        font_btn = pg.font.Font(pg.font.match_font('arial'), 28)
        font_hint = pg.font.Font(pg.font.match_font('arial'), 16)
        font_world = pg.font.Font(pg.font.match_font('arial'), 18)
        title_surf = font_title.render(TITLE, True, WHITE)
        tag_surf = font_tag.render("Descend. Discover. Survive.", True, DARKGRAY)
        self.screen.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, panel_y + 92)))
        self.screen.blit(tag_surf, tag_surf.get_rect(center=(WIDTH // 2, panel_y + 145)))
        if self.current_save_name:
            world_surf = font_world.render(f"Active world: {self.current_save_name}", True, GOLD)
            self.screen.blit(world_surf, world_surf.get_rect(center=(WIDTH // 2, panel_y + 176)))

        btn_w, btn_h = 300, 62
        self.title_start_btn_rect = pg.Rect(WIDTH // 2 - btn_w // 2, panel_y + 220, btn_w, btn_h)
        self.title_new_world_btn_rect = pg.Rect(WIDTH // 2 - btn_w // 2, panel_y + 300, btn_w, btn_h)
        self.title_quit_btn_rect = pg.Rect(WIDTH // 2 - btn_w // 2, panel_y + 380, btn_w, btn_h)
        for rect, text in (
            (self.title_start_btn_rect, "Start / Continue"),
            (self.title_new_world_btn_rect, "New World"),
            (self.title_quit_btn_rect, "Quit"),
        ):
            hover = rect.collidepoint(pg.mouse.get_pos())
            color = (90, 90, 110) if hover else (60, 60, 80)
            pg.draw.rect(self.screen, color, rect)
            pg.draw.rect(self.screen, WHITE, rect, 2)
            surf = font_btn.render(text, True, WHITE)
            self.screen.blit(surf, surf.get_rect(center=rect.center))

        hint = font_hint.render("Click a button, Enter=Continue, N=New World", True, GOLD)
        self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, panel_y + panel_h - 26)))
        self.display.blit(self.screen, (0, 0))
        pg.display.flip()

    def draw_hud(self):
        """Top-left HUD: health bar, attack cooldown bar, labels."""
        x, y = HUD_PADDING, HUD_PADDING
        font = pg.font.Font(pg.font.match_font('arial'), HUD_FONT_SIZE)
        # Health
        label = font.render("Health", True, WHITE)
        self.screen.blit(label, (x, y))
        y += HUD_LINE_HEIGHT
        bar_x, bar_y = x, y
        eff_max = self.player.get_effective_max_health()
        self.screen.fill(HP_BAR_BG, (bar_x, bar_y, HUD_HEALTH_BAR_W, HUD_HEALTH_BAR_H))
        if eff_max > 0:
            fill_w = max(1, int(HUD_HEALTH_BAR_W * self.player.health / eff_max))
            self.screen.fill(HP_BAR_FG, (bar_x, bar_y, fill_w, HUD_HEALTH_BAR_H))
        hp_text = font.render(f"{self.player.health} / {eff_max}", True, WHITE)
        self.screen.blit(hp_text, (bar_x + HUD_HEALTH_BAR_W + 8, bar_y - 2))
        y += HUD_HEALTH_BAR_H + 12
        # Attack cooldown
        label = font.render("Attack", True, WHITE)
        self.screen.blit(label, (x, y))
        y += HUD_LINE_HEIGHT
        remaining = self.player.get_attack_cooldown_remaining()
        self.screen.fill(HP_BAR_BG, (x, y, HUD_ATTACK_BAR_W, HUD_ATTACK_BAR_H))
        if self.player.attacking:
            status = "Attacking..."
        elif remaining <= 0:
            self.screen.fill(HP_BAR_FG, (x, y, HUD_ATTACK_BAR_W, HUD_ATTACK_BAR_H))
            status = "Ready"
        else:
            fill_w = max(0, int(HUD_ATTACK_BAR_W * (1 - remaining / PLAYER_ATTACK_COOLDOWN_MS)))
            if fill_w > 0:
                self.screen.fill(HP_BAR_FG, (x, y, fill_w, HUD_ATTACK_BAR_H))
            status = f"{remaining} ms"
        status_surf = font.render(status, True, GOLD if remaining <= 0 else WHITE)
        self.screen.blit(status_surf, (x + HUD_ATTACK_BAR_W + 8, y - 2))

    def draw_slot(self, x, y, slot_data, selected=False, highlight=False, dimmed=False):
        """Draw one inventory slot at (x, y). Returns the pg.Rect."""
        rect = pg.Rect(x, y, SLOT_SIZE, SLOT_SIZE)
        border_color = SLOT_SELECTED if selected else (WHITE if highlight else SLOT_BORDER)
        pg.draw.rect(self.screen, SLOT_BG, rect)
        pg.draw.rect(self.screen, border_color, rect, 2)
        if slot_data:
            item_id, count = slot_data
            if item_id in ITEM_DEFS:
                color = ITEM_DEFS[item_id]['color']
                if dimmed:
                    color = tuple(max(0, c // 2) for c in color)
                pad = 6
                pg.draw.rect(self.screen, color, (x + pad, y + pad, SLOT_SIZE - 2 * pad, SLOT_SIZE - 2 * pad))
            font = pg.font.Font(pg.font.match_font('arial'), 14)
            if count > 1:
                text = font.render(str(count), True, WHITE)
                badge_w = text.get_width() + 4
                badge_h = text.get_height() + 2
                badge_x = x + SLOT_SIZE - badge_w - 1
                badge_y = y + SLOT_SIZE - badge_h - 1
                pg.draw.rect(self.screen, (20, 20, 20), (badge_x, badge_y, badge_w, badge_h))
                pg.draw.rect(self.screen, (70, 70, 70), (badge_x, badge_y, badge_w, badge_h), 1)
                self.screen.blit(text, (badge_x + 2, badge_y + 1))
        return rect

    def draw_hotbar(self):
        """Draw item bar at bottom center. Hotbar shows first HOTBAR_SLOTS slots; one is selected."""
        total_w = HOTBAR_SLOTS * SLOT_SIZE + (HOTBAR_SLOTS - 1) * SLOT_GAP
        start_x = (WIDTH - total_w) // 2
        y = HEIGHT - SLOT_SIZE - HUD_PADDING
        for i in range(HOTBAR_SLOTS):
            x = start_x + i * (SLOT_SIZE + SLOT_GAP)
            slot_data = self.inventory.get_hotbar_slot(i)
            self.draw_slot(x, y, slot_data, selected=(i == self.inventory.selected_hotbar_index))
        font = pg.font.Font(pg.font.match_font('arial'), 14)
        hint = font.render("1-8 select  F use item  E / I inventory", True, DARKGRAY)
        self.screen.blit(hint, (start_x, y + SLOT_SIZE + 4))

    def use_selected_item(self):
        """Use currently selected hotbar item (e.g. health potion)."""
        idx = self.inventory.selected_hotbar_index
        slot_data = self.inventory.get_slot(idx)
        if slot_data is None:
            return False
        item_id, _ = slot_data
        item_def = ITEM_DEFS.get(item_id, {})
        if item_def.get('type') != 'consumable':
            return False
        effect = item_def.get('effect', {})
        healed = int(effect.get('heal', 0))
        applied = False
        if healed > 0:
            max_hp = self.player.get_effective_max_health()
            old_hp = self.player.health
            self.player.health = min(max_hp, self.player.health + healed)
            applied = self.player.health > old_hp
        if not applied:
            return False
        consumed = self.inventory.consume_from_slot(idx, 1)
        return consumed is not None

    def draw_inventory(self):
        """Minecraft-style inventory with hover tooltips, click-to-select, drag-and-drop, right-click equip."""
        overlay = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        font_title = pg.font.Font(pg.font.match_font('arial'), 28)
        font = pg.font.Font(pg.font.match_font('arial'), HUD_FONT_SIZE)
        font_sm = pg.font.Font(pg.font.match_font('arial'), 14)
        font_tip = pg.font.Font(pg.font.match_font('arial'), 13)

        mouse_pos = pg.mouse.get_pos()
        self.inv_slot_rects = []
        hovered_item_id = None

        panel_w = 700
        panel_h = 530
        panel_x = (WIDTH - panel_w) // 2
        panel_y = (HEIGHT - panel_h) // 2
        pg.draw.rect(self.screen, (30, 30, 30), (panel_x, panel_y, panel_w, panel_h))
        pg.draw.rect(self.screen, GOLD, (panel_x, panel_y, panel_w, panel_h), 2)

        close_hint = font_sm.render("E / I / Esc to close   Left-click: select   Right-click: equip/unequip   Drag to swap", True, GOLD)
        self.screen.blit(close_hint, (panel_x + 12, panel_y + panel_h - 22))

        # --- LEFT SIDE: player preview, armor slots, stats ---
        left_x = panel_x + 20
        cy = panel_y + 16

        preview_size = 96
        player_img = self.player.move_frames.get(self.player.facing, [None])[0]
        if player_img:
            preview = pg.transform.scale(player_img, (preview_size, preview_size))
            preview_rect = pg.Rect(left_x + 10, cy, preview_size, preview_size)
            pg.draw.rect(self.screen, SLOT_BG, preview_rect.inflate(8, 8))
            pg.draw.rect(self.screen, SLOT_BORDER, preview_rect.inflate(8, 8), 2)
            self.screen.blit(preview, preview_rect)

        eq_x = left_x + preview_size + 30
        eq_y = cy
        eq_label_map = {'head': 'Head', 'chest': 'Chest', 'boots': 'Boots', 'shield': 'Shield', 'weapon': 'Weapon'}
        eq_order = ['head', 'chest', 'boots', 'shield', 'weapon']
        for eq_slot in eq_order:
            item_id = self.inventory.equipment.get(eq_slot)
            slot_data = (item_id, 1) if item_id else None
            is_drag_src = self.inv_dragging and self.inv_dragging[0] == 'equip' and self.inv_dragging[1] == eq_slot
            is_selected = self.inv_selected == ('equip', eq_slot)
            r = self.draw_slot(eq_x, eq_y, slot_data, highlight=is_selected, dimmed=is_drag_src)
            self.inv_slot_rects.append((r, 'equip', eq_slot))
            if r.collidepoint(mouse_pos) and item_id and not is_drag_src:
                hovered_item_id = item_id
            label = font_sm.render(eq_label_map[eq_slot], True, DARKGRAY)
            self.screen.blit(label, (eq_x + SLOT_SIZE + 6, eq_y + SLOT_SIZE // 2 - label.get_height() // 2))
            eq_y += SLOT_SIZE + 4

        # Stats
        stats_y = cy + preview_size + 20
        section = font.render("Stats", True, GOLD)
        self.screen.blit(section, (left_x, stats_y))
        stats_y += 26
        attrs = self.player.get_effective_attrs()
        bonuses = self.inventory.get_equipment_stat_bonuses()
        for stat in ['strength', 'dexterity', 'intelligence', 'health']:
            b = bonuses.get(stat, 0)
            bonus_str = f"  (+{b})" if b > 0 else ""
            line = font_sm.render(f"{stat.capitalize()}: {attrs.get(stat, 0)}{bonus_str}", True, WHITE)
            self.screen.blit(line, (left_x + 8, stats_y))
            stats_y += 20
        stats_y += 8
        eff_max = self.player.get_effective_max_health()
        for text in [f"HP: {self.player.health} / {eff_max}",
                     f"Damage: {self.player.get_effective_damage()}",
                     f"Defense: {self.inventory.get_total_defense()}"]:
            self.screen.blit(font_sm.render(text, True, WHITE), (left_x + 8, stats_y))
            stats_y += 20

        # --- RIGHT SIDE: inventory grid ---
        inv_cols = INVENTORY_COLS
        inv_rows = INVENTORY_ROWS
        total_inv_w = inv_cols * SLOT_SIZE + (inv_cols - 1) * SLOT_GAP
        inv_x = panel_x + panel_w - total_inv_w - 20
        inv_label = font.render("Inventory", True, GOLD)
        self.screen.blit(inv_label, (inv_x, panel_y + 16))
        inv_start_y = panel_y + 50
        for row in range(inv_rows):
            for col in range(inv_cols):
                idx = row * inv_cols + col
                sx = inv_x + col * (SLOT_SIZE + SLOT_GAP)
                sy = inv_start_y + row * (SLOT_SIZE + SLOT_GAP)
                slot_data = self.inventory.get_slot(idx)
                is_drag_src = self.inv_dragging and self.inv_dragging[0] == 'inv' and self.inv_dragging[1] == idx
                is_selected = self.inv_selected == ('inv', idx)
                is_hotbar = idx < HOTBAR_SLOTS and idx == self.inventory.selected_hotbar_index
                r = self.draw_slot(sx, sy, slot_data, selected=is_hotbar, highlight=is_selected, dimmed=is_drag_src)
                self.inv_slot_rects.append((r, 'inv', idx))
                if r.collidepoint(mouse_pos) and slot_data and not is_drag_src:
                    hovered_item_id = slot_data[0]

        # --- Drag ghost ---
        if self.inv_dragging:
            _, _, drag_item_id, drag_count = self.inv_dragging
            if drag_item_id in ITEM_DEFS:
                color = ITEM_DEFS[drag_item_id]['color']
                ghost_size = SLOT_SIZE - 8
                gx = mouse_pos[0] - ghost_size // 2
                gy = mouse_pos[1] - ghost_size // 2
                ghost = pg.Surface((ghost_size, ghost_size), pg.SRCALPHA)
                pg.draw.rect(ghost, (*color, 180), (0, 0, ghost_size, ghost_size))
                self.screen.blit(ghost, (gx, gy))
                if drag_count > 1:
                    cnt = font_sm.render(str(drag_count), True, WHITE)
                    self.screen.blit(cnt, (gx + ghost_size - cnt.get_width(), gy + ghost_size - cnt.get_height()))

        # --- Tooltip ---
        if hovered_item_id and not self.inv_dragging:
            self._draw_tooltip(mouse_pos, hovered_item_id, font_tip)

    def _draw_tooltip(self, pos, item_id, font):
        """Render a multi-line tooltip box next to the cursor."""
        item = ITEM_DEFS.get(item_id, {})
        lines = []
        lines.append(item.get('name', item_id))
        itype = item.get('type', '')
        if itype:
            lines.append(f"Type: {itype.capitalize()}")
        desc = item.get('description', '')
        if desc:
            lines.append(desc)
        if item.get('base_damage'):
            lines.append(f"Base Damage: {item['base_damage']}")
        if item.get('scaling_stat'):
            lines.append(f"Scales: {item['scaling_stat'].capitalize()} x{item.get('scaling_factor', 0)}")
        if item.get('defense'):
            lines.append(f"Defense: {item['defense']}")
        sb = item.get('stat_bonus', {})
        if sb:
            parts = [f"{k.capitalize()} +{v}" for k, v in sb.items()]
            lines.append("Bonus: " + ", ".join(parts))
        if item.get('effect'):
            for ek, ev in item['effect'].items():
                lines.append(f"Effect: {ek} {ev}")

        rendered = [font.render(l, True, WHITE) for l in lines]
        name_surf = pg.font.Font(pg.font.match_font('arial'), 15).render(lines[0], True, GOLD) if lines else None
        if name_surf:
            rendered[0] = name_surf
        pad = 8
        tip_w = max(s.get_width() for s in rendered) + pad * 2
        tip_h = sum(s.get_height() + 2 for s in rendered) + pad * 2
        tx = pos[0] + 16
        ty = pos[1] + 4
        if tx + tip_w > WIDTH:
            tx = pos[0] - tip_w - 4
        if ty + tip_h > HEIGHT:
            ty = HEIGHT - tip_h - 4
        bg = pg.Surface((tip_w, tip_h), pg.SRCALPHA)
        bg.fill((20, 20, 20, 230))
        self.screen.blit(bg, (tx, ty))
        pg.draw.rect(self.screen, SLOT_BORDER, (tx, ty, tip_w, tip_h), 1)
        cy = ty + pad
        for surf in rendered:
            self.screen.blit(surf, (tx + pad, cy))
            cy += surf.get_height() + 2

    def _inv_hit_test(self, pos):
        """Return (source, index) for the slot under pos, or None."""
        for rect, source, index in self.inv_slot_rects:
            if rect.collidepoint(pos):
                return (source, index)
        return None

    def _inv_mouse_down(self, event):
        hit = self._inv_hit_test(event.pos)
        if hit is None:
            self.inv_selected = None
            return
        source, index = hit
        if event.button == 1:
            # Left click: start drag if slot has item, or select
            if source == 'inv':
                slot_data = self.inventory.get_slot(index)
                if slot_data:
                    self.inv_dragging = (source, index, slot_data[0], slot_data[1])
                    self.inv_selected = hit
                else:
                    self.inv_selected = hit
            elif source == 'equip':
                item_id = self.inventory.equipment.get(index)
                if item_id:
                    self.inv_dragging = (source, index, item_id, 1)
                    self.inv_selected = hit
                else:
                    self.inv_selected = hit
        elif event.button == 3:
            # Right click: equip from inventory, or unequip from equipment
            if source == 'inv':
                slot_data = self.inventory.get_slot(index)
                if slot_data:
                    item_def = ITEM_DEFS.get(slot_data[0], {})
                    if item_def.get('slot') in EQUIPMENT_SLOTS:
                        self.inventory.equip_from_slot(index)
            elif source == 'equip':
                self.inventory.unequip(index)

    def _inv_mouse_up(self, event):
        if event.button != 1 or not self.inv_dragging:
            self.inv_dragging = None
            return
        drag_src, drag_idx, drag_item, drag_count = self.inv_dragging
        drop_hit = self._inv_hit_test(event.pos)
        self.inv_dragging = None

        if drop_hit is None:
            return
        drop_src, drop_idx = drop_hit
        if (drag_src, drag_idx) == (drop_src, drop_idx):
            return

        # Swap logic between inventory slots and equipment slots
        if drag_src == 'inv' and drop_src == 'inv':
            # Swap two inventory slots
            a = self.inventory.get_slot(drag_idx)
            b = self.inventory.get_slot(drop_idx)
            self.inventory.slots[drag_idx] = b
            self.inventory.slots[drop_idx] = a
        elif drag_src == 'inv' and drop_src == 'equip':
            item_def = ITEM_DEFS.get(drag_item, {})
            if item_def.get('slot') == drop_idx:
                old_eq = self.inventory.equipment.get(drop_idx)
                self.inventory.equipment[drop_idx] = drag_item
                if old_eq:
                    self.inventory.set_slot(drag_idx, old_eq, 1)
                else:
                    self.inventory.remove_item(drag_idx, drag_count)
        elif drag_src == 'equip' and drop_src == 'inv':
            drop_data = self.inventory.get_slot(drop_idx)
            if drop_data is None:
                self.inventory.set_slot(drop_idx, drag_item, 1)
                self.inventory.equipment[drag_idx] = None
            else:
                drop_item_def = ITEM_DEFS.get(drop_data[0], {})
                if drop_item_def.get('slot') == drag_idx:
                    self.inventory.equipment[drag_idx] = drop_data[0]
                    self.inventory.set_slot(drop_idx, drag_item, 1)
                else:
                    leftover = self.inventory.add_item(drag_item, 1)
                    if leftover == 0:
                        self.inventory.equipment[drag_idx] = None
        elif drag_src == 'equip' and drop_src == 'equip':
            if drag_idx == drop_idx:
                return
            # Can't swap between different equipment slot types

    def draw_text(self, text, size, color, x, y):
        font_name = pg.font.match_font('arial')
        font = pg.font.Font(font_name, size)
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        text_rect.midtop = (x, y)
        self.screen.blit(text_surface, text_rect)

    def _handle_click_target(self, mouse_pos):
        """Select nearest clicked mob on screen; click empty space to clear target."""
        mx, my = mouse_pos
        clicked = []
        for mob in self.all_mobs:
            if getattr(mob, 'state', None) == 'dead':
                continue
            screen_rect = self.camera.apply(mob)
            if screen_rect.collidepoint(mx, my):
                cx, cy = screen_rect.centerx, screen_rect.centery
                d_sq = (mx - cx) ** 2 + (my - cy) ** 2
                clicked.append((d_sq, mob))
        if clicked:
            clicked.sort(key=lambda t: t[0])
            self.manual_target = clicked[0][1]
        else:
            self.manual_target = None

    def _get_best_attack_target(self):
        """Return manual target if valid/in-range, else nearest in-range live mob."""
        px, py = self.player.hit_rect.centerx, self.player.hit_rect.centery
        best = None
        best_d_sq = PLAYER_ATTACK_RANGE * PLAYER_ATTACK_RANGE
        if self.manual_target is not None:
            if self.manual_target.alive() and getattr(self.manual_target, 'state', None) != 'dead':
                mx = self.manual_target.hit_rect.centerx
                my = self.manual_target.hit_rect.centery
                d_sq = (px - mx) ** 2 + (py - my) ** 2
                if d_sq <= best_d_sq:
                    return self.manual_target
        for mob in self.all_mobs:
            if getattr(mob, 'state', None) == 'dead':
                continue
            mx = mob.hit_rect.centerx
            my = mob.hit_rect.centery
            d_sq = (px - mx) ** 2 + (py - my) ** 2
            if d_sq <= best_d_sq:
                best_d_sq = d_sq
                best = mob
        return best


if __name__ == "__main__":
    g = Game()
    while g.running:
        g.new()
    pg.quit()
