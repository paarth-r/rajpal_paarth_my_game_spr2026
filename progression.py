"""
Player classes, XP curve, and skill-tree helpers (data/classes.json).
"""
import json
from os import path

from settings import PLAYER_BASE_ATTRS

_DATA_DIR = path.join(path.dirname(__file__), 'data')


def load_class_defs():
    fp = path.join(_DATA_DIR, 'classes.json')
    with open(fp, 'r') as f:
        data = json.load(f)
    return {c['id']: c for c in data.get('classes', [])}


CLASS_DEFS = load_class_defs()
DEFAULT_CLASS_ID = 'legionnaire'


def get_class_def(class_id):
    if not class_id:
        return CLASS_DEFS.get(DEFAULT_CLASS_ID)
    return CLASS_DEFS.get(class_id) or CLASS_DEFS.get(DEFAULT_CLASS_ID)


def xp_for_next_level(current_level):
    """XP required to advance from current_level to current_level + 1."""
    return max(35, int(45 + (current_level - 1) * 40))


def apply_skill_node_bonuses(class_id, purchased_node_ids):
    """Cumulative stat bonuses from purchased skill nodes."""
    bonuses = {}
    c = get_class_def(class_id)
    if not c:
        return bonuses
    nodes = {n['id']: n for n in c.get('skill_nodes', [])}
    for nid in purchased_node_ids:
        n = nodes.get(nid)
        if not n:
            continue
        for stat, val in n.get('stat_bonus', {}).items():
            bonuses[stat] = bonuses.get(stat, 0) + val
    return bonuses


def can_unlock_skill(class_id, node_id, player_level, purchased, skill_points):
    if skill_points < 1:
        return False
    c = get_class_def(class_id)
    if not c:
        return False
    nodes = {n['id']: n for n in c.get('skill_nodes', [])}
    n = nodes.get(node_id)
    if not n or node_id in purchased:
        return False
    if player_level < n.get('min_level', 1):
        return False
    for req in n.get('requires', []):
        if req not in purchased:
            return False
    return True


def compute_base_attrs_for_level(class_id, player_level):
    """Base attributes from class template + per-level growth (level 1 = no growth yet)."""
    c = get_class_def(class_id)
    out = dict(PLAYER_BASE_ATTRS)
    if c:
        out.update(c.get('base_attrs', {}))
        growth = c.get('level_growth', {})
        lv = max(1, int(player_level))
        for stat, inc in growth.items():
            out[stat] = out.get(stat, 0) + inc * (lv - 1)
    return out
