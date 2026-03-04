import pygame as pg

WIDTH = 800
HEIGHT = 600
TITLE = "Dungeon Crawl"
FPS = 60
TILESIZE = 32

# player values
PLAYER_SPEED = 280
PLAYER_HIT_RECT = pg.Rect(0, 0, TILESIZE - 5, TILESIZE - 5)

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
