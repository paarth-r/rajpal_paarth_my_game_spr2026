'''
Main file responsible for game loop including input, update, and draw methods.
'''

import pygame as pg
import sys
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
        self.wall_img = pg.image.load(path.join(self.img_dir, 'wall_art.png')).convert_alpha()
        self.map = Map(path.join(self.game_dir, 'level1.txt'))

        self.map_img = pg.Surface((self.map.width, self.map.height))
        self.map_img.fill(FLOOR_COLOR)
        self.map_rect = self.map_img.get_rect()

    def is_walkable(self, col, row):
        """True if (col, row) is in bounds, not a wall, and not occupied by a mob or player (current or sliding-to)."""
        if row < 0 or row >= len(self.map.data):
            return False
        if col < 0 or col >= len(self.map.data[0]):
            return False
        if self.map.data[row][col] == '1':
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
        self.all_sprites = pg.sprite.Group()
        self.all_walls = pg.sprite.Group()
        self.all_mobs = pg.sprite.Group()
        self.all_drops = pg.sprite.Group()

        for row, tiles in enumerate(self.map.data):
            for col, tile in enumerate(tiles):
                if tile == '1':
                    Wall(self, col, row)
                if tile == 'P':
                    self.player = Player(self, col, row)
                if tile == 'M':
                    Mob(self, col, row)
                if tile == 'C':
                    Coin(self, col, row)

        self.camera = Camera(self.map.width, self.map.height)
        self.inventory = Inventory(INVENTORY_SLOTS, HOTBAR_SLOTS)
        self.inventory.add_item('gold_coin', 5)
        self.inventory.add_item('health_potion', 2)
        # Starting gear: gladius + legionnaire armor set (equip directly)
        self.inventory.equipment['weapon'] = 'gladius'
        self.inventory.equipment['head'] = 'legion_helm'
        self.inventory.equipment['chest'] = 'legion_cuirass'
        self.inventory.equipment['boots'] = 'legion_boots'
        self.inventory_open = False
        self.manual_target = None
        # Inventory UI state
        self.inv_slot_rects = []    # built each frame: list of (pg.Rect, source, index)
        self.inv_dragging = None    # (source, index, item_id, count) while dragging
        self.inv_drag_offset = (0, 0)
        self.inv_selected = None    # (source, index) for click-highlight
        self.state = 'intro'
        self.run()

    def run(self):
        while self.running:
            self.dt = self.clock.tick(FPS) / 1000
            self.events()
            if self.state == 'intro':
                self.draw_intro()
            else:
                if not self.inventory_open:
                    self.update()
                self.draw()

    def events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                if self.playing:
                    self.playing = False
                self.running = False
            if event.type == pg.KEYDOWN:
                if self.state == 'intro':
                    self.state = 'playing'
                    continue
                if self.state != 'playing':
                    continue
                if self.inventory_open:
                    if event.key in (INVENTORY_KEY, CHARACTER_KEY, pg.K_ESCAPE):
                        self.inventory_open = False
                    continue
                if event.key in (INVENTORY_KEY, CHARACTER_KEY):
                    self.inventory_open = True
                    continue
                if pg.K_1 <= event.key <= pg.K_8:
                    self.inventory.selected_hotbar_index = event.key - pg.K_1
                    continue
                if event.key == pg.K_SPACE:
                    self.player.attack()
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
                if self.state != 'playing' or self.inventory_open:
                    continue
                self._handle_click_target(event.pos)

    def quit(self):
        pass

    def update(self):
        self.all_sprites.update()
        # Keep manual target valid
        if self.manual_target is not None:
            if (not self.manual_target.alive()) or getattr(self.manual_target, 'state', None) == 'dead':
                self.manual_target = None
        # Player attack: auto-target one attackable entity within range (regardless of facing)
        if self.player.attacking and not self.player.attack_hit_dealt:
            px, py = self.player.hit_rect.centerx, self.player.hit_rect.centery
            best = None
            best_d_sq = PLAYER_ATTACK_RANGE * PLAYER_ATTACK_RANGE
            # Manual target overrides auto-target if it is valid and in range.
            if self.manual_target is not None:
                mx = self.manual_target.hit_rect.centerx
                my = self.manual_target.hit_rect.centery
                d_sq = (px - mx) ** 2 + (py - my) ** 2
                if d_sq <= best_d_sq:
                    best = self.manual_target
            if best is None:
                for mob in self.all_mobs:
                    if getattr(mob, 'state', None) == 'dead':
                        continue
                    mx = mob.hit_rect.centerx
                    my = mob.hit_rect.centery
                    d_sq = (px - mx) ** 2 + (py - my) ** 2
                    if d_sq <= best_d_sq:
                        best_d_sq = d_sq
                        best = mob
            if best is not None:
                best.hurt(self.player.get_effective_damage())
                self.player.attack_hit_dealt = True
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
        # Click-target selector: green if in attack range, red if out of range
        if self.manual_target is not None and self.manual_target.alive() and getattr(self.manual_target, 'state', None) != 'dead':
            target_rect = self.camera.apply(self.manual_target).inflate(8, 8)
            px, py = self.player.hit_rect.centerx, self.player.hit_rect.centery
            mx, my = self.manual_target.hit_rect.centerx, self.manual_target.hit_rect.centery
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
        self.display.blit(self.screen, (0, 0))
        pg.display.flip()

    def draw_intro(self):
        """Title screen: Relictus, tagline, prompt to start."""
        self.screen.fill(BGCOLOR)
        font_title = pg.font.Font(pg.font.match_font('arial'), INTRO_TITLE_SIZE)
        font_tag = pg.font.Font(pg.font.match_font('arial'), INTRO_TAGLINE_SIZE)
        font_prompt = pg.font.Font(pg.font.match_font('arial'), INTRO_PROMPT_SIZE)
        title_surf = font_title.render(TITLE, True, WHITE)
        tag_surf = font_tag.render(INTRO_TAGLINE, True, DARKGRAY)
        prompt_surf = font_prompt.render(INTRO_PROMPT, True, GOLD)
        title_rect = title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60))
        tag_rect = tag_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 10))
        prompt_rect = prompt_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 80))
        self.screen.blit(title_surf, title_rect)
        self.screen.blit(tag_surf, tag_rect)
        self.screen.blit(prompt_surf, prompt_rect)
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
                self.screen.blit(text, (x + SLOT_SIZE - text.get_width() - 2, y + SLOT_SIZE - text.get_height() - 2))
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
        hint = font.render("1-8 select  E / I inventory", True, DARKGRAY)
        self.screen.blit(hint, (start_x, y + SLOT_SIZE + 4))

    def draw_inventory(self):
        """Minecraft-style inventory: player preview + armor slots on left, stats below, inventory grid on right."""
        overlay = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        font_title = pg.font.Font(pg.font.match_font('arial'), 28)
        font = pg.font.Font(pg.font.match_font('arial'), HUD_FONT_SIZE)
        font_sm = pg.font.Font(pg.font.match_font('arial'), 14)

        panel_w = 680
        panel_h = 520
        panel_x = (WIDTH - panel_w) // 2
        panel_y = (HEIGHT - panel_h) // 2
        pg.draw.rect(self.screen, (30, 30, 30), (panel_x, panel_y, panel_w, panel_h))
        pg.draw.rect(self.screen, GOLD, (panel_x, panel_y, panel_w, panel_h), 2)

        close_hint = font_sm.render("E / I / Esc to close", True, GOLD)
        self.screen.blit(close_hint, (panel_x + panel_w - close_hint.get_width() - 12, panel_y + 8))

        # --- LEFT SIDE: player preview, armor slots, stats ---
        left_x = panel_x + 20
        cy = panel_y + 16

        # Player preview (large sprite)
        preview_size = 96
        player_img = self.player.move_frames.get(self.player.facing, [None])[0]
        if player_img:
            preview = pg.transform.scale(player_img, (preview_size, preview_size))
            preview_rect = pg.Rect(left_x + 10, cy, preview_size, preview_size)
            pg.draw.rect(self.screen, SLOT_BG, preview_rect.inflate(8, 8))
            pg.draw.rect(self.screen, SLOT_BORDER, preview_rect.inflate(8, 8), 2)
            self.screen.blit(preview, preview_rect)

        # Armor slots to the right of preview
        eq_x = left_x + preview_size + 30
        eq_y = cy
        eq_slot_size = SLOT_SIZE
        eq_label_map = {
            'head': 'Head',
            'chest': 'Chest',
            'boots': 'Boots',
            'shield': 'Shield',
            'weapon': 'Weapon',
        }
        eq_order = ['head', 'chest', 'boots', 'shield', 'weapon']
        for eq_slot in eq_order:
            item_id = self.inventory.equipment.get(eq_slot)
            slot_data = (item_id, 1) if item_id else None
            self.draw_slot(eq_x, eq_y, slot_data)
            label = font_sm.render(eq_label_map[eq_slot], True, DARKGRAY)
            self.screen.blit(label, (eq_x + eq_slot_size + 6, eq_y + eq_slot_size // 2 - label.get_height() // 2))
            if item_id:
                item_def = ITEM_DEFS.get(item_id, {})
                name_surf = font_sm.render(item_def.get('name', item_id), True, WHITE)
                self.screen.blit(name_surf, (eq_x + eq_slot_size + 60, eq_y + eq_slot_size // 2 - name_surf.get_height() // 2))
            eq_y += eq_slot_size + 4

        # Stats below player preview + armor
        stats_y = cy + preview_size + 20
        section = font.render("Stats", True, GOLD)
        self.screen.blit(section, (left_x, stats_y))
        stats_y += 26

        attrs = self.player.get_effective_attrs()
        bonuses = self.inventory.get_equipment_stat_bonuses()
        stat_order = ['strength', 'dexterity', 'intelligence', 'health']
        for stat in stat_order:
            base_val = self.player.base_attrs.get(stat, 0)
            total_val = attrs.get(stat, 0)
            b = bonuses.get(stat, 0)
            bonus_str = ""
            if b > 0:
                bonus_str = f"  (+{b})"
            line = font_sm.render(f"{stat.capitalize()}: {total_val}{bonus_str}", True, WHITE)
            self.screen.blit(line, (left_x + 8, stats_y))
            stats_y += 20
        stats_y += 8

        # Derived stats
        eff_max = self.player.get_effective_max_health()
        hp_line = font_sm.render(f"HP: {self.player.health} / {eff_max}", True, WHITE)
        self.screen.blit(hp_line, (left_x + 8, stats_y))
        stats_y += 20
        dmg = self.player.get_effective_damage()
        dmg_line = font_sm.render(f"Damage: {dmg}", True, WHITE)
        self.screen.blit(dmg_line, (left_x + 8, stats_y))
        stats_y += 20
        defense = self.inventory.get_total_defense()
        def_line = font_sm.render(f"Defense: {defense}", True, WHITE)
        self.screen.blit(def_line, (left_x + 8, stats_y))

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
                selected = idx < HOTBAR_SLOTS and idx == self.inventory.selected_hotbar_index
                self.draw_slot(sx, sy, slot_data, selected=selected)

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


if __name__ == "__main__":
    g = Game()
    while g.running:
        g.new()
    pg.quit()
