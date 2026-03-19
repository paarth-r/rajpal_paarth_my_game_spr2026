import pygame as pg

# Window and viewport size (fixed on screen). SCALE = zoom: higher = see less world, things look bigger.
WIDTH = 1280
HEIGHT = 720
SCALE = 2  # Zoom level: view shows (WIDTH/SCALE x HEIGHT/SCALE) world, drawn at WIDTH x HEIGHT
TITLE = "Relictus"
FPS = 60
TILESIZE = 32

# player values
PLAYER_SPEED = 128  # small multiple of TILESIZE (32)
PLAYER_HIT_RECT = pg.Rect(0, 0, TILESIZE - 5, TILESIZE - 5)
PLAYER_ANIM_SPEED = 150
PLAYER_ATTACK_SPEED = 100
PLAYER_ATTACK_RANGE = TILESIZE * 2  # radius in pixels; any attackable in this range is auto-targeted
PLAYER_MAX_HEALTH = 100
PLAYER_ATTACK_DAMAGE = 50
PLAYER_ATTACK_COOLDOWN_MS = 400  # ms after attack ends before next attack allowed (HUD shows this)

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
# statue spritesheet: 512x256 image, 8 cols x 4 rows = 64x64 per frame (row 0 idle, 1 walk, 2 attack, 3 death)
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

# Inventory and item bar (hotbar)
INVENTORY_SLOTS = 24
HOTBAR_SLOTS = 8
SLOT_SIZE = 44
SLOT_GAP = 4
SLOT_BG = (50, 50, 50)
SLOT_BORDER = (80, 80, 80)
SLOT_SELECTED = GOLD
INVENTORY_COLS = 6
INVENTORY_ROWS = 4
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
