#!/usr/bin/env python3
"""
Standalone tile map editor for levels/*.txt (same format as utils.Map / game.systems.world_ops).

Controls:
  1-8          Select hotbar slot (tile mode: terrain/specials; mob mode: spawn types)
  E            Toggle tile mode / mob placement mode
  LMB / hold   Paint selected tile or mob spawn (M/A)
  RMB / hold   Remove (floor '.')
  Space        Zoom in (centered on mouse)
  Shift        Zoom out (centered on mouse)
  Arrows/WASD  Pan camera
  Ctrl+S       Save current file
  Ctrl+O       Open next level in levels/ folder (wrap)
  Ctrl+Shift+O Open previous level
  F2           New map (bordered empty room; Ctrl+S picks editor_new_XXX.txt if new)
  Esc          Quit
"""
from __future__ import annotations

import json
import os
import sys
from os import path

import pygame as pg

from settings import (
    BGCOLOR,
    FLOOR_COLOR,
    GOLD,
    GRID_COLOR,
    HEIGHT,
    HUD_PADDING,
    SLOT_GAP,
    SLOT_SIZE,
    TILESIZE,
    TITLE,
    WHITE,
    WIDTH,
)
from utils import Map

EDITOR_HOTBAR_SLOTS = 8

# Tile hotbar: chars understood by load_level (mobs M/A only in mob mode hotbar).
TILE_PALETTE: list[tuple[str, str]] = [
    (".", "Floor"),
    ("1", "Wall"),
    ("2", "Floor alt"),
    ("P", "Player spawn"),
    ("K", "Checkpoint"),
    ("N", "Exit"),
    ("R", "Return"),
    (" ", "Erase→floor"),  # writes '.' (space is only UI label)
]

# Mob mode: (mob_type_id, map_char, label) — must match world_ops.load_level
MOB_SPAWN_PALETTE: list[tuple[str, str, str]] = [
    ("statue", "M", "Stone sentinel"),
    ("shadow_assassin", "A", "Shadow assassin"),
    ("ghost", "G", "Spectral stalker"),
]


def _game_root() -> str:
    return path.dirname(path.abspath(__file__))


def _levels_dir() -> str:
    return path.join(_game_root(), "levels")


def _load_mob_names() -> dict[str, str]:
    fp = path.join(_game_root(), "data", "mobs.json")
    try:
        with open(fp, "r") as f:
            raw = json.load(f)
        return {k: v.get("name", k) for k, v in raw.items() if isinstance(v, dict)}
    except OSError:
        return {}


def new_bordered_map(cols: int = 42, rows: int = 24) -> list[str]:
    """Rectangle of walkable floor with wall border."""
    cols = max(8, cols)
    rows = max(8, rows)
    inner = "." * (cols - 2)
    lines = ["1" * cols]
    for _ in range(rows - 2):
        lines.append("1" + inner + "1")
    lines.append("1" * cols)
    return lines


def load_level_lines(fp: str) -> list[str]:
    m = Map(fp)
    return [row[:] for row in m.data]


def save_level_lines(fp: str, lines: list[str]) -> None:
    if not lines:
        return
    w = len(lines[0])
    with open(fp, "w") as f:
        for row in lines:
            if len(row) != w:
                raise ValueError("All rows must have the same width")
            f.write(row + "\n")


