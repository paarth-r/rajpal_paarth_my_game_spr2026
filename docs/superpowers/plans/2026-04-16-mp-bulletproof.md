# Multiplayer Bulletproof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the AttributeError crash in multiplayer, and separate solo/MP save worlds so only MP worlds can be hosted.

**Architecture:** The crash is a missing method binding (`tile_walkable_terrain` defined in `world_ops.py` but never patched onto `Game`). The world separation adds an `mp_world_NNN.json` naming convention, filters save listings by mode, and keeps solo and MP save files cleanly apart.

**Tech Stack:** Python, pygame-ce, JSON save files

---

## Files

| File | Change |
|---|---|
| `main.py` | Add one binding line; update save picker title/filter; update "New World" to pass mp flag when hosting |
| `game/systems/save_ops.py` | Add `is_mp_save()` helper; update `create_new_world(mp=False)`; update `list_save_files(mp=None)`; make `init_save_system` mode-aware |

---

### Task 1: Fix the crash — bind `tile_walkable_terrain` to `Game`

**Problem:** `world_ops.tile_walkable_terrain` is defined but never patched onto `Game`, so `is_walkable` (which calls `self.tile_walkable_terrain`) always crashes in gameplay.

**Files:**
- Modify: `main.py:3454-3461` (bindings block)

- [ ] **Step 1: Add the missing binding**

In `main.py`, find the bindings block (around line 3455) and add one line after `Game.is_walkable`:

```python
Game.tile_walkable_terrain = world_system.tile_walkable_terrain
```

So the block reads:
```python
Game.load_data = world_system.load_data
Game.tile_walkable_terrain = world_system.tile_walkable_terrain   # ADD THIS
Game.is_walkable = world_system.is_walkable
Game.tile_blocks_line_of_sight = world_system.tile_blocks_line_of_sight
Game.has_line_of_sight_tiles = world_system.has_line_of_sight_tiles
Game.load_level = world_system.load_level
Game._compute_reachable_tiles_from = world_system._compute_reachable_tiles_from
Game.go_to_next_level = world_system.go_to_next_level
Game.go_to_prev_level = world_system.go_to_prev_level
```

- [ ] **Step 2: Verify fix**

Launch two instances and walk around. The `AttributeError: 'Game' object has no attribute 'tile_walkable_terrain'` should be gone.

```bash
python main.py --mp-host &
sleep 2
python main.py --mp-join 127.0.0.1:5050
```

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "fix: bind tile_walkable_terrain to Game — fixes mp crash on player movement"
```

---

### Task 2: Add `is_mp_save()` helper and filter `list_save_files`

**Files:**
- Modify: `game/systems/save_ops.py`

- [ ] **Step 1: Add `is_mp_save` at the top of the file (after imports)**

```python
def is_mp_save(name):
    """True for saves that belong to multiplayer worlds (mp_world_NNN.json)."""
    return name.startswith('mp_')
```

- [ ] **Step 2: Update `list_save_files` to accept an optional `mp` filter**

Replace:
```python
def list_save_files(self):
    return sorted([f for f in os.listdir(self.saves_dir) if f.endswith('.json')])
```

With:
```python
def list_save_files(self, mp=None):
    """List save files. mp=True → mp only, mp=False → solo only, mp=None → all."""
    all_saves = sorted([f for f in os.listdir(self.saves_dir) if f.endswith('.json')])
    if mp is True:
        return [f for f in all_saves if is_mp_save(f)]
    if mp is False:
        return [f for f in all_saves if not is_mp_save(f)]
    return all_saves
```

- [ ] **Step 3: Verify no callers break**

All existing calls to `list_save_files()` (no args) still return all saves — no change in behaviour. Check:

```bash
grep -rn "list_save_files" .
```

Expected: all callers use `list_save_files()` with no args — they continue to work.

---

### Task 3: Update `create_new_world` to support MP naming

**Files:**
- Modify: `game/systems/save_ops.py` — `create_new_world`

- [ ] **Step 1: Add `mp=False` parameter and use `mp_world_` prefix when True**

Replace the current `create_new_world(self, class_id=None)` signature and its name-generation block:

```python
def create_new_world(self, class_id=None, mp=False):
    saves = [f for f in os.listdir(self.saves_dir) if f.endswith('.json')]
    prefix = 'mp_world_' if mp else 'world_'
    nums = []
    for s in saves:
        if s.startswith(prefix) and s.endswith('.json'):
            stem = s[len(prefix):-len('.json')]
            if stem.isdigit():
                nums.append(int(stem))
    next_num = (max(nums) + 1) if nums else 1
    new_name = f"{prefix}{next_num:03d}.json"
    # rest of function unchanged from here...
