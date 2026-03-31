"""Save/load/world-selection Game operations."""
import json
import os
from os import path

from inventory import ITEM_DEFS, EQUIPMENT_SLOTS, pack_slot, unpack_slot
from progression import DEFAULT_CLASS_ID, get_class_def
from crafting import default_starts_known_recipe_ids, recipes_unlocked_by_item


def init_save_system(self):
    os.makedirs(self.saves_dir, exist_ok=True)
    legacy_save = path.join(self.game_dir, 'save_inventory.json')
    legacy_target = path.join(self.saves_dir, 'world_001.json')
    if path.exists(legacy_save) and not path.exists(legacy_target):
        try:
            with open(legacy_save, 'r') as src:
                payload = json.load(src)
            with open(legacy_target, 'w') as dst:
                json.dump(payload, dst, indent=2)
        except Exception:
            pass
    saves = sorted([f for f in os.listdir(self.saves_dir) if f.endswith('.json')])
    active = None
    if path.exists(self.active_save_path):
        try:
            with open(self.active_save_path, 'r') as f:
                name = f.read().strip()
            if name in saves:
                active = name
        except Exception:
            active = None
    if active is None:
        active = saves[0] if saves else 'world_001.json'
    self.set_active_world(active)


def set_active_world(self, save_name):
    self.current_save_name = save_name
    self.save_path = path.join(self.saves_dir, save_name)
    try:
        with open(self.active_save_path, 'w') as f:
            f.write(save_name)
    except Exception:
        pass


def _load_world_state_from_save(self):
    if not path.exists(self.save_path):
        return
    try:
        with open(self.save_path, 'r') as f:
            payload = json.load(f)
        level_name = payload.get('current_level')
        if level_name in self.level_order:
            self.current_level_name = level_name
        elif 'level1.txt' in self.level_order:
            # Legacy saves without current_level: skip intro (added after early saves).
            self.current_level_name = 'level1.txt'
        mob_states = payload.get('mob_states', {})
        if isinstance(mob_states, dict):
            self.mob_states_by_level = mob_states
    except Exception:
        pass


def create_new_world(self, class_id=None):
    saves = [f for f in os.listdir(self.saves_dir) if f.endswith('.json')]
    nums = []
    for s in saves:
        if s.startswith('world_') and s.endswith('.json'):
            stem = s[len('world_'):-len('.json')]
            if stem.isdigit():
                nums.append(int(stem))
    next_num = (max(nums) + 1) if nums else 1
    new_name = f"world_{next_num:03d}.json"
    cid = class_id or DEFAULT_CLASS_ID
    if get_class_def(cid) is None:
        cid = DEFAULT_CLASS_ID
    self.player_class_id = cid
    self.player_level = 1
    self.player_xp = 0
    self.skill_points = 0
    self.purchased_skill_nodes = set()
    self.class_picker_for_new_world = False
    self.set_active_world(new_name)
    self.current_level_name = self.level_order[0]
    self.mob_states_by_level = {}
    self.opened_chests = set()
    self.intro_exit_unlocked = False
    self._pending_empty_character_start = True
    self.load_level(self.current_level_name, create_player=True)
    self._initialize_player_inventory()
    self._pending_empty_character_start = False
    self.pause_menu_open = False
    self.inventory_open = False
    self.inv_dragging = None
    self.inv_selected = None
    self.inventory_tab = 'character'
    self.craft_selected_recipe_id = None
    self.manual_target = None
    self.state = 'playing'


def list_save_files(self):
    return sorted([f for f in os.listdir(self.saves_dir) if f.endswith('.json')])


def delete_save(self, save_name):
    saves = self.list_save_files()
    if save_name not in saves:
        return
    fp = path.join(self.saves_dir, save_name)
    try:
        os.remove(fp)
    except OSError:
        return
    was_active = self.current_save_name == save_name
    remaining = self.list_save_files()
    if was_active:
        self.set_active_world(remaining[0] if remaining else 'world_001.json')


