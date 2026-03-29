"""Player-run shop: coin purchases, level-gated listings. NPC shops use npc_shops.json separately."""
import json
from os import path

from inventory import ITEM_DEFS, EQUIPMENT_SLOTS

_ROOT = path.dirname(path.dirname(path.dirname(__file__)))
_PLAYER_SHOP_PATH = path.join(_ROOT, 'data', 'player_shop.json')


def _load_listings():
    try:
        with open(_PLAYER_SHOP_PATH, 'r') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    raw = data.get('listings', [])
    out = []
    for row in raw:
        lid = row.get('id')
        iid = row.get('item_id')
        if not lid or not iid or iid not in ITEM_DEFS:
            continue
        out.append({
            'id': str(lid),
            'item_id': str(iid),
            'price_coins': max(0, int(row.get('price_coins', 0))),
            'min_player_level': max(1, int(row.get('min_player_level', 1))),
        })
    return out


PLAYER_SHOP_LISTINGS = _load_listings()


def player_owns_item_anywhere(inventory, item_id):
    """True if item appears in bag, hotbar, or any equipment slot."""
    if inventory.count_item(item_id) > 0:
        return True
    for slot in EQUIPMENT_SLOTS:
        if inventory.equipment.get(slot) == item_id:
            return True
    return False


def listing_state(game, listing):
    """Resolve UI state: locked_level, can_buy, owned, reason text."""
    item_id = listing['item_id']
    price = listing['price_coins']
    need_lv = listing['min_player_level']
    inv = game.inventory
    coins = inv.count_item('gold_coin')
    owned = player_owns_item_anywhere(inv, item_id)
    item_def = ITEM_DEFS.get(item_id, {})
    stackable = item_def.get('stackable', True)

    if game.player_level < need_lv:
        return {
            'locked_level': True,
            'can_buy': False,
            'owned': owned,
            'status': f"Requires level {need_lv}",
        }
    if owned and not stackable:
        return {
            'locked_level': False,
            'can_buy': False,
            'owned': True,
            'status': 'Owned',
        }
    if coins < price:
        return {
            'locked_level': False,
            'can_buy': False,
            'owned': owned,
            'status': f"Need {price} coins (have {coins})",
        }
    return {
        'locked_level': False,
        'can_buy': True,
        'owned': owned,
        'status': f"{price} coins",
    }


def try_buy_player_listing(game, listing_id):
    """Spend coins and deliver item. Returns (success: bool, message: str)."""
    listing = next((L for L in PLAYER_SHOP_LISTINGS if L['id'] == listing_id), None)
    if listing is None:
        return False, "Unknown listing."
    st = listing_state(game, listing)
    if not st['can_buy']:
        return False, st['status']
    item_id = listing['item_id']
    price = listing['price_coins']
    inv = game.inventory
    leftover = inv.add_item(item_id, 1)
    if leftover > 0:
        return False, "No inventory space."
    removed = inv.remove_item_by_id('gold_coin', price)
    if removed < price:
        inv.remove_item_by_id(item_id, 1)
        return False, "Not enough coins."
    game.on_items_gained(item_id, 1)
    game.save_inventory_state()
    return True, "Purchased."


def iter_player_shop_listings(game):
    """Yield (listing_dict, state_dict) for each catalog row."""
    for L in PLAYER_SHOP_LISTINGS:
        yield L, listing_state(game, L)
