"""
Crafting definitions loaded from data/crafting.json.
"""
import json
from os import path

from inventory import ITEM_DEFS

_DATA_DIR = path.join(path.dirname(__file__), 'data')


def load_crafting():
    fp = path.join(_DATA_DIR, 'crafting.json')
    with open(fp, 'r') as f:
        return json.load(f)


CRAFTING = load_crafting()
WEAPON_TYPES = CRAFTING.get('weapon_types', {})
RECIPES = {r['id']: r for r in CRAFTING.get('recipes', [])}


def get_recipe_list():
    return list(CRAFTING.get('recipes', []))


def recipes_unlocked_by_item(item_id):
    """Recipe ids that discover when this item enters the inventory."""
    return [r['id'] for r in CRAFTING.get('recipes', []) if item_id in r.get('discover_on_items', [])]


def default_starts_known_recipe_ids():
    return {r['id'] for r in CRAFTING.get('recipes', []) if r.get('starts_known')}


def recipe_inputs_required(recipe):
    """Return dict slot -> item_id for non-null inputs."""
    inputs = recipe.get('inputs', {})
    return {k: v for k, v in inputs.items() if v is not None}


def normalize_craft_placement(val):
    """Craft slot may store item_id (legacy) or (item_id, count)."""
    if val is None:
        return None, 0
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return val[0], int(val[1])
    if isinstance(val, str):
        return val, 1
    return None, 0


def recipe_slot_quantity(recipe, slot_key):
    return max(1, int(recipe.get('input_counts', {}).get(slot_key, 1)))


def can_craft(inventory, recipe_id):
    """True if craft_placements match recipe (items already staged in craft UI)."""
    recipe = RECIPES.get(recipe_id)
    if recipe is None:
        return False
    placements = getattr(inventory, '_craft_placements', None)
    if placements is None:
        return False
    for slot_key, need_id in recipe.get('inputs', {}).items():
        if need_id is None:
            continue
        need_n = recipe_slot_quantity(recipe, slot_key)
        pid, pn = normalize_craft_placement(placements.get(slot_key))
        if pid != need_id or pn != need_n:
            return False
    return True


def try_finish_craft(inventory, recipe_id):
    """Consume staged items and add output. Returns True on success."""
    recipe = RECIPES.get(recipe_id)
    if recipe is None:
        return False
    if not can_craft(inventory, recipe_id):
        return False
    out = recipe.get('output', {})
    item_id = out.get('item_id')
    count = int(out.get('count', 1))
    if not item_id or item_id not in ITEM_DEFS:
        return False
    leftover = inventory.add_item(item_id, count)
    if leftover > 0:
        return False
    # Clear placements (items were already removed from bag when staged)
    inventory._craft_placements.clear()
    return True


def rune_item_ids():
    return {
        item_id for item_id, d in ITEM_DEFS.items()
        if d.get('type') == 'rune'
    }


def can_infuse_weapon(inventory):
    weapon_id = getattr(inventory, '_upgrade_weapon_item_id', None)
    rune_id = getattr(inventory, '_upgrade_rune_item_id', None)
    if not weapon_id or not rune_id:
        return False, "Place a weapon and a rune."
    w = ITEM_DEFS.get(weapon_id, {})
    r = ITEM_DEFS.get(rune_id, {})
    if w.get('type') != 'weapon':
        return False, "Upgrade slot requires a weapon."
    if r.get('type') != 'rune':
        return False, "Rune slot requires a rune."
    out_id = w.get('augment_output')
    if out_id not in ITEM_DEFS:
        return False, "This weapon has no augmented form."
    coin_cost = int(w.get('augment_coin_cost', 25))
    if inventory.count_item('gold_coin') < coin_cost:
        return False, f"Need {coin_cost} gold coins."
    return True, ""


def try_finish_infusion(inventory):
    ok, reason = can_infuse_weapon(inventory)
    if not ok:
        return False, reason
    weapon_id = inventory._upgrade_weapon_item_id
    w = ITEM_DEFS.get(weapon_id, {})
    out_id = w.get('augment_output')
    coin_cost = int(w.get('augment_coin_cost', 25))
    if inventory.remove_item_by_id('gold_coin', coin_cost) < coin_cost:
        return False, "Not enough gold coins."
    rune_id = inventory._upgrade_rune_item_id
    forged_meta = {'infused_rune': rune_id} if rune_id else None
    leftover = inventory.add_item(out_id, 1, slot_meta=forged_meta)
    if leftover > 0:
        # Refund coins; weapon/rune were never removed from forge slots (still staged).
        inventory.add_item('gold_coin', coin_cost)
        return False, "Inventory full — make space, then try again."
    inventory._upgrade_weapon_item_id = None
    inventory._upgrade_rune_item_id = None
    return True, ""
