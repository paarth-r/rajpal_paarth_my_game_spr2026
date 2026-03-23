import pygame as pg
import json
import random
from pygame.sprite import Sprite
from settings import *
from utils import *
from os import path

vec = pg.math.Vector2

_DATA_DIR = path.join(path.dirname(__file__), 'data')

def load_mob_defs():
    fp = path.join(_DATA_DIR, 'mobs.json')
    with open(fp, 'r') as f:
        return json.load(f)

MOB_DEFS = load_mob_defs()


def collide_hit_rect(one, two):
    return one.hit_rect.colliderect(two.rect)


def collide_with_walls(sprite, group, dir):
    if dir == 'x':
        hits = pg.sprite.spritecollide(sprite, group, False, collide_hit_rect)
        if hits:
            if hits[0].rect.centerx > sprite.hit_rect.centerx:
                sprite.pos.x = hits[0].rect.left - sprite.hit_rect.width / 2
            if hits[0].rect.centerx < sprite.hit_rect.centerx:
                sprite.pos.x = hits[0].rect.right + sprite.hit_rect.width / 2
            sprite.vel.x = 0
            sprite.hit_rect.centerx = sprite.pos.x
    if dir == 'y':
        hits = pg.sprite.spritecollide(sprite, group, False, collide_hit_rect)
        if hits:
            if hits[0].rect.centery > sprite.hit_rect.centery:
                sprite.pos.y = hits[0].rect.top - sprite.hit_rect.height / 2
            if hits[0].rect.centery < sprite.hit_rect.centery:
                sprite.pos.y = hits[0].rect.bottom + sprite.hit_rect.height / 2
            sprite.vel.y = 0
            sprite.hit_rect.centery = sprite.pos.y


