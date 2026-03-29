"""World/level spatial operations."""
from collections import deque
from os import path

import pygame as pg

from settings import FLOOR_COLOR, MOB_HP, TILESIZE
from utils import Map, Camera, tiles_on_grid_line
from sprites import Wall, Mob, Player
from game.systems import intro_ops

vec = pg.math.Vector2


def load_data(self):
    self.game_dir = path.dirname(__file__)
    self.game_dir = path.dirname(path.dirname(self.game_dir))  # back to project root
    self.img_dir = path.join(self.game_dir, 'images')
    self.levels_dir = path.join(self.game_dir, 'levels')
    self.saves_dir = path.join(self.game_dir, 'saves')
    self.active_save_path = path.join(self.saves_dir, 'active_world.txt')
    self.wall_img = pg.image.load(path.join(self.img_dir, 'wall_art.png')).convert_alpha()
    self.level_order = [
        'intro.txt',
        'level1.txt',
        'level2.txt',
        'level3.txt',
        'level4.txt',
        'level5.txt',
        'level6.txt',
        'level7.txt',
        'level8.txt',
        'level9.txt',
    ]
    self.current_level_name = self.level_order[0]
    self.current_save_name = None
    self.save_path = None
    self.mob_states_by_level = {}
    self.opened_chests = set()
    self.intro_exit_unlocked = False
    self.init_save_system()
    self._load_world_state_from_save()
    self.load_level(self.current_level_name, create_player=True)
    self._item_sprite_cache = {}


def is_walkable(self, col, row):
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


def tile_blocks_line_of_sight(self, col, row):
    if row < 0 or row >= len(self.map.data):
        return True
    if col < 0 or col >= len(self.map.data[0]):
        return True
    tile = self.map.data[row][col]
    if tile == '1':
        return True
    if tile == 'N' and not self.level_exit_open:
        return True
    return False


def has_line_of_sight_tiles(self, c0, r0, c1, r1):
    for c, r in tiles_on_grid_line(c0, r0, c1, r1):
        if self.tile_blocks_line_of_sight(c, r):
            return False
    return True


def load_level(self, level_name, create_player=False):
    self.current_level_name = level_name
    level_path = path.join(self.levels_dir, level_name)
    self.map = Map(level_path)
    self.map_img = pg.Surface((self.map.width, self.map.height))
    self.map_img.fill(FLOOR_COLOR)
    self.map_rect = self.map_img.get_rect()
    self.all_sprites = pg.sprite.Group()
    self.all_walls = pg.sprite.Group()
    self.all_mobs = pg.sprite.Group()
    self.all_projectiles = pg.sprite.Group()
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
            elif tile == 'A':
                default_mob_spawns.append((col, row, 'shadow_assassin'))
            elif tile == 'G':
                default_mob_spawns.append((col, row, 'ghost'))
            elif tile == 'D':
                default_mob_spawns.append((col, row, 'training_dummy'))

    if self.checkpoint_tile is None and player_spawn is not None:
        self.checkpoint_tile = player_spawn
    if player_spawn is None:
        player_spawn = self.checkpoint_tile if self.checkpoint_tile else (1, 1)
    reachable_tiles = self._compute_reachable_tiles_from(player_spawn[0], player_spawn[1])

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
            tx = int(m.get('tile_x', 0)); ty = int(m.get('tile_y', 0))
            if (tx, ty) not in reachable_tiles:
                continue
            mob_type = m.get('mob_type', 'statue')
            health = int(m.get('health', MOB_HP))
            if health <= 0:
                continue
            mob = Mob(self, tx, ty, mob_type=mob_type)
            mob.health = max(1, health)
            if m.get('state') in ('inactive', 'idle', 'walk', 'attack'):
                mob.state = m.get('state')
    else:
        for spawn in default_mob_spawns:
            if len(spawn) == 3:
                col, row, mob_type = spawn
            else:
                col, row = spawn; mob_type = 'statue'
            if (col, row) not in reachable_tiles:
                continue
            Mob(self, col, row, mob_type=mob_type)

    self.level_exit_open = len([m for m in self.all_mobs if getattr(m, 'state', None) != 'dead']) == 0
    if intro_ops.is_intro_level(self):
        intro_ops.refresh_intro_exit_open(self)
    if hasattr(self, '_apply_opened_chests_to_map'):
        self._apply_opened_chests_to_map()
    self.camera = Camera(self.map.width, self.map.height)
    self.manual_target = None


def _compute_reachable_tiles_from(self, start_col, start_row):
    h = len(self.map.data)
    w = len(self.map.data[0]) if h > 0 else 0
    if w == 0 or h == 0:
        return set()
    if not (0 <= start_col < w and 0 <= start_row < h):
        return set()
    start_tile = self.map.data[start_row][start_col]
    if start_tile == '1':
        return set()
    q = deque()
    q.append((start_col, start_row))
    seen = {(start_col, start_row)}
    while q:
        c, r = q.popleft()
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc, nr = c + dc, r + dr
            if not (0 <= nc < w and 0 <= nr < h):
                continue
            if (nc, nr) in seen:
                continue
            t = self.map.data[nr][nc]
            if t == '1':
                continue
            seen.add((nc, nr))
            q.append((nc, nr))
    return seen


def go_to_next_level(self):
    try:
        idx = self.level_order.index(self.current_level_name)
    except ValueError:
        idx = 0
    if idx + 1 >= len(self.level_order):
        return
    self.mob_states_by_level[self.current_level_name] = self._snapshot_current_level_mobs()
    next_level = self.level_order[idx + 1]
    self.load_level(next_level, create_player=False)
    self.pause_menu_open = False
    self.inventory.return_craft_staging()
    self.inventory.return_upgrade_staging()
    self.inventory_open = False
    self.inv_dragging = None
    self.inv_selected = None
    self.manual_target = None
    self.camera.update(self.player)
    self.save_inventory_state()


def go_to_prev_level(self):
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
    self.inventory.return_craft_staging()
    self.inventory.return_upgrade_staging()
    self.inventory_open = False
    self.inv_dragging = None
    self.inv_selected = None
    self.manual_target = None
    self.camera.update(self.player)
    self.save_inventory_state()

