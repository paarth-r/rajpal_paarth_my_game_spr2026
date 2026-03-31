"""Host snapshot build + client apply (authoritative world state)."""
import pygame as pg

from settings import TILESIZE, MAX_MULTIPLAYERS, PROJECTILE_RADIUS_PX, WHITE
from sprites import Mob, Player, GhostProjectile, GhostDroppedItem

vec = pg.math.Vector2


def iter_active_players(game):
    pl = getattr(game, 'players', None)
    if not pl:
        p = getattr(game, 'player', None)
        if p is not None:
            yield p
        return
    for p in pl:
        if p is not None:
            yield p


def find_spawn_tile(game, origin_col, origin_row):
    """Walkable terrain near origin ignoring other entities (for joining players)."""
    from game.systems import world_ops

    for ring in range(1, 8):
        for dc in range(-ring, ring + 1):
            for dr in range(-ring, ring + 1):
                if max(abs(dc), abs(dr)) != ring:
                    continue
                c, r = origin_col + dc, origin_row + dr
                if world_ops.tile_walkable_terrain(game, c, r):
                    return c, r
    return origin_col, origin_row


def _serialize_player(p, slot):
    stt = None
    if p.slide_to_tile is not None:
        stt = [int(p.slide_to_tile[0]), int(p.slide_to_tile[1])]
    return {
        'sl': slot,
        'px': float(p.pos.x),
        'py': float(p.pos.y),
        'tx': int(p.tile_x),
        'ty': int(p.tile_y),
        'f': p.facing,
        'atk': bool(p.attacking),
        'acf': int(p.current_frame),
        'ms': p.move_state,
        'mv': bool(p.moving),
        'h': int(p.health),
        'mh': int(p.max_health),
        'stt': stt,
    }


def _serialize_mob(m):
    return {
        'id': int(m.network_id),
        'mt': m.mob_type,
        'px': float(m.pos.x),
        'py': float(m.pos.y),
        'tx': int(m.tile_x),
        'ty': int(m.tile_y),
        'st': m.state,
        'af': int(m.anim_frame),
        'fl': bool(m.facing_left),
        'h': int(m.health),
        'mh': int(m.max_health),
        'sbu': int(getattr(m, 'status_burn_until', 0)),
        'ssu': int(getattr(m, 'status_slow_until', 0)),
    }


def build_snapshot(game, tick):
    players = []
    pl = getattr(game, 'players', None)
    if pl:
        for i, p in enumerate(pl):
            if p is not None:
                players.append(_serialize_player(p, i))
    elif getattr(game, 'player', None):
        players.append(_serialize_player(game.player, 0))

    mobs = []
    for m in game.all_mobs:
        if getattr(m, 'network_id', 0):
            mobs.append(_serialize_mob(m))

    proj = []
    for pr in game.all_projectiles:
        if getattr(pr, 'mp_ghost', False):
            continue
        tid = 0
        if pr.target is not None and getattr(pr.target, 'network_id', None):
            tid = int(pr.target.network_id)
        proj.append({
            'px': float(pr.pos.x),
            'py': float(pr.pos.y),
            'tid': tid,
        })

    drops = []
    for d in game.all_drops:
        if getattr(d, 'mp_ghost', False):
            continue
        drops.append({
            'px': float(d.pos.x),
            'py': float(d.pos.y),
            'item': d.item_id,
            'c': int(d.count),
        })

    snap = {
        'type': 'snapshot',
        'tick': int(tick),
        'level': getattr(game, 'current_level_name', ''),
        'leo': bool(getattr(game, 'level_exit_open', False)),
        'oc': sorted(getattr(game, 'opened_chests', set())),
        'players': players,
        'mobs': mobs,
        'proj': proj,
        'drops': drops,
        'dn': getattr(game, 'mp_snap_damage_numbers', []),
        'cl': getattr(game, 'mp_snap_chain_fx', []),
    }
    game.mp_snap_damage_numbers = []
    game.mp_snap_chain_fx = []
    return snap


def _apply_player_visual(p, d):
    p.pos.x = float(d['px'])
    p.pos.y = float(d['py'])
    p.tile_x = int(d['tx'])
    p.tile_y = int(d['ty'])
    p.facing = d['f']
    p.attacking = bool(d['atk'])
    p.current_frame = int(d['acf'])
    p.move_state = d['ms']
    p.moving = bool(d['mv'])
    p.health = int(d['h'])
    p.max_health = int(d['mh'])
    stt = d.get('stt')
    p.slide_to_tile = (int(stt[0]), int(stt[1])) if stt else None
    p.hit_rect.center = (p.pos.x, p.pos.y)
    fac = p.facing
    if p.attacking:
        frames = p.attack_frames.get(fac, p.attack_frames['down'])
        i = max(0, min(p.current_frame, len(frames) - 1))
        p.image = frames[i]
    elif p.moving or p.move_state == 'sliding':
        frames = p.move_frames.get(fac, p.move_frames['down'])
        i = p.current_frame % len(frames)
        p.image = frames[i]
    else:
        frames = p.move_frames.get(fac, p.move_frames['down'])
        p.image = frames[0]
    p.rect = p.image.get_rect()
    p.rect.center = p.hit_rect.center