class Player(Sprite):
    def __init__(self, game, x, y):
        self.groups = game.all_sprites
        Sprite.__init__(self, self.groups)
        self.game = game
        self.spritesheet = Spritesheet(path.join(self.game.img_dir, "knight.png"))
        self.load_images()
        self.facing = 'down'
        self.image = self.move_frames['down'][0]
        self.rect = self.image.get_rect()
        self.vel = vec(0, 0)
        self.tile_x, self.tile_y = x, y
        self.pos = vec(self.tile_x * TILESIZE + TILESIZE / 2, self.tile_y * TILESIZE + TILESIZE / 2)
        self.hit_rect = PLAYER_HIT_RECT.copy()
        self.hit_rect.center = self.pos
        self.moving = False
        self.attacking = False
        self.last_update = 0
        self.current_frame = 0
        self.base_attrs = dict(PLAYER_BASE_ATTRS)
        self.health = PLAYER_MAX_HEALTH
        self.max_health = PLAYER_MAX_HEALTH
        self.last_hurt = 0
        self.attack_hit_dealt = False
        self.last_attack_end_time = 0
        # Move queue: list of (dx, dy); executed at speed (smooth slide per tile)
        self.move_queue = []
        self.move_state = 'idle'  # 'idle' or 'sliding'
        self.slide_from = None
        self.slide_to = None
        self.slide_to_tile = None  # (nx, ny) – commit tile only when slide completes
        self.slide_start_time = 0
        self.slide_duration_ms = max(50, 1000 * TILESIZE / PLAYER_SPEED)  # ms per tile

    def queue_move(self, dx, dy):
        """Add one tile step to the queue (from key hold)."""
        if self.attacking or len(self.move_queue) >= PLAYER_MOVE_QUEUE_MAX:
            return
        self.move_queue.append((dx, dy))

    def clear_move_queue(self):
        self.move_queue.clear()

    def get_path_tiles(self):
        """List of (tile_x, tile_y) for path to draw: current tile + queued steps (outlined)."""
        if self.move_state == 'sliding' and self.slide_to_tile is not None:
            path = [(self.tile_x, self.tile_y), self.slide_to_tile]
            tx, ty = self.slide_to_tile
        else:
            path = [(self.tile_x, self.tile_y)]
            tx, ty = self.tile_x, self.tile_y
        for (dx, dy) in self.move_queue:
            tx, ty = tx + dx, ty + dy
            path.append((tx, ty))
        return path

    def try_move_tile(self, dx, dy):
        """Execute one tile step if walkable (used when consuming from queue). Returns True if moved."""
        if self.attacking:
            return False
        nx, ny = self.tile_x + dx, self.tile_y + dy
        if not self.game.is_walkable(nx, ny):
            return False
        self.tile_x, self.tile_y = nx, ny
        self.pos = vec(self.tile_x * TILESIZE + TILESIZE / 2, self.tile_y * TILESIZE + TILESIZE / 2)
        if dx < 0:
            self.facing = 'left'
        elif dx > 0:
            self.facing = 'right'
        elif dy < 0:
            self.facing = 'up'
        elif dy > 0:
            self.facing = 'down'
        return True

    def load_images(self):
        fw = TILESIZE
        fh = TILESIZE
        self.move_frames = {
            'down':  [self.spritesheet.get_image(i * fw, 0 * fh, fw, fh) for i in range(5)],
            'up':    [self.spritesheet.get_image(i * fw, 1 * fh, fw, fh) for i in range(5)],
            'left':  [self.spritesheet.get_image(i * fw, 2 * fh, fw, fh) for i in range(5)],
            'right': [self.spritesheet.get_image(i * fw, 3 * fh, fw, fh) for i in range(5)],
        }
        self.attack_frames = {
            'down':  [self.spritesheet.get_image(i * fw, 4 * fh, fw, fh) for i in range(5)],
            'up':    [self.spritesheet.get_image(i * fw, 5 * fh, fw, fh) for i in range(5)],
            'left':  [self.spritesheet.get_image(i * fw, 6 * fh, fw, fh) for i in range(5)],
            'right': [self.spritesheet.get_image(i * fw, 7 * fh, fw, fh) for i in range(5)],
        }

    def attack(self):
        now = pg.time.get_ticks()
        weapon_id = None
        if hasattr(self.game, 'inventory'):
            weapon_id = self.game.inventory.equipment.get('weapon')
        # Cannot attack unarmed.
        if weapon_id is None:
            return
        if self.attacking:
            return
        if (now - self.last_attack_end_time) < self.get_attack_cooldown_ms():
            return
        self.attacking = True
        self.attack_hit_dealt = False
        self.current_frame = 0
        self.last_update = pg.time.get_ticks()
        self.image = self.attack_frames[self.facing][0]

    def get_effective_attrs(self):
        """Base attrs + equipment bonuses."""
        attrs = dict(self.base_attrs)
        if hasattr(self.game, 'inventory'):
            for stat, val in self.game.inventory.get_equipment_stat_bonuses().items():
                attrs[stat] = attrs.get(stat, 0) + val
        return attrs

    def get_effective_max_health(self):
        attrs = self.get_effective_attrs()
        return PLAYER_MAX_HEALTH + attrs.get('health', 0) * HEALTH_ATTR_HP_BONUS

    def get_effective_damage(self):
        if hasattr(self.game, 'inventory'):
            return self.game.inventory.get_weapon_damage(self.get_effective_attrs())
        return PLAYER_ATTACK_DAMAGE

    def recalc_stats(self):
        """Recalculate derived stats from attributes (call after equip changes)."""
        new_max = self.get_effective_max_health()
        if new_max != self.max_health:
            delta = new_max - self.max_health
            self.max_health = new_max
            if delta > 0:
                self.health = min(self.health + delta, self.max_health)
            else:
                self.health = min(self.health, self.max_health)

    def get_attack_cooldown_remaining(self):
        """Ms until next attack allowed; 0 if ready. While attacking, returns full cooldown (bar shows 'recharging')."""
        now = pg.time.get_ticks()
        cooldown = self.get_attack_cooldown_ms()
        if self.attacking:
            return cooldown  # show as recharging until animation + cooldown
        elapsed = now - self.last_attack_end_time
        return max(0, cooldown - elapsed)

    def get_attack_cooldown_ms(self):
        if hasattr(self.game, 'inventory'):
            return self.game.inventory.get_weapon_cooldown_ms(PLAYER_ATTACK_COOLDOWN_MS)
        return PLAYER_ATTACK_COOLDOWN_MS

    def get_attack_rect(self):
        """Rect in front of player used for hitting mobs. Only valid while attacking."""
        if not self.attacking:
            return None
        pad = PLAYER_ATTACK_RANGE
        r = self.hit_rect.inflate(4, 4).copy()
        if self.facing == 'left':
            r.left = self.hit_rect.left - pad
            r.width = pad
        elif self.facing == 'right':
            r.left = self.hit_rect.right
            r.width = pad
        elif self.facing == 'up':
            r.bottom = self.hit_rect.top
            r.height = pad
        elif self.facing == 'down':
            r.top = self.hit_rect.bottom
            r.height = pad
        return r

    def animate(self):
        now = pg.time.get_ticks()
        if self.attacking:
            if now - self.last_update > PLAYER_ATTACK_SPEED:
                self.last_update = now
                self.current_frame += 1
                if self.current_frame >= len(self.attack_frames[self.facing]):
                    self.attacking = False
                    self.attack_hit_dealt = False
                    self.current_frame = 0
                    self.last_attack_end_time = pg.time.get_ticks()
                    self.image = self.move_frames[self.facing][0]
                else:
                    self.image = self.attack_frames[self.facing][self.current_frame]
                self.rect = self.image.get_rect()
                self.rect.center = self.hit_rect.center
        elif self.moving:
            if now - self.last_update > PLAYER_ANIM_SPEED:
                self.last_update = now
                self.current_frame = (self.current_frame + 1) % len(self.move_frames[self.facing])
                self.image = self.move_frames[self.facing][self.current_frame]
                self.rect = self.image.get_rect()
                self.rect.center = self.hit_rect.center
        else:
            if now - self.last_update > 350:
                self.last_update = now
                self.image = self.move_frames[self.facing][0]
                self.rect = self.image.get_rect()
                self.rect.center = self.hit_rect.center

    def state_check(self):
        self.moving = self.move_state == 'sliding' or len(self.move_queue) > 0

    def hurt(self, damage):
        now = pg.time.get_ticks()
        if now - self.last_hurt >= PLAYER_HURT_COOLDOWN:
            self.health = max(0, self.health - damage)
            self.last_hurt = now

    def update(self):
        now = pg.time.get_ticks()
        if self.move_state == 'sliding':
            t = (now - self.slide_start_time) / self.slide_duration_ms
            if t >= 1:
                # Commit tile only when slide completes – snap to exact center
                if self.slide_to_tile is not None:
                    self.tile_x, self.tile_y = self.slide_to_tile
                self.pos = vec(self.tile_x * TILESIZE + TILESIZE / 2, self.tile_y * TILESIZE + TILESIZE / 2)
                self.slide_to_tile = None
                self.hit_rect.center = self.pos
                self.rect.center = self.hit_rect.center
                self.move_state = 'idle'
                self._start_next_queued_move()
            else:
                self.pos = self.slide_from + (self.slide_to - self.slide_from) * t
                self.hit_rect.center = self.pos
                self.rect.center = self.hit_rect.center
        else:
            self._start_next_queued_move()
        self.state_check()
        self.animate()
        if self.move_state != 'sliding':
            self.hit_rect.center = self.pos
            self.rect.center = self.hit_rect.center

    def _start_next_queued_move(self):
        if self.move_state != 'idle' or self.attacking or not self.move_queue:
            return
        dx, dy = self.move_queue.pop(0)
        nx, ny = self.tile_x + dx, self.tile_y + dy
        if not self.game.is_walkable(nx, ny):
            return
        if dx < 0:
            self.facing = 'left'
        elif dx > 0:
            self.facing = 'right'
        elif dy < 0:
            self.facing = 'up'
        elif dy > 0:
            self.facing = 'down'
        self.slide_from = vec(self.pos.x, self.pos.y)
        self.slide_to = vec(nx * TILESIZE + TILESIZE / 2, ny * TILESIZE + TILESIZE / 2)
        self.slide_to_tile = (nx, ny)  # commit tile only when slide completes
        self.slide_start_time = pg.time.get_ticks()
        self.move_state = 'sliding'


