'''
Main file responsible for game loop including input, update, and draw methods.
'''



import pygame as pg
import random
import subprocess
import sys
import json
import os
import math
from collections import deque
from os import path
from settings import *
from sprites import *
from utils import *
from crafting import (
    RECIPES,
    WEAPON_TYPES,
    can_infuse_weapon,
    default_starts_known_recipe_ids,
    get_recipe_list,
    normalize_craft_placement,
    recipes_unlocked_by_item,
    recipe_slot_quantity,
    try_finish_craft,
    try_finish_infusion,
)
from inventory import Inventory, ITEM_DEFS, EQUIPMENT_SLOTS, pack_slot, unpack_slot, weapon_cooldown_ms_for_item
from weapons import format_on_hit_effect_tooltip, resolve_on_hit_effect
from progression import (
    CLASS_DEFS,
    DEFAULT_CLASS_ID,
    apply_skill_node_bonuses,
    can_unlock_skill,
    compute_base_attrs_for_level,
    get_class_def,
    xp_for_next_level,
)
from game.systems import intro_ops
from game.systems import progression_ops as progression_system
from game.systems import player_shop as player_shop_system
from game.systems import save_ops as save_system
from game.systems import world_ops as world_system

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
        self.level_order = [
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
        self.init_save_system()
        self._load_world_state_from_save()
        self.load_level(self.current_level_name, create_player=True)
        self._item_sprite_cache = {}

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

    def tile_blocks_line_of_sight(self, col, row):
        """Terrain that blocks mob↔player sight (walls, closed exit gate)."""
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
        """True if a straight tile line from (c0,r0) to (c1,r1) has no blocking terrain."""
        for c, r in tiles_on_grid_line(c0, r0, c1, r1):
            if self.tile_blocks_line_of_sight(c, r):
                return False
        return True

    def new(self):
        self.player_class_id = DEFAULT_CLASS_ID
        self.player_level = 1
        self.player_xp = 0
        self.skill_points = 0
        self.purchased_skill_nodes = set()
        self.load_data()
        self._initialize_player_inventory()
        self.inventory_open = False
        self.manual_target = None
        # Inventory UI state
        self.inv_slot_rects = []    # built each frame: list of (pg.Rect, source, index)
        self.inv_dragging = None    # (source, index, item_id, count[, meta_dict]) while dragging
        self.inv_drag_offset = (0, 0)
        self.inv_selected = None    # (source, index) for click-highlight
        self.inventory_tab = 'character'  # 'character' | 'skills' | 'craft' | 'upgrade' | 'shop'
        self.stats_dropdown_open = False
        self.craft_selected_recipe_id = None
        self.pause_menu_open = False
        self.pause_save_btn_rect = None
        self.pause_quit_title_btn_rect = None
        self.pause_resume_btn_rect = None
        self.title_start_btn_rect = None
        self.title_new_world_btn_rect = None
        self.title_choose_save_btn_rect = None
        self.title_quit_btn_rect = None
        self.save_picker_open = False
        self.save_picker_slot_rects = []
        self.save_picker_delete_rects = []
        self.respawn_button_rect = None
        self.class_picker_for_new_world = False
        self.class_picker_selected_id = DEFAULT_CLASS_ID
        self.class_picker_class_rects = []
        self.class_picker_begin_rect = None
        self.skill_node_rects = []
        self.skill_tree_page = 0
        self.damage_numbers = []
        self.chain_lightning_fx = []
        self.death_screen_coins_lost = 0
        self.death_screen_xp_lost = 0
        self.state = 'intro'
        self.run()

    # save/world/progression methods were extracted to game.systems modules.

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
                    if event.key == pg.K_ESCAPE:
                        if self.class_picker_for_new_world:
                            self.class_picker_for_new_world = False
                            continue
                        if self.save_picker_open:
                            self.save_picker_open = False
                            continue
                    if event.key == pg.K_RETURN:
                        if self.class_picker_for_new_world:
                            self.create_new_world(self.class_picker_selected_id)
                            continue
                        self.state = 'playing'
                    if event.key == pg.K_n:
                        self.class_picker_for_new_world = True
                        self.class_picker_selected_id = DEFAULT_CLASS_ID
                    if event.key == pg.K_s:
                        self.save_picker_open = not self.save_picker_open
                    if (
                        event.key == pg.K_l
                        and not self.save_picker_open
                        and not self.class_picker_for_new_world
                    ):
                        editor = path.join(self.game_dir, "level_editor.py")
                        if path.isfile(editor):
                            subprocess.Popen([sys.executable, editor], cwd=self.game_dir)
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
                        self.inventory.return_craft_staging()
                        self.inventory.return_upgrade_staging()
                        self.inventory_open = False
                        self.inv_dragging = None
                        self.inv_selected = None
                    continue
                if self.pause_menu_open:
                    continue
                if self.inventory_open:
                    if event.key in (INVENTORY_KEY, CHARACTER_KEY, pg.K_ESCAPE):
                        self.inventory.return_craft_staging()
                        self.inventory.return_upgrade_staging()
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
                if event.key == pg.K_g:
                    self.try_interact_chest()
                if event.key == pg.K_DELETE or event.key == pg.K_BACKSPACE:
                    self.player.clear_move_queue()
                # Hold keys to queue moves (path preview); executes at speed
                if event.key in (pg.K_w, pg.K_UP):
                    self.player.queue_move(0, -1)
                if event.key in (pg.K_s, pg.K_DOWN):
                    self.player.queue_move(0, 1)
                if event.key in (pg.K_a, pg.K_LEFT):
                    self.player.queue_move(-1, 0)
                if event.key in (pg.K_d, pg.K_RIGHT):
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
                    if self.class_picker_for_new_world:
                        hit = False
                        for rect, cid in self.class_picker_class_rects:
                            if rect.collidepoint(event.pos):
                                self.class_picker_selected_id = cid
                                hit = True
                                break
                        if self.class_picker_begin_rect and self.class_picker_begin_rect.collidepoint(event.pos):
                            self.create_new_world(self.class_picker_selected_id)
                            hit = True
                        if not hit:
                            self.class_picker_for_new_world = False
                        continue
                    if self.save_picker_open:
                        hit = False
                        for rect, save_name in self.save_picker_delete_rects:
                            if rect.collidepoint(event.pos):
                                self.delete_save(save_name)
                                hit = True
                                break
                        if not hit:
                            for rect, save_name in self.save_picker_slot_rects:
                                if rect.collidepoint(event.pos):
                                    self.select_world(save_name)
                                    hit = True
                                    break
                        if not hit:
                            self.save_picker_open = False
                        continue
                    if self.title_start_btn_rect and self.title_start_btn_rect.collidepoint(event.pos):
                        self.state = 'playing'
                    elif self.title_new_world_btn_rect and self.title_new_world_btn_rect.collidepoint(event.pos):
                        self.class_picker_for_new_world = True
                        self.class_picker_selected_id = DEFAULT_CLASS_ID
                    elif self.title_choose_save_btn_rect and self.title_choose_save_btn_rect.collidepoint(event.pos):
                        self.save_picker_open = True
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
                        self.inventory.return_craft_staging()
                        self.inventory.return_upgrade_staging()
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

    # save/inventory sync methods extracted to game.systems.save_ops

    def add_damage_number(self, world_pos, amount, color=(255, 60, 60)):
        """Queue a floating number in world space (red damage, green heal, orange burn DoT)."""
        amt = int(max(1, round(float(amount))))
        self.damage_numbers.append({
            'pos': vec(world_pos[0], world_pos[1] - TILESIZE * 0.45),
            'amount': amt,
            'color': color,
            'life_ms': 1000,
            'age_ms': 0,
        })

    def update(self):
        self.all_sprites.update()
        dt_ms = int(self.dt * 1000)
        live = []
        for dn in self.damage_numbers:
            dn['age_ms'] += dt_ms
            dn['pos'].y -= 24 * self.dt
            if dn['age_ms'] < dn['life_ms']:
                live.append(dn)
        self.damage_numbers = live
        if self.chain_lightning_fx:
            live_fx = []
            for fx in self.chain_lightning_fx:
                fx['age_ms'] = fx.get('age_ms', 0) + dt_ms
                if fx['age_ms'] < fx['life_ms']:
                    live_fx.append(fx)
            self.chain_lightning_fx = live_fx
        if self.player.health <= 0:
            self._apply_death_penalties()
            self.state = 'death'
            self.inventory.return_craft_staging()
            self.inventory.return_upgrade_staging()
            self.inventory_open = False
            self.inv_dragging = None
            self.inv_selected = None
            return
        live_mobs = [m for m in self.all_mobs if getattr(m, 'state', None) != 'dead' and m.health > 0]
        if intro_ops.is_intro_level(self):
            intro_ops.refresh_intro_exit_open(self)
        elif not self.level_exit_open and len(live_mobs) == 0:
            self.level_exit_open = True
        # Keep manual target valid
        if self.manual_target is not None:
            if (not self.manual_target.alive()) or getattr(self.manual_target, 'state', None) == 'dead':
                self.manual_target = None
        # Player attack: direct melee hit or projectile launch, depending on weapon type.
        if self.player.attacking and not self.player.attack_hit_dealt:
            best = self._get_best_attack_target()
            if self.player.is_ranged_weapon():
                if best is not None:
                    self._spawn_player_projectile(best)
                    self.player.attack_hit_dealt = True
            elif best is not None:
                dmg = self._roll_player_hit_damage()
                best.hurt(dmg)
                self.apply_rune_on_hit_effects(best, dmg)
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
        self._draw_world_chests()
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
            if isinstance(sprite, Mob) and getattr(sprite, 'state', None) != 'dead':
                tfx = pg.time.get_ticks()
                if getattr(sprite, 'status_slow_until', 0) > tfx:
                    draw_corner_brackets(self.screen, dest, (70, 150, 255), corner_len=9, thickness=2)
                if getattr(sprite, 'status_burn_until', 0) > tfx:
                    draw_corner_brackets(self.screen, dest, (255, 140, 40), corner_len=9, thickness=2)
        # Target selector: shows manual target, or current auto-target if no manual one.
        selected_target = self._get_best_attack_target()
        if selected_target is not None and selected_target.alive() and getattr(selected_target, 'state', None) != 'dead':
            target_rect = self.camera.apply(selected_target).inflate(8, 8)
            px, py = self.player.hit_rect.centerx, self.player.hit_rect.centery
            mx, my = selected_target.hit_rect.centerx, selected_target.hit_rect.centery
            d_sq = (px - mx) ** 2 + (py - my) ** 2
            pr = self.player.get_effective_attack_range()
            in_range = d_sq <= pr * pr
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
            # Match Mob.update: tile-space Euclidean distance (includes diagonals when in range).
            mtx, mty = mob.tile_x, mob.tile_y
            r_sq = mob.mob_attack_range_tiles * mob.mob_attack_range_tiles
            for tx in range(self.map.tilewidth):
                for ty in range(self.map.tileheight):
                    dx = tx - mtx
                    dy = ty - mty
                    if dx * dx + dy * dy <= r_sq:
                        path_rect.x = tx * TILESIZE
                        path_rect.y = ty * TILESIZE
                        screen_rect = self.camera.apply_rect(path_rect)
                        overlay.fill(MOB_ATTACK_OVERLAY, screen_rect)
        self.screen.blit(overlay, (0, 0))
        self._draw_shield_mob_trail()
        if self.chain_lightning_fx:
            cam = self.camera.camera
            for fx in self.chain_lightning_fx:
                ax = int((fx['a'].x - cam.x) * SCALE)
                ay = int((fx['a'].y - cam.y) * SCALE)
                bx = int((fx['b'].x - cam.x) * SCALE)
                by = int((fx['b'].y - cam.y) * SCALE)
                life = max(1, fx['life_ms'])
                age_ratio = fx['age_ms'] / life
                fade = max(0.15, 1.0 - age_ratio)
                col = (int(180 + 75 * fade), int(180 + 75 * fade), int(60 + 40 * fade))
                draw_lightning_bolt(self.screen, (ax, ay), (bx, by), col, width=2)
        if self.damage_numbers:
            dmg_font = pg.font.Font(pg.font.match_font('arial'), 22)
            for dn in self.damage_numbers:
                sx = int((dn['pos'].x - self.camera.camera.x) * SCALE)
                sy = int((dn['pos'].y - self.camera.camera.y) * SCALE)
                life = max(1, dn['life_ms'])
                age_ratio = dn['age_ms'] / life
                if age_ratio < 0.7:
                    alpha = 255
                else:
                    alpha = max(0, int(255 * (1.0 - (age_ratio - 0.7) / 0.3)))
                txt = dmg_font.render(str(dn['amount']), True, dn['color'])
                txt.set_alpha(alpha)
                tx = sx - txt.get_width() // 2
                ty = sy - txt.get_height() // 2
                self.screen.blit(txt, (tx, ty))
        self.draw_hud()
        self._draw_intro_tutorial_overlay()
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
        loss_font = pg.font.Font(pg.font.match_font('arial'), 20)
        btn_font = pg.font.Font(pg.font.match_font('arial'), 28)
        title = title_font.render("You Died", True, RED)
        msg = msg_font.render("The dungeon has claimed you... for now.", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 140)))
        self.screen.blit(msg, msg.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80)))
        cl = self.death_screen_coins_lost
        xl = self.death_screen_xp_lost
        gold = self.inventory.count_item('gold_coin')
        if cl > 0:
            line_g = loss_font.render(f"Gold lost: {cl} coins  (remaining: {gold})", True, GOLD)
        else:
            line_g = loss_font.render("Gold lost: none  (no coins held)", True, UI_TEXT_MUTED)
        if xl > 0:
            line_x = loss_font.render(f"XP lost: {xl}", True, (180, 200, 255))
        elif self.player_level == 1 and self.player_xp == 0:
            line_x = loss_font.render(
                "XP lost: none  (at XP floor: level 1, 0 XP)",
                True,
                UI_TEXT_MUTED,
            )
        else:
            line_x = loss_font.render(
                "XP lost: none  (no XP in progress bar)",
                True,
                UI_TEXT_MUTED,
            )
        self.screen.blit(line_g, line_g.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 28)))
        self.screen.blit(line_x, line_x.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 2)))
        btn_w, btn_h = 240, 60
        btn_x = WIDTH // 2 - btn_w // 2
        btn_y = HEIGHT // 2 + 88
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
        self.pause_resume_btn_rect = pg.Rect(x, y0, btn_w, btn_h)
        self.pause_save_btn_rect = pg.Rect(x, y0 + 72, btn_w, btn_h)
        self.pause_quit_title_btn_rect = pg.Rect(x, y0 + 144, btn_w, btn_h)
        for rect, text in (
            (self.pause_resume_btn_rect, "Resume"),
            (self.pause_save_btn_rect, "Save Game"),
            (self.pause_quit_title_btn_rect, "Save & Quit to Title"),
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
        self.death_screen_coins_lost = 0
        self.death_screen_xp_lost = 0
        self.state = 'playing'

    # level transition methods extracted to game.systems.world_ops

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
        self.title_choose_save_btn_rect = pg.Rect(WIDTH // 2 - btn_w // 2, panel_y + 380, btn_w, btn_h)
        self.title_quit_btn_rect = pg.Rect(WIDTH // 2 - btn_w // 2, panel_y + 460, btn_w, btn_h)
        for rect, text in (
            (self.title_start_btn_rect, "Start / Continue"),
            (self.title_new_world_btn_rect, "New World"),
            (self.title_choose_save_btn_rect, "Choose Save"),
            (self.title_quit_btn_rect, "Quit"),
        ):
            hover = rect.collidepoint(pg.mouse.get_pos())
            color = (90, 90, 110) if hover else (60, 60, 80)
            pg.draw.rect(self.screen, color, rect)
            pg.draw.rect(self.screen, WHITE, rect, 2)
            surf = font_btn.render(text, True, WHITE)
            self.screen.blit(surf, surf.get_rect(center=rect.center))

        hint = font_hint.render(
            "Enter=Continue, N=New class+world, S=Choose Save, L=Level editor (separate window)",
            True,
            GOLD,
        )
        self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, panel_y + panel_h - 26)))

        if self.save_picker_open:
            self.draw_save_picker()
        if self.class_picker_for_new_world:
            self.draw_class_picker_intro()
        self.display.blit(self.screen, (0, 0))
        pg.display.flip()

    def draw_save_picker(self):
        """Overlay panel to choose active world save."""
        self.save_picker_slot_rects = []
        self.save_picker_delete_rects = []
        overlay = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))
        panel_w, panel_h = 560, 420
        panel_x = (WIDTH - panel_w) // 2
        panel_y = (HEIGHT - panel_h) // 2
        pg.draw.rect(self.screen, (30, 30, 38), (panel_x, panel_y, panel_w, panel_h))
        pg.draw.rect(self.screen, WHITE, (panel_x, panel_y, panel_w, panel_h), 2)
        title_font = pg.font.Font(pg.font.match_font('arial'), 32)
        row_font = pg.font.Font(pg.font.match_font('arial'), 20)
        row_sub_font = pg.font.Font(pg.font.match_font('arial'), 14)
        del_font = pg.font.Font(pg.font.match_font('arial'), 18)
        hint_font = pg.font.Font(pg.font.match_font('arial'), 15)
        title = title_font.render("Choose Save", True, WHITE)
        self.screen.blit(title, (panel_x + 20, panel_y + 16))
        saves = self.list_save_files()
        y = panel_y + 70
        row_h = 54
        max_rows = 7
        inner_w = panel_w - 40
        del_w = 88
        gap = 8
        sel_w = inner_w - del_w - gap
        mx, my = pg.mouse.get_pos()
        for save_name in saves[:max_rows]:
            select_rect = pg.Rect(panel_x + 20, y, sel_w, row_h)
            del_rect = pg.Rect(select_rect.right + gap, y, del_w, row_h)
            hover_sel = select_rect.collidepoint(mx, my)
            hover_del = del_rect.collidepoint(mx, my)
            active = save_name == self.current_save_name
            color = (70, 70, 96) if hover_sel else (50, 50, 70)
            if active:
                color = (85, 95, 140)
            pg.draw.rect(self.screen, color, select_rect)
            pg.draw.rect(self.screen, WHITE, select_rect, 1)
            label = save_name + ("  (active)" if active else "")
            surf = row_font.render(label, True, WHITE)
            self.screen.blit(surf, (select_rect.x + 12, select_rect.y + 5))
            class_name = self._get_save_class_name(save_name)
            class_surf = row_sub_font.render(f"Class: {class_name}", True, UI_TEXT_MUTED)
            self.screen.blit(class_surf, (select_rect.x + 12, select_rect.y + 30))
            self.save_picker_slot_rects.append((select_rect, save_name))
            del_bg = (140, 65, 65) if hover_del else (100, 45, 45)
            pg.draw.rect(self.screen, del_bg, del_rect)
            pg.draw.rect(self.screen, WHITE, del_rect, 1)
            del_surf = del_font.render("Delete", True, WHITE)
            self.screen.blit(del_surf, del_surf.get_rect(center=del_rect.center))
            self.save_picker_delete_rects.append((del_rect, save_name))
            y += row_h + 8
        hint = hint_font.render(
            "Click row to switch active save. Delete removes that file. Outside / Esc closes.",
            True,
            GOLD,
        )
        self.screen.blit(hint, (panel_x + 20, panel_y + panel_h - 28))

    # save class lookup extracted to game.systems.save_ops

    def draw_class_picker_intro(self):
        """Overlay to pick class before create_new_world."""
        self.class_picker_class_rects = []
        overlay = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))
        panel_w, panel_h = 640, 470
        panel_x = (WIDTH - panel_w) // 2
        panel_y = (HEIGHT - panel_h) // 2
        pg.draw.rect(self.screen, (28, 28, 36), (panel_x, panel_y, panel_w, panel_h))
        pg.draw.rect(self.screen, GOLD, (panel_x, panel_y, panel_w, panel_h), 2)
        title_font = pg.font.Font(pg.font.match_font('arial'), 32)
        body_font = pg.font.Font(pg.font.match_font('arial'), 17)
        btn_font = pg.font.Font(pg.font.match_font('arial'), 22)
        self.screen.blit(title_font.render("Choose your class", True, WHITE), (panel_x + 20, panel_y + 14))
        y = panel_y + 56
        row_h = 96
        mx, my = pg.mouse.get_pos()
        for cid in sorted(CLASS_DEFS.keys()):
            cdef = CLASS_DEFS[cid]
            rect = pg.Rect(panel_x + 20, y, panel_w - 40, row_h)
            sel = cid == self.class_picker_selected_id
            bg = (85, 95, 130) if sel else (52, 52, 68)
            if rect.collidepoint(mx, my) and not sel:
                bg = (68, 70, 88)
            pg.draw.rect(self.screen, bg, rect)
            pg.draw.rect(self.screen, GOLD if sel else (100, 100, 120), rect, 2)
            self.screen.blit(body_font.render(cdef['name'], True, WHITE), (rect.x + 12, rect.y + 10))
            desc = (cdef.get('description', '') or '')[:140]
            self.screen.blit(body_font.render(desc, True, UI_TEXT_MUTED), (rect.x + 12, rect.y + 38))
            self.class_picker_class_rects.append((rect, cid))
            y += row_h + 10
        self.class_picker_begin_rect = pg.Rect(panel_x + 20, panel_y + panel_h - 58, panel_w - 40, 44)
        bh = self.class_picker_begin_rect
        bcol = (60, 120, 70) if bh.collidepoint(mx, my) else (45, 90, 55)
        pg.draw.rect(self.screen, bcol, bh)
        pg.draw.rect(self.screen, WHITE, bh, 2)
        bsurf = btn_font.render("Begin Adventure", True, WHITE)
        self.screen.blit(bsurf, bsurf.get_rect(center=bh.center))
        hint_font = pg.font.Font(pg.font.match_font('arial'), 14)
        self.screen.blit(
            hint_font.render("Esc = back  |  Enter = begin with selected class", True, GOLD),
            (panel_x + 20, panel_y + panel_h - 12),
        )

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
        # Level / XP
        need_xp = xp_for_next_level(self.player_level)
        label = font.render(f"Level {self.player_level}", True, WHITE)
        self.screen.blit(label, (x, y))
        y += HUD_LINE_HEIGHT
        ox = HUD_XP_BAR_OUTLINE_W
        ix, iy = x + ox, y + ox
        iw = HUD_HEALTH_BAR_W - 2 * ox
        ih = HUD_HEALTH_BAR_H - 2 * ox
        self.screen.fill(HUD_XP_BAR_TRACK, (ix, iy, iw, ih))
        if need_xp > 0:
            fill_w = max(1, int(iw * min(1.0, self.player_xp / need_xp)))
            self.screen.fill(HUD_XP_BAR_FILL, (ix, iy, fill_w, ih))
        xp_outer = pg.Rect(x, y, HUD_HEALTH_BAR_W, HUD_HEALTH_BAR_H)
        pg.draw.rect(self.screen, HUD_XP_BAR_OUTLINE, xp_outer, HUD_XP_BAR_OUTLINE_W)
        xp_txt = font.render(f"{self.player_xp} / {need_xp} XP", True, WHITE)
        self.screen.blit(xp_txt, (x + HUD_HEALTH_BAR_W + 8, y - 2))
        y += HUD_HEALTH_BAR_H + 12
        # Attack cooldown
        label = font.render("Attack", True, WHITE)
        self.screen.blit(label, (x, y))
        y += HUD_LINE_HEIGHT
        remaining = self.player.get_attack_cooldown_remaining()
        cooldown_total = max(1, self.player.get_attack_cooldown_ms())
        self.screen.fill(HP_BAR_BG, (x, y, HUD_ATTACK_BAR_W, HUD_ATTACK_BAR_H))
        if self.player.attacking:
            status = "Attacking..."
        elif remaining <= 0:
            self.screen.fill(HP_BAR_FG, (x, y, HUD_ATTACK_BAR_W, HUD_ATTACK_BAR_H))
            status = "Ready"
        else:
            fill_w = max(0, int(HUD_ATTACK_BAR_W * (1 - remaining / cooldown_total)))
            if fill_w > 0:
                self.screen.fill(HP_BAR_FG, (x, y, fill_w, HUD_ATTACK_BAR_H))
            status = f"{remaining} ms"
        status_surf = font.render(status, True, GOLD if remaining <= 0 else WHITE)
        self.screen.blit(status_surf, (x + HUD_ATTACK_BAR_W + 8, y - 2))
        self._draw_top_right_dungeon_panel()

    def _live_mob_count(self):
        """Mobs that still block the exit (same notion as level_exit_open)."""
        return sum(
            1
            for m in self.all_mobs
            if getattr(m, 'state', None) != 'dead' and getattr(m, 'health', 0) > 0
        )

    def _dungeon_floor_index(self):
        """1-based floor index and total, or (None, None) if level not in order."""
        try:
            idx = self.level_order.index(self.current_level_name)
            return idx + 1, len(self.level_order)
        except ValueError:
            return None, None

    def _draw_top_right_dungeon_panel(self):
        """Top-right: save/world label, dungeon floor, minimap with player, live mob count."""
        if not hasattr(self, 'map') or self.player is None:
            return
        pad = HUD_PADDING
        font = pg.font.Font(pg.font.match_font('arial'), HUD_FONT_SIZE)
        small = pg.font.Font(pg.font.match_font('arial'), 16)
        lines = []
        if self.current_save_name:
            stem = self.current_save_name.replace('.json', '')
            lines.append(small.render(f"World: {stem}", True, UI_TEXT_MUTED))
        floor_n, floor_total = self._dungeon_floor_index()
        if floor_n is not None:
            lines.append(font.render(f"Dungeon {floor_n} / {floor_total}", True, UI_TEXT_BRIGHT))
        else:
            lines.append(font.render(self.current_level_name.replace('.txt', ''), True, UI_TEXT_BRIGHT))
        n_mobs = self._live_mob_count()
        lines.append(font.render(f"Mobs left: {n_mobs}", True, WHITE))

        tw, th = self.map.tilewidth, self.map.tileheight
        max_tiles = max(tw, th, 1)
        cell = max(1, DUNGEON_PANEL_MINIMAP_MAX_PX // max_tiles)
        mw, mh = tw * cell, th * cell
        mini = pg.Surface((mw, mh))
        mini.fill(DUNGEON_PANEL_MINIMAP_FLOOR)
        for r in range(th):
            for c in range(tw):
                if self.map.data[r][c] == '1':
                    mini.fill(DUNGEON_PANEL_MINIMAP_WALL, (c * cell, r * cell, cell, cell))
        px, py = self.player.tile_x, self.player.tile_y
        if 0 <= px < tw and 0 <= py < th:
            cx = px * cell + cell // 2
            cy = py * cell + cell // 2
            rad = max(2, min(cell // 2, 5))
            pg.draw.circle(mini, DUNGEON_PANEL_MINIMAP_PLAYER, (cx, cy), rad)
            pg.draw.circle(mini, BLACK, (cx, cy), rad, 1)

        text_w = max((s.get_width() for s in lines), default=0)
        panel_w = max(text_w, mw)
        y = pad
        x0 = WIDTH - pad - panel_w
        for s in lines[:-1]:
            self.screen.blit(s, (WIDTH - pad - s.get_width(), y))
            y += s.get_height() + 4
        mx = x0 + (panel_w - mw) // 2
        pg.draw.rect(self.screen, UI_TEXT_MUTED, (mx - 1, y - 1, mw + 2, mh + 2), 1)
        self.screen.blit(mini, (mx, y))
        y += mh + 8
        last = lines[-1]
        self.screen.blit(last, (WIDTH - pad - last.get_width(), y))

    def _draw_shield_mob_trail(self):
        """Lichenward Strap: subtle animated green motes toward nearest living mob (shield equipped)."""
        if self.player is None or not hasattr(self, 'camera'):
            return
        sid = self.inventory.equipment.get('shield')
        if not sid or not ITEM_DEFS.get(sid, {}).get('shield_trail_nearest_mob'):
            return
        px, py = self.player.hit_rect.center
        best = None
        best_d = None
        for m in self.all_mobs:
            if getattr(m, 'state', None) == 'dead' or getattr(m, 'health', 0) <= 0:
                continue
            mx, my = m.hit_rect.center
            d = (px - mx) ** 2 + (py - my) ** 2
            if best_d is None or d < best_d:
                best_d = d
                best = m
        if best is None:
            return
        cam = self.camera.camera
        ax = (px - cam.x) * SCALE
        ay = (py - cam.y) * SCALE
        bx = (best.hit_rect.centerx - cam.x) * SCALE
        by = (best.hit_rect.centery - cam.y) * SCALE
        t = (pg.time.get_ticks() % 1800) / 1800.0
        n = 12
        for i in range(n):
            u = ((i + 0.35) / n + t) % 1.0
            x = int(ax + (bx - ax) * u)
            y = int(ay + (by - ay) * u)
            pulse = 0.28 + 0.42 * math.sin(u * math.pi)
            rad = max(1, int(1 + 2 * pulse))
            g = int(95 + 75 * pulse)
            col = (int(38 + 40 * pulse), g, int(62 + 50 * pulse))
            pg.draw.circle(self.screen, col, (x, y), rad)

    def _wrap_ui_font_lines(self, font, text, max_px):
        """Word-wrap to fit pixel width (for UI copy)."""
        words = (text or '').split()
        if not words:
            return []
        lines = []
        cur = words[0]
        for w in words[1:]:
            trial = f"{cur} {w}"
            if font.size(trial)[0] <= max_px:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        return lines

    def _set_map_tile(self, col, row, ch):
        if row < 0 or row >= len(self.map.data):
            return
        s = self.map.data[row]
        if col < 0 or col >= len(s):
            return
        lst = list(s)
        lst[col] = ch
        self.map.data[row] = ''.join(lst)

    def _apply_opened_chests_to_map(self):
        if not hasattr(self, 'map') or not getattr(self, 'opened_chests', None):
            return
        lv = self.current_level_name
        for row in range(self.map.tileheight):
            line = self.map.data[row]
            for col, c in enumerate(line):
                if c != 'C':
                    continue
                k = intro_ops.chest_storage_key(lv, col, row)
                if k in self.opened_chests:
                    self._set_map_tile(col, row, '.')

    def try_interact_chest(self):
        """Open adjacent (or standing on) chest tile."""
        if not hasattr(self, 'map') or self.player is None:
            return False
        if self.player.move_state != 'idle' or self.player.slide_to_tile is not None:
            return False
        px, py = self.player.tile_x, self.player.tile_y
        seen = set()
        for cx, cy in ((px, py), (px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
            if (cx, cy) in seen:
                continue
            seen.add((cx, cy))
            if cy < 0 or cy >= len(self.map.data) or cx < 0 or cx >= len(self.map.data[cy]):
                continue
            if self.map.data[cy][cx] != 'C':
                continue
            k = intro_ops.chest_storage_key(self.current_level_name, cx, cy)
            if k in self.opened_chests:
                continue
            self._open_chest_at(cx, cy)
            return True
        return False

    def _open_chest_at(self, col, row):
        entries = intro_ops.loot_entries_for_intro_chest(self, col, row)
        if entries is None:
            entries = []
        leftover = 0
        for item_id, n in entries:
            leftover += self.inventory.add_item(item_id, int(n))
        if leftover > 0:
            return
        k = intro_ops.chest_storage_key(self.current_level_name, col, row)
        self.opened_chests.add(k)
        self._set_map_tile(col, row, '.')
        if intro_ops.is_intro_level(self) and (col, row) in intro_ops.STARTER_CHEST_TILES:
            self.intro_exit_unlocked = True
        for item_id, n in entries:
            self.on_items_gained(item_id, int(n))
        intro_ops.refresh_intro_exit_open(self)
        self.save_inventory_state()

    def _intro_tutorial_lines(self):
        if not intro_ops.is_intro_level(self):
            return []
        sc = intro_ops.STARTER_CHEST_TILES
        opened_starter = False
        oc = getattr(self, 'opened_chests', set())
        for sx, sy in sc:
            if intro_ops.chest_storage_key(self.current_level_name, sx, sy) in oc:
                opened_starter = True
                break
        if not opened_starter:
            return [
                'Movement: WASD or arrow keys queue one tile at a time; a yellow path shows your upcoming steps.',
                'Lore: these vaults were built to train and bury legions — stone does not forget who passed.',
                'Stand beside the supply chest and press G to open it. You start with nothing; your class kit waits inside.',
            ]
        live = sum(
            1 for m in self.all_mobs
            if getattr(m, 'state', None) != 'dead' and getattr(m, 'health', 0) > 0
        )
        if live > 0:
            return [
                'Press F with a hotbar slot selected (1–8) to drink potions or to equip and swap weapons, armor, and shield.',
                'E / I: full inventory — drag items to equipment slots or onto the hotbar; F still acts on the highlighted slot.',
                'Space: attack. The relics “choose” a foe: the closest enemy inside your weapon range becomes your target.',
                'Watch the outline: green means in range, red means too far. Click a monster to pin it; click empty floor to hand targeting back to the vault’s instinct.',
                'Lore: sentinels and straw targets alike were hung here so recruits would learn range before the real dark woke up.',
                'Destroy the straw target; the forward seal stays shut until it falls.',
            ]
        return [
            'Lore: the threshold you cross is only the outer lip of something hungrier — the dungeon deepens with every floor.',
            'The way is open. Step into the purple exit when you are ready; greater gates and a true boss still lie ahead.',
        ]

    def _draw_world_chests(self):
        if not hasattr(self, 'map'):
            return
        cam = self.camera.camera
        path_rect = pg.Rect(0, 0, TILESIZE, TILESIZE)
        for ty in range(self.map.tileheight):
            row = self.map.data[ty]
            for tx, ch in enumerate(row):
                if ch != 'C':
                    continue
                path_rect.x = tx * TILESIZE
                path_rect.y = ty * TILESIZE
                scr = self.camera.apply_rect(path_rect)
                if scr.width <= 0 or scr.height <= 0:
                    continue
                pg.draw.rect(self.screen, (95, 72, 38), scr)
                pg.draw.rect(self.screen, (200, 165, 80), scr, 2)
                ix = scr.centerx - 4
                iy = scr.centery - 6
                pg.draw.rect(self.screen, (40, 32, 22), (ix, iy, 8, 10))

    def _draw_intro_tutorial_overlay(self):
        lines = self._intro_tutorial_lines()
        if not lines:
            return
        font = pg.font.Font(pg.font.match_font('arial'), 16)
        pad = 12
        max_w = min(WIDTH - 2 * HUD_PADDING, 820)
        wrapped = []
        for raw in lines:
            wrapped.extend(self._wrap_ui_font_lines(font, raw, max_w - 2 * pad))
        line_h = font.get_height() + 4
        box_h = pad * 2 + len(wrapped) * line_h
        box = pg.Surface((max_w, box_h), pg.SRCALPHA)
        box.fill((12, 14, 22, 210))
        pg.draw.rect(box, (130, 140, 170), box.get_rect(), 1)
        y = pad
        for ln in wrapped:
            box.blit(font.render(ln, True, UI_TEXT_BRIGHT), (pad, y))
            y += line_h
        bx = (WIDTH - max_w) // 2
        # Leave room for two-line hotbar hints below slots
        by = HEIGHT - box_h - HUD_PADDING - (SLOT_SIZE + 4 + 2 * (font.get_height() + 5) + 12)
        by = max(HUD_PADDING, by)
        self.screen.blit(box, (bx, by))

    def _slot_bg_for_item(self, item_id):
        if not item_id or item_id not in ITEM_DEFS:
            return SLOT_BG
        r = ITEM_DEFS[item_id].get('rarity', 'common')
        return RARITY_SLOT_BG.get(r, SLOT_BG)

    def get_item_sprite_scaled(self, item_id, inner_size):
        """Scaled square icon for inventory/hotbar, or None if no sprite file."""
        if item_id not in ITEM_DEFS or inner_size < 4:
            return None
        fn = ITEM_DEFS[item_id].get('sprite')
        if not fn:
            return None
        cache_key = (fn, inner_size)
        if cache_key in self._item_sprite_cache:
            return self._item_sprite_cache[cache_key]
        fp = path.join(self.img_dir, fn)
        if not path.isfile(fp):
            return None
        try:
            img = pg.image.load(fp).convert_alpha()
        except (pg.error, OSError):
            return None
        iw, ih = img.get_size()
        scale = min(inner_size / iw, inner_size / ih)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        scaled = pg.transform.smoothscale(img, (nw, nh))
        self._item_sprite_cache[cache_key] = scaled
        return scaled

    def _draw_infused_rune_corners(self, rect, color, dimmed=False, arm=11, width=3):
        """L-shaped highlights at each slot corner using the infused rune's colour."""
        if dimmed:
            color = tuple(max(0, min(255, int(c * 0.55))) for c in color)
        x, y, w, h = rect.x, rect.y, rect.width, rect.height
        a = max(4, min(arm, w // 3, h // 3))
        # Top-left
        pg.draw.line(self.screen, color, (x, y), (x + a, y), width)
        pg.draw.line(self.screen, color, (x, y), (x, y + a), width)
        # Top-right
        pg.draw.line(self.screen, color, (x + w - 1, y), (x + w - 1 - a, y), width)
        pg.draw.line(self.screen, color, (x + w - 1, y), (x + w - 1, y + a), width)
        # Bottom-left
        pg.draw.line(self.screen, color, (x, y + h - 1), (x + a, y + h - 1), width)
        pg.draw.line(self.screen, color, (x, y + h - 1), (x, y + h - 1 - a), width)
        # Bottom-right
        pg.draw.line(self.screen, color, (x + w - 1, y + h - 1), (x + w - 1 - a, y + h - 1), width)
        pg.draw.line(self.screen, color, (x + w - 1, y + h - 1), (x + w - 1, y + h - 1 - a), width)

    def draw_slot(self, x, y, slot_data, selected=False, highlight=False, dimmed=False):
        """Draw one inventory slot at (x, y). Returns the pg.Rect."""
        rect = pg.Rect(x, y, SLOT_SIZE, SLOT_SIZE)
        border_color = SLOT_SELECTED if selected else (WHITE if highlight else (120, 125, 145))
        item_id = slot_data[0] if slot_data else None
        bg = self._slot_bg_for_item(item_id) if item_id else SLOT_BG
        if dimmed and item_id:
            bg = tuple(max(0, min(255, int(c * 0.55))) for c in bg)
        pg.draw.rect(self.screen, bg, rect)
        pg.draw.rect(self.screen, border_color, rect, 2)
        if slot_data:
            item_id, count, meta = unpack_slot(slot_data)
            pad = 5
            inner = SLOT_SIZE - 2 * pad
            if item_id in ITEM_DEFS:
                sp = self.get_item_sprite_scaled(item_id, inner)
                if sp:
                    sw, sh = sp.get_size()
                    bx = x + pad + (inner - sw) // 2
                    by = y + pad + (inner - sh) // 2
                    if dimmed:
                        sp = sp.copy()
                        sp.set_alpha(120)
                    self.screen.blit(sp, (bx, by))
                else:
                    color = ITEM_DEFS[item_id]['color']
                    if dimmed:
                        color = tuple(max(0, c // 2) for c in color)
                    pg.draw.rect(self.screen, color, (x + pad, y + pad, inner, inner))
            font = pg.font.Font(pg.font.match_font('arial'), 14)
            if count > 1:
                text = str(count)
                t_surf = font.render(text, True, UI_TEXT_BRIGHT)
                bw = t_surf.get_width() + 8
                bh = t_surf.get_height() + 5
                badge_x = x + SLOT_SIZE - bw - 3
                badge_y = y + SLOT_SIZE - bh - 3
                pg.draw.rect(self.screen, (10, 10, 16), (badge_x, badge_y, bw, bh))
                pg.draw.rect(self.screen, (95, 98, 120), (badge_x, badge_y, bw, bh), 1)
                self.screen.blit(font.render(text, True, (0, 0, 0)), (badge_x + 5, badge_y + 3))
                self.screen.blit(t_surf, (badge_x + 4, badge_y + 2))
            rune_id = meta.get('infused_rune') if meta else None
            if (
                rune_id
                and item_id
                and ITEM_DEFS.get(item_id, {}).get('type') == 'weapon'
            ):
                rdef = ITEM_DEFS.get(rune_id)
                if rdef:
                    rc = rdef.get('color', (220, 220, 220))
                    if isinstance(rc, list):
                        rc = tuple(rc)
                    self._draw_infused_rune_corners(rect, rc, dimmed=dimmed)
        return rect

    def draw_hotbar(self):
        """Draw item bar at bottom center. Hotbar shows first HOTBAR_SLOTS slots; one is selected."""
        total_w = HOTBAR_SLOTS * SLOT_SIZE + (HOTBAR_SLOTS - 1) * SLOT_GAP
        start_x = (WIDTH - total_w) // 2
        font = pg.font.Font(pg.font.match_font('arial'), 14)
        hint_dy = font.get_height() + 5
        y = HEIGHT - SLOT_SIZE - HUD_PADDING - hint_dy
        for i in range(HOTBAR_SLOTS):
            x = start_x + i * (SLOT_SIZE + SLOT_GAP)
            slot_data = self.inventory.get_hotbar_slot(i)
            self.draw_slot(x, y, slot_data, selected=(i == self.inventory.selected_hotbar_index))
        hint_lines = (
            '1–8 hotbar · Space attack · G chest · E/I inventory · click foe to pin target',
            'F: use potions and equip or swap weapons / armor / shield (selected slot)',
        )
        hy = y + SLOT_SIZE + 4
        for i, text in enumerate(hint_lines):
            surf = font.render(text, True, UI_TEXT_MUTED)
            hx = (WIDTH - surf.get_width()) // 2
            shadow = font.render(text, True, (0, 0, 0))
            yy = hy + i * hint_dy
            self.screen.blit(shadow, (hx + 1, yy + 1))
            self.screen.blit(surf, (hx, yy))

    def use_selected_item(self):
        """Equip gear from hotbar (weapon/armor/shield) or use consumables (e.g. potions)."""
        idx = self.inventory.selected_hotbar_index
        slot_data = self.inventory.get_hotbar_slot(idx)
        if slot_data is None:
            return False
        if self.inventory.equip_from_hotbar(idx):
            self.save_inventory_state()
            return True
        item_id, _count, _meta = unpack_slot(slot_data)
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
            if applied:
                self.add_damage_number(
                    self.player.hit_rect.center,
                    self.player.health - old_hp,
                    color=(100, 240, 130),
                )
        if not applied:
            return False
        consumed = self.inventory.consume_from_hotbar(idx, 1)
        return consumed is not None

    def draw_inventory(self):
        """Character sheet + Craft tab (JSON recipes, weapon-type slots)."""
        overlay = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        font = pg.font.Font(pg.font.match_font('arial'), HUD_FONT_SIZE)
        font_sm = pg.font.Font(pg.font.match_font('arial'), 15)
        font_md = pg.font.Font(pg.font.match_font('arial'), 16)
        font_tip = pg.font.Font(pg.font.match_font('arial'), 14)

        mouse_pos = pg.mouse.get_pos()
        self.inv_slot_rects = []
        hovered_item_id = None
        hovered_item_meta = {}

        panel_w = 1120
        panel_h = 660
        panel_x = (WIDTH - panel_w) // 2
        panel_y = (HEIGHT - panel_h) // 2
        pg.draw.rect(self.screen, (30, 30, 30), (panel_x, panel_y, panel_w, panel_h))
        pg.draw.rect(self.screen, GOLD, (panel_x, panel_y, panel_w, panel_h), 2)

        hint_shadow = font_sm.render(
            "E / I / Esc close | Shift+tooltip: salvage odds | Shift+R-click: salvage weapon (bag, hotbar, equip)",
            True, (0, 0, 0))
        self.screen.blit(hint_shadow, (panel_x + 13, panel_y + panel_h - 21))
        close_hint = font_sm.render(
            "E / I / Esc close | Shift+tooltip: salvage odds | Shift+R-click: salvage weapon (bag, hotbar, equip)",
            True, UI_TEXT_BRIGHT)
        self.screen.blit(close_hint, (panel_x + 12, panel_y + panel_h - 22))

        tab_gap = 6
        tab_specs = [
            ('character', 'Character'),
            ('skills', 'Skills'),
            ('craft', 'Craft'),
            ('upgrade', 'Upgrade'),
            ('shop', 'Shop'),
        ]
        tab_row_inner_w = panel_w - 24
        tab_w = (tab_row_inner_w - tab_gap * (len(tab_specs) - 1)) // max(1, len(tab_specs))
        tx_tab = panel_x + 12
        inv_tab_rects = {}
        for tid, _lbl in tab_specs:
            inv_tab_rects[tid] = pg.Rect(tx_tab, panel_y + 10, tab_w, 30)
            tx_tab += tab_w + tab_gap

        content_top = panel_y + 54
        left_x = panel_x + 20
        recipe_col_x = panel_x + 14
        recipe_col_w = 260
        inv_cols = INVENTORY_COLS
        inv_rows = INVENTORY_ROWS
        total_inv_w = inv_cols * SLOT_SIZE + (inv_cols - 1) * SLOT_GAP
        # Keep inventory/hotbar as one 8-slot wide block with extra breathing room.
        inv_x = panel_x + panel_w - total_inv_w - 50
        inv_start_y = content_top + 36

        if self.inventory_tab == 'character':
            cy = content_top
            preview_size = 96
            player_img = self.player.move_frames.get(self.player.facing, [None])[0]
            preview_rect = None
            if player_img:
                preview = pg.transform.scale(player_img, (preview_size, preview_size))
                preview_rect = pg.Rect(left_x + 10, cy, preview_size, preview_size)
                pg.draw.rect(self.screen, SLOT_BG, preview_rect.inflate(8, 8))
                pg.draw.rect(self.screen, SLOT_BORDER, preview_rect.inflate(8, 8), 2)
                self.screen.blit(preview, preview_rect)
            if preview_rect and preview_rect.collidepoint(mouse_pos):
                hovered_item_id = '__player_stats__'

            eq_x = left_x + preview_size + 30
            eq_y = cy
            eq_label_map = {'head': 'Head', 'chest': 'Chest', 'boots': 'Boots', 'shield': 'Shield', 'weapon': 'Weapon'}
            eq_order = ['head', 'chest', 'boots', 'shield', 'weapon']
            for eq_slot in eq_order:
                item_id = self.inventory.equipment.get(eq_slot)
                em = self.inventory.equipment_meta.get(eq_slot)
                slot_data = pack_slot(item_id, 1, em) if item_id else None
                is_drag_src = self.inv_dragging and self.inv_dragging[0] == 'equip' and self.inv_dragging[1] == eq_slot
                is_selected = self.inv_selected == ('equip', eq_slot)
                r = self.draw_slot(eq_x, eq_y, slot_data, highlight=is_selected, dimmed=is_drag_src)
                self.inv_slot_rects.append((r, 'equip', eq_slot))
                if r.collidepoint(mouse_pos) and item_id and not is_drag_src:
                    hovered_item_id = item_id
                    hovered_item_meta = dict(self.inventory.equipment_meta.get(eq_slot, {}))
                label = font_sm.render(eq_label_map[eq_slot], True, UI_TEXT_MUTED)
                self.screen.blit(label, (eq_x + SLOT_SIZE + 6, eq_y + SLOT_SIZE // 2 - label.get_height() // 2))
                eq_y += SLOT_SIZE + 4
            vit_x = eq_x + 150
            vit_y = cy + 2
            vit_w = max(210, min(320, inv_x - vit_x - 16))
            vit_h = 186
            vit = pg.Rect(vit_x, vit_y, vit_w, vit_h)
            pg.draw.rect(self.screen, (34, 36, 46), vit)
            pg.draw.rect(self.screen, (95, 105, 130), vit, 2)
            self.screen.blit(font_sm.render("Vitals", True, GOLD), (vit.x + 10, vit.y + 8))
            cdef = get_class_def(self.player_class_id)
            cls = cdef['name'] if cdef else "Unknown"
            eff_max = self.player.get_effective_max_health()
            need_xp = xp_for_next_level(self.player_level)
            coin_ct = self.inventory.count_item('gold_coin')
            vy = vit.y + 32
            for t in (
                f"Class: {cls}",
                f"Level: {self.player_level}",
                f"Health: {self.player.health}/{eff_max}",
                f"XP: {self.player_xp}/{need_xp}",
                f"Coins: {coin_ct}",
                f"Damage: {self.player.get_effective_damage()}",
                f"Defense: {self.inventory.get_total_defense()}",
            ):
                self.screen.blit(font_sm.render(t, True, UI_TEXT_BRIGHT), (vit.x + 10, vy))
                vy += 22
            dd_y = max(cy + preview_size + 18, eq_y + 8)
            dd_w = max(220, min(360, inv_x - left_x - 28))
            dd = pg.Rect(left_x + 8, dd_y, dd_w, 28)
            pg.draw.rect(self.screen, (46, 50, 62), dd)
            pg.draw.rect(self.screen, (95, 105, 130), dd, 2)
            arrow = "▼" if self.stats_dropdown_open else "▶"
            self.screen.blit(font_sm.render(f"{arrow} Quick Stats", True, UI_TEXT_BRIGHT), (dd.x + 10, dd.y + 5))
            self.inv_slot_rects.append((dd, 'stats_toggle', 0))
            if self.stats_dropdown_open:
                attrs = self.player.get_effective_attrs()
                bonuses = self.inventory.get_equipment_stat_bonuses()
                sy2 = dd.bottom + 8
                for stat in ['strength', 'dexterity', 'intelligence', 'health']:
                    b = bonuses.get(stat, 0)
                    self.screen.blit(font_sm.render(f"{stat[:3].upper()}: {attrs.get(stat,0)}  (armor +{b})", True, UI_TEXT_MUTED), (dd.x + 8, sy2))
                    sy2 += 18
        elif self.inventory_tab == 'skills':
            sy = content_top
            cdef = get_class_def(self.player_class_id) or get_class_def(DEFAULT_CLASS_ID)
            self.screen.blit(font.render("Skills", True, GOLD), (left_x, sy))
            sy += 28
            need_xp = xp_for_next_level(self.player_level)
            self.screen.blit(
                font_sm.render(
                    f"{cdef['name']}  |  Lv.{self.player_level}  |  {self.player_xp}/{need_xp} XP  |  Points: {self.skill_points}",
                    True,
                    UI_TEXT_BRIGHT,
                ),
                (left_x, sy),
            )
            sy += 24
            self.screen.blit(
                font_sm.render(
                    "Unlock nodes with points. Tier pages are based on prerequisite depth.",
                    True,
                    UI_TEXT_MUTED,
                ),
                (left_x, sy),
            )
            sy += 26

            nodes = list(cdef.get('skill_nodes', []))
            node_map = {n['id']: n for n in nodes}
            memo = {}
            def depth_of(nid):
                if nid in memo:
                    return memo[nid]
                n = node_map.get(nid)
                if not n:
                    memo[nid] = 0
                    return 0
                reqs = n.get('requires', [])
                if not reqs:
                    memo[nid] = 0
                else:
                    memo[nid] = 1 + max(depth_of(r) for r in reqs)
                return memo[nid]

            for n in nodes:
                depth_of(n['id'])
            depth_buckets = {}
            for n in nodes:
                d = memo.get(n['id'], 0)
                depth_buckets.setdefault(d, []).append(n)
            depths = sorted(depth_buckets.keys())
            rows_per_page = 3
            total_pages = max(1, (len(depths) + rows_per_page - 1) // rows_per_page)
            self.skill_tree_page = max(0, min(self.skill_tree_page, total_pages - 1))
            start = self.skill_tree_page * rows_per_page
            shown_depths = depths[start:start + rows_per_page]

            tree_x = left_x + 10
            tree_w = max(260, inv_x - left_x - 36)
            row_step = 100
            row_top = sy + 24
            centers = {}
            for ridx, d in enumerate(shown_depths):
                row_nodes = depth_buckets.get(d, [])
                ct = max(1, len(row_nodes))
                y = row_top + ridx * row_step
                for i, n in enumerate(row_nodes):
                    x = tree_x + int((i + 0.5) * tree_w / ct)
                    centers[n['id']] = (x, y)

            for nid, (x, y) in centers.items():
                n = node_map[nid]
                for req in n.get('requires', []):
                    if req not in centers:
                        continue
                    rx, ry = centers[req]
                    learned_link = req in self.purchased_skill_nodes
                    lc = (120, 180, 130) if learned_link else (95, 98, 115)
                    pg.draw.line(self.screen, lc, (rx, ry), (x, y), 3)

            for nid, (x, y) in centers.items():
                n = node_map[nid]
                owned = nid in self.purchased_skill_nodes
                can = can_unlock_skill(
                    self.player_class_id,
                    nid,
                    self.player_level,
                    self.purchased_skill_nodes,
                    self.skill_points,
                )
                r = pg.Rect(x - 72, y - 34, 144, 68)
                if owned:
                    bg = (58, 96, 68); bd = (145, 210, 160)
                elif can:
                    bg = (56, 70, 96) if r.collidepoint(mouse_pos) else (44, 56, 76); bd = (140, 170, 220)
                else:
                    bg = (42, 44, 52); bd = (90, 95, 112)
                pg.draw.rect(self.screen, bg, r, border_radius=8)
                pg.draw.rect(self.screen, bd, r, 2, border_radius=8)
                self.screen.blit(font_sm.render(n['name'], True, WHITE), (r.x + 8, r.y + 8))
                sb = n.get('stat_bonus', {})
                bonus_txt = "  ".join([f"+{v} {k[:3].upper()}" for k, v in sb.items()]) if sb else "No bonus"
                self.screen.blit(font_sm.render(bonus_txt, True, GOLD), (r.x + 8, r.y + 27))
                req_txt = f"Lv.{n.get('min_level', 1)}"
                if n.get('requires'):
                    req_txt += "  req"
                self.screen.blit(font_sm.render(req_txt, True, UI_TEXT_MUTED), (r.x + 8, r.y + 46))
                self.inv_slot_rects.append((r, 'skill_node', nid))

            pager_y = row_top + rows_per_page * row_step - 12
            prev_r = pg.Rect(left_x + 6, pager_y, 80, 28)
            next_r = pg.Rect(left_x + 92, pager_y, 80, 28)
            pg.draw.rect(self.screen, (48, 50, 58), prev_r)
            pg.draw.rect(self.screen, (95, 98, 115), prev_r, 1)
            pg.draw.rect(self.screen, (48, 50, 58), next_r)
            pg.draw.rect(self.screen, (95, 98, 115), next_r, 1)
            self.screen.blit(font_sm.render("Prev", True, UI_TEXT_BRIGHT), (prev_r.x + 22, prev_r.y + 6))
            self.screen.blit(font_sm.render("Next", True, UI_TEXT_BRIGHT), (next_r.x + 22, next_r.y + 6))
            self.inv_slot_rects.append((prev_r, 'skill_page_prev', 0))
            self.inv_slot_rects.append((next_r, 'skill_page_next', 0))
            self.screen.blit(
                font_sm.render(f"Page {self.skill_tree_page + 1}/{total_pages}", True, UI_TEXT_MUTED),
                (left_x + 184, pager_y + 6),
            )
        elif self.inventory_tab == 'craft':
            rlist = get_recipe_list()
            known = [r for r in rlist if r['id'] in self.discovered_recipe_ids]
            if (
                (not self.craft_selected_recipe_id or self.craft_selected_recipe_id not in RECIPES
                 or self.craft_selected_recipe_id not in self.discovered_recipe_ids)
                and known
            ):
                self.craft_selected_recipe_id = known[0]['id']

            mats_x = recipe_col_x + recipe_col_w + 20
            recipe_panel = pg.Rect(recipe_col_x - 6, content_top - 8, recipe_col_w + 12, panel_h - (content_top - panel_y) - 58)
            mats_panel_w = max(280, inv_x - mats_x - 20)
            mats_panel = pg.Rect(mats_x - 8, content_top - 8, mats_panel_w + 16, panel_h - (content_top - panel_y) - 58)
            pg.draw.rect(self.screen, (36, 38, 48), recipe_panel)
            pg.draw.rect(self.screen, (92, 98, 120), recipe_panel, 2)
            pg.draw.rect(self.screen, (36, 38, 48), mats_panel)
            pg.draw.rect(self.screen, (92, 98, 120), mats_panel, 2)

            self.screen.blit(font.render("Known Recipes", True, GOLD), (recipe_col_x + 6, content_top))
            ry = content_top + 30
            if not known:
                self.screen.blit(
                    font_sm.render("No recipes yet.", True, UI_TEXT_BRIGHT),
                    (recipe_col_x, ry))
                ry += 22
                self.screen.blit(
                    font_sm.render("Pick up special materials", True, UI_TEXT_MUTED),
                    (recipe_col_x, ry))
                ry += 20
                self.screen.blit(
                    font_sm.render("to discover formulas.", True, UI_TEXT_MUTED),
                    (recipe_col_x, ry))
                ry += 28
            for rec in known:
                rid = rec['id']
                rr = pg.Rect(recipe_col_x + 6, ry, recipe_col_w - 12, 34)
                sel = rid == self.craft_selected_recipe_id
                pg.draw.rect(self.screen, (48, 72, 52) if sel else (42, 44, 52), rr)
                pg.draw.rect(self.screen, GOLD if sel else (110, 115, 135), rr, 2)
                name_s = font_sm.render(rec.get('display_name', rid), True, UI_TEXT_BRIGHT)
                self.screen.blit(name_s, (rr.x + 8, rr.y + 9))
                self.inv_slot_rects.append((rr, 'craft_recipe', rid))
                ry += 38

            self.screen.blit(font.render("Crafting Bench", True, GOLD), (mats_x, content_top))
            recipe_obj = RECIPES.get(self.craft_selected_recipe_id) if known else None
            my = content_top + 30
            if recipe_obj:
                out = recipe_obj.get('output', {})
                out_id = out.get('item_id', '')
                out_name = ITEM_DEFS.get(out_id, {}).get('name', out_id)
                self.screen.blit(
                    font_md.render(f"Recipe: {recipe_obj.get('display_name', '')}", True, UI_TEXT_BRIGHT),
                    (mats_x, my))
                my += 26
                self.screen.blit(
                    font_sm.render(f"Output: {out_name} x{int(out.get('count', 1))}", True, UI_TEXT_MUTED),
                    (mats_x, my))
                my += 28

                wt = recipe_obj.get('weapon_type', 'dagger')
                slots_order = WEAPON_TYPES.get(wt, {}).get('slots', [])
                inputs = recipe_obj.get('inputs', {})
                for sk in slots_order:
                    need = inputs.get(sk)
                    slot_title = sk.replace('_', ' ').title()
                    self.screen.blit(font_md.render(slot_title, True, GOLD), (mats_x, my))
                    my += 24
                    if need is None:
                        self.screen.blit(
                            font_sm.render("Magic — not implemented yet", True, UI_TEXT_DIM),
                            (mats_x + 4, my))
                        my += 28
                        continue
                    req_n = recipe_slot_quantity(recipe_obj, sk)
                    have = self.inventory.count_item(need)
                    pr_id, pr_n = normalize_craft_placement(self.inventory._craft_placements.get(sk))
                    if pr_id == need:
                        have += pr_n
                    nm = ITEM_DEFS.get(need, {}).get('name', need)
                    self.screen.blit(font_sm.render(f"Item: {nm}", True, UI_TEXT_BRIGHT), (mats_x + 4, my))
                    my += 22
                    ok = have >= req_n
                    count_col = (130, 210, 140) if ok else (255, 130, 130)
                    count_line = f"Required: {req_n}          In inventory: {have}"
                    self.screen.blit(font_md.render(count_line, True, count_col), (mats_x + 4, my))
                    my += 24
                    placed_id, placed_n = normalize_craft_placement(self.inventory._craft_placements.get(sk))
                    slot_data = (placed_id, placed_n) if placed_id else None
                    is_drag_src = self.inv_dragging and self.inv_dragging[0] == 'craft' and self.inv_dragging[1] == sk
                    r = self.draw_slot(mats_x + 4, my, slot_data, dimmed=is_drag_src)
                    self.inv_slot_rects.append((r, 'craft', sk))
                    if r.collidepoint(mouse_pos) and placed_id and not is_drag_src:
                        hovered_item_id = placed_id
                    self.screen.blit(
                        font_sm.render("Drag from inventory", True, UI_TEXT_MUTED),
                        (mats_x + 8 + SLOT_SIZE + SLOT_GAP, my + 12))
                    my += SLOT_SIZE + 20

                cbtn = pg.Rect(mats_x, my + 10, 220, 42)
                pg.draw.rect(self.screen, (52, 92, 58), cbtn)
                pg.draw.rect(self.screen, GOLD, cbtn, 2)
                self.screen.blit(font_md.render("Craft Item", True, UI_TEXT_BRIGHT), (cbtn.x + 58, cbtn.y + 11))
                self.inv_slot_rects.append((cbtn, 'craft_btn', 0))
            elif not known:
                self.screen.blit(
                    font_sm.render("Discover a recipe to see materials here.", True, UI_TEXT_DIM),
                    (mats_x, my))
        elif self.inventory_tab == 'shop':
            shop_x = left_x
            shop_margin_r = 16
            shop_inner_w = max(200, min(inv_x - shop_x - shop_margin_r, panel_x + panel_w - shop_x - 24))
            content_bottom = panel_y + panel_h - 52
            shop_panel_top = content_top - 8
            shop_panel_h = max(120, content_bottom - shop_panel_top)
            shop_panel = pg.Rect(shop_x - 6, shop_panel_top, shop_inner_w + 12, shop_panel_h)
            pg.draw.rect(self.screen, (36, 38, 48), shop_panel)
            pg.draw.rect(self.screen, (92, 98, 120), shop_panel, 2)
            self.screen.blit(font.render("Relic Broker", True, GOLD), (shop_x, content_top))
            sy = content_top + 34
            blurb = (
                "Your catalogue (coins + level). NPC merchants will use a separate stock later."
            )
            for blurb_ln in self._wrap_ui_font_lines(font_sm, blurb, shop_inner_w - 4):
                self.screen.blit(font_sm.render(blurb_ln, True, UI_TEXT_MUTED), (shop_x, sy))
                sy += 18
            sy += 6
            coin_ct = self.inventory.count_item('gold_coin')
            self.screen.blit(
                font_sm.render(f"Coins carried: {coin_ct}", True, GOLD),
                (shop_x, sy),
            )
            sy += 24
            text_col_x = shop_x + SLOT_SIZE + 12
            text_col_w = max(80, shop_inner_w - SLOT_SIZE - 20)
            buy_w = min(max(text_col_w, 120), 260)
            listings = list(player_shop_system.iter_player_shop_listings(self))
            if not listings:
                self.screen.blit(font_sm.render("No listings in player_shop.json.", True, UI_TEXT_DIM), (shop_x, sy))
            truncated = False
            for listing, st in listings:
                item_id = listing['item_id']
                idef = ITEM_DEFS.get(item_id, {})
                row_top = sy
                if row_top > content_bottom - 72:
                    truncated = True
                    break
                ir = self.draw_slot(shop_x, row_top, (item_id, 1))
                self.inv_slot_rects.append((ir, 'shop_item', item_id))
                if ir.collidepoint(mouse_pos):
                    hovered_item_id = item_id
                tx = text_col_x
                ny = row_top
                name_s = font_md.render(idef.get('name', item_id), True, UI_TEXT_BRIGHT)
                if name_s.get_width() > text_col_w:
                    name_s = font_sm.render(idef.get('name', item_id), True, UI_TEXT_BRIGHT)
                self.screen.blit(name_s, (tx, ny))
                ny += name_s.get_height() + 4
                desc_lines = self._wrap_ui_font_lines(font_sm, idef.get('description', ''), text_col_w)[:5]
                for dl in desc_lines:
                    self.screen.blit(font_sm.render(dl, True, UI_TEXT_MUTED), (tx, ny))
                    ny += 18
                ny += 4
                price = listing['price_coins']
                need_lv = listing['min_player_level']
                meta_col = UI_TEXT_MUTED if st['locked_level'] else UI_TEXT_BRIGHT
                self.screen.blit(
                    font_sm.render(f"Lv.{need_lv}+  ·  {price} coins", True, meta_col),
                    (tx, ny),
                )
                ny += 22
                buy_r = pg.Rect(tx, ny, buy_w, 30)
                can = st['can_buy']
                bcol = (52, 110, 72) if can else (58, 58, 66)
                pg.draw.rect(self.screen, bcol, buy_r)
                pg.draw.rect(self.screen, GOLD if can else (85, 85, 95), buy_r, 2)
                lbl = "Buy" if can else ("Owned" if st['owned'] else "Locked")
                ls = font_sm.render(lbl, True, UI_TEXT_BRIGHT if can else UI_TEXT_DIM)
                self.screen.blit(ls, (buy_r.x + max(6, (buy_r.width - ls.get_width()) // 2), buy_r.y + 7))
                self.inv_slot_rects.append((buy_r, 'player_shop_buy', listing['id']))
                ny = buy_r.bottom + 6
                if not can and not st['owned']:
                    for st_ln in self._wrap_ui_font_lines(font_tip, st['status'], text_col_w):
                        self.screen.blit(font_tip.render(st_ln, True, (200, 140, 140)), (tx, ny))
                        ny += 16
                sy = max(ir.bottom, ny) + 16
            if truncated:
                self.screen.blit(
                    font_tip.render("Resize the window or shrink UI if shop rows are clipped.", True, UI_TEXT_DIM),
                    (shop_x, min(sy, content_bottom - 20)),
                )
        elif self.inventory_tab == 'upgrade':
            # Forge on the left — avoids overlapping the inventory column on the right.
            up_x = left_x
            up_panel_w = min(360, max(280, inv_x - up_x - 32))
            guide_panel = pg.Rect(up_x - 4, content_top - 8, up_panel_w + 8, 86)
            forge_panel = pg.Rect(up_x - 4, content_top + 88, up_panel_w + 8, 268)
            pg.draw.rect(self.screen, (36, 38, 48), guide_panel)
            pg.draw.rect(self.screen, (92, 98, 120), guide_panel, 2)
            pg.draw.rect(self.screen, (36, 38, 48), forge_panel)
            pg.draw.rect(self.screen, (92, 98, 120), forge_panel, 2)
            self.screen.blit(font.render("Upgrade Forge", True, GOLD), (up_x, content_top))
            uy = content_top + 34
            self.screen.blit(
                font_sm.render("Infuse a weapon with a rune + coins to forge an augmented weapon.", True, UI_TEXT_MUTED),
                (up_x, uy))
            uy += 72
            self.screen.blit(font_md.render("Weapon", True, GOLD), (up_x, uy))
            uy += 24
            wid = self.inventory._upgrade_weapon_item_id
            wdata = (wid, 1) if wid else None
            is_w_drag = self.inv_dragging and self.inv_dragging[0] == 'upgrade_weapon'
            wr = self.draw_slot(up_x, uy, wdata, dimmed=is_w_drag)
            self.inv_slot_rects.append((wr, 'upgrade_weapon', 0))
            if wr.collidepoint(mouse_pos) and wid and not is_w_drag:
                hovered_item_id = wid
            uy += SLOT_SIZE + 14
            self.screen.blit(font_md.render("Rune", True, GOLD), (up_x, uy))
            uy += 24
            rid = self.inventory._upgrade_rune_item_id
            rdata = (rid, 1) if rid else None
            is_r_drag = self.inv_dragging and self.inv_dragging[0] == 'upgrade_rune'
            rr = self.draw_slot(up_x, uy, rdata, dimmed=is_r_drag)
            self.inv_slot_rects.append((rr, 'upgrade_rune', 0))
            if rr.collidepoint(mouse_pos) and rid and not is_r_drag:
                hovered_item_id = rid
            uy += SLOT_SIZE + 18
            ok, reason = can_infuse_weapon(self.inventory)
            cost = 0
            if wid:
                cost = int(ITEM_DEFS.get(wid, {}).get('augment_coin_cost', 25))
            self.screen.blit(font_sm.render(f"Coin cost: {cost}", True, GOLD), (up_x, uy))
            uy += 24
            status_col = (120, 220, 130) if ok else (220, 130, 130)
            self.screen.blit(font_sm.render("Ready" if ok else reason, True, status_col), (up_x, uy))
            uy += 26
            ubtn = pg.Rect(up_x, uy, 240, 42)
            pg.draw.rect(self.screen, (64, 82, 122), ubtn)
            pg.draw.rect(self.screen, GOLD, ubtn, 2)
            self.screen.blit(font_md.render("Infuse Weapon", True, UI_TEXT_BRIGHT), (ubtn.x + 52, ubtn.y + 11))
            self.inv_slot_rects.append((ubtn, 'upgrade_btn', 0))

        if self.inventory_tab != 'skills':
            self.screen.blit(font.render("Inventory", True, GOLD), (inv_x, content_top))
            hb_y = content_top + 34
            for i in range(HOTBAR_SLOTS):
                hx = inv_x + i * (SLOT_SIZE + SLOT_GAP)
                hdata = self.inventory.get_hotbar_slot(i)
                is_h_drag = self.inv_dragging and self.inv_dragging[0] == 'hotbar' and self.inv_dragging[1] == i
                is_h_sel = i == self.inventory.selected_hotbar_index
                hr = self.draw_slot(hx, hb_y, hdata, selected=is_h_sel, dimmed=is_h_drag)
                self.inv_slot_rects.append((hr, 'hotbar', i))
                if hr.collidepoint(mouse_pos) and hdata and not is_h_drag:
                    hovered_item_id = hdata[0]
                    _hid, _hc, hmeta = unpack_slot(hdata)
                    hovered_item_meta = dict(hmeta) if hmeta else {}
            self.screen.blit(font_sm.render("Hotbar", True, UI_TEXT_MUTED), (inv_x, hb_y + SLOT_SIZE + 6))
            inv_start_y = hb_y + SLOT_SIZE + 24
            for row in range(inv_rows):
                for col in range(inv_cols):
                    idx = row * inv_cols + col
                    sx = inv_x + col * (SLOT_SIZE + SLOT_GAP)
                    sy = inv_start_y + row * (SLOT_SIZE + SLOT_GAP)
                    slot_data = self.inventory.get_slot(idx)
                    is_drag_src = self.inv_dragging and self.inv_dragging[0] == 'inv' and self.inv_dragging[1] == idx
                    is_selected = self.inv_selected == ('inv', idx)
                    r = self.draw_slot(sx, sy, slot_data, selected=False, highlight=is_selected, dimmed=is_drag_src)
                    self.inv_slot_rects.append((r, 'inv', idx))
                    if r.collidepoint(mouse_pos) and slot_data and not is_drag_src:
                        hovered_item_id = slot_data[0]
                        _iid, _ic, imeta = unpack_slot(slot_data)
                        hovered_item_meta = dict(imeta) if imeta else {}

        tab_hit = []
        for tid, lbl in tab_specs:
            rect = inv_tab_rects[tid]
            sel = self.inventory_tab == tid
            pg.draw.rect(self.screen, (48, 48, 48), rect)
            pg.draw.rect(self.screen, GOLD if sel else (100, 100, 100), rect, 2)
            surf = font_sm.render(lbl, True, GOLD if sel else WHITE)
            lx = rect.x + max(4, (rect.width - surf.get_width()) // 2)
            self.screen.blit(surf, (lx, rect.y + 7))
            tab_hit.append((rect, 'tab', tid))
        self.inv_slot_rects = tab_hit + self.inv_slot_rects

        # --- Drag ghost ---
        if self.inv_dragging:
            _, _, drag_item_id, drag_count, drag_meta = self._inv_drag_parts()
            ghost_size = SLOT_SIZE - 8
            gx = mouse_pos[0] - ghost_size // 2
            gy = mouse_pos[1] - ghost_size // 2
            inner = ghost_size - 6
            sp = self.get_item_sprite_scaled(drag_item_id, inner) if drag_item_id in ITEM_DEFS else None
            ghost = pg.Surface((ghost_size, ghost_size), pg.SRCALPHA)
            if sp:
                sw, sh = sp.get_size()
                bx = (ghost_size - sw) // 2
                by = (ghost_size - sh) // 2
                sp2 = sp.copy()
                sp2.set_alpha(220)
                ghost.blit(sp2, (bx, by))
            elif drag_item_id in ITEM_DEFS:
                color = ITEM_DEFS[drag_item_id]['color']
                pg.draw.rect(ghost, (*color, 200), (4, 4, ghost_size - 8, ghost_size - 8))
            self.screen.blit(ghost, (gx, gy))
            drune = (drag_meta or {}).get('infused_rune')
            if (
                drune
                and drag_item_id
                and ITEM_DEFS.get(drag_item_id, {}).get('type') == 'weapon'
            ):
                rd = ITEM_DEFS.get(drune)
                if rd:
                    rc = rd.get('color', (220, 220, 220))
                    if isinstance(rc, list):
                        rc = tuple(rc)
                    self._draw_infused_rune_corners(pg.Rect(gx, gy, ghost_size, ghost_size), rc)
            if drag_count > 1:
                cnt = font_sm.render(str(drag_count), True, UI_TEXT_BRIGHT)
                self.screen.blit(font_sm.render(str(drag_count), True, (0, 0, 0)), (gx + ghost_size - cnt.get_width() + 1, gy + ghost_size - cnt.get_height() + 1))
                self.screen.blit(cnt, (gx + ghost_size - cnt.get_width(), gy + ghost_size - cnt.get_height()))

        # --- Tooltip ---
        if hovered_item_id and not self.inv_dragging:
            shift_on = pg.key.get_mods() & pg.KMOD_SHIFT
            self._draw_tooltip(
                mouse_pos, hovered_item_id, font_tip,
                slot_meta=hovered_item_meta,
                show_salvage=shift_on,
            )

    def _inv_drag_parts(self):
        d = self.inv_dragging
        if not d:
            return None, None, None, None, {}
        src, ref, iid, cnt = d[0], d[1], d[2], d[3]
        meta = d[4] if len(d) > 4 and isinstance(d[4], dict) else {}
        return src, ref, iid, cnt, meta

    def _draw_tooltip(self, pos, item_id, font, slot_meta=None, show_salvage=False):
        """Render a multi-line tooltip box next to the cursor."""
        slot_meta = slot_meta or {}
        if item_id == '__player_stats__':
            attrs = self.player.get_effective_attrs()
            bonuses = self.inventory.get_equipment_stat_bonuses()
            lines = ["Player Attributes"]
            for stat in ['strength', 'dexterity', 'intelligence', 'health']:
                base_like = attrs.get(stat, 0) - bonuses.get(stat, 0)
                lines.append(f"{stat.capitalize()}: {attrs.get(stat,0)}  (base {base_like} + armor {bonuses.get(stat,0)})")
            lines.append(f"Defense: {self.inventory.get_total_defense()}")
            item = {}
        else:
            item = ITEM_DEFS.get(item_id, {})
            lines = []
            lines.append(item.get('name', item_id))
            rune_id = slot_meta.get('infused_rune')
            if rune_id and rune_id in ITEM_DEFS:
                rn = ITEM_DEFS[rune_id].get('name', rune_id)
                lines.append(f"Infused rune: {rn}")
                patron = ITEM_DEFS[rune_id].get('patron_god')
                if patron:
                    lines.append(f"Patron: {patron}")
        if item.get('type') == 'weapon':
            lines.append("Weapon Stats")
            base_dmg = int(item.get('base_damage', 0))
            rt = item.get('attack_range_tiles', PLAYER_DEFAULT_ATTACK_RANGE_TILES)
            lines.append(f"  Base: {base_dmg}  |  Range: {rt} tile(s)")
            cd = weapon_cooldown_ms_for_item(item_id)
            if cd is not None:
                lines.append(f"  Cooldown: {cd} ms")
            if item.get('scaling_stat'):
                lines.append(f"  Scaling: {item['scaling_stat'].capitalize()} x{item.get('scaling_factor', 0)}")
            rb = item.get('rune_blessings', {})
            if rb:
                lines.append("Rune Blessings")
                for rid, bless in rb.items():
                    rname = ITEM_DEFS.get(rid, {}).get('name', rid)
                    btxt = bless.get('summary', '')
                    if btxt:
                        lines.append(f"  {rname}: {btxt}")
                    else:
                        lines.append(f"  {rname}")
        eff = resolve_on_hit_effect(item, slot_meta.get('infused_rune'))
        tip_line = format_on_hit_effect_tooltip(eff)
        if tip_line:
            lines.append(tip_line)
        if item.get('defense'):
            lines.append(f"Defense: {item['defense']}")
        sb = item.get('stat_bonus', {})
        if sb:
            parts = [f"{k.capitalize()} +{v}" for k, v in sb.items()]
            lines.append("Bonus: " + ", ".join(parts))
        if item.get('effect'):
            for ek, ev in item['effect'].items():
                lines.append(f"Effect: {ek} {ev}")
        desc = item.get('description', '')
        if desc:
            lines.append(desc)
        salv = item.get('salvage')
        if show_salvage and salv:
            lines.append("Salvage (Shift+right-click):")
            for entry in salv:
                nid = entry['item_id']
                nm = ITEM_DEFS.get(nid, {}).get('name', nid)
                lo, hi = entry['count']
                ch = int(float(entry.get('chance', 1)) * 100)
                lines.append(f"  {nm} x{lo}-{hi} ({ch}% per roll)")

        name_font = pg.font.Font(pg.font.match_font('arial'), 16)
        pad = 10
        tip_w = pad * 2
        line_surfs = []
        for i, l in enumerate(lines):
            fnt = name_font if i == 0 else font
            col = GOLD if i == 0 else UI_TEXT_BRIGHT
            w = fnt.render(l, True, col).get_width()
            tip_w = max(tip_w, w + pad * 2)
            line_surfs.append((l, fnt, col))
        tip_h = pad * 2
        for l, fnt, col in line_surfs:
            tip_h += fnt.render(l, True, col).get_height() + 3
        tx = pos[0] + 18
        ty = pos[1] + 6
        if tx + tip_w > WIDTH:
            tx = pos[0] - tip_w - 6
        if ty + tip_h > HEIGHT:
            ty = HEIGHT - tip_h - 6
        bg = pg.Surface((tip_w, tip_h), pg.SRCALPHA)
        bg.fill((34, 36, 44, 248))
        self.screen.blit(bg, (tx, ty))
        pg.draw.rect(self.screen, (150, 155, 175), (tx, ty, tip_w, tip_h), 2)
        cy = ty + pad
        for l, fnt, col in line_surfs:
            sh = fnt.render(l, True, (0, 0, 0))
            self.screen.blit(sh, (tx + pad + 1, cy + 1))
            self.screen.blit(fnt.render(l, True, col), (tx + pad, cy))
            cy += fnt.render(l, True, col).get_height() + 3

    def _drop_onto_craft_slot(self, craft_slot_key, item_id):
        """Stage items for the selected recipe; returns False if not enough materials."""
        recipe = RECIPES.get(self.craft_selected_recipe_id)
        if recipe is None:
            return False
        need_id = recipe.get('inputs', {}).get(craft_slot_key)
        if need_id is None or item_id != need_id:
            return False
        need_n = recipe_slot_quantity(recipe, craft_slot_key)
        old_raw = self.inventory._craft_placements.get(craft_slot_key)
        oid, on = normalize_craft_placement(old_raw)
        pool = self.inventory.count_item(item_id)
        if oid == item_id:
            pool += on
        if pool < need_n:
            return False
        if oid and on > 0:
            self.inventory.add_item(oid, on)
        removed = self.inventory.remove_item_by_id(item_id, need_n)
        if removed < need_n:
            return False
        self.inventory._craft_placements[craft_slot_key] = (item_id, need_n)
        return True

    def _inv_hit_test(self, pos):
        """Return (source, index) for the slot under pos, or None.

        Later entries win so the inventory grid (registered after the upgrade panel)
        takes precedence over any accidental overlap; tabs stay first in the list and
        are still found when not covered by other rects.
        """
        for rect, source, index in reversed(self.inv_slot_rects):
            if rect.collidepoint(pos):
                return (source, index)
        return None

    def _inv_mouse_down(self, event):
        if self.inventory_tab == 'skills' and event.button in (4, 5):
            if event.button == 4:
                self.skill_tree_page = max(0, self.skill_tree_page - 1)
            else:
                self.skill_tree_page += 1
            return
        hit = self._inv_hit_test(event.pos)
        if hit is None:
            self.inv_selected = None
            return
        source, index = hit
        if event.button == 1:
            if source == 'tab':
                if index == 'character':
                    if self.inventory_tab == 'craft':
                        self.inventory.return_craft_staging()
                    if self.inventory_tab == 'upgrade':
                        self.inventory.return_upgrade_staging()
                    self.inventory_tab = 'character'
                elif index == 'skills':
                    if self.inventory_tab == 'craft':
                        self.inventory.return_craft_staging()
                    if self.inventory_tab == 'upgrade':
                        self.inventory.return_upgrade_staging()
                    self.inventory_tab = 'skills'
                elif index == 'craft':
                    if self.inventory_tab == 'upgrade':
                        self.inventory.return_upgrade_staging()
                    self.inventory_tab = 'craft'
                    self._sync_discovered_recipes_from_inventory()
                elif index == 'shop':
                    if self.inventory_tab == 'craft':
                        self.inventory.return_craft_staging()
                    if self.inventory_tab == 'upgrade':
                        self.inventory.return_upgrade_staging()
                    self.inventory_tab = 'shop'
                elif index == 'upgrade':
                    if self.inventory_tab == 'craft':
                        self.inventory.return_craft_staging()
                    self.inventory_tab = 'upgrade'
                return
            if source == 'stats_toggle':
                self.stats_dropdown_open = not self.stats_dropdown_open
                return
            if source in ('skill_buy', 'skill_node'):
                self.try_purchase_skill_node(index)
                return
            if source == 'skill_page_prev':
                self.skill_tree_page = max(0, self.skill_tree_page - 1)
                return
            if source == 'skill_page_next':
                self.skill_tree_page += 1
                return
            if source == 'craft_recipe':
                if self.craft_selected_recipe_id != index:
                    self.inventory.return_craft_staging()
                    self.craft_selected_recipe_id = index
                return
            if source == 'craft_btn':
                if try_finish_craft(self.inventory, self.craft_selected_recipe_id):
                    self._sync_discovered_recipes_from_inventory()
                    self.save_inventory_state()
                return
            if source == 'player_shop_buy':
                player_shop_system.try_buy_player_listing(self, index)
                return
            if source == 'upgrade_btn':
                ok, _ = try_finish_infusion(self.inventory)
                if ok:
                    self.save_inventory_state()
                return
            if source == 'craft':
                pid, pn = normalize_craft_placement(self.inventory._craft_placements.get(index))
                if pid and pn > 0:
                    self.inv_dragging = (source, index, pid, pn, {})
                    self.inv_selected = hit
                return
            if source == 'upgrade_weapon':
                item_id = self.inventory._upgrade_weapon_item_id
                if item_id:
                    self.inv_dragging = ('upgrade_weapon', 0, item_id, 1)
                    self.inv_selected = hit
                return
            if source == 'upgrade_rune':
                item_id = self.inventory._upgrade_rune_item_id
                if item_id:
                    self.inv_dragging = ('upgrade_rune', 0, item_id, 1)
                    self.inv_selected = hit
                return
            if source == 'inv':
                slot_data = self.inventory.get_slot(index)
                if slot_data:
                    iid, ic, im = unpack_slot(slot_data)
                    self.inv_dragging = (source, index, iid, ic, im)
                    self.inv_selected = hit
            elif source == 'hotbar':
                slot_data = self.inventory.get_hotbar_slot(index)
                if slot_data:
                    iid, ic, im = unpack_slot(slot_data)
                    self.inv_dragging = (source, index, iid, ic, im)
                    self.inv_selected = hit
                else:
                    self.inv_selected = hit
            elif source == 'equip':
                item_id = self.inventory.equipment.get(index)
                if item_id:
                    em = dict(self.inventory.equipment_meta.get(index, {}))
                    self.inv_dragging = (source, index, item_id, 1, em)
                    self.inv_selected = hit
                else:
                    self.inv_selected = hit
        elif event.button == 3:
            if pg.key.get_mods() & pg.KMOD_SHIFT:
                if source == 'inv':
                    if self.inventory.try_salvage_inv_slot(index):
                        self._sync_discovered_recipes_from_inventory()
                        self.save_inventory_state()
                elif source == 'hotbar':
                    if self.inventory.try_salvage_hotbar_slot(index):
                        self._sync_discovered_recipes_from_inventory()
                        self.save_inventory_state()
                elif source == 'equip' and index == 'weapon':
                    if self.inventory.try_salvage_equipped_weapon():
                        self._sync_discovered_recipes_from_inventory()
                        self.save_inventory_state()
                return
            if source == 'inv':
                slot_data = self.inventory.get_slot(index)
                if slot_data:
                    item_def = ITEM_DEFS.get(slot_data[0], {})
                    if item_def.get('slot') in EQUIPMENT_SLOTS:
                        self.inventory.equip_from_slot(index)
            elif source == 'hotbar':
                slot_data = self.inventory.get_hotbar_slot(index)
                if slot_data:
                    item_def = ITEM_DEFS.get(slot_data[0], {})
                    eq_slot = item_def.get('slot')
                    if eq_slot in EQUIPMENT_SLOTS:
                        self.inventory.equip_from_hotbar(index)
                        self.save_inventory_state()
            elif source == 'equip':
                self.inventory.unequip(index)

    def _inv_mouse_up(self, event):
        if event.button != 1 or not self.inv_dragging:
            self.inv_dragging = None
            return
        drag_src, drag_idx, drag_item, drag_count, drag_meta = self._inv_drag_parts()
        drop_hit = self._inv_hit_test(event.pos)

        if drop_hit is None:
            self.inv_dragging = None
            return
        drop_src, drop_idx = drop_hit
        if (drag_src, drag_idx) == (drop_src, drop_idx):
            self.inv_dragging = None
            return

        if self.inventory_tab == 'craft':
            if drag_src == 'inv' and drop_src == 'craft':
                if self._drop_onto_craft_slot(drop_idx, drag_item):
                    self.save_inventory_state()
                    self.inv_dragging = None
                return
            if drag_src == 'hotbar' and drop_src == 'craft':
                if self._drop_onto_craft_slot(drop_idx, drag_item):
                    self.save_inventory_state()
                    self.inv_dragging = None
                return
            if drag_src == 'equip' and drop_src == 'craft' and drag_idx == 'weapon':
                return
            if drag_src == 'craft' and drop_src == 'inv':
                craft_sk = drag_idx
                drop_data = self.inventory.get_slot(drop_idx)
                if drop_data is None:
                    self.inventory.set_slot(drop_idx, drag_item, drag_count, meta=drag_meta if drag_meta else None)
                    self.inventory._craft_placements.pop(craft_sk, None)
                    self.save_inventory_state()
                    self.inv_dragging = None
                    return
                di, dc = drop_data[0], drop_data[1]
                idef = ITEM_DEFS.get(di, {})
                mx = idef.get('max_stack', 99)
                if di == drag_item and idef.get('stackable', True) and dc + drag_count <= mx:
                    self.inventory.set_slot(drop_idx, di, dc + drag_count)
                    self.inventory._craft_placements.pop(craft_sk, None)
                    self.save_inventory_state()
                    self.inv_dragging = None
                    return
                return
            if drag_src == 'craft' and drop_src == 'hotbar':
                craft_sk = drag_idx
                hb = self.inventory.get_hotbar_slot(drop_idx)
                if hb is None:
                    self.inventory.set_hotbar_slot(
                        drop_idx, drag_item, drag_count,
                        meta=drag_meta if drag_meta else None,
                    )
                    self.inventory._craft_placements.pop(craft_sk, None)
                    self.save_inventory_state()
                    self.inv_dragging = None
                    return
                hi, hc = hb[0], hb[1]
                idef = ITEM_DEFS.get(hi, {})
                mx = idef.get('max_stack', 99)
                if hi == drag_item and idef.get('stackable', True) and hc + drag_count <= mx:
                    self.inventory.set_hotbar_slot(drop_idx, hi, hc + drag_count)
                    self.inventory._craft_placements.pop(craft_sk, None)
                    self.save_inventory_state()
                    self.inv_dragging = None
                    return
                return
            if drag_src == 'craft' and drop_src == 'equip' and drop_idx == 'weapon':
                return
        if self.inventory_tab == 'upgrade':
            if drag_src == 'inv' and drop_src == 'upgrade_weapon':
                idef = ITEM_DEFS.get(drag_item, {})
                if idef.get('type') != 'weapon':
                    return
                if not self.inventory.remove_item(drag_idx, 1):
                    return
                old = self.inventory._upgrade_weapon_item_id
                if old:
                    self.inventory.add_item(old, 1)
                self.inventory._upgrade_weapon_item_id = drag_item
                self.save_inventory_state()
                self.inv_dragging = None
                return
            if drag_src == 'hotbar' and drop_src == 'upgrade_weapon':
                idef = ITEM_DEFS.get(drag_item, {})
                if idef.get('type') != 'weapon':
                    return
                hb = self.inventory.get_hotbar_slot(drag_idx)
                if not hb:
                    return
                hi, hc, hm = unpack_slot(hb)
                if hi != drag_item or hc < 1:
                    return
                if hc <= 1:
                    self.inventory.set_hotbar_slot(drag_idx, None, 0)
                else:
                    self.inventory.set_hotbar_slot(drag_idx, hi, hc - 1, meta=hm if hm else None)
                old = self.inventory._upgrade_weapon_item_id
                if old:
                    self.inventory.add_item(old, 1)
                self.inventory._upgrade_weapon_item_id = drag_item
                self.save_inventory_state()
                self.inv_dragging = None
                return
            if drag_src == 'equip' and drag_idx == 'weapon' and drop_src == 'upgrade_weapon':
                old = self.inventory._upgrade_weapon_item_id
                if old:
                    self.inventory.add_item(old, 1)
                self.inventory._upgrade_weapon_item_id = drag_item
                self.inventory.equipment['weapon'] = None
                self.inventory.equipment_meta.pop('weapon', None)
                self.save_inventory_state()
                self.inv_dragging = None
                return
            if drag_src == 'inv' and drop_src == 'upgrade_rune':
                idef = ITEM_DEFS.get(drag_item, {})
                if idef.get('type') != 'rune':
                    return
                if not self.inventory.remove_item(drag_idx, 1):
                    return
                old = self.inventory._upgrade_rune_item_id
                if old:
                    self.inventory.add_item(old, 1)
                self.inventory._upgrade_rune_item_id = drag_item
                self.save_inventory_state()
                self.inv_dragging = None
                return
            if drag_src == 'hotbar' and drop_src == 'upgrade_rune':
                idef = ITEM_DEFS.get(drag_item, {})
                if idef.get('type') != 'rune':
                    return
                hb = self.inventory.get_hotbar_slot(drag_idx)
                if not hb:
                    return
                hi, hc, hm = unpack_slot(hb)
                if hi != drag_item or hc < 1:
                    return
                if hc <= 1:
                    self.inventory.set_hotbar_slot(drag_idx, None, 0)
                else:
                    self.inventory.set_hotbar_slot(drag_idx, hi, hc - 1, meta=hm if hm else None)
                old = self.inventory._upgrade_rune_item_id
                if old:
                    self.inventory.add_item(old, 1)
                self.inventory._upgrade_rune_item_id = drag_item
                self.save_inventory_state()
                self.inv_dragging = None
                return
            if drag_src == 'upgrade_weapon' and drop_src == 'inv':
                drop_data = self.inventory.get_slot(drop_idx)
                if drop_data is None:
                    self.inventory.set_slot(drop_idx, drag_item, 1, meta=drag_meta if drag_meta else None)
                    self.inventory._upgrade_weapon_item_id = None
                    self.save_inventory_state()
                    self.inv_dragging = None
                    return
                return
            if drag_src == 'upgrade_weapon' and drop_src == 'hotbar':
                hb = self.inventory.get_hotbar_slot(drop_idx)
                if hb is None:
                    self.inventory.set_hotbar_slot(
                        drop_idx, drag_item, 1, meta=drag_meta if drag_meta else None,
                    )
                    self.inventory._upgrade_weapon_item_id = None
                    self.save_inventory_state()
                    self.inv_dragging = None
                    return
                return
            if drag_src == 'upgrade_rune' and drop_src == 'inv':
                drop_data = self.inventory.get_slot(drop_idx)
                if drop_data is None:
                    self.inventory.set_slot(drop_idx, drag_item, 1, meta=drag_meta if drag_meta else None)
                    self.inventory._upgrade_rune_item_id = None
                    self.save_inventory_state()
                    self.inv_dragging = None
                    return
                di, dc, dm = unpack_slot(drop_data)
                idef = ITEM_DEFS.get(di, {})
                mx = idef.get('max_stack', 99)
                if di == drag_item and idef.get('stackable', True) and dc < mx:
                    self.inventory.set_slot(drop_idx, di, dc + 1, meta=dm if dm else None)
                    self.inventory._upgrade_rune_item_id = None
                    self.save_inventory_state()
                    self.inv_dragging = None
                    return
                return
            if drag_src == 'upgrade_rune' and drop_src == 'hotbar':
                hb = self.inventory.get_hotbar_slot(drop_idx)
                if hb is None:
                    self.inventory.set_hotbar_slot(
                        drop_idx, drag_item, 1, meta=drag_meta if drag_meta else None,
                    )
                    self.inventory._upgrade_rune_item_id = None
                    self.save_inventory_state()
                    self.inv_dragging = None
                    return
                hi, hc, hm = unpack_slot(hb)
                idef = ITEM_DEFS.get(hi, {})
                mx = idef.get('max_stack', 99)
                if hi == drag_item and idef.get('stackable', True) and hc < mx:
                    self.inventory.set_hotbar_slot(drop_idx, hi, hc + 1, meta=hm if hm else None)
                    self.inventory._upgrade_rune_item_id = None
                    self.save_inventory_state()
                    self.inv_dragging = None
                    return
                return
            if drag_src == 'upgrade_weapon' and drop_src == 'equip' and drop_idx == 'weapon':
                if self.inventory.equipment.get('weapon') is not None:
                    return
                self.inventory.equipment['weapon'] = drag_item
                if drag_meta:
                    self.inventory.equipment_meta['weapon'] = dict(drag_meta)
                else:
                    self.inventory.equipment_meta.pop('weapon', None)
                self.inventory._upgrade_weapon_item_id = None
                self.save_inventory_state()
                self.inv_dragging = None
                return

        self.inv_dragging = None

        # Swap logic between inventory slots and equipment slots
        if drag_src == 'inv' and drop_src == 'inv':
            a = self.inventory.get_slot(drag_idx)
            b = self.inventory.get_slot(drop_idx)
            if a and b and a[0] == b[0]:
                idef = ITEM_DEFS.get(a[0], {})
                if idef.get('stackable', True):
                    mx = int(idef.get('max_stack', 99))
                    space = max(0, mx - b[1])
                    if space > 0:
                        moved = min(space, a[1])
                        ai, ac, am = unpack_slot(a)
                        bi, bc, bm = unpack_slot(b)
                        self.inventory.set_slot(drop_idx, bi, bc + moved, meta=bm if bm else None)
                        remain = ac - moved
                        self.inventory.set_slot(drag_idx, ai, remain, meta=am if am else None) if remain > 0 else self.inventory.set_slot(drag_idx, None, 0)
                        self.save_inventory_state()
                        return
            self.inventory.slots[drag_idx] = b
            self.inventory.slots[drop_idx] = a
        elif drag_src == 'inv' and drop_src == 'hotbar':
            a = self.inventory.get_slot(drag_idx)
            b = self.inventory.get_hotbar_slot(drop_idx)
            if a and b and a[0] == b[0]:
                idef = ITEM_DEFS.get(a[0], {})
                if idef.get('stackable', True):
                    mx = int(idef.get('max_stack', 99))
                    space = max(0, mx - b[1])
                    if space > 0:
                        moved = min(space, a[1])
                        ai, ac, am = unpack_slot(a)
                        bi, bc, bm = unpack_slot(b)
                        self.inventory.set_hotbar_slot(
                            drop_idx, bi, bc + moved, meta=bm if bm else None,
                        )
                        remain = ac - moved
                        self.inventory.set_slot(drag_idx, ai, remain, meta=am if am else None) if remain > 0 else self.inventory.set_slot(drag_idx, None, 0)
                        self.save_inventory_state()
                        return
            self.inventory.slots[drag_idx] = b
            if a:
                ai, ac, am = unpack_slot(a)
                self.inventory.set_hotbar_slot(drop_idx, ai, ac, meta=am if am else None)
            else:
                self.inventory.set_hotbar_slot(drop_idx, None, 0)
        elif drag_src == 'hotbar' and drop_src == 'inv':
            a = self.inventory.get_hotbar_slot(drag_idx)
            b = self.inventory.get_slot(drop_idx)
            if a and b and a[0] == b[0]:
                idef = ITEM_DEFS.get(a[0], {})
                if idef.get('stackable', True):
                    mx = int(idef.get('max_stack', 99))
                    space = max(0, mx - b[1])
                    if space > 0:
                        moved = min(space, a[1])
                        ai, ac, am = unpack_slot(a)
                        bi, bc, bm = unpack_slot(b)
                        self.inventory.set_slot(
                            drop_idx, bi, bc + moved, meta=bm if bm else None,
                        )
                        remain = ac - moved
                        if remain > 0:
                            self.inventory.set_hotbar_slot(drag_idx, ai, remain, meta=am if am else None)
                        else:
                            self.inventory.set_hotbar_slot(drag_idx, None, 0)
                        self.save_inventory_state()
                        return
            if b:
                bi, bc, bm = unpack_slot(b)
                self.inventory.set_hotbar_slot(drag_idx, bi, bc, meta=bm if bm else None)
            else:
                self.inventory.set_hotbar_slot(drag_idx, None, 0)
            self.inventory.slots[drop_idx] = a
        elif drag_src == 'hotbar' and drop_src == 'hotbar':
            a = self.inventory.get_hotbar_slot(drag_idx)
            b = self.inventory.get_hotbar_slot(drop_idx)
            if a and b and a[0] == b[0]:
                idef = ITEM_DEFS.get(a[0], {})
                if idef.get('stackable', True):
                    mx = int(idef.get('max_stack', 99))
                    space = max(0, mx - b[1])
                    if space > 0:
                        moved = min(space, a[1])
                        ai, ac, am = unpack_slot(a)
                        bi, bc, bm = unpack_slot(b)
                        self.inventory.set_hotbar_slot(drop_idx, bi, bc + moved, meta=bm if bm else None)
                        remain = ac - moved
                        if remain > 0:
                            self.inventory.set_hotbar_slot(drag_idx, ai, remain, meta=am if am else None)
                        else:
                            self.inventory.set_hotbar_slot(drag_idx, None, 0)
                        self.save_inventory_state()
                        return
            if b:
                bi, bc, bm = unpack_slot(b)
                self.inventory.set_hotbar_slot(drag_idx, bi, bc, meta=bm if bm else None)
            else:
                self.inventory.set_hotbar_slot(drag_idx, None, 0)
            if a:
                ai, ac, am = unpack_slot(a)
                self.inventory.set_hotbar_slot(drop_idx, ai, ac, meta=am if am else None)
            else:
                self.inventory.set_hotbar_slot(drop_idx, None, 0)
        elif drag_src == 'hotbar' and drop_src == 'equip':
            item_def = ITEM_DEFS.get(drag_item, {})
            if item_def.get('slot') == drop_idx:
                old_eq = self.inventory.equipment.get(drop_idx)
                old_meta = dict(self.inventory.equipment_meta.get(drop_idx, {}))
                self.inventory.equipment[drop_idx] = drag_item
                if drag_meta:
                    self.inventory.equipment_meta[drop_idx] = dict(drag_meta)
                else:
                    self.inventory.equipment_meta.pop(drop_idx, None)
                if old_eq:
                    self.inventory.set_hotbar_slot(drag_idx, old_eq, 1, meta=old_meta if old_meta else None)
                else:
                    self.inventory.set_hotbar_slot(drag_idx, None, 0)
        elif drag_src == 'inv' and drop_src == 'equip':
            item_def = ITEM_DEFS.get(drag_item, {})
            if item_def.get('slot') == drop_idx:
                old_eq = self.inventory.equipment.get(drop_idx)
                old_meta = dict(self.inventory.equipment_meta.get(drop_idx, {}))
                self.inventory.equipment[drop_idx] = drag_item
                if drag_meta:
                    self.inventory.equipment_meta[drop_idx] = dict(drag_meta)
                else:
                    self.inventory.equipment_meta.pop(drop_idx, None)
                if old_eq:
                    self.inventory.set_slot(drag_idx, old_eq, 1, meta=old_meta if old_meta else None)
                else:
                    self.inventory.remove_item(drag_idx, drag_count)
        elif drag_src == 'equip' and drop_src == 'inv':
            drop_data = self.inventory.get_slot(drop_idx)
            eq_meta = dict(self.inventory.equipment_meta.get(drag_idx, {}))
            if drop_data is None:
                self.inventory.set_slot(drop_idx, drag_item, 1, meta=eq_meta if eq_meta else None)
                self.inventory.equipment[drag_idx] = None
                self.inventory.equipment_meta.pop(drag_idx, None)
            else:
                drop_item_def = ITEM_DEFS.get(drop_data[0], {})
                if drop_item_def.get('slot') == drag_idx:
                    di, dc, dm = unpack_slot(drop_data)
                    self.inventory.equipment[drag_idx] = di
                    if dm:
                        self.inventory.equipment_meta[drag_idx] = dict(dm)
                    else:
                        self.inventory.equipment_meta.pop(drag_idx, None)
                    self.inventory.set_slot(drop_idx, drag_item, 1, meta=eq_meta if eq_meta else None)
                else:
                    leftover = self.inventory.add_item(drag_item, 1, slot_meta=eq_meta if eq_meta else None)
                    if leftover == 0:
                        self.inventory.equipment[drag_idx] = None
                        self.inventory.equipment_meta.pop(drag_idx, None)
        elif drag_src == 'equip' and drop_src == 'hotbar':
            drop_data = self.inventory.get_hotbar_slot(drop_idx)
            eq_meta = dict(self.inventory.equipment_meta.get(drag_idx, {}))
            if drop_data is None:
                self.inventory.set_hotbar_slot(drop_idx, drag_item, 1, meta=eq_meta if eq_meta else None)
                self.inventory.equipment[drag_idx] = None
                self.inventory.equipment_meta.pop(drag_idx, None)
            else:
                drop_item_def = ITEM_DEFS.get(drop_data[0], {})
                if drop_item_def.get('slot') == drag_idx:
                    di, dc, dm = unpack_slot(drop_data)
                    self.inventory.equipment[drag_idx] = di
                    if dm:
                        self.inventory.equipment_meta[drag_idx] = dict(dm)
                    else:
                        self.inventory.equipment_meta.pop(drag_idx, None)
                    self.inventory.set_hotbar_slot(drop_idx, drag_item, 1, meta=eq_meta if eq_meta else None)
        elif drag_src == 'equip' and drop_src == 'equip':
            if drag_idx == drop_idx:
                return
            # Can't swap between different equipment slot types
        self.save_inventory_state()

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
        """Return manual target if valid/in-range, else nearest in-range live mob.
        Range matches the active weapon's attack_range_tiles (equipped or selected hotbar weapon)."""
        px, py = self.player.hit_rect.centerx, self.player.hit_rect.centery
        best = None
        pr = self.player.get_effective_attack_range()
        if pr <= 0:
            return None
        best_d_sq = pr * pr
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

    def _spawn_player_projectile(self, target):
        """Fire a projectile locked to the chosen auto-target."""
        start = vec(self.player.hit_rect.centerx, self.player.hit_rect.centery)
        Projectile(
            self,
            start_pos=start,
            target=target,
            damage=self._roll_player_hit_damage(),
            max_range_px=self.player.get_effective_attack_range(),
        )

    def _roll_player_hit_damage(self):
        """Base weapon damage (Vulcan burn is DoT on hit, not rolled here)."""
        dmg = self.player.get_effective_damage()
        return max(1, int(dmg))

    def apply_rune_on_hit_effects(self, primary_mob, damage_dealt):
        """Vulcan burn, Neptune slow, Jupiter chain — always apply when a secondary target exists for chain."""
        wid = self.inventory.get_effective_weapon_item_id()
        if not wid or primary_mob is None:
            return
        item = ITEM_DEFS.get(wid, {})
        rune_id = self.inventory.get_infused_rune_for_weapon_id(wid)
        eff = resolve_on_hit_effect(item, rune_id)
        kind = eff.get('kind')
        if kind == 'burn_on_hit':
            primary_mob.apply_rune_burn(
                int(eff.get('duration_ms', 4000)),
                int(eff.get('tick_interval_ms', 500)),
                int(eff.get('damage_per_tick', 4)),
            )
        elif kind == 'slow_on_hit':
            primary_mob.apply_rune_slow(
                int(eff.get('duration_ms', 2500)),
                float(eff.get('move_mult', 0.55)),
            )
        elif kind == 'chain_damage':
            self._apply_jupiter_chain_damage(primary_mob, damage_dealt, eff)
        elif kind == 'lifesteal_on_hit':
            ch = float(eff.get('chance', 1.0))
            if random.random() < max(0.0, min(1.0, ch)):
                frac = float(eff.get('damage_fraction', 0.15))
                heal = max(1, int(damage_dealt * max(0.0, frac)))
                eff_max = self.player.get_effective_max_health()
                old_hp = self.player.health
                self.player.health = min(eff_max, old_hp + heal)
                if self.player.health > old_hp:
                    self.add_damage_number(
                        self.player.hit_rect.center,
                        self.player.health - old_hp,
                        color=(120, 220, 160),
                    )

    def add_chain_lightning(self, world_a, world_b):
        self.chain_lightning_fx.append({
            'a': vec(world_a[0], world_a[1]),
            'b': vec(world_b[0], world_b[1]),
            'age_ms': 0,
            'life_ms': 400,
        })

    def _apply_jupiter_chain_damage(self, primary_mob, damage_dealt, eff):
        radius = float(eff.get('radius_tiles', 2.0))
        frac = float(eff.get('damage_fraction', 0.35))
        r_sq = radius * radius
        px, py = primary_mob.tile_x, primary_mob.tile_y
        best = None
        best_d = None
        for o in self.all_mobs:
            if o is primary_mob or getattr(o, 'state', None) == 'dead':
                continue
            dx = float(o.tile_x - px)
            dy = float(o.tile_y - py)
            d_sq = dx * dx + dy * dy
            if d_sq <= r_sq and d_sq > 0:
                if best_d is None or d_sq < best_d:
                    best_d = d_sq
                    best = o
        if best is not None:
            splash = max(1, int(damage_dealt * frac))
            self.add_chain_lightning(primary_mob.hit_rect.center, best.hit_rect.center)
            best.hurt(splash)


# --- Refactored subsystem bindings (structure-only, no gameplay changes) ---
Game.load_data = world_system.load_data
Game.is_walkable = world_system.is_walkable
Game.tile_blocks_line_of_sight = world_system.tile_blocks_line_of_sight
Game.has_line_of_sight_tiles = world_system.has_line_of_sight_tiles
Game.load_level = world_system.load_level
Game._compute_reachable_tiles_from = world_system._compute_reachable_tiles_from
Game.go_to_next_level = world_system.go_to_next_level
Game.go_to_prev_level = world_system.go_to_prev_level

Game.get_skill_attr_bonuses = progression_system.get_skill_attr_bonuses
Game._recompute_player_base_attrs_from_progression = progression_system._recompute_player_base_attrs_from_progression
Game._apply_starting_gear_for_class = progression_system._apply_starting_gear_for_class
Game.add_player_xp = progression_system.add_player_xp
Game.try_purchase_skill_node = progression_system.try_purchase_skill_node
Game.on_mob_kill = progression_system.on_mob_kill
Game._apply_death_penalties = progression_system._apply_death_penalties

Game.init_save_system = save_system.init_save_system
Game.set_active_world = save_system.set_active_world
Game._load_world_state_from_save = save_system._load_world_state_from_save
Game.create_new_world = save_system.create_new_world
Game.list_save_files = save_system.list_save_files
Game.delete_save = save_system.delete_save
Game.select_world = save_system.select_world
Game._snapshot_current_level_mobs = save_system._snapshot_current_level_mobs
Game.save_inventory_state = save_system.save_inventory_state
Game.load_inventory_state = save_system.load_inventory_state
Game._apply_starts_known_recipes = save_system._apply_starts_known_recipes
Game._sync_discovered_recipes_from_inventory = save_system._sync_discovered_recipes_from_inventory
Game.on_items_gained = save_system.on_items_gained
Game._initialize_player_inventory = save_system._initialize_player_inventory
Game._get_save_class_name = save_system._get_save_class_name


if __name__ == "__main__":
    g = Game()
    while g.running:
        g.new()
    pg.quit()
