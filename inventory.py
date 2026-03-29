"""
Inventory, equipment, and item system. Item definitions loaded from data/items.json.
"""
import json
import random
from os import path
from settings import *
from weapons import (
    item_is_ranged_weapon,
    weapon_cooldown_ms_for_item as _weapon_cooldown_from_item,
    weapon_damage_from_attrs,
    weapon_range_px,
    weapon_range_tiles,
)

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


def unpack_slot(s):
    """Bag/hotbar slot: None, (id, n), or (id, n, meta_dict)."""
    if s is None:
        return None, 0, {}
    item_id, count = s[0], int(s[1])
    meta = {}
    if len(s) > 2 and isinstance(s[2], dict):
        meta = dict(s[2])
    return item_id, count, meta


def pack_slot(item_id, count, meta=None):
    if not item_id or count <= 0:
        return None
    if meta:
        return (item_id, int(count), meta)
    return (item_id, int(count))


def weapon_cooldown_ms_for_item(item_id):
    item = ITEM_DEFS.get(item_id, {})
    return _weapon_cooldown_from_item(item)


class Inventory:
    """Slot-based inventory with equipment. Each slot is (item_id, count) or (item_id, count, meta)."""

    def __init__(self, num_slots, hotbar_size=8):
        self.num_slots = num_slots
        self.hotbar_size = max(1, int(hotbar_size))
        self.slots = [None] * num_slots
        self.hotbar = [None] * self.hotbar_size
        self.selected_hotbar_index = 0
        self.equipment = {slot: None for slot in EQUIPMENT_SLOTS}
        # Per equipped slot: extra data e.g. {"infused_rune": "ember_rune"} for forged weapons.
        self.equipment_meta = {}
        # Crafting UI staging: slot_name -> item_id (one per slot; removed from bag while staged)
        self._craft_placements = {}
        # Upgrade UI staging: weapon+rune before infusion.
        self._upgrade_weapon_item_id = None
        self._upgrade_rune_item_id = None

    def return_craft_staging(self):
        """Return staged crafting parts to inventory and clear the craft grid."""
        from crafting import normalize_craft_placement

        for _slot, val in list(self._craft_placements.items()):
            item_id, n = normalize_craft_placement(val)
            if item_id and n > 0:
                self.add_item(item_id, n)
        self._craft_placements.clear()

    def return_upgrade_staging(self):
        """Return staged upgrade parts to inventory and clear upgrade slots."""
        if self._upgrade_weapon_item_id:
            self.add_item(self._upgrade_weapon_item_id, 1)
            self._upgrade_weapon_item_id = None
        if self._upgrade_rune_item_id:
            self.add_item(self._upgrade_rune_item_id, 1)
            self._upgrade_rune_item_id = None

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
        item_id, _cnt, _m = unpack_slot(s)
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
        self.equipment_meta.pop('weapon', None)
        return True

    def get_slot(self, index):
        if 0 <= index < self.num_slots:
            return self.slots[index]
        return None

    def count_item(self, item_id):
        """Total count of item_id across bag + hotbar slots (not equipment)."""
        n = 0
        for s in self.slots:
            if s is not None and s[0] == item_id:
                n += s[1]
        for s in self.hotbar:
            if s is not None and s[0] == item_id:
                n += s[1]
        return n

    def set_slot(self, index, item_id, count, meta=None):
        if index < 0 or index >= self.num_slots:
            return
        if count <= 0 or item_id is None:
            self.slots[index] = None
        else:
            self.slots[index] = pack_slot(item_id, count, meta)

    def add_item(self, item_id, count=1, slot_meta=None):
        """Add items; return leftover that didn't fit.

        Merges into existing stacks in hotbar or bag when item_id, stackable, and meta match.
        New stacks use empty hotbar slots first, then bag. slot_meta applies only for a single-item
        placement (count==1) into a new slot.
        """
        if item_id not in ITEM_DEFS or count <= 0:
            return count
        item_def = ITEM_DEFS[item_id]
        max_stack = item_def.get('max_stack', 99)
        stackable = item_def.get('stackable', True)
        attach_meta = slot_meta if (count == 1 and isinstance(slot_meta, dict) and slot_meta) else None
        incoming_meta = dict(attach_meta) if attach_meta else {}

        remaining = count

        def try_merge_into(collection):
            nonlocal remaining
            for i in range(len(collection)):
                if remaining <= 0:
                    break
                existing = collection[i]
                if existing is None:
                    continue
                eid, current, em = unpack_slot(existing)
                if eid != item_id or not stackable:
                    continue
                if (em or {}) != incoming_meta:
                    continue
                room = max_stack - current
                if room <= 0:
                    continue
                add = min(remaining, room)
                meta_out = em if em else None
                collection[i] = pack_slot(item_id, current + add, meta_out)
                remaining -= add

        # 1) Stack onto existing piles (hotbar first, then bag)
        try_merge_into(self.hotbar)
        try_merge_into(self.slots)

        # 2) New stacks: prefer empty hotbar, then bag
        for collection in (self.hotbar, self.slots):
            if remaining <= 0:
                break
            limit = self.hotbar_size if collection is self.hotbar else self.num_slots
            for i in range(limit):
                if remaining <= 0:
                    break
                if collection[i] is not None:
                    continue
                add = min(remaining, max_stack)
                use_meta = attach_meta if (add == 1 and remaining == 1 and attach_meta) else None
                collection[i] = pack_slot(item_id, add, use_meta)
                remaining -= add
                if use_meta:
                    attach_meta = None

        return remaining

    def remove_item(self, slot_index, amount=1):
        s = self.get_slot(slot_index)
        if s is None or amount <= 0:
            return False
        item_id, current, meta = unpack_slot(s)
        remove = min(amount, current)
        if remove >= current:
            self.set_slot(slot_index, None, 0)
        else:
            self.set_slot(slot_index, item_id, current - remove, meta=meta if meta else None)
        return True

    def remove_item_by_id(self, item_id, amount):
        """Remove up to amount of item_id from bag+hotbar slots. Returns removed count."""
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
            _iid, c, _m = unpack_slot(s)
            take = min(remaining, c)
            if take > 0:
                self.remove_item(i, take)
                removed += take
                remaining -= take
        for i in range(self.hotbar_size):
            if remaining <= 0:
                break
            s = self.hotbar[i]
            if s is None or s[0] != item_id:
                continue
            _iid, c, hmeta = unpack_slot(s)
            take = min(remaining, c)
            if take > 0:
                if take >= c:
                    self.hotbar[i] = None
                else:
                    self.hotbar[i] = pack_slot(item_id, c - take, hmeta if hmeta else None)
                removed += take
                remaining -= take
        return removed

    def get_hotbar_slot(self, hotbar_index):
        if 0 <= hotbar_index < self.hotbar_size:
            return self.hotbar[hotbar_index]
        return None

    def set_hotbar_slot(self, hotbar_index, item_id, count, meta=None):
        if 0 <= hotbar_index < self.hotbar_size:
            if count <= 0 or item_id is None:
                self.hotbar[hotbar_index] = None
            else:
                self.hotbar[hotbar_index] = pack_slot(item_id, int(count), meta)

    def get_selected_item(self):
        return self.get_hotbar_slot(self.selected_hotbar_index)

    def consume_from_slot(self, slot_index, amount=1):
        """Consume amount from a slot; return consumed item_id or None."""
        s = self.get_slot(slot_index)
        if s is None or amount <= 0:
            return None
        item_id, count, _meta = unpack_slot(s)
        used = min(amount, count)
        self.remove_item(slot_index, used)
        return item_id

    def consume_from_hotbar(self, hotbar_index, amount=1):
        s = self.get_hotbar_slot(hotbar_index)
        if s is None or amount <= 0:
            return None
        item_id, count, hmeta = unpack_slot(s)
        used = min(amount, count)
        if used >= count:
            self.hotbar[hotbar_index] = None
        else:
            self.hotbar[hotbar_index] = pack_slot(item_id, count - used, hmeta if hmeta else None)
        return item_id

    def equip_from_slot(self, slot_index):
        """Equip item from inventory slot. Swaps with currently equipped if slot occupied."""
        s = self.get_slot(slot_index)
        if s is None:
            return False
        item_id, count, meta = unpack_slot(s)
        item_def = ITEM_DEFS.get(item_id)
        if item_def is None:
            return False
        eq_slot = item_def.get('slot')
        if eq_slot is None or eq_slot not in EQUIPMENT_SLOTS:
            return False
        old_id = self.equipment[eq_slot]
        old_meta = dict(self.equipment_meta.get(eq_slot, {}))
        self.equipment[eq_slot] = item_id
        if meta:
            self.equipment_meta[eq_slot] = dict(meta)
        else:
            self.equipment_meta.pop(eq_slot, None)
        if old_id is not None:
            self.set_slot(slot_index, old_id, 1, meta=old_meta if old_meta else None)
        else:
            self.remove_item(slot_index, 1)
        return True

    def equip_from_hotbar(self, hotbar_index):
        """Equip from hotbar (e.g. right-click equip). Swaps with currently equipped if slot occupied."""
        s = self.get_hotbar_slot(hotbar_index)
        if s is None:
            return False
        item_id, count, meta = unpack_slot(s)
        item_def = ITEM_DEFS.get(item_id)
        if item_def is None:
            return False
        eq_slot = item_def.get('slot')
        if eq_slot is None or eq_slot not in EQUIPMENT_SLOTS:
            return False
        old_id = self.equipment[eq_slot]
        old_meta = dict(self.equipment_meta.get(eq_slot, {}))
        self.equipment[eq_slot] = item_id
        if meta:
            self.equipment_meta[eq_slot] = dict(meta)
        else:
            self.equipment_meta.pop(eq_slot, None)
        if old_id is not None:
            self.set_hotbar_slot(hotbar_index, old_id, 1, meta=old_meta if old_meta else None)
        else:
            self.hotbar[hotbar_index] = None
        return True

    def unequip(self, eq_slot):
        """Unequip item from equipment slot back to inventory."""
        if eq_slot not in EQUIPMENT_SLOTS:
            return False
        item_id = self.equipment.get(eq_slot)
        if item_id is None:
            return False
        em = self.equipment_meta.get(eq_slot, {})
        slot_meta = dict(em) if em else None
        leftover = self.add_item(item_id, 1, slot_meta=slot_meta)
        if leftover == 0:
            self.equipment[eq_slot] = None
            self.equipment_meta.pop(eq_slot, None)
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

    def get_effective_weapon_item_id(self):
        """Weapon used for attacks: equipped weapon, else selected hotbar slot if it holds a weapon."""
        eq = self.equipment.get('weapon')
        if eq is not None:
            return eq
        sel = self.get_selected_item()
        if sel:
            item_id, _cnt, _m = unpack_slot(sel)
            d = ITEM_DEFS.get(item_id, {})
            if d.get('type') == 'weapon':
                return item_id
        return None

    def get_effective_weapon_item_def(self):
        wid = self.get_effective_weapon_item_id()
        return ITEM_DEFS.get(wid, {}) if wid else {}

    def get_infused_rune_for_weapon_id(self, weapon_id):
        """Return infused_rune id from equipment_meta or any bag/hotbar stack holding this weapon id."""
        if not weapon_id:
            return None
        if self.equipment.get('weapon') == weapon_id:
            return self.equipment_meta.get('weapon', {}).get('infused_rune')
        for i in range(self.hotbar_size):
            s = self.get_hotbar_slot(i)
            if not s:
                continue
            iid, _c, meta = unpack_slot(s)
            if iid == weapon_id and meta:
                r = meta.get('infused_rune')
                if r:
                    return r
        for i in range(self.num_slots):
            s = self.get_slot(i)
            if not s:
                continue
            iid, _c, meta = unpack_slot(s)
            if iid == weapon_id and meta:
                r = meta.get('infused_rune')
                if r:
                    return r
        return None

    def get_weapon_damage(self, player_attrs):
        """Damage = weapon_base * (1 + strength/20) + scaling_stat * scaling_factor.
        Strength always contributes a multiplier; the weapon's scaling_stat adds flat bonus."""
        weapon_id = self.get_effective_weapon_item_id()
        if weapon_id is None:
            return 0
        weapon = ITEM_DEFS.get(weapon_id, {})
        return weapon_damage_from_attrs(weapon, player_attrs)

    def get_weapon_cooldown_ms(self, base_cooldown_ms):
        """Return cooldown adjusted by equipped weapon attack_speed_bonus."""
        weapon_id = self.get_effective_weapon_item_id()
        if weapon_id is None:
            return int(base_cooldown_ms)
        weapon = ITEM_DEFS.get(weapon_id, {})
        bonus = int(weapon.get('attack_speed_bonus', 0))
        # Negative bonus = faster weapon. Keep a safe floor.
        return max(80, int(base_cooldown_ms + bonus))

    def get_weapon_attack_range_px(self):
        """Radius in world pixels for auto-attack targeting (from weapon attack_range_tiles)."""
        weapon_id = self.get_effective_weapon_item_id()
        if weapon_id is None:
            return 0
        weapon = ITEM_DEFS.get(weapon_id, {})
        return weapon_range_px(weapon)

    def get_weapon_attack_range_tiles(self):
        """Attack range in tiles, clamped so all weapon attacks are at least 2 tiles."""
        weapon_id = self.get_effective_weapon_item_id()
        if weapon_id is None:
            return 0.0
        weapon = ITEM_DEFS.get(weapon_id, {})
        return weapon_range_tiles(weapon)

    def is_weapon_ranged(self):
        weapon_id = self.get_effective_weapon_item_id()
        if weapon_id is None:
            return False
        return item_is_ranged_weapon(ITEM_DEFS.get(weapon_id, {}))