def _apply_mob_visual(mob, md):
    mob.state = md['st']
    mob.anim_frame = int(md['af'])
    mob.facing_left = bool(md['fl'])
    mob.health = int(md['h'])
    mob.max_health = int(md['mh'])
    mob.tile_x = int(md['tx'])
    mob.tile_y = int(md['ty'])
    mob.pos.x = float(md['px'])
    mob.pos.y = float(md['py'])
    mob.status_burn_until = int(md.get('sbu', 0))
    mob.status_slow_until = int(md.get('ssu', 0))
    mob.hit_rect.center = mob.pos

    st = mob.state
    if st == 'dead':
        fr = mob.death_frames
    elif st == 'attack':
        fr = mob.attack_frames
    elif st == 'heal':
        fr = mob.heal_frames if mob.heal_frames else mob.idle_frames
    elif st == 'walk':
        fr = mob.walk_frames
    else:
        fr = mob.idle_frames
    if fr:
        i = max(0, min(mob.anim_frame, len(fr) - 1))
        mob._update_image_cache(fr[i])
    mob.rect.center = mob.hit_rect.center


def apply_snapshot(game, snap):
    if snap.get('type') != 'snapshot':
        return

    game.level_exit_open = bool(snap.get('leo', False))
    oc = snap.get('oc')
    if isinstance(oc, list):
        game.opened_chests = {str(x) for x in oc}
    if hasattr(game, '_apply_opened_chests_to_map'):
        game._apply_opened_chests_to_map()

    if not isinstance(getattr(game, 'players', None), list) or len(game.players) != MAX_MULTIPLAYERS:
        game.players = [None] * MAX_MULTIPLAYERS

    pls = snap.get('players') or []
    seen_slots = set()
    for d in pls:
        sl = int(d['sl'])
        if sl < 0 or sl >= MAX_MULTIPLAYERS:
            continue
        seen_slots.add(sl)
        if game.players[sl] is None:
            game.players[sl] = Player(game, int(d['tx']), int(d['ty']))
            game.players[sl].mp_slot = sl
        _apply_player_visual(game.players[sl], d)
    for i in range(MAX_MULTIPLAYERS):
        if i not in seen_slots and game.players[i] is not None:
            game.players[i].kill()
            game.players[i] = None

    seen_m = set()
    for md in snap.get('mobs') or []:
        nid = int(md['id'])
        seen_m.add(nid)
        mob = game._mob_by_net_id.get(nid)
        if mob is None:
            mob = Mob(game, int(md['tx']), int(md['ty']), mob_type=md['mt'])
            mob.network_id = nid
            game._mob_by_net_id[nid] = mob
        _apply_mob_visual(mob, md)
    for nid, mob in list(game._mob_by_net_id.items()):
        if nid not in seen_m:
            mob.kill()
            del game._mob_by_net_id[nid]

    for s in list(game.all_projectiles):
        if getattr(s, 'mp_ghost', False):
            s.kill()
    for pd in snap.get('proj') or []:
        GhostProjectile(game, float(pd['px']), float(pd['py']))

    for s in list(game.all_drops):
        if getattr(s, 'mp_ghost', False):
            s.kill()
    for dd in snap.get('drops') or []:
        GhostDroppedItem(game, float(dd['px']), float(dd['py']), dd['item'], int(dd.get('c', 1)))

    game.damage_numbers = []
    for dn in snap.get('dn') or []:
        game.damage_numbers.append({
            'pos': vec(float(dn['x']), float(dn['y'])),
            'amount': int(dn['a']),
            'color': tuple(dn['c']),
            'life_ms': int(dn.get('l', 1000)),
            'age_ms': int(dn.get('g', 0)),
        })

    game.chain_lightning_fx = []
    for fx in snap.get('cl') or []:
        game.chain_lightning_fx.append({
            'a': vec(float(fx['ax']), float(fx['ay'])),
            'b': vec(float(fx['bx']), float(fx['by'])),
            'age_ms': int(fx.get('g', 0)),
            'life_ms': int(fx.get('l', 400)),
        })