def collide_mob_walls(sprite, group, dir):
    """Mob vs walls using hit_rect."""
    if dir == 'x':
        hits = pg.sprite.spritecollide(sprite, group, False, collide_hit_rect)
        if hits:
            if hits[0].rect.centerx > sprite.hit_rect.centerx:
                sprite.pos.x = hits[0].rect.left - sprite.hit_rect.width / 2
            else:
                sprite.pos.x = hits[0].rect.right + sprite.hit_rect.width / 2
            sprite.vel.x = 0
            sprite.hit_rect.centerx = sprite.pos.x
    if dir == 'y':
        hits = pg.sprite.spritecollide(sprite, group, False, collide_hit_rect)
        if hits:
            if hits[0].rect.centery > sprite.hit_rect.centery:
                sprite.pos.y = hits[0].rect.top - sprite.hit_rect.height / 2
            else:
                sprite.pos.y = hits[0].rect.bottom + sprite.hit_rect.height / 2
            sprite.vel.y = 0
            sprite.hit_rect.centery = sprite.pos.y


def _scale_mob_frame(surf):
    """Scale 64x64 frame to TILESIZE x TILESIZE (same size as player)."""
    if surf.get_size() == (TILESIZE, TILESIZE):
        return surf
    return pg.transform.scale(surf, (TILESIZE, TILESIZE))


