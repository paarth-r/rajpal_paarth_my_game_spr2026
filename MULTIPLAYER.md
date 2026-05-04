# Multiplayer Architecture

Relictus uses a **host-authoritative** TCP multiplayer model. One player runs the full game simulation (the host); other players send inputs and receive world snapshots every frame. Clients never simulate game logic — they only render what the host tells them.

---

## Starting a Session

### Host
The host launches normally and their world is shared automatically. From the title screen, create or load an MP world (prefixed `mp_world_`). The host binds a TCP server on port `5555` (configurable via `MULTIPLAYER_PORT`).

```python
# main.py – host startup
if self.mp_host_flag:
    self.mp_mode = 'host'
    self.mp_host_session = HostSession(self, MULTIPLAYER_PORT)
```

### Client
The client launches via `--mp-join <ip>` (or the in-game join button), connects to the host's IP, and receives a `welcome` message that assigns them a player slot and the current level name.

```python
# game/mp/session.py
def build_welcome(slot, level_name):
    return {
        'type': 'welcome',
        'version': MP_PROTOCOL_VERSION,
        'slot': slot,
        'level': level_name,
    }
```

After receiving the welcome, the client loads the level and sends a `class_setup` message identifying themselves:

```python
write_message(sock, {
    'type': 'class_setup',
    'class_id': self.player_class_id,
    'username': self.username,
})
```

---

## Wire Protocol

All messages are **length-prefixed JSON frames** over TCP. Each frame is a big-endian `uint32` byte-count followed by a UTF-8 encoded JSON object.

```python
# game/mp/protocol.py
def write_message(sock, obj: dict) -> None:
    raw = json.dumps(obj, separators=(',', ':')).encode('utf-8')
    sock.sendall(struct.pack('>I', len(raw)) + raw)

def parse_frames_from_buffer(buf: bytearray) -> list:
    out = []
    while True:
        if len(buf) < 4:
            break
        (n,) = struct.unpack('>I', buf[:4])
        if len(buf) < 4 + n:
            break
        payload = bytes(buf[4:4 + n])
        del buf[:4 + n]
        out.append(json.loads(payload.decode('utf-8')))
    return out
```

Max frame size is **4 MB**. Partial frames are held in a `bytearray` buffer until complete.

---

## Threading Model

All network I/O is non-blocking relative to the game loop. Reads happen on background daemon threads; the main thread only touches queues.

### Host threads
| Thread | Purpose |
|--------|---------|
| `_accept_loop` | Waits for new TCP connections, enqueues them in `pending_connections` |
| `_reader_loop` (per client) | Reads frames from one client socket, puts `(slot, msg)` into `mp_inbox` |

```python
# game/mp/session.py – HostSession reader
def _reader_loop(self, sock, slot):
    buf = bytearray()
    while self._running:
        msgs = read_messages(sock, buf)   # blocks until data arrives
        for m in msgs:
            self.game.mp_inbox.put((slot, m))
```

### Client thread
One reader thread receives all host messages. Snapshots (`type: snapshot`) overwrite `mp_latest_snapshot` directly (only the newest snapshot matters). All other messages go into `mp_host_messages` (a `queue.Queue`) for ordered processing.

```python
# game/mp/session.py – ClientSession reader
def _reader_loop(self):
    while self._running:
        msgs = read_messages(self._sock, self._buf)
        for m in msgs:
            if m.get('type') == 'snapshot':
                self.game.mp_latest_snapshot = m   # latest wins, no queue
            else:
                self.game.mp_host_messages.put(m)
```

---

## Game Loop Integration

Every frame the host and client each drain their queues:

```
HOST frame:
  _mp_poll_host_network()   ← drain mp_inbox + mp_disconnect_queue
  _mp_apply_host_remote_inputs()   ← apply queued client inputs to guest sprites
  update()   ← simulate world (mobs, physics, combat)
  _mp_host_flush_snapshot()   ← build + send snapshot to all clients

CLIENT frame:
  _mp_client_update()   ← apply latest snapshot, drain mp_host_messages
  draw()   ← render (no simulation)
```

