"""
Inventory, equipment, and item system. Item definitions loaded from data/items.json.
"""
import json
import random
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
        d.setdefault('rarity', 'common')
        if d.get('type') == 'weapon':
            d.setdefault('attack_range_tiles', PLAYER_DEFAULT_ATTACK_RANGE_TILES)
        defs[item_id] = d
    return defs

ITEM_DEFS = load_item_defs()

EQUIPMENT_SLOTS = ['weapon', 'head', 'chest', 'boots', 'shield']


def weapon_cooldown_ms_for_item(item_id):
    """Effective attack cooldown (ms) if this item is equipped as weapon (matches Inventory.get_weapon_cooldown_ms)."""
    item = ITEM_DEFS.get(item_id, {})
    if item.get('type') != 'weapon':
        return None
    bonus = int(item.get('attack_speed_bonus', 0))
    return max(80, int(PLAYER_ATTACK_COOLDOWN_MS + bonus))


def item_is_ranged_weapon(item_def):
    """All staff-class weapons are ranged/projectile weapons."""
    return item_def.get('type') == 'weapon' and item_def.get('weapon_type') == 'staff'


class Inventory:
    """Slot-based inventory with equipment. Each slot is (item_id, count) or None."""

    def __init__(self, num_slots, hotbar_size=8):
        self.num_slots = num_slots
        self.hotbar_size = min(hotbar_size, num_slots)
        self.slots = [None] * num_slots
        self.selected_hotbar_index = 0
        self.equipment = {slot: None for slot in EQUIPMENT_SLOTS}
        # Crafting UI staging: slot_name -> item_id (one per slot; removed from bag while staged)
        self._craft_placements = {}

    def return_craft_staging(self):
        """Return staged crafting parts to inventory and clear the craft grid."""
        for _slot, item_id in list(self._craft_placements.items()):
            self.add_item(item_id, 1)
        self._craft_placements.clear()

    def apply_salvage_from_weapon(self, item_id):
        """Roll salvage drops for a weapon definition. Returns True if salvage was defined and rolled."""
        item = ITEM_DEFS.get(item_id)
        if item is None or item.get('type') != 'weapon':
            return False
        salvage = item.get('salvage')
        if not salvage:
            return False
        for entry in salvage:
            chance = float(entry.get('chance', 1.0))
            if random.random() > chance:
                continue
            lo, hi = entry['count']
            count = random.randint(int(lo), int(hi))
            nid = entry['item_id']
            if nid in ITEM_DEFS and count > 0:
                self.add_item(nid, count)
        return True

    def try_salvage_inv_slot(self, slot_index):
        """Shift+right-click: destroy one weapon in inventory, yield salvage."""
        s = self.get_slot(slot_index)
        if s is None:
            return False
        item_id, _cnt = s
        if not self.apply_salvage_from_weapon(item_id):
            return False
        self.remove_item(slot_index, 1)
        return True

    def try_salvage_equipped_weapon(self):
        """Salvage the equipped weapon (unequips it)."""
        w = self.equipment.get('weapon')
        if w is None:
            return False
        if not self.apply_salvage_from_weapon(w):
            return False
        self.equipment['weapon'] = None
        return True

    def get_slot(self, index):
        if 0 <= index < self.num_slots:
            return self.slots[index]
        return None

    def count_item(self, item_id):
        """Total count of item_id across inventory slots (not equipment)."""
        n = 0
        for s in self.slots:
            if s is not None and s[0] == item_id:
                n += s[1]
        return n

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

    def remove_item_by_id(self, item_id, amount):
        """Remove up to amount of item_id from bag slots. Returns how many were removed."""
        if amount <= 0 or item_id not in ITEM_DEFS:
            return 0
        remaining = amount
        removed = 0
        for i in range(self.num_slots):
            if remaining <= 0:
                break
            s = self.slots[i]
            if s is None or s[0] != item_id:
                continue
            _, c = s
            take = min(remaining, c)
            if take > 0:
                self.remove_item(i, take)
                removed += take
                remaining -= take
        return removed

    def get_hotbar_slot(self, hotbar_index):
        if 0 <= hotbar_index < self.hotbar_size:
            return self.get_slot(hotbar_index)
        return None

    def get_selected_item(self):
        return self.get_hotbar_slot(self.selected_hotbar_index)

    def consume_from_slot(self, slot_index, amount=1):
        """Consume amount from a slot; return consumed item_id or None."""
        s = self.get_slot(slot_index)
        if s is None or amount <= 0:
            return None
        item_id, count = s
        used = min(amount, count)
        self.remove_item(slot_index, used)
        return item_id

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
            return 0
        weapon = ITEM_DEFS.get(weapon_id, {})
        base = weapon.get('base_damage', PLAYER_ATTACK_DAMAGE)
        strength = player_attrs.get('strength', 0)
        scaling_stat = weapon.get('scaling_stat', 'strength')
        scaling_factor = weapon.get('scaling_factor', 0.0)
        scaling_val = player_attrs.get(scaling_stat, 0)
        dmg = int(base * (1 + strength / 20) + scaling_val * scaling_factor)
        if item_is_ranged_weapon(weapon):
            dmg = max(1, int(round(dmg * RANGED_WEAPON_DAMAGE_MULT)))
        return dmg

    def get_weapon_cooldown_ms(self, base_cooldown_ms):
        """Return cooldown adjusted by equipped weapon attack_speed_bonus."""
        weapon_id = self.equipment.get('weapon')
        if weapon_id is None:
            return int(base_cooldown_ms)
        weapon = ITEM_DEFS.get(weapon_id, {})
        bonus = int(weapon.get('attack_speed_bonus', 0))
        # Negative bonus = faster weapon. Keep a safe floor.
        return max(80, int(base_cooldown_ms + bonus))

    def get_weapon_attack_range_px(self):
        """Radius in world pixels for auto-attack targeting (from weapon attack_range_tiles)."""
        tiles = self.get_weapon_attack_range_tiles()
        return max(1, int(round(tiles * TILESIZE)))

    def get_weapon_attack_range_tiles(self):
        """Attack range in tiles, clamped so all weapon attacks are at least 2 tiles."""
        weapon_id = self.equipment.get('weapon')
        if weapon_id is None:
            return 0.0
        weapon = ITEM_DEFS.get(weapon_id, {})
        tiles = weapon.get('attack_range_tiles', PLAYER_DEFAULT_ATTACK_RANGE_TILES)
        try:
            tiles = float(tiles)
        except (TypeError, ValueError):
            tiles = float(PLAYER_DEFAULT_ATTACK_RANGE_TILES)
        return max(float(MIN_WEAPON_ATTACK_RANGE_TILES), tiles)

    def is_weapon_ranged(self):
        weapon_id = self.equipment.get('weapon')
        if weapon_id is None:
            return False
        return item_is_ranged_weapon(ITEM_DEFS.get(weapon_id, {}))