class Mob(Sprite):
    # Mob visuals/stats are data-driven by MOB_DEFS (spritesheet rows: idle, walk, attack, death).
    def __init__(self, game, x, y, mob_type='statue'):
        self.groups = game.all_sprites, game.all_mobs
        Sprite.__init__(self, self.groups)
        self.game = game
        self.mob_type = mob_type
        d = MOB_DEFS.get(mob_type, MOB_DEFS.get('statue', {}))
        self.hp = d.get('hp', MOB_HP)
        self.mob_damage = d.get('damage', MOB_DAMAGE)
        self.mob_attack_cooldown = d.get('attack_cooldown_ms', MOB_ATTACK_COOLDOWN)
        self.mob_attack_range_tiles = d.get('attack_range_tiles', MOB_ATTACK_RANGE / TILESIZE)
        self.mob_attack_anim_speed = d.get('attack_anim_speed_ms', MOB_ATTACK_ANIM_SPEED)
        self.mob_anim_speed = d.get('anim_speed_ms', MOB_ANIM_SPEED)
        self.mob_move_delay = d.get('move_delay_ms', MOB_MOVE_DELAY)
        self.mob_slide_duration = d.get('slide_duration_ms', MOB_SLIDE_DURATION_MS)
        self.mob_chase_range_tiles = d.get('chase_range_tiles', MOB_CHASE_RANGE / TILESIZE)
        self.mob_activation_range_tiles = d.get('activation_range_tiles', MOB_ACTIVATION_RANGE_TILES)
        self.mob_hit_frame = d.get('hit_frame', 3)
        self.idle_row = d.get('idle_row', 0)
        self.walk_row = d.get('walk_row', 1)
        self.attack_row = d.get('attack_row', 2)
        self.death_row = d.get('death_row', 3)
        self.heal_row = d.get('heal_row', None)
        self.heal_frame_count = d.get('heal_frames', 0)
        self.heal_once_amount = d.get('heal_once_amount', 0)
        self.heal_threshold_pct = float(d.get('heal_threshold_pct', 0.5))
        self.heal_used = False

        w = d.get('frame_w', MOB_FRAME_W)
        h = d.get('frame_h', MOB_FRAME_H)
        sprite_name = d.get('spritesheet', 'statue.png')
        sprite_path = path.join(game.img_dir, sprite_name)
        idle_n = d.get('idle_frames', 1)
        walk_n = d.get('walk_frames', 1)
        atk_n = d.get('attack_frames', 1)
        death_n = d.get('death_frames', 1)

        if path.exists(sprite_path):
            sheet = Spritesheet(sprite_path)
            raw_idle = [sheet.get_image(i * w, self.idle_row * h, w, h) for i in range(idle_n)]
            raw_walk = [sheet.get_image(i * w, self.walk_row * h, w, h) for i in range(walk_n)]
            raw_attack = [sheet.get_image(i * w, self.attack_row * h, w, h) for i in range(atk_n)]
            raw_death = [sheet.get_image(i * w, self.death_row * h, w, h) for i in range(death_n)]
            self.idle_frames = [_scale_mob_frame(f) for f in raw_idle]
            self.walk_frames = [_scale_mob_frame(f) for f in raw_walk]
            self.attack_frames = [_scale_mob_frame(f) for f in raw_attack]
            self.death_frames = [_scale_mob_frame(f) for f in raw_death]
            if self.heal_row is not None and self.heal_frame_count > 0:
                raw_heal = [sheet.get_image(i * w, self.heal_row * h, w, h) for i in range(self.heal_frame_count)]
                self.heal_frames = [_scale_mob_frame(f) for f in raw_heal]
            else:
                self.heal_frames = []
            self.image = self.idle_frames[0] if self.idle_frames else pg.Surface((TILESIZE, TILESIZE))
        else:
            self.image = pg.Surface((TILESIZE, TILESIZE))
            self.image.fill(DARKRED)
            self.idle_frames = self.walk_frames = [self.image]
            self.attack_frames = self.death_frames = [self.image]
            self.heal_frames = [self.image]
        self.rect = self.image.get_rect()
        self.tile_x, self.tile_y = x, y
        self.pos = vec(self.tile_x * TILESIZE + TILESIZE / 2, self.tile_y * TILESIZE + TILESIZE / 2)
        self.vel = vec(0, 0)
        self.hit_rect = MOB_HIT_RECT.copy()
        self.hit_rect.center = self.pos
        self.rect.center = self.hit_rect.center
        self.speed = d.get('speed', MOB_SPEED)
        self.health = self.hp
        self.max_health = self.hp
        self.last_attack = 0
        self.last_move = pg.time.get_ticks()
        self.state = 'inactive'  # inactive -> idle still (row 0 frame 0); activate when player in 5 block radius
        self.anim_frame = 0
        self.last_anim = pg.time.get_ticks()
        self.attack_damage_dealt = False
        self.facing_left = False
        self._cached_image = None
        self._cache_key = None  # (state, anim_frame, facing_left)
        # Smooth tile-to-tile movement (like player slide)
        self.move_target = None  # vec tile center we are sliding to
        self.slide_from = None
        self.slide_start_time = 0
        self.slide_duration_ms = self.mob_slide_duration

    def _image_for_frame(self, frame_surf):
        """Return frame with flip applied; cache result to avoid flicker from new surfaces every frame."""
        if frame_surf is None:
            return self.image
        if self.facing_left:
            return pg.transform.flip(frame_surf, True, False)
        return frame_surf

    def _ensure_rect_valid(self):
        """Prevent disappearing: always keep rect drawable (non-zero size, correct center)."""
        if self.rect is None:
            return
        if self.rect.width <= 0 or self.rect.height <= 0:
            self.rect.size = (TILESIZE, TILESIZE)
        self.rect.center = self.hit_rect.center

    def _update_image_cache(self, frame_surf):
        """Set self.image from frame (with flip); keep rect size in sync. Skip if frame is blank/invalid."""
        if frame_surf is None or frame_surf.get_width() <= 0 or frame_surf.get_height() <= 0:
            return
        self.image = self._image_for_frame(frame_surf)
        if self.rect is not None and self.image is not None:
            old_center = self.rect.center
            self.rect.size = self.image.get_size()
            if self.rect.width <= 0 or self.rect.height <= 0:
                self.rect.size = (TILESIZE, TILESIZE)
            self.rect.center = old_center

    def try_move_tile(self, dx, dy):
        """Begin moving one tile in (dx, dy) if walkable and not onto player.

        Matches player-style slide: we interpolate from current position to tile center over a
        fixed duration (slide_duration_ms), instead of teleporting or using raw dt*speed.
        """
        # Don't start a new move while already gliding
        if self.move_target is not None:
            return False
        nx, ny = self.tile_x + dx, self.tile_y + dy
        if not self.game.is_walkable(nx, ny):
            return False
        if (nx, ny) == (self.game.player.tile_x, self.game.player.tile_y):
            return False
        # Commit logical tile immediately so game logic knows which tile mob is on
        self.tile_x, self.tile_y = nx, ny
        target = vec(self.tile_x * TILESIZE + TILESIZE / 2,
                     self.tile_y * TILESIZE + TILESIZE / 2)
        self.slide_from = vec(self.pos.x, self.pos.y)
        self.move_target = target
        self.slide_start_time = pg.time.get_ticks()
        if dx != 0:
            self.facing_left = dx < 0
        return True

    def hurt(self, damage):
        if self.state == 'dead':
            return
        self.health = max(0, self.health - damage)
        if self.health <= 0:
            self.state = 'dead'
            self.anim_frame = 0
            self.last_anim = pg.time.get_ticks()
            self.vel = vec(0, 0)
            self._update_image_cache(self.death_frames[0])

    def update(self):
        now = pg.time.get_ticks()
        player = self.game.player
        px, py = player.tile_x, player.tile_y
        dx_tile = px - self.tile_x
        dy_tile = py - self.tile_y
        dist_sq_tiles = dx_tile * dx_tile + dy_tile * dy_tile
        activation_radius_sq = self.mob_activation_range_tiles * self.mob_activation_range_tiles

        # Inactive: stand as "idle still" (top-left frame) until player within 5 block radius
        if self.state == 'inactive':
            if dist_sq_tiles <= activation_radius_sq:
                self.state = 'idle'
                self.anim_frame = 0
                self.last_anim = now
            else:
                self._update_image_cache(self.idle_frames[0])
                self.hit_rect.center = self.pos
                self.rect.center = self.hit_rect.center
                self._ensure_rect_valid()
                return

        if self.state == 'dead':
            if now - self.last_anim > self.mob_anim_speed:
                self.last_anim = now
                self.anim_frame += 1
                if self.anim_frame >= len(self.death_frames):
                    drops = roll_mob_drops(self.mob_type)
                    for item_id, count in drops:
                        ox = random.randint(-8, 8)
                        oy = random.randint(-8, 8)
                        DroppedItem(self.game, self.pos.x + ox, self.pos.y + oy, item_id, count)
                    self.kill()
                    return
                self._update_image_cache(self.death_frames[self.anim_frame])
            self.rect.center = self.hit_rect.center
            self._ensure_rect_valid()
            return

        # Optional one-time combat heal (used by shadow assassin).
        if (
            self.state not in ('attack', 'heal')
            and not self.heal_used
            and self.heal_once_amount > 0
            and self.heal_frames
            and dist_sq_tiles > 0
            and dist_sq_tiles <= (self.mob_chase_range_tiles ** 2)
            and self.health <= int(self.max_health * self.heal_threshold_pct)
        ):
            self.heal_used = True
            self.health = min(self.max_health, self.health + self.heal_once_amount)
            self.state = 'heal'
            self.anim_frame = 0
            self.last_anim = now
            self._update_image_cache(self.heal_frames[0])
            self.rect.center = self.hit_rect.center
            self._ensure_rect_valid()
            return

        if self.state == 'heal':
            if now - self.last_anim > self.mob_anim_speed:
                self.last_anim = now
                self.anim_frame += 1
                if self.anim_frame >= len(self.heal_frames):
                    self.state = 'idle'
                    self.anim_frame = 0
                    self._update_image_cache(self.idle_frames[0])
                else:
                    self._update_image_cache(self.heal_frames[self.anim_frame])
            self.rect.center = self.hit_rect.center
            self._ensure_rect_valid()
            return

        in_chase = dist_sq_tiles <= (self.mob_chase_range_tiles ** 2) and dist_sq_tiles > 0
        adjacent = (abs(dx_tile) + abs(dy_tile)) == 1
        in_attack_range = dist_sq_tiles <= (self.mob_attack_range_tiles ** 2)

        if self.state == 'attack':
            if now - self.last_anim > self.mob_attack_anim_speed:
                self.last_anim = now
                self.anim_frame += 1
                # Frame 3 of the attack (index 3) is the actual hit
                if self.anim_frame == self.mob_hit_frame and not self.attack_damage_dealt:
                    if in_attack_range:
                        player.hurt(self.mob_damage)
                    self.attack_damage_dealt = True
                if self.anim_frame >= len(self.attack_frames):
                    self.state = 'idle'
                    self.anim_frame = 0
                    self.attack_damage_dealt = False
                    self._update_image_cache(self.idle_frames[0])  # avoid blank/wrong frame after attack
                else:
                    self._update_image_cache(self.attack_frames[self.anim_frame])
            self.rect.center = self.hit_rect.center
            self._ensure_rect_valid()
            return

        if adjacent and in_attack_range and (now - self.last_attack) >= self.mob_attack_cooldown:
            # Briefly show "blade-ready" stance before attack frames when available.
            if self.idle_frames:
                self._update_image_cache(self.idle_frames[0])
            self.state = 'attack'
            self.facing_left = px < self.tile_x
            self.anim_frame = 0
            self.last_anim = now
            self.last_attack = now
            self.attack_damage_dealt = False
            self._update_image_cache(self.attack_frames[0])
            self.rect.center = self.hit_rect.center
            self._ensure_rect_valid()
            return

        # Tile-based move: one step every MOB_MOVE_DELAY toward player
        if in_chase and self.move_target is None and (now - self.last_move) >= self.mob_move_delay:
            self.last_move = now
            if adjacent:
                pass  # next tick can attack
            else:
                step_x = 0 if dx_tile == 0 else (1 if dx_tile > 0 else -1)
                step_y = 0 if dy_tile == 0 else (1 if dy_tile > 0 else -1)
                if abs(dx_tile) >= abs(dy_tile):
                    self.try_move_tile(step_x, 0) or self.try_move_tile(0, step_y)
                else:
                    self.try_move_tile(0, step_y) or self.try_move_tile(step_x, 0)

        # Smooth slide toward tile center with ease-in-out (slow start/end, clearer which tile they're on)
        if self.move_target is not None and self.slide_from is not None:
            raw_t = (now - self.slide_start_time) / self.slide_duration_ms
            if raw_t >= 1:
                self.pos = self.move_target
                self.move_target = None
                self.slide_from = None
            else:
                # Smoothstep: eases in and out so motion isn't snappy or floaty
                t = raw_t * raw_t * (3 - 2 * raw_t)
                self.pos = self.slide_from + (self.move_target - self.slide_from) * t

        self.hit_rect.center = self.pos
        self.rect.center = self.hit_rect.center
        self._ensure_rect_valid()

        # Row 0 = idle (active), row 1 = walk; use walk when in chase and not adjacent
        if in_chase and not adjacent:
            self.state = 'walk'
        else:
            self.state = 'idle'
        if now - self.last_anim > self.mob_anim_speed:
            self.last_anim = now
            frames = self.walk_frames if self.state == 'walk' else self.idle_frames
            self.anim_frame = (self.anim_frame + 1) % len(frames)
            self._update_image_cache(frames[self.anim_frame])