---

## Snapshots (Host → Clients, every frame)

The host serialises the entire world state into a snapshot JSON and broadcasts it to all connected clients.

```python
# game/mp/sync.py
snap = {
    'type': 'snapshot',
    'tick': int(tick),
    'level': current_level_name,       # triggers level reload on client if changed
    'leo': level_exit_open,
    'oc': sorted(opened_chests),
    'players': [...],                  # position, health, animation frame per slot
    'mobs': [...],                     # position, HP, state, network_id per mob
    'proj': [...],                     # active projectiles
    'drops': [...],                    # ground items
    'dn': [...],                       # damage number floaters
    'cl': [...],                       # chain lightning FX
}
```

**Level transitions** are handled automatically: when the snapshot's `level` field differs from the client's current level, the client reloads the map before applying the rest of the snapshot.

```python
# game/mp/sync.py – apply_snapshot
snap_level = snap.get('level', '')
if snap_level and snap_level != getattr(game, 'current_level_name', ''):
    game.load_level(snap_level, create_player=False, mp_client=True)
```

Each mob has a stable `network_id` assigned by the host at spawn. The client maintains `_mob_by_net_id` to match incoming mob data to existing sprites, creating or removing sprites as needed.

---

## Client Input (Clients → Host, every frame)

Clients never move their own sprite. They queue inputs locally and send them each frame:

```python
self.mp_client_session.send({
    'type': 'input',
    'moves': [...],        # list of (dx, dy) tile moves queued this frame
    'attack': bool,        # attack button pressed
    'clear': bool,         # clear move queue
    'tgt': network_id,     # manual attack target (or null)
    'weapon_id': str,      # currently equipped/selected weapon item ID
    'heal': int,           # HP recovered from consumables this frame
})
```

The host applies these in `_mp_apply_host_remote_inputs()`, driving the guest's `Player` sprite directly:

```python
p.mp_guest_weapon_id = msg.get('weapon_id')  # used for stat isolation
for m in msg.get('moves') or []:
    p.queue_move(int(m[0]), int(m[1]))
if msg.get('attack'):
    p.attack()
heal = int(msg.get('heal') or 0)
if heal > 0:
    p.health = min(p.get_effective_max_health(), p.health + heal)
```

---

## Guest Stat Isolation

Guest player sprites on the host must not inherit the host's inventory stats. Each `Player` sprite has an `_is_mp_guest()` check:

```python
# sprites.py
def _is_mp_guest(self):
    local = int(getattr(self.game, 'mp_local_slot', 0))
    return getattr(self, 'mp_slot', 0) != local
```

Weapon stats are resolved from `mp_guest_weapon_id` (sent with every input) rather than the host's inventory:

```python
def get_effective_damage(self):
    guest_wid = getattr(self, 'mp_guest_weapon_id', None)
    if guest_wid is not None:
        return weapon_damage_from_attrs(ITEM_DEFS[guest_wid], self.get_effective_attrs())
    if self._is_mp_guest():
        return PLAYER_ATTACK_DAMAGE   # unarmed default, not host's weapon
    return self.game.inventory.get_weapon_damage(self.get_effective_attrs())
```

The same pattern applies to `get_effective_attack_range()`, `is_ranged_weapon()`, and `get_attack_cooldown_ms()`.

---

## Message Reference

### Host → Client (non-snapshot)

| `type` | When sent | Payload |
|--------|-----------|---------|
| `welcome` | On connect | `slot`, `level`, `version` |
| `inv_restore` | After `class_setup` if player has saved state | Full inventory + stats |
| `grant_items` | After `class_setup` if starter chest already open | `items: [[item_id, count], ...]` |
| `chest_looted_for_you` | After guest opens a chest | `col`, `row` |
| `chest_depleted` | After all players have looted a chest | `col`, `row` |
| `xp_gain` | On any mob kill | `xp` |
| `rejected` | Player not in world roster | `reason` |

### Client → Host

