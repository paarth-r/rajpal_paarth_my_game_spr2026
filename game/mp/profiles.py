"""Guest profile I/O — per-world inventory/state persistence for MP players."""
import json
import os
from os import path

from inventory import ITEM_DEFS, EQUIPMENT_SLOTS, pack_slot, unpack_slot


def profiles_dir(saves_dir):
    return path.join(saves_dir, 'profiles')


def profile_path(saves_dir, username):
    return path.join(profiles_dir(saves_dir), f'{username}.json')


def world_key(save_name):
    """'mp_world_001.json' → 'mp_world_001'"""
    return save_name[:-5] if save_name and save_name.endswith('.json') else save_name


def load_mp_profile(saves_dir, username):
    fp = profile_path(saves_dir, username)
    if not fp or not path.exists(fp):
        return None
    try:
        with open(fp, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def save_mp_profile(saves_dir, username, profile):
    os.makedirs(profiles_dir(saves_dir), exist_ok=True)
    try:
        with open(profile_path(saves_dir, username), 'w') as f:
            json.dump(profile, f, indent=2)
    except Exception:
        pass


def get_world_entry(profile, wkey):
    return (profile or {}).get('worlds', {}).get(wkey)


def set_world_entry(profile, wkey, entry):
    profile.setdefault('worlds', {})[wkey] = entry


def inv_sync_to_entry(inv_data, class_id, current_level):
    """Convert an inv_sync message to a saveable world-entry dict."""
    return {
        'player_class_id': class_id,
        'player_level': int(inv_data.get('player_level', 1)),
        'player_xp': int(inv_data.get('player_xp', 0)),
        'skill_points': int(inv_data.get('skill_points', 0)),
        'purchased_skill_nodes': list(inv_data.get('purchased_skill_nodes', [])),
        'player_health': int(inv_data.get('player_health', 80)),
        'current_level': current_level,
        'slots': inv_data.get('slots', []),
        'hotbar': inv_data.get('hotbar', []),
        'equipment': inv_data.get('equipment', {}),
        'equipment_meta': inv_data.get('equipment_meta', {}),
        'selected_hotbar_index': int(inv_data.get('selected_hotbar_index', 0)),
    }


def build_inv_restore(entry):
    """Build an inv_restore message the host can send to a rejoining guest."""
    return dict(entry, type='inv_restore')


def apply_inv_restore(game, data):
    """Apply an inv_restore message to the client game object."""
    inv = game.inventory

    slots = data.get('slots', [])
    for i in range(min(len(slots), inv.num_slots)):
        s = slots[i]
        if s is None:
            inv.slots[i] = None
        elif isinstance(s, list) and len(s) >= 2 and s[0] in ITEM_DEFS and isinstance(s[1], int) and s[1] > 0:
            meta = s[2] if len(s) >= 3 and isinstance(s[2], dict) else None
            inv.slots[i] = pack_slot(s[0], s[1], meta)

    hot = data.get('hotbar', [])
    if isinstance(hot, list):
        for i in range(min(len(hot), inv.hotbar_size)):
            s = hot[i]
            if isinstance(s, list) and len(s) >= 2 and s[0] in ITEM_DEFS and isinstance(s[1], int) and s[1] > 0:
                meta = s[2] if len(s) >= 3 and isinstance(s[2], dict) else None
                inv.hotbar[i] = pack_slot(s[0], s[1], meta)

    eq = data.get('equipment', {})
    for slot_name in EQUIPMENT_SLOTS:
        item_id = eq.get(slot_name)
        inv.equipment[slot_name] = item_id if item_id in ITEM_DEFS else None

    inv.equipment_meta.clear()
    for slot_name, meta in data.get('equipment_meta', {}).items():
        if slot_name in EQUIPMENT_SLOTS and isinstance(meta, dict) and meta:
            inv.equipment_meta[slot_name] = dict(meta)

    idx = int(data.get('selected_hotbar_index', 0))
    inv.selected_hotbar_index = max(0, min(inv.hotbar_size - 1, idx))

    game.player_class_id = data.get('player_class_id', game.player_class_id)
    game.player_level = max(1, int(data.get('player_level', 1)))
    game.player_xp = max(0, int(data.get('player_xp', 0)))
    game.skill_points = max(0, int(data.get('skill_points', 0)))
    ps = data.get('purchased_skill_nodes', [])
    game.purchased_skill_nodes = set(ps) if isinstance(ps, list) else set()

    if game.player is not None:
        saved_hp = data.get('player_health')
        if isinstance(saved_hp, int):
            max_hp = game.player.get_effective_max_health()
            game.player.health = max(1, min(saved_hp, max_hp))
