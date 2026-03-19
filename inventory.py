"""
Inventory, equipment, and item system. Item definitions loaded from data/items.json.
"""
import json
from os import path
from settings import *

_DATA_DIR = path.join(path.dirname(__file__), 'data')

def load_item_defs():
    fp = path.join(_DATA_DIR, 'items.json')
    with open(fp, 'r') as f:
        raw = json.load(f)
    defs = {}
    for item_id, d in raw.items():
        d['color'] = tuple(d.get('color', [200, 200, 200]))
        defs[item_id] = d
    return defs

ITEM_DEFS = load_item_defs()

EQUIPMENT_SLOTS = ['weapon', 'head', 'chest', 'boots', 'shield']


class Inventory:
    """Slot-based inventory with equipment. Each slot is (item_id, count) or None."""

    def __init__(self, num_slots, hotbar_size=8):
        self.num_slots = num_slots
        self.hotbar_size = min(hotbar_size, num_slots)
        self.slots = [None] * num_slots
        self.selected_hotbar_index = 0
        self.equipment = {slot: None for slot in EQUIPMENT_SLOTS}

    def get_slot(self, index):
        if 0 <= index < self.num_slots:
            return self.slots[index]
        return None

    def set_slot(self, index, item_id, count):
        if index < 0 or index >= self.num_slots:
            return
        if count <= 0:
            self.slots[index] = None
        else:
            self.slots[index] = (item_id, count)

    def add_item(self, item_id, count=1):
        """Add items; return leftover that didn't fit."""
        if item_id not in ITEM_DEFS or count <= 0:
            return count
        item_def = ITEM_DEFS[item_id]
        max_stack = item_def.get('max_stack', 99)
        stackable = item_def.get('stackable', True)
        for i in range(self.num_slots):
            if count <= 0:
                break
            existing = self.slots[i]
            if existing is not None and existing[0] == item_id and stackable:
                current = existing[1]
                add = min(count, max_stack - current)
                if add > 0:
                    self.slots[i] = (item_id, current + add)
                    count -= add
        for i in range(self.num_slots):
            if count <= 0:
                break
            if self.slots[i] is None:
                add = min(count, max_stack)
                self.slots[i] = (item_id, add)
                count -= add
        return count

    def remove_item(self, slot_index, amount=1):
        s = self.get_slot(slot_index)
        if s is None or amount <= 0:
            return False
        item_id, current = s
        remove = min(amount, current)
        if remove >= current:
            self.set_slot(slot_index, None, 0)
        else:
            self.set_slot(slot_index, item_id, current - remove)
        return True

    def get_hotbar_slot(self, hotbar_index):
        if 0 <= hotbar_index < self.hotbar_size:
            return self.get_slot(hotbar_index)
        return None

    def get_selected_item(self):
        return self.get_hotbar_slot(self.selected_hotbar_index)

    def equip_from_slot(self, slot_index):
        """Equip item from inventory slot. Swaps with currently equipped if slot occupied."""
        s = self.get_slot(slot_index)
        if s is None:
            return False
        item_id, count = s
        item_def = ITEM_DEFS.get(item_id)
        if item_def is None:
            return False
        eq_slot = item_def.get('slot')
        if eq_slot is None or eq_slot not in EQUIPMENT_SLOTS:
            return False
        old = self.equipment[eq_slot]
        self.equipment[eq_slot] = item_id
        if old is not None:
            self.set_slot(slot_index, old, 1)
        else:
            self.remove_item(slot_index, 1)
        return True

    def unequip(self, eq_slot):
        """Unequip item from equipment slot back to inventory."""
        if eq_slot not in EQUIPMENT_SLOTS:
            return False
        item_id = self.equipment.get(eq_slot)
        if item_id is None:
            return False
        leftover = self.add_item(item_id, 1)
        if leftover == 0:
            self.equipment[eq_slot] = None
            return True
        return False

    def get_total_defense(self):
        total = 0
        for eq_slot in EQUIPMENT_SLOTS:
            item_id = self.equipment.get(eq_slot)
            if item_id is None:
                continue
            item_def = ITEM_DEFS.get(item_id, {})
            total += item_def.get('defense', 0)
        return total

    def get_equipment_stat_bonuses(self):
        """Return dict of stat -> total bonus from all equipped items."""
        bonuses = {}
        for eq_slot in EQUIPMENT_SLOTS:
            item_id = self.equipment.get(eq_slot)
            if item_id is None:
                continue
            item_def = ITEM_DEFS.get(item_id, {})
            for stat, val in item_def.get('stat_bonus', {}).items():
                bonuses[stat] = bonuses.get(stat, 0) + val
        return bonuses

    def get_weapon_damage(self, player_attrs):
        """Damage = weapon_base * (1 + strength/20) + scaling_stat * scaling_factor.
        Strength always contributes a multiplier; the weapon's scaling_stat adds flat bonus."""
        weapon_id = self.equipment.get('weapon')
        if weapon_id is None:
            return PLAYER_ATTACK_DAMAGE
        weapon = ITEM_DEFS.get(weapon_id, {})
        base = weapon.get('base_damage', PLAYER_ATTACK_DAMAGE)
        strength = player_attrs.get('strength', 0)
        scaling_stat = weapon.get('scaling_stat', 'strength')
        scaling_factor = weapon.get('scaling_factor', 0.0)
        scaling_val = player_attrs.get(scaling_stat, 0)
        return int(base * (1 + strength / 20) + scaling_val * scaling_factor)