```

The rest of the function body (setting `player_class_id`, `player_level`, etc.) stays identical.

- [ ] **Step 2: Verify solo new-world still works**

Launch normally (no `--mp-host`), create a new world, confirm it creates `world_NNN.json` in `saves/`.

---

### Task 4: Make `init_save_system` mode-aware

When starting in `--mp-host` mode the game should default to an MP save (not a solo one).

**Files:**
- Modify: `game/systems/save_ops.py` — `init_save_system`

- [ ] **Step 1: Pass and use an `mp` flag in `init_save_system`**

Replace:
```python
def init_save_system(self):
    ...
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
```

With:
```python
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
    is_mp_mode = bool(getattr(self, 'mp_host_flag', False))
    saves = self.list_save_files(mp=is_mp_mode if is_mp_mode else False)
    # If no matching saves at all, fall back to full list
    if not saves:
        saves = self.list_save_files()
    active = None
    if path.exists(self.active_save_path):
        try:
            with open(self.active_save_path, 'r') as f:
                name = f.read().strip()
            # Only accept the saved active name if it matches the current mode
            if name in saves:
                active = name
        except Exception:
            active = None
    if active is None:
        fallback = 'mp_world_001.json' if is_mp_mode else 'world_001.json'
        active = saves[0] if saves else fallback
    self.set_active_world(active)
```

Note: `self.list_save_files` is available here because `init_save_system` is called *after* all bindings are applied (it's called from `load_data` which runs at game start).

- [ ] **Step 2: Smoke test**

```bash
# Solo: should pick world_NNN.json
python main.py

# MP host: should pick mp_world_NNN.json (or create one on first run)
python main.py --mp-host
```

---

### Task 5: Save picker and "New World" button filter by mode in UI

**Files:**
- Modify: `main.py` — `draw_save_picker`, save picker click handler, "New World" button click handler

- [ ] **Step 1: Filter saves shown in `draw_save_picker`**

In `draw_save_picker` (around line 1181), change:
```python
saves = self.list_save_files()
```
To:
```python
is_mp = bool(getattr(self, 'mp_host_flag', False))
saves = self.list_save_files(mp=is_mp)
```

And update the picker title to show context:
```python
# Change the title render line:
picker_title = "Choose MP World" if is_mp else "Choose Save"
title = title_font.render(picker_title, True, WHITE)
```

- [ ] **Step 2: "New World" creates MP save when hosting**

In the mouse click handler for `title_new_world_btn_rect` (around line 467):

```python
elif self.title_new_world_btn_rect and self.title_new_world_btn_rect.collidepoint(event.pos):
    self.class_picker_for_new_world = True
    self.class_picker_selected_id = DEFAULT_CLASS_ID
```

Store whether we're in MP mode so `create_new_world` gets the right flag when the class picker confirms. Add a flag in `__init__` setup (around line 164):

```python
self.class_picker_for_new_world = False
self.class_picker_new_world_is_mp = False   # ADD
self.class_picker_selected_id = DEFAULT_CLASS_ID
```

Set it when the button is clicked:
```python
elif self.title_new_world_btn_rect and self.title_new_world_btn_rect.collidepoint(event.pos):
    self.class_picker_for_new_world = True
    self.class_picker_new_world_is_mp = bool(getattr(self, 'mp_host_flag', False))
    self.class_picker_selected_id = DEFAULT_CLASS_ID
```

- [ ] **Step 3: Pass the mp flag into `create_new_world`**

Find all calls to `create_new_world` (there are two: keyboard handler `K_RETURN` and mouse click on `class_picker_begin_rect`). Update both to pass `mp=self.class_picker_new_world_is_mp`:

```python
# Keyboard path (around line 343):
self.create_new_world(self.class_picker_selected_id, mp=getattr(self, 'class_picker_new_world_is_mp', False))

# Mouse path (around line 444):
self.create_new_world(self.class_picker_selected_id, mp=getattr(self, 'class_picker_new_world_is_mp', False))
```

- [ ] **Step 4: Also update the `K_n` keyboard shortcut for New World**

Around line 347:
```python
if event.key == pg.K_n:
    self.class_picker_for_new_world = True
    self.class_picker_new_world_is_mp = bool(getattr(self, 'mp_host_flag', False))
    self.class_picker_selected_id = DEFAULT_CLASS_ID
```

- [ ] **Step 5: Update the title screen "New World" button label when hosting**

In `draw_intro`, update the button label in the for-loop list:
```python
new_world_label = "New MP World" if getattr(self, 'mp_host_flag', False) else "New World"
for rect, text in (
    (self.title_start_btn_rect, "Start / Continue"),
    (self.title_new_world_btn_rect, new_world_label),
    (self.title_choose_save_btn_rect, "Choose Save"),
    (self.title_mp_join_btn_rect, "Join Multiplayer"),
    (self.title_quit_btn_rect, "Quit"),
):
```

- [ ] **Step 6: End-to-end test**

```bash
# Host flow: create a new MP world, host it, join with second instance
python main.py --mp-host &
# In that window: click "New MP World", pick class, start playing
# In another terminal:
python main.py --mp-join 127.0.0.1:5050

# Solo flow: create a normal world, confirm it's named world_NNN.json
python main.py
```

Verify `saves/` contains both `world_NNN.json` and `mp_world_NNN.json` files as expected.

- [ ] **Step 7: Commit**

```bash
git add main.py game/systems/save_ops.py
git commit -m "feat: separate mp/solo worlds, fix tile_walkable_terrain crash, filter save picker by mode"
```
