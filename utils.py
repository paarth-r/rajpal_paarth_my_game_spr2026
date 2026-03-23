import pygame as pg
from settings import *


class Map:
    def __init__(self, filename):
        self.data = []
        with open(filename, 'rt') as f:
            for line in f:
                self.data.append(line.strip())

        self.tilewidth = len(self.data[0])
        self.tileheight = len(self.data)
        self.width = self.tilewidth * TILESIZE
        self.height = self.tileheight * TILESIZE


class Camera:
    """Camera tracks a zoomed viewport. View size in world = (WIDTH/SCALE, HEIGHT/SCALE).
    World is drawn scaled up by SCALE so the window stays (WIDTH, HEIGHT) but things look bigger."""
    def __init__(self, map_width, map_height):
        self.map_width = map_width
        self.map_height = map_height
        self.view_w = WIDTH / SCALE
        self.view_h = HEIGHT / SCALE
        self.camera = pg.Rect(0, 0, self.view_w, self.view_h)

    def apply(self, entity):
        # World to screen: subtract view topleft, then scale by SCALE
        r = entity.rect
        x = (r.x - self.camera.x) * SCALE
        y = (r.y - self.camera.y) * SCALE
        w = r.width * SCALE
        h = r.height * SCALE
        return pg.Rect(round(x), round(y), max(1, round(w)), max(1, round(h)))

    def apply_rect(self, rect):
        x = (rect.x - self.camera.x) * SCALE
        y = (rect.y - self.camera.y) * SCALE
        w = rect.width * SCALE
        h = rect.height * SCALE
        return pg.Rect(round(x), round(y), max(1, round(w)), max(1, round(h)))

    def update(self, target):
        x = target.rect.centerx - self.view_w / 2
        y = target.rect.centery - self.view_h / 2
        # Unclamped camera: allow viewing beyond map boundaries/walls.
        self.camera = pg.Rect(x, y, self.view_w, self.view_h)


class Spritesheet:
    def __init__(self, filename):
        self.spritesheet = pg.image.load(filename).convert_alpha()

    def get_image(self, x, y, width, height):
        image = pg.Surface((width, height), pg.SRCALPHA)
        image.blit(self.spritesheet, (0, 0), (x, y, width, height))
        return image


class Cooldown:
    def __init__(self, time):
        self.start_time = 0
        self.time = time

    def start(self):
        self.start_time = pg.time.get_ticks()

    def ready(self):
        current_time = pg.time.get_ticks()
        return current_time - self.start_time >= self.time


def tiles_on_grid_line(c0, r0, c1, r1):
    """Bresenham line in tile column/row space. Inclusive endpoints. (col, row) order."""
    c0, r0, c1, r1 = int(c0), int(r0), int(c1), int(r1)
    cells = []
    dx = abs(c1 - c0)
    dy = abs(r1 - r0)
    sx = 1 if c0 < c1 else -1
    sy = 1 if r0 < r1 else -1
    err = dx - dy
    c, r = c0, r0
    while True:
        cells.append((c, r))
        if c == c1 and r == r1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            c += sx
        if e2 < dx:
            err += dx
            r += sy
    return cells
