"""Progression and class-related Game operations."""
from progression import (
    apply_skill_node_bonuses,
    can_unlock_skill,
    compute_base_attrs_for_level,
    get_class_def,
    xp_for_next_level,
)
from settings import DEATH_GOLD_LOSS_PCT, DEATH_XP_LOSS_PCT
from sprites import MOB_DEFS
from inventory import ITEM_DEFS, EQUIPMENT_SLOTS


def get_skill_attr_bonuses(self):
    return apply_skill_node_bonuses(self.player_class_id, self.purchased_skill_nodes)


def _recompute_player_base_attrs_from_progression(self):
    self.player.base_attrs = compute_base_attrs_for_level(self.player_class_id, self.player_level)


def _apply_starting_gear_for_class(self):
    c = get_class_def(self.player_class_id)
    if not c:
        return
    si = c.get('starting_inventory', {})
    for item_id, qty in si.get('items', {}).items():
        if item_id in ITEM_DEFS:
            self.inventory.add_item(item_id, int(qty))
    for slot, item_id in si.get('equipment', {}).items():
        if slot in EQUIPMENT_SLOTS and item_id in ITEM_DEFS:
            self.inventory.equipment[slot] = item_id


def add_player_xp(self, amount):
    if amount <= 0:
        return
    self.player_xp += amount
    while self.player_level < 99:
        need = xp_for_next_level(self.player_level)
        if self.player_xp < need:
            break
        self.player_xp -= need
        self.player_level += 1
        self.skill_points += 1
        self._recompute_player_base_attrs_from_progression()
        self.player.recalc_stats()
    self.save_inventory_state()


def try_purchase_skill_node(self, node_id):
    purchased = self.purchased_skill_nodes
    if not can_unlock_skill(
        self.player_class_id, node_id, self.player_level, purchased, self.skill_points
    ):
        return False
    self.skill_points -= 1
    self.purchased_skill_nodes = set(purchased) | {node_id}
    self.player.recalc_stats()
    self.save_inventory_state()
    return True


def on_mob_kill(self, mob):
    if self.state != 'playing':
        return
    d = MOB_DEFS.get(getattr(mob, 'mob_type', 'statue'), {})
    xp = int(d.get('xp', 25))
    self.add_player_xp(xp)


def _apply_death_penalties(self):
    """Lose a fraction of gold and XP toward next level; skip at floor states."""
    gold = self.inventory.count_item('gold_coin')
    coins_lost = 0
    if gold > 0:
        coins_lost = max(1, int(gold * DEATH_GOLD_LOSS_PCT))
        coins_lost = min(coins_lost, gold)
        self.inventory.remove_item_by_id('gold_coin', coins_lost)

    xp_lost = 0
    at_xp_floor = self.player_level == 1 and self.player_xp == 0
    if not at_xp_floor and self.player_xp > 0:
        xp_lost = max(1, int(self.player_xp * DEATH_XP_LOSS_PCT))
        xp_lost = min(xp_lost, self.player_xp)
        self.player_xp -= xp_lost

    self.death_screen_coins_lost = coins_lost
    self.death_screen_xp_lost = xp_lost
    self.save_inventory_state()