def select_world(self, save_name):
    if save_name not in self.list_save_files():
        return False
    self.player_class_id = DEFAULT_CLASS_ID
    self.player_level = 1
    self.player_xp = 0
    self.skill_points = 0
    self.purchased_skill_nodes = set()
    self.set_active_world(save_name)
    self.current_level_name = self.level_order[0]
    self.mob_states_by_level = {}
    self._load_world_state_from_save()
    self.load_level(self.current_level_name, create_player=True)
    self._initialize_player_inventory()
    self.pause_menu_open = False
    self.inventory_open = False
    self.inv_dragging = None
    self.inv_selected = None
    self.inventory_tab = 'character'
    self.craft_selected_recipe_id = None
    self.manual_target = None
    self.save_picker_open = False
    return True


def _snapshot_current_level_mobs(self):
    result = []
    for mob in self.all_mobs:
        if getattr(mob, 'state', None) == 'dead' or mob.health <= 0:
            continue
        result.append({
            'tile_x': int(mob.tile_x),
            'tile_y': int(mob.tile_y),
            'health': int(mob.health),
            'state': mob.state,
            'mob_type': getattr(mob, 'mob_type', 'statue'),
        })
    return result


def save_inventory_state(self):
    if getattr(self, 'mp_mode', None) == 'client':
        return False
    if not getattr(self, 'save_path', None):
        return False
    try:
        self.mob_states_by_level[self.current_level_name] = self._snapshot_current_level_mobs()
        def _serialize_slot(s):
            if s is None:
                return None
            item_id, cnt, meta = unpack_slot(s)
            if meta:
                return [item_id, cnt, meta]
            return [item_id, cnt]

        slots = [_serialize_slot(slot) for slot in self.inventory.slots]
        em = {k: dict(v) for k, v in self.inventory.equipment_meta.items() if v}
        payload = {
            'slots': slots,
            'hotbar': [_serialize_slot(s) for s in self.inventory.hotbar],
            'equipment': dict(self.inventory.equipment),
            'equipment_meta': em,
            'selected_hotbar_index': int(self.inventory.selected_hotbar_index),
            'player_health': int(self.player.health),
            'current_level': self.current_level_name,
            'mob_states': self.mob_states_by_level,
            'discovered_recipes': sorted(self.discovered_recipe_ids),
            'player_class_id': self.player_class_id,
            'player_level': int(self.player_level),
            'player_xp': int(self.player_xp),
            'skill_points': int(self.skill_points),
            'purchased_skill_nodes': sorted(self.purchased_skill_nodes),
            'opened_chests': sorted(getattr(self, 'opened_chests', set())),
            'intro_exit_unlocked': bool(getattr(self, 'intro_exit_unlocked', False)),
        }
        with open(self.save_path, 'w') as f:
            json.dump(payload, f, indent=2)
        return True
    except Exception:
        return False


