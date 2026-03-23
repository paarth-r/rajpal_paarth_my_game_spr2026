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


def can_craft(inventory, recipe_id):
    """True if craft_placements match recipe (items already staged in craft UI)."""
    recipe = RECIPES.get(recipe_id)
    if recipe is None:
        return False
    required = recipe_inputs_required(recipe)
    placements = getattr(inventory, '_craft_placements', None)
    if placements is None:
        return False
    for slot, need_id in required.items():
        if placements.get(slot) != need_id:
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