class LevelEditor:
    def __init__(self, start_file: str | None = None):
        pg.init()
        pg.display.set_caption(f"{TITLE} — Level editor")
        self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        self.clock = pg.time.Clock()
        self.running = True

        self.levels_dir = _levels_dir()
        self.wall_img = pg.image.load(path.join(_game_root(), "images", "wall_art.png")).convert_alpha()

        self.lines: list[str] = new_bordered_map()
        self.current_path: str | None = None
        self._dirty = False

        self.mode = "tiles"  # 'tiles' | 'mobs'
        self.hotbar_index = 0
        self.zoom = 3.0
        self.cam_x = 0.0
        self.cam_y = 0.0

        self._paint_last: tuple[int, int, int] | None = None
        self._paint_buttons: set[int] = set()

        self.mob_display_names = _load_mob_names()
        self.status_msg = ""
        self.status_until_ms = 0

        self._level_files = self._scan_levels()
        if start_file:
            ap = path.abspath(start_file)
            if path.isfile(ap):
                self._open_path(ap)
            elif path.isfile(path.join(self.levels_dir, start_file)):
                self._open_path(path.join(self.levels_dir, start_file))

        self._center_camera_on_map()

    def _scan_levels(self) -> list[str]:
        try:
            names = sorted(f for f in os.listdir(self.levels_dir) if f.endswith(".txt"))
        except OSError:
            names = []
        return [path.join(self.levels_dir, n) for n in names]

    def _open_path(self, fp: str) -> None:
        try:
            self.lines = load_level_lines(fp)
            self.current_path = fp
            self._dirty = False
            self._set_status(f"Opened {path.basename(fp)}")
            self._center_camera_on_map()
        except (OSError, ValueError, IndexError) as e:
            self._set_status(f"Open failed: {e}")

    def _center_camera_on_map(self) -> None:
        if not self.lines:
            return
        mw = len(self.lines[0]) * TILESIZE
        mh = len(self.lines) * TILESIZE
        vw = WIDTH / self.zoom
        vh = HEIGHT / self.zoom
        self.cam_x = max(0, (mw - vw) / 2)
        self.cam_y = max(0, (mh - vh) / 2)

    def _set_status(self, msg: str, ms: int = 2500) -> None:
        self.status_msg = msg
        self.status_until_ms = pg.time.get_ticks() + ms

    @property
    def map_w(self) -> int:
        return len(self.lines[0]) * TILESIZE if self.lines else 0

    @property
    def map_h(self) -> int:
        return len(self.lines) * TILESIZE if self.lines else 0

    def _paint_char(self) -> str:
        if self.mode == "tiles":
            ch, _ = TILE_PALETTE[self.hotbar_index % len(TILE_PALETTE)]
            return "." if ch == " " else ch
        _tid, ch, _ = MOB_SPAWN_PALETTE[self.hotbar_index % len(MOB_SPAWN_PALETTE)]
        return ch

    def _screen_to_world(self, mx: int, my: int) -> tuple[float, float]:
        return self.cam_x + mx / self.zoom, self.cam_y + my / self.zoom

    def _world_to_tile(self, wx: float, wy: float) -> tuple[int, int]:
        return int(wx // TILESIZE), int(wy // TILESIZE)

    def _zoom_at_mouse(self, mx: int, my: int, factor: float) -> None:
        wx, wy = self._screen_to_world(mx, my)
        new_z = max(0.35, min(12.0, self.zoom * factor))
        self.cam_x = wx - mx / new_z
        self.cam_y = wy - my / new_z
        self.zoom = new_z
        self._clamp_camera()

    def _clamp_camera(self) -> None:
        vw = WIDTH / self.zoom
        vh = HEIGHT / self.zoom
        max_x = max(0.0, self.map_w - vw)
        max_y = max(0.0, self.map_h - vh)
        self.cam_x = max(0.0, min(max_x, self.cam_x))
        self.cam_y = max(0.0, min(max_y, self.cam_y))

    def _set_cell(self, col: int, row: int, ch: str) -> None:
        if not self.lines or row < 0 or row >= len(self.lines):
            return
        row_s = self.lines[row]
        if col < 0 or col >= len(row_s):
            return
        if row_s[col] == ch:
            return
        self.lines[row] = row_s[:col] + ch + row_s[col + 1 :]
        self._dirty = True

    def _apply_paint(self, col: int, row: int, button: int) -> None:
        key = (col, row, button)
        if self._paint_last == key:
            return
        self._paint_last = key
        if button == 1:
            self._set_cell(col, row, self._paint_char())
        elif button == 3:
            self._set_cell(col, row, ".")

    def _handle_mouse_tile(self, mx: int, my: int) -> None:
        wx, wy = self._screen_to_world(mx, my)
        col, row = self._world_to_tile(wx, wy)
        for b in (1, 3):
            if b in self._paint_buttons:
                self._apply_paint(col, row, b)

    def save(self) -> None:
        if not self.current_path:
            # Default untitled name
            n = 1
            while True:
                cand = path.join(self.levels_dir, f"editor_new_{n:03d}.txt")
                if not path.isfile(cand):
                    self.current_path = cand
                    break
                n += 1
        try:
            os.makedirs(self.levels_dir, exist_ok=True)
            save_level_lines(self.current_path, self.lines)
            self._dirty = False
            self._set_status(f"Saved {path.basename(self.current_path)}")
            self._level_files = self._scan_levels()
        except OSError as e:
            self._set_status(f"Save failed: {e}")

    def _cycle_open(self, delta: int) -> None:
        if not self._level_files:
            self._set_status("No .txt files in levels/")
            return
        if self.current_path in self._level_files:
            i = self._level_files.index(self.current_path)
        else:
            i = 0
        i = (i + delta) % len(self._level_files)
        self._open_path(self._level_files[i])

    def new_map(self) -> None:
        self.lines = new_bordered_map()
        self.current_path = None
        self._dirty = True
        self._set_status("New map (Ctrl+S saves as editor_new_XXX.txt)")
        self._center_camera_on_map()

    def _draw_tile_world(self, surf: pg.Surface, col: int, row: int, ch: str) -> None:
        x = col * TILESIZE
        y = row * TILESIZE
        rect = pg.Rect(x, y, TILESIZE, TILESIZE)
        if ch == "1":
            scaled = pg.transform.scale(self.wall_img, (TILESIZE, TILESIZE))
            surf.blit(scaled, rect.topleft)
            return
        if ch == "2":
            surf.fill((75, 82, 78), rect)
        else:
            surf.fill(FLOOR_COLOR, rect)
        if ch == "P":
            pg.draw.circle(surf, (90, 170, 255), rect.center, TILESIZE // 3)
        elif ch == "K":
            pg.draw.rect(surf, (50, 200, 100), rect.inflate(-6, -6))
        elif ch == "N":
            pg.draw.rect(surf, (160, 70, 210), rect.inflate(-4, -4))
        elif ch == "R":
            pg.draw.rect(surf, (45, 190, 190), rect.inflate(-4, -4))
        elif ch == "M":
            pg.draw.circle(surf, (200, 200, 80), rect.center, TILESIZE // 4)
            pg.draw.circle(surf, (40, 40, 40), rect.center, TILESIZE // 6)
        elif ch == "A":
            pg.draw.polygon(surf, (120, 80, 160), [
                (rect.centerx, rect.top + 4),
                (rect.right - 5, rect.bottom - 5),
                (rect.left + 5, rect.bottom - 5),
            ])
        elif ch == "G":
            pg.draw.circle(surf, (140, 220, 255), rect.center, TILESIZE // 3)
            pg.draw.circle(surf, (80, 140, 200), rect.center, TILESIZE // 5)

    def _brush_char_for_slot(self, slot_i: int) -> str | None:
        """Character preview for hotbar slot index, or None if slot unused (mob mode)."""
        if self.mode == "tiles":
            if 0 <= slot_i < len(TILE_PALETTE):
                ch, _ = TILE_PALETTE[slot_i]
                return "." if ch == " " else ch
            return None
        if slot_i < len(MOB_SPAWN_PALETTE):
            return MOB_SPAWN_PALETTE[slot_i][1]
        return None

    def _draw_brush_preview_in_rect(self, rect: pg.Rect, ch: str) -> None:
        """Fill inner tile preview (screen coords)."""
        if ch == "1":
            scaled = pg.transform.scale(self.wall_img, (rect.width, rect.height))
            self.screen.blit(scaled, rect.topleft)
            return
        if ch == "2":
            pg.draw.rect(self.screen, (75, 82, 78), rect)
            return
        pg.draw.rect(self.screen, FLOOR_COLOR, rect)
        if ch == "P":
            pg.draw.circle(self.screen, (90, 170, 255), rect.center, min(rect.w, rect.h) // 3)
        elif ch == "K":
            pg.draw.rect(self.screen, (50, 200, 100), rect.inflate(-4, -4))
        elif ch == "N":
            pg.draw.rect(self.screen, (160, 70, 210), rect.inflate(-3, -3))
        elif ch == "R":
            pg.draw.rect(self.screen, (45, 190, 190), rect.inflate(-3, -3))
        elif ch == "M":
            pg.draw.circle(self.screen, (200, 200, 80), rect.center, min(rect.w, rect.h) // 4)
            pg.draw.circle(self.screen, (40, 40, 40), rect.center, min(rect.w, rect.h) // 6)
        elif ch == "A":
            pg.draw.polygon(self.screen, (120, 80, 160), [
                (rect.centerx, rect.top + 2),
                (rect.right - 3, rect.bottom - 3),
                (rect.left + 3, rect.bottom - 3),
            ])
        elif ch == "G":
            pg.draw.circle(self.screen, (140, 220, 255), rect.center, min(rect.w, rect.h) // 3)
            pg.draw.circle(self.screen, (80, 140, 200), rect.center, min(rect.w, rect.h) // 5)
        elif ch == ".":
            pg.draw.rect(self.screen, (55, 58, 62), rect.inflate(-6, -6))

    def _draw_slot_hotbar(self, slots_top: int) -> None:
        font_key = pg.font.Font(pg.font.match_font("arial"), 13)
        font_lbl = pg.font.Font(pg.font.match_font("arial"), 11)
        total_w = EDITOR_HOTBAR_SLOTS * SLOT_SIZE + (EDITOR_HOTBAR_SLOTS - 1) * SLOT_GAP
        start_x = (WIDTH - total_w) // 2
        n_sel = len(TILE_PALETTE) if self.mode == "tiles" else len(MOB_SPAWN_PALETTE)
        idx_mod = self.hotbar_index % n_sel

        for i in range(EDITOR_HOTBAR_SLOTS):
            x = start_x + i * (SLOT_SIZE + SLOT_GAP)
            rect = pg.Rect(x, slots_top, SLOT_SIZE, SLOT_SIZE)
            ch = self._brush_char_for_slot(i)
            dimmed = self.mode == "mobs" and i >= len(MOB_SPAWN_PALETTE)
            if self.mode == "tiles":
                selected = i == (self.hotbar_index % len(TILE_PALETTE))
            else:
                selected = i < n_sel and idx_mod == i

            border_col = GOLD if selected else (72, 74, 92)
            border_w = 3 if selected else 2
            pg.draw.rect(self.screen, (32, 34, 44), rect)
            inner = rect.inflate(-8, -8)
            if ch is not None:
                self._draw_brush_preview_in_rect(inner, ch)
            else:
                pg.draw.rect(self.screen, (24, 25, 30), inner)
            if dimmed:
                veil = pg.Surface((rect.width, rect.height), pg.SRCALPHA)
                veil.fill((0, 0, 0, 100))
                self.screen.blit(veil, rect.topleft)
            pg.draw.rect(self.screen, border_col, rect, border_w)
            key_s = font_key.render(str(i + 1), True, (160, 162, 180))
            self.screen.blit(key_s, (rect.x + 4, rect.bottom - key_s.get_height() - 2))
            if ch is not None and not dimmed:
                disp = "." if ch == " " else ch
                t = font_lbl.render(disp, True, WHITE)
                self.screen.blit(t, (rect.centerx - t.get_width() // 2, rect.y + 3))

        title = "Tile brushes (keys 1-8)" if self.mode == "tiles" else "Mob spawns (keys 1-3: M / A / G)"
        tf = pg.font.Font(pg.font.match_font("arial"), 15)
        ts = tf.render(title, True, (230, 230, 235))
        self.screen.blit(ts, (start_x, slots_top - 22))

    def draw(self) -> None:
        vw = max(1, int(WIDTH / self.zoom))
        vh = max(1, int(HEIGHT / self.zoom))
        view = pg.Surface((vw, vh))
        view.fill(BGCOLOR)

        if self.lines:
            c0 = int(self.cam_x // TILESIZE)
            r0 = int(self.cam_y // TILESIZE)
            c1 = int((self.cam_x + vw) // TILESIZE) + 1
            r1 = int((self.cam_y + vh) // TILESIZE) + 1
            for r in range(max(0, r0), min(len(self.lines), r1)):
                row_s = self.lines[r]
                for c in range(max(0, c0), min(len(row_s), c1)):
                    self._draw_tile_world(view, c, r, row_s[c])

            for wx in range(0, self.map_w + 1, TILESIZE):
                sx = int(wx - self.cam_x)
                if 0 <= sx <= vw:
                    pg.draw.line(view, GRID_COLOR, (sx, 0), (sx, vh))
            for wy in range(0, self.map_h + 1, TILESIZE):
                sy = int(wy - self.cam_y)
                if 0 <= sy <= vh:
                    pg.draw.line(view, GRID_COLOR, (0, sy), (vw, sy))

        scaled = pg.transform.scale(view, (WIDTH, HEIGHT))
        self.screen.blit(scaled, (0, 0))

        # Bottom UI strip (hotbar + hints) so brushes are always visible like the main game.
        panel_h = SLOT_SIZE + 88
        panel_top = HEIGHT - panel_h
        bar = pg.Surface((WIDTH, panel_h), pg.SRCALPHA)
        bar.fill((16, 18, 26, 248))
        self.screen.blit(bar, (0, panel_top))

        # Top-left file / mode (readable over map).
        info = pg.Surface((min(520, WIDTH - 16), 52), pg.SRCALPHA)
        info.fill((16, 18, 26, 236))
        self.screen.blit(info, (8, 8))
        font = pg.font.Font(pg.font.match_font("arial"), 16)
        font_sm = pg.font.Font(pg.font.match_font("arial"), 14)
        mode_txt = "Tiles" if self.mode == "tiles" else "Mob spawns"
        hdr = font.render(
            f"{mode_txt}  |  {path.basename(self.current_path) if self.current_path else '(new map)'}",
            True,
            (240, 240, 240),
        )
        self.screen.blit(hdr, (16, 14))
        if self.mode == "tiles":
            _ch, lbl = TILE_PALETTE[self.hotbar_index % len(TILE_PALETTE)]
            sub = font_sm.render(lbl, True, (180, 185, 200))
        else:
            tid, _c, short = MOB_SPAWN_PALETTE[self.hotbar_index % len(MOB_SPAWN_PALETTE)]
            name = self.mob_display_names.get(tid, short)
            sub = font_sm.render(name, True, (180, 185, 200))
        self.screen.blit(sub, (16, 36))

        hotbar_y = panel_top + 28
        self._draw_slot_hotbar(hotbar_y)

        help_lines = [
            "LMB paint  RMB clear  |  E: tiles / mobs  |  Space / Shift: zoom at cursor  |  Arrows / WASD: pan",
            "Ctrl+S save  Ctrl+O / Ctrl+Shift+O cycle levels  F2 new map  Esc quit",
        ]
        hy = panel_top + SLOT_SIZE + 38
        for hl in help_lines:
            self.screen.blit(font_sm.render(hl, True, (150, 152, 168)), (HUD_PADDING, hy))
            hy += 18

        if pg.time.get_ticks() < self.status_until_ms and self.status_msg:
            st = font_sm.render(self.status_msg, True, (120, 255, 140))
            self.screen.blit(st, (WIDTH // 2 - st.get_width() // 2, panel_top + 6))

        if self._dirty:
            self.screen.blit(font_sm.render("* unsaved", True, (255, 180, 80)), (WIDTH - 120, 12))

        pg.display.flip()

    def run(self) -> None:
        pg.key.set_repeat(280, 45)

        while self.running:
            self.clock.tick(60)
            mx, my = pg.mouse.get_pos()

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.running = False
                elif event.type == pg.KEYDOWN:
                    mods = pg.key.get_mods()
                    ctrl = mods & pg.KMOD_CTRL
                    shift_mod = mods & pg.KMOD_SHIFT

                    if event.key == pg.K_ESCAPE:
                        self.running = False
                    elif ctrl and event.key == pg.K_s:
                        self.save()
                    elif ctrl and event.key == pg.K_o:
                        self._cycle_open(-1 if shift_mod else 1)
                    elif event.key == pg.K_F2:
                        self.new_map()
                    elif event.key == pg.K_e:
                        self.mode = "mobs" if self.mode == "tiles" else "tiles"
                        self.hotbar_index = 0
                        self._set_status(f"Mode: {'Mob spawns' if self.mode == 'mobs' else 'Tiles'}")
                    elif event.key == pg.K_SPACE:
                        self._zoom_at_mouse(mx, my, 1.12)
                    elif event.key in (pg.K_LSHIFT, pg.K_RSHIFT):
                        self._zoom_at_mouse(mx, my, 1 / 1.12)
                    elif pg.K_1 <= event.key <= pg.K_8:
                        self.hotbar_index = event.key - pg.K_1
                        n = len(TILE_PALETTE) if self.mode == "tiles" else len(MOB_SPAWN_PALETTE)
                        self.hotbar_index %= n
                    elif event.key in (pg.K_LEFT, pg.K_a):
                        self.cam_x = max(0.0, self.cam_x - 32 / self.zoom)
                    elif event.key in (pg.K_RIGHT, pg.K_d):
                        self.cam_x = min(max(0.0, self.map_w - WIDTH / self.zoom), self.cam_x + 32 / self.zoom)
                    elif event.key in (pg.K_UP, pg.K_w):
                        self.cam_y = max(0.0, self.cam_y - 32 / self.zoom)
                    elif event.key in (pg.K_DOWN, pg.K_s):
                        if not ctrl:
                            self.cam_y = min(max(0.0, self.map_h - HEIGHT / self.zoom), self.cam_y + 32 / self.zoom)

                elif event.type == pg.MOUSEBUTTONDOWN:
                    if event.button in (1, 3):
                        self._paint_buttons.add(event.button)
                        self._paint_last = None
                        self._handle_mouse_tile(event.pos[0], event.pos[1])
                elif event.type == pg.MOUSEBUTTONUP:
                    if event.button in (1, 3):
                        self._paint_buttons.discard(event.button)
                    if not self._paint_buttons:
                        self._paint_last = None
                elif event.type == pg.MOUSEMOTION:
                    if self._paint_buttons:
                        self._handle_mouse_tile(event.pos[0], event.pos[1])

            self.draw()

        pg.quit()


def main() -> None:
    start = sys.argv[1] if len(sys.argv) > 1 else None
    LevelEditor(start_file=start).run()


if __name__ == "__main__":
    main()