def load_inventory_state(self):
    if not path.exists(self.save_path):
        return False
    try:
        with open(self.save_path, 'r') as f:
            payload = json.load(f)
        slots = payload.get('slots', [])
        for i in range(min(len(slots), self.inventory.num_slots)):
            s = slots[i]
            if s is None:
                self.inventory.slots[i] = None
                continue
            if not isinstance(s, list) or len(s) < 2:
                continue
            item_id, count = s[0], s[1]
            meta = s[2] if len(s) >= 3 and isinstance(s[2], dict) else None
            if item_id in ITEM_DEFS and isinstance(count, int) and count > 0:
                self.inventory.slots[i] = pack_slot(item_id, count, meta)
        hot = payload.get('hotbar')
        if isinstance(hot, list):
            for i in range(min(len(hot), self.inventory.hotbar_size)):
                s = hot[i]
                if isinstance(s, list) and len(s) >= 2 and s[0] in ITEM_DEFS and isinstance(s[1], int) and s[1] > 0:
                    hmeta = s[2] if len(s) >= 3 and isinstance(s[2], dict) else None
                    self.inventory.hotbar[i] = pack_slot(s[0], s[1], hmeta)
        else:
            for i in range(min(self.inventory.hotbar_size, self.inventory.num_slots)):
                s = self.inventory.slots[i]
                self.inventory.hotbar[i] = s
                self.inventory.slots[i] = None
        eq = payload.get('equipment', {})
        for slot_name in EQUIPMENT_SLOTS:
            item_id = eq.get(slot_name)
            self.inventory.equipment[slot_name] = item_id if item_id in ITEM_DEFS else None
        self.inventory.equipment_meta.clear()
        raw_em = payload.get('equipment_meta', {})
        if isinstance(raw_em, dict):
            for slot_name, meta in raw_em.items():
                if slot_name in EQUIPMENT_SLOTS and isinstance(meta, dict) and meta:
                    self.inventory.equipment_meta[slot_name] = dict(meta)
        idx = int(payload.get('selected_hotbar_index', 0))
        self.inventory.selected_hotbar_index = max(0, min(self.inventory.hotbar_size - 1, idx))
        saved_hp = payload.get('player_health')
        if isinstance(saved_hp, int):
            max_hp = self.player.get_effective_max_health()
            self.player.health = max(0, min(saved_hp, max_hp))
        dr = payload.get('discovered_recipes')
        if isinstance(dr, list):
            self.discovered_recipe_ids.update(str(x) for x in dr)
        self.player_class_id = payload.get('player_class_id', DEFAULT_CLASS_ID)
        if get_class_def(self.player_class_id) is None:
            self.player_class_id = DEFAULT_CLASS_ID
        self.player_level = max(1, int(payload.get('player_level', 1)))
        self.player_xp = max(0, int(payload.get('player_xp', 0)))
        self.skill_points = max(0, int(payload.get('skill_points', 0)))
        ps = payload.get('purchased_skill_nodes', [])
        self.purchased_skill_nodes = set(ps) if isinstance(ps, list) else set()
        oc = payload.get('opened_chests', [])
        if isinstance(oc, list):
            self.opened_chests = {str(x) for x in oc}
        else:
            self.opened_chests = set()
        self.intro_exit_unlocked = bool(payload.get('intro_exit_unlocked', False))
        self._apply_starts_known_recipes()
        self._sync_discovered_recipes_from_inventory()
        return True
    except Exception:
        return False


def _apply_starts_known_recipes(self):
    self.discovered_recipe_ids |= default_starts_known_recipe_ids()


def _sync_discovered_recipes_from_inventory(self):
    for i in range(self.inventory.num_slots):
        s = self.inventory.get_slot(i)
        if not s:
            continue
        item_id, _, _meta = unpack_slot(s)
        for rid in recipes_unlocked_by_item(item_id):
            self.discovered_recipe_ids.add(rid)
    for i in range(self.inventory.hotbar_size):
        s = self.inventory.get_hotbar_slot(i)
        if not s:
            continue
        item_id, _, _meta = unpack_slot(s)
        for rid in recipes_unlocked_by_item(item_id):
            self.discovered_recipe_ids.add(rid)


def on_items_gained(self, item_id, count=1):
    for rid in recipes_unlocked_by_item(item_id):
        self.discovered_recipe_ids.add(rid)


def _initialize_player_inventory(self):
    from inventory import Inventory
    from settings import INVENTORY_SLOTS, HOTBAR_SLOTS
    self.inventory = Inventory(INVENTORY_SLOTS, HOTBAR_SLOTS)
    self.discovered_recipe_ids = set()
    loaded = self.load_inventory_state()
    if loaded:
        self._recompute_player_base_attrs_from_progression()
        self.player.recalc_stats()
        if hasattr(self, '_apply_opened_chests_to_map'):
            self._apply_opened_chests_to_map()
        return
    self._apply_starts_known_recipes()
    self._sync_discovered_recipes_from_inventory()
    if getattr(self, '_pending_empty_character_start', False):
        self.intro_exit_unlocked = False
    else:
        self._apply_starting_gear_for_class()
    self.save_inventory_state()


def _get_save_class_name(self, save_name):
    fp = path.join(self.saves_dir, save_name)
    class_id = DEFAULT_CLASS_ID
    try:
        with open(fp, 'r') as f:
            payload = json.load(f)
        class_id = payload.get('player_class_id', DEFAULT_CLASS_ID)
    except Exception:
        class_id = DEFAULT_CLASS_ID
    cdef = get_class_def(class_id)
    if cdef:
        return cdef.get('name', 'Unknown')
    return get_class_def(DEFAULT_CLASS_ID).get('name', 'Legionnaire')

