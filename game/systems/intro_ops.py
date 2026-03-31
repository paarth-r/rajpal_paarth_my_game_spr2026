"""Intro/tutorial level: starter chest loot, exit gating, helpers. Boss content comes later."""
from progression import get_class_def
from inventory import ITEM_DEFS, EQUIPMENT_SLOTS

INTRO_LEVEL_NAME = 'intro.txt'

# Must match the `C` tile in levels/intro.txt (col, row).
STARTER_CHEST_TILES = {(13, 1)}


def is_intro_level(game):
    return getattr(game, 'current_level_name', None) == INTRO_LEVEL_NAME


def chest_storage_key(level_name, col, row):
    return f"{level_name}:{int(col)},{int(row)}"


def class_starter_loot_entries(class_id):
    """Replicate what _apply_starting_gear_for_class would grant, as bag items only."""
    c = get_class_def(class_id)
    if not c:
        return []
    si = c.get('starting_inventory', {})
    out = []
    for item_id, qty in si.get('items', {}).items():
        if item_id in ITEM_DEFS:
            out.append((item_id, int(qty)))
    for _slot, item_id in si.get('equipment', {}).items():
        if item_id in ITEM_DEFS:
            out.append((item_id, 1))
    return out


def loot_entries_for_intro_chest(game, col, row):
    """Return list of (item_id, count) for this chest, or None if not a scripted intro chest."""
    if not is_intro_level(game):
        return None
    if (col, row) in STARTER_CHEST_TILES:
        return class_starter_loot_entries(game.player_class_id)
    return None


def intro_starter_chest_opened(game):
    if not is_intro_level(game):
        return False
    oc = getattr(game, 'opened_chests', set())
    lv = getattr(game, 'current_level_name', None)
    for sx, sy in STARTER_CHEST_TILES:
        if chest_storage_key(lv, sx, sy) in oc:
            return True
    return False


def refresh_intro_exit_open(game):
    """Intro forward exit: starter chest opened, straw target defeated, skill point spent, no live mobs."""
    if not is_intro_level(game):
        return
    live = [
        m for m in game.all_mobs
        if getattr(m, 'state', None) != 'dead' and getattr(m, 'health', 0) > 0
    ]
    chest_ok = intro_starter_chest_opened(game)
    skill_ok = len(getattr(game, 'purchased_skill_nodes', set())) >= 1
    unlocked = chest_ok and skill_ok
    game.intro_exit_unlocked = unlocked
    game.level_exit_open = unlocked and len(live) == 0