class Wall(Sprite):
    def __init__(self, game, x, y):
        self.groups = game.all_sprites, game.all_walls
        Sprite.__init__(self, self.groups)
        self.game = game
        self.image = game.wall_img
        self.rect = self.image.get_rect()
        # Center on tile so wall aligns with player move grid (tile center = col*TILESIZE + TILESIZE/2)
        self.pos = vec(x * TILESIZE + TILESIZE / 2, y * TILESIZE + TILESIZE / 2)
        self.rect.center = self.pos

    def update(self):
        pass


class Coin(Sprite):
    def __init__(self, game, x, y):
        self.groups = game.all_sprites
        Sprite.__init__(self, self.groups)
        self.game = game
        self.image = pg.Surface((TILESIZE, TILESIZE))
        self.image.fill(GOLD)
        self.rect = self.image.get_rect()
        self.pos = vec(x * TILESIZE + TILESIZE / 2, y * TILESIZE + TILESIZE / 2)
        self.rect.center = self.pos

    def update(self):
        pass


class DroppedItem(Sprite):
    """An item sitting on the ground, auto-picked up when player walks over it."""

    def __init__(self, game, world_x, world_y, item_id, count=1):
        self.groups = game.all_sprites, game.all_drops
        Sprite.__init__(self, self.groups)
        self.game = game
        self.item_id = item_id
        self.count = count
        from inventory import ITEM_DEFS
        item_def = ITEM_DEFS.get(item_id, {})
        color = item_def.get('color', (200, 200, 200))
        size = max(8, TILESIZE // 2)
        self.image = pg.Surface((size, size), pg.SRCALPHA)
        pg.draw.rect(self.image, color, (0, 0, size, size))
        pg.draw.rect(self.image, WHITE, (0, 0, size, size), 1)
        self.rect = self.image.get_rect()
        self.pos = vec(world_x, world_y)
        self.rect.center = self.pos

    def update(self):
        player = self.game.player
        if self.rect.colliderect(player.hit_rect):
            leftover = self.game.inventory.add_item(self.item_id, self.count)
            if leftover < self.count:
                self.count = leftover
                if self.count <= 0:
                    self.kill()


def roll_mob_drops(mob_type_id):
    """Given a mob type id, roll drops from its drop table. Returns list of (item_id, count)."""
    mob_def = MOB_DEFS.get(mob_type_id, {})
    drops = mob_def.get('drops', [])
    result = []
    for drop in drops:
        if random.random() <= drop.get('chance', 0):
            lo, hi = drop.get('count', [1, 1])
            count = random.randint(lo, hi)
            if count > 0:
                result.append((drop['item_id'], count))
    return result
