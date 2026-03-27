import math
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


def key_checkerboard_placeholder(surf):
    """Turn baked-in checkerboard fills into real transparency.

    Some PNGs use opaque dark grays (common export pattern) instead of an alpha channel.
    Mutates surf in place; surf must be per-pixel alpha (e.g. convert_alpha()).
    """
    rgb = pg.surfarray.array3d(surf)
    mask = ((rgb[:, :, 0] == 20) & (rgb[:, :, 1] == 20) & (rgb[:, :, 2] == 20)) | (
        (rgb[:, :, 0] == 30) & (rgb[:, :, 1] == 30) & (rgb[:, :, 2] == 30)
    )
    alpha = pg.surfarray.pixels_alpha(surf)
    alpha[mask] = 0
    del alpha
    return surf


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


def draw_corner_brackets(screen, rect, color, corner_len=10, thickness=2, inset=2):
    """Small L-shaped corners around a screen rect (status FX frame)."""
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    x0, y0 = x + inset, y + inset
    x1, y1 = x + w - inset, y + h - inset
    L = max(4, min(corner_len, w // 2 - 2, h // 2 - 2))
    pg.draw.line(screen, color, (x0, y0), (x0 + L, y0), thickness)
    pg.draw.line(screen, color, (x0, y0), (x0, y0 + L), thickness)
    pg.draw.line(screen, color, (x1, y0), (x1 - L, y0), thickness)
    pg.draw.line(screen, color, (x1, y0), (x1, y0 + L), thickness)
    pg.draw.line(screen, color, (x0, y1), (x0 + L, y1), thickness)
    pg.draw.line(screen, color, (x0, y1), (x0, y1 - L), thickness)
    pg.draw.line(screen, color, (x1, y1), (x1 - L, y1), thickness)
    pg.draw.line(screen, color, (x1, y1), (x1, y1 - L), thickness)


def draw_lightning_bolt(screen, p0, p1, color, width=2):
    """Jagged lightning polyline between two screen-space points."""
    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy) or 1.0
    n = max(4, int(dist / 14))
    pts = [(x0, y0)]
    for i in range(1, n):
        t = i / n
        bx = x0 + dx * t
        by = y0 + dy * t
        ox = -dy / dist * (7 + 5 * math.sin(i * 0.9 + x0 * 0.03))
        oy = dx / dist * (7 + 5 * math.sin(i * 0.9 + x0 * 0.03))
        pts.append((round(bx + ox), round(by + oy)))
    pts.append((x1, y1))
    core = (255, 250, 200)
    for i in range(len(pts) - 1):
        pg.draw.line(screen, color, pts[i], pts[i + 1], width + 1)
        pg.draw.line(screen, core, pts[i], pts[i + 1], max(1, width - 1))
