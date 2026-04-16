# Multiplayer Auth & Persistent Guest Profiles — Design Spec

**Date:** 2026-04-16  
**Status:** Approved  

---

## Goal

Guest players in multiplayer must register a username, password, and class on first join. Profiles are stored globally and carry per-world progress. Guests can only join during the tutorial; returning guests resume from their last saved position.

---

## Data Model

**Location:** `saves/profiles/<username>.json`

```json
{
  "username": "alice",
  "password_hash": "<sha256 hex>",
  "worlds": {
    "mp_world_001": {
      "player_class_id": "legionnaire",
      "player_level": 3,
      "player_xp": 450,
      "skill_points": 1,
      "purchased_skill_nodes": [],
      "player_health": 80,
      "current_level": "level2.txt",
      "slots": [],
      "hotbar": [],
      "equipment": {},
      "equipment_meta": {},
      "selected_hotbar_index": 0
    }
  }
}
```

- Password stored as `sha256(password)` hex — plaintext never written to disk or sent over the wire
- `worlds` keyed by mp save filename (e.g. `mp_world_001`) — same username has independent progress per world
- New guest first joining a world gets a fresh world entry initialised from their chosen class's starting gear
- `saves/profiles/` directory created automatically on first join

---

## Handshake Protocol

**Message types added to `game/mp/protocol.py` (conceptually — same JSON framing):**

```
auth_request  { type: "auth_request" }
auth          { type: "auth", username: str, password_hash: str, class_id: str }
rejected      { type: "rejected", reason: str }
welcome       { type: "welcome", version: int, slot: int, level: str, new_user: bool }
              (level = guest's last saved level, or "intro.txt" for new users)
```

**Flow:**

```
Guest connects
    │
    ▼
Host: is current_level_name == "intro.txt"?
    ├─ NO  → send rejected(reason="past_tutorial") → close socket
    └─ YES → is a slot free AND host player exists?
                ├─ NO  → send rejected(reason="world_full") → close socket
                └─ YES → send auth_request, add socket to _mp_pending_auth dict

Guest receives auth_request → shows auth UI
Guest sends auth{username, password_hash, class_id}

Host receives auth:
    ├─ profile exists AND password_hash matches:
    │       world entry exists → load it → send welcome(level=saved_level, new_user=false)
    │       world entry absent → create it from class → send welcome(level="intro.txt", new_user=true)
    └─ profile exists AND password_hash WRONG → send rejected(reason="bad_password") → close socket
    └─ profile absent → create new profile → create world entry → send welcome(level="intro.txt", new_user=true)

Host on welcome sent:
    → spawn Player sprite at correct level/position
    → move socket from _mp_pending_auth to mp_clients
    → start reader thread
```

---

## Guest-Side UI States

The client has a new `auth` game state inserted between connecting and `playing`.

### Screen 1 — Login / Register

Shown after receiving `auth_request`.

- **Username field** — text input, printable chars only
- **Password field** — text input, characters masked as `*`
- **Class picker button** — "New player? Choose class →" advances to Screen 2 before submitting
- **Enter** — submits auth message (uses currently selected class, defaults to `DEFAULT_CLASS_ID` if not chosen)
- **Esc** — cancels, closes socket, returns to title screen

### Screen 2 — Class Picker

Reuses `draw_class_picker_intro` overlay. "Join" confirm button sends auth and transitions to `playing`.

Only shown if the user explicitly clicks "New player?". Returning players can skip directly to Enter.

### Rejected Screen

Shown after receiving `rejected`.

- Displays human-readable message:
  - `past_tutorial` → "The world is past the tutorial — joining is closed."
  - `bad_password` → "Incorrect password."
  - `world_full` → "This world is full (4 players max)."
- Auto-closes after 3 seconds or on any keypress
- Returns to title screen

---

## Host-Side Changes

### `_mp_accept_client(conn)` — `main.py`

New behaviour:
1. Check `current_level_name == 'intro.txt'` — reject if not
2. Find free slot (slots 1–3) — reject with `world_full` if none
3. Check `players[0]` exists — reject if host not in game yet
4. Send `auth_request`
5. Add to `self._mp_pending_auth: dict[socket, slot]`
6. Start a **pending reader thread** that puts `(socket, message)` into `mp_inbox`

### `_mp_poll_host_network()` — `main.py`

Handle new message type `auth` arriving from pending sockets:
- Validate username/password against `saves/profiles/<username>.json`
- On success: promote socket from `_mp_pending_auth` to `mp_clients`, create Player sprite, send `welcome`
- On failure: send `rejected`, close socket, remove from `_mp_pending_auth`

### `_mp_eject_client(slot)` — `main.py`

On disconnect: snapshot guest player state and write to their profile's world entry before killing the sprite.

### `go_to_next_level` / `go_to_prev_level` — `game/systems/world_ops.py`

After host transitions: snapshot all connected guest slots and save to their profiles.

---

## Profile I/O — `game/mp/profiles.py` (new file)

All profile read/write logic lives here to keep `main.py` and `save_ops.py` clean.

```python
load_profile(username) -> dict | None
save_profile(profile: dict)
verify_password(profile, password_hash) -> bool
get_world_entry(profile, world_key) -> dict | None
set_world_entry(profile, world_key, entry: dict)
snapshot_guest_state(game, slot) -> dict   # serialises Player + inventory for a slot
apply_guest_state(game, slot, entry: dict) # loads inventory/stats onto an existing Player
hash_password(password: str) -> str        # sha256 hex
```

Profile directory: `saves/profiles/` — created by `load_profile` / `save_profile` as needed.

---

## Constants / Settings

No new settings constants needed. `MAX_MULTIPLAYERS = 4` already enforces the player cap.

---

## Files Changed / Created

| File | Change |
|---|---|
| `game/mp/profiles.py` | **New** — all profile I/O, password hashing, state snapshot/apply |
| `game/mp/session.py` | Add `send_rejected(conn, reason)` and `send_auth_request(conn)` helpers |
| `main.py` | `_mp_accept_client` multi-step auth; `_mp_poll_host_network` handles `auth` messages; `_mp_eject_client` saves guest state; new `auth` game state + UI drawing; class picker wired to auth flow |
| `game/systems/world_ops.py` | `go_to_next_level` / `go_to_prev_level` save guest profiles on transition |

---

## Out of Scope

- Host-set world password (access control) — not requested
- Cross-world inventory sharing — profiles are per-world intentionally
- Username change — username is set once and immutable
