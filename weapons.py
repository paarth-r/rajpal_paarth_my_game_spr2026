"""Weapon-centric helpers (damage, cooldown, range, type checks)."""
from settings import (
    MIN_WEAPON_ATTACK_RANGE_TILES,
    PLAYER_ATTACK_COOLDOWN_MS,
    PLAYER_ATTACK_DAMAGE,
    PLAYER_DEFAULT_ATTACK_RANGE_TILES,
    RANGED_WEAPON_DAMAGE_MULT,
    TILESIZE,
)


def item_is_ranged_weapon(item_def):
    return item_def.get('type') == 'weapon' and item_def.get('weapon_type') == 'staff'


def weapon_cooldown_ms_for_item(item):
    if item.get('type') != 'weapon':
        return None
    bonus = int(item.get('attack_speed_bonus', 0))
    return max(80, int(PLAYER_ATTACK_COOLDOWN_MS + bonus))


def weapon_damage_from_attrs(item, player_attrs):
    base = item.get('base_damage', PLAYER_ATTACK_DAMAGE)
    strength = player_attrs.get('strength', 0)
    scaling_stat = item.get('scaling_stat', 'strength')
    scaling_factor = item.get('scaling_factor', 0.0)
    scaling_val = player_attrs.get(scaling_stat, 0)
    dmg = int(base * (1 + strength / 20) + scaling_val * scaling_factor)
    if item_is_ranged_weapon(item):
        dmg = max(1, int(round(dmg * RANGED_WEAPON_DAMAGE_MULT)))
    return dmg


def weapon_range_tiles(item):
    tiles = item.get('attack_range_tiles', PLAYER_DEFAULT_ATTACK_RANGE_TILES)
    try:
        tiles = float(tiles)
    except (TypeError, ValueError):
        tiles = float(PLAYER_DEFAULT_ATTACK_RANGE_TILES)
    return max(float(MIN_WEAPON_ATTACK_RANGE_TILES), tiles)


def weapon_range_px(item):
    return max(1, int(round(weapon_range_tiles(item) * TILESIZE)))

