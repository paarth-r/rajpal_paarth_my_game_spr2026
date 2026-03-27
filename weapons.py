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
    if item_def.get('type') != 'weapon':
        return False
    wt = item_def.get('weapon_type')
    return wt in ('staff', 'bow')


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


def resolve_on_hit_effect(item_def, infused_rune_id):
    """Augmented weapons define rune_blessings per rune; else fall back to on_hit_effect."""
    if not item_def:
        return {}
    rb = item_def.get('rune_blessings', {})
    if infused_rune_id and infused_rune_id in rb:
        eff = rb[infused_rune_id].get('on_hit_effect')
        if eff:
            return eff
    return item_def.get('on_hit_effect', {}) or {}


def format_on_hit_effect_tooltip(eff):
    """One line describing proc for tooltips."""
    if not eff:
        return None
    kind = eff.get('kind')
    if kind == 'burn_on_hit':
        dur = int(eff.get('duration_ms', 4000)) / 1000.0
        ti = int(eff.get('tick_interval_ms', 500)) / 1000.0
        dpt = int(eff.get('damage_per_tick', 4))
        return f"On-hit: lingering fire — {dpt} damage every {ti:.1f}s for {dur:.1f}s (Vulcan)"
    if kind == 'slow_on_hit':
        dur = int(eff.get('duration_ms', 2000)) / 1000.0
        sm = int((1.0 - float(eff.get('move_mult', 0.55))) * 100)
        return f"On-hit: slow move speed by {sm}% for {dur:.1f}s (Neptune)"
    if kind == 'chain_damage':
        frac = int(float(eff.get('damage_fraction', 0.35)) * 100)
        rt = float(eff.get('radius_tiles', 2))
        return f"On-hit: arc {frac}% damage to nearest foe within {rt} tiles (Jupiter)"
    return None

