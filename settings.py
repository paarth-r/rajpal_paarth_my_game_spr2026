import pygame as pg

# Window and viewport size (fixed on screen). SCALE = zoom: higher = see less world, things look bigger.
WIDTH = 1500
HEIGHT = 900
SCALE = 3  # Zoom level: view shows (WIDTH/SCALE x HEIGHT/SCALE) world, drawn at WIDTH x HEIGHT
TITLE = "Relictus"
FPS = 60
TILESIZE = 32

# player values
PLAYER_SPEED = 128  # small multiple of TILESIZE (32)
PLAYER_HIT_RECT = pg.Rect(0, 0, TILESIZE - 5, TILESIZE - 5)
PLAYER_ANIM_SPEED = 150
PLAYER_ATTACK_SPEED = 100
# Default melee reach in tiles (weapons override via items.json attack_range_tiles)
PLAYER_DEFAULT_ATTACK_RANGE_TILES = 2
# Legacy pixel radius when no weapon / fallback (matches 2 tiles)
PLAYER_ATTACK_RANGE = TILESIZE * PLAYER_DEFAULT_ATTACK_RANGE_TILES
MIN_WEAPON_ATTACK_RANGE_TILES = 2
PLAYER_MAX_HEALTH = 100
PLAYER_ATTACK_DAMAGE = 50
PLAYER_ATTACK_COOLDOWN_MS = 400  # ms after attack ends before next attack allowed (HUD shows this)
# Ranged attacks (staves and bows) trade damage for safety.
RANGED_WEAPON_DAMAGE_MULT = 0.58  # staff / bow final damage modifier (safety vs melee range)
PROJECTILE_SPEED_PX_PER_SEC = 640
PROJECTILE_RADIUS_PX = 5

# mob values (statue: idle until player in range, then chase/attack)
MOB_ACTIVATION_RANGE_TILES = 5  # blocks; mob stays "idle still" (row 0 frame 0) until player this close
MOB_SPEED = 12
MOB_CHASE_RANGE = 6 * TILESIZE
MOB_HIT_RECT = pg.Rect(0, 0, TILESIZE - 4, TILESIZE - 4)
MOB_HP = 200
MOB_DAMAGE = 50  # per attack
MOB_ATTACK_COOLDOWN = 4000  # ms between attacks (easier to dodge)
MOB_ATTACK_RANGE = TILESIZE * 1.2  # shorter reach, must get close
MOB_ATTACK_ANIM_SPEED = 150  # ms per attack frame (slower windup, telegraphed)
PLAYER_HURT_COOLDOWN = 800  # ms before player can be hurt again
# statue spritesheet (statue.png): 1016x534; 8×4 grid of ~127×133 px cells (row 0 idle, 1 walk, 2 attack, 3 death)
MOB_FRAME_W = 64
MOB_FRAME_H = 64
MOB_ANIM_SPEED = 120  # ms per frame
MOB_MOVE_DELAY = 500  # ms between tile steps (grid cadence unchanged)
MOB_SLIDE_DURATION_MS = 220  # ms gliding between tiles; rest of cycle spent on tile (ease-in-out)

# color values
BLACK = (0, 0, 0)
DARKGRAY = (40, 40, 40)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
DARKRED = (150, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
GOLD = (255, 215, 0)

BGCOLOR = BLACK
FLOOR_COLOR = DARKGRAY
GRID_COLOR = (30, 30, 30)  # subtle grid on map
# Translucent overlays for attack range (RGBA)
PLAYER_ATTACK_OVERLAY = (255, 0, 0, 70)   # red, translucent
MOB_ATTACK_OVERLAY = (200, 0, 0, 55)      # darker red for mob range

# HP bar (drawn above sprites)
HP_BAR_HEIGHT = 4
HP_BAR_OFFSET = -8  # pixels above sprite
HP_BAR_WIDTH = 24
HP_BAR_BG = DARKRED
HP_BAR_FG = GREEN

# Move queue path preview (tiles player will step to)
PATH_TILE_OUTLINE_COLOR = YELLOW
PATH_TILE_OUTLINE_WIDTH = 2
PLAYER_MOVE_QUEUE_MAX = 30  # max queued tiles so path is visible but bounded

# Intro / title screen
INTRO_TAGLINE = "Only you remained."
INTRO_PROMPT = "Press any key to begin"
INTRO_TITLE_SIZE = 72
INTRO_TAGLINE_SIZE = 28
INTRO_PROMPT_SIZE = 22

# HUD (top-left)
HUD_PADDING = 16
HUD_LINE_HEIGHT = 28
HUD_FONT_SIZE = 20
HUD_HEALTH_BAR_W = 120
HUD_HEALTH_BAR_H = 12
HUD_ATTACK_BAR_W = 100
HUD_ATTACK_BAR_H = 8
# XP bar: black frame + dark track (health bar keeps red DARKRED track)
HUD_XP_BAR_TRACK = BLACK
HUD_XP_BAR_FILL = (70, 110, 200)
HUD_XP_BAR_OUTLINE = BLACK
HUD_XP_BAR_OUTLINE_W = 2

# Top-right: dungeon floor, minimap, mob count
DUNGEON_PANEL_MINIMAP_MAX_PX = 118  # longest side of minimap (scales with map size)
DUNGEON_PANEL_MINIMAP_EXPAND_MULT = 1.42  # click minimap to enlarge; shows exit tiles
DUNGEON_PANEL_MINIMAP_WALL = (22, 24, 32)
DUNGEON_PANEL_MINIMAP_FLOOR = (48, 50, 58)
DUNGEON_PANEL_MINIMAP_PLAYER = (255, 220, 80)
DUNGEON_PANEL_MINIMAP_GATE_OPEN = (145, 60, 210)
DUNGEON_PANEL_MINIMAP_GATE_LOCKED = (72, 48, 92)

# Inventory and item bar (hotbar)
INVENTORY_SLOTS = 40
HOTBAR_SLOTS = 8
SLOT_SIZE = 52
SLOT_GAP = 6
SLOT_BG = (50, 50, 50)
SLOT_BORDER = (80, 80, 80)
SLOT_SELECTED = GOLD
# Inventory / hotbar slot tint behind item icon (by item rarity)
RARITY_SLOT_BG = {
    'common': (95, 95, 95),         # grey
    'uncommon': (148, 210, 148),    # light green
    'rare': (145, 195, 255),        # light blue
    'epic': (170, 120, 220),        # purple
    'legendary': (240, 205, 95),    # gold
    'mythic': (245, 145, 210),      # pink
    'divine': (85, 150, 255),       # blue
    'gamebreaking': (240, 70, 70),  # red
}
UI_TEXT_BRIGHT = (245, 245, 248)
UI_TEXT_MUTED = (190, 195, 210)
UI_TEXT_DIM = (140, 145, 165)
INVENTORY_COLS = 8
INVENTORY_ROWS = 5
INVENTORY_KEY = pg.K_i  # toggle inventory (pg.K_i)
CHARACTER_KEY = pg.K_e  # toggle character/equipment screen

# Player base attributes
PLAYER_BASE_ATTRS = {
    'strength': 5,
    'dexterity': 5,
    'intelligence': 5,
    'health': 10,
}
HEALTH_ATTR_HP_BONUS = 5
DEXTERITY_SPEED_BONUS = 2

# Death penalties (fraction of current gold / current XP bar; floors apply — see Game._apply_death_penalties)
DEATH_GOLD_LOSS_PCT = 0.25
DEATH_XP_LOSS_PCT = 0.25