| `type` | When sent | Payload |
|--------|-----------|---------|
| `class_setup` | After welcome received | `class_id`, `username` |
| `input` | Every frame | `moves`, `attack`, `clear`, `tgt`, `weapon_id`, `heal` |
| `inv_sync` | After inventory changes (equip, use item) | Full serialised inventory |
| `chest_req` | Player presses G near a chest | `col`, `row` |
| `drop_item` | Player drags item out of inventory | `item`, `count`, `wx`, `wy` |

---

## Chest System (Per-Player Loot)

Each chest must be individually looted by every live player before it disappears. The host tracks this with `_chest_openers`:

```python
# Chest opened by guest:
rec = self._chest_openers.setdefault(key, {'slots': set(), 'col': col, 'row': row})
rec['slots'].add(slot)
# ... send loot to that guest ...
self._check_chest_depletion(key)

def _check_chest_depletion(self, key):
    live_slots = [i for i in range(MAX_MULTIPLAYERS) if self.players[i] is not None]
    if rec['slots'].issuperset(live_slots):
        self._deplete_chest(key, col, row)   # broadcast chest_depleted, remove tile
```

Clients track two sets: `opened_chests` (globally gone) and `my_opened_chests` (this player has looted it).

---

## XP — Party Stat

XP is shared equally. When any mob dies, the host adds XP to its own progression and broadcasts to all clients:

```python
# game/systems/progression_ops.py
def on_mob_kill(self, mob):
    ...
    self.add_player_xp(xp)
    if getattr(self, 'mp_mode', None) == 'host':
        _broadcast_xp_gain(self, xp)
```

Clients receive `{'type': 'xp_gain', 'xp': N}` and call `add_player_xp` locally, handling level-ups and skill point grants client-side.

---

## World Roster & Access Control

Each MP save file contains a `player_roster` (username → saved state) and a `roster_locked` flag.

- **During the tutorial** (`intro.txt`): any player who connects is added to the roster.
- **When the host exits the tutorial**: `roster_locked = True` is written to the save. No new players may join after this point.
- **On join**: the host checks the roster. If locked and the username is absent, a `rejected` message is sent and the connection is closed.
- **On disconnect**: the guest's last `inv_sync` state is written back into `player_roster` in the save file so their inventory is restored on the next join.

```python
# Enforcement in _mp_poll_host_network
if locked and username not in roster:
    self.mp_host_session.send_to_slot(data['sock'], data['lock'], {
        'type': 'rejected',
        'reason': 'This world is locked. Only original players may join.',
    })
    self._mp_eject_client(slot)
else:
    roster_entry = roster.get(username, {})
    if roster_entry:
        # Restore saved inventory + stats
        self.mp_host_session.send_to_slot(data['sock'], data['lock'],
            dict(roster_entry, type='inv_restore'))
```

---

## Level Transitions

Level transitions require **all live players** to be within 1 tile of an exit tile (`N`) before the world advances. This prevents one player racing ahead.

```python
# main.py – update()
live_players = [p for p in self.players if p is not None]
if self.level_exit_open and live_players and self.level_exit_tiles:
    exit_set = set(self.level_exit_tiles)
    def _near_exit(p):
        return any(abs(p.tile_x - tc) <= 1 and abs(p.tile_y - tr) <= 1
                   for tc, tr in exit_set)
    if all(_near_exit(p) for p in live_players):
        self.go_to_next_level()
```

Before transitioning, the host saves all guest profiles to disk via `_save_all_guest_profiles()`.

---

## File Layout

```
game/mp/
  protocol.py   — wire framing (length-prefixed JSON)
  session.py    — HostSession, ClientSession, threading
  sync.py       — build_snapshot(), apply_snapshot(), find_spawn_tile()
  profiles.py   — per-world guest inventory persistence
```

Save files:
```
saves/
  mp_world_001.json   — world state + player_roster + roster_locked
  profiles/
    <username>.json   — per-user cross-world profile (solo saves + MP history)
  user_config.json    — local username (gitignored)
```
