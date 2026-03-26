# Relictus

`Relictus` is a top-down dungeon crawler built with `pygame-ce`, featuring tile-based movement, animated combat, inventory/equipment, multi-level progression, checkpoint/death flow, save slots, and data-driven mobs/items.

For a **long-form design plan** (lore bible, three-act story, hub/branches, level/mob roadmap, coin sinks, crafting hooks, and phased implementation), see [`docs/EXPANSION_DESIGN.md`](docs/EXPANSION_DESIGN.md).

## Tech Stack

- Python 3 + `pygame-ce`
- JSON-driven content for items and mobs
- Text tilemaps for levels
- Local file persistence for save worlds

## Project Structure

- `main.py` - game loop, state machine, level loading, save system, UI screens, targeting, transitions
- `sprites.py` - `Player`, `Mob`, `Wall`, dropped item behavior, mob combat/AI/animation
- `utils.py` - `Map`, `Camera`, `Spritesheet`, cooldown helper
- `inventory.py` - inventory slots, equipment logic, item stacking, damage/defense calculations
- `settings.py` - global constants for gameplay, rendering, controls, UI dimensions
- `data/items.json` - item definitions (stats, descriptions, effects, scaling, stack rules)
- `data/mobs.json` - mob archetypes and drop tables
- `levels/*.txt` - level tilemaps and dungeon progression layout
- `images/*` - character/mob/wall spritesheets
- `saves/*.json` - per-world save files (auto-managed)

## Core Runtime Architecture

### `Game` state machine (`main.py`)

Game flow is driven by `self.state`:

- `intro` - title screen + world controls
- `playing` - gameplay update/draw loop
- `death` - death screen with respawn button

Additional modal states:

- `inventory_open` - pauses gameplay update, shows interactive inventory UI
- `pause_menu_open` - Esc pause menu with save actions
- `save_picker_open` - title overlay for choosing active save slot

### Main loop

`Game.run()` does:

1. process events
2. update only when not paused by modal screens
3. draw the active screen/state

## Rendering and Camera

### Camera (`utils.py`)

- Camera uses a world viewport of `(WIDTH / SCALE, HEIGHT / SCALE)` and converts to screen space.
- `Camera.apply()` and `Camera.apply_rect()` handle world -> screen transforms and scaling.
- Camera is intentionally **unclamped** so you can pan beyond map boundaries/walls.

### Draw order (`main.py`)

- Map + grid rendered first
- Tile overlays (checkpoint, exits, path preview, mob tile outlines)
- Sprites sorted by `(centery, centerx)` for stable layering
- HP bars on entities with health
- Target outline and mob range overlay
- HUD/hotbar/inventory/pause UI overlays

## Input and Controls

### Movement / Combat

- `WASD`: queue tile movement
- `Space`: attack (weapon required)
- `Delete`/`Backspace`: clear movement queue

### Inventory / Items

- `E` or `I`: open/close inventory
- `1-8`: select hotbar slot
- `F`: use selected consumable (e.g., potion)

### Menus / Display

- `Esc`: pause menu (when in gameplay), close picker
- `F11`: toggle fullscreen
- `Enter`: quick start/continue from title
- `N`: open **class picker**, then start a **new world** with that class
- `S`: open save picker from title

## Player System

Implemented in `sprites.py` (`Player` class):

- Tile-based queued movement with smooth interpolation (`slide_from -> slide_to`)
- Attack animation and cooldown timing
- Hit handling with hurt cooldown
- Derived stats from equipment:
  - effective attributes
  - effective max HP
  - effective weapon damage

Attack is blocked when no weapon is equipped.

### Attribute effects (actual gameplay impact)

Attributes come from:

- class base stats + per-level class growth (`data/classes.json`)
- equipped item `stat_bonus` values (`data/items.json`)
- purchased skill node `stat_bonus` values (`data/classes.json`)

Current runtime effects:

- `health`
  - Increases max HP through `Player.get_effective_max_health()`.
  - Formula: `max_hp = PLAYER_MAX_HEALTH + health * HEALTH_ATTR_HP_BONUS`.
  - With current settings, each +1 health attribute gives +5 max HP.
- `strength`
  - Increases weapon damage for **all** weapons via a global multiplier.
  - Formula component in `Inventory.get_weapon_damage()`: `base_damage * (1 + strength / 20)`.
- `dexterity` and `intelligence`
  - Affect damage when the equipped weapon scales with that stat (`scaling_stat`, `scaling_factor` in item defs).
  - Added as flat bonus in formula: `+ (scaling_stat_value * scaling_factor)`.
  - Example: daggers typically scale from dexterity; staves scale from intelligence.

Weapon-specific modifiers that combine with attributes:

- `attack_speed_bonus` modifies attack cooldown (negative = faster, positive = slower).
- `attack_range_tiles` sets reach/range (minimum 2 tiles enforced by code).
- Staff weapons are ranged/projectile weapons and use a reduced damage multiplier for balance.

Important implementation note:

- `Defense` is currently shown in the character UI from equipped armor totals, but incoming damage reduction from defense is not yet applied in combat calculations.

## Mob System

Implemented in `sprites.py` (`Mob` class), data-driven from `data/mobs.json`.

### State flow

- `inactive` -> `idle` -> `walk` -> `attack` -> `dead`

### Behavior

- Activation range before waking up
- Tile chase with smooth sliding
- Timed attack animation with configurable hit frame
- Death animation and drop generation
- Left/right flip based on movement direction

### Data-driven mob configuration

For each mob type:

- sprite sheet file + frame size
- number of frames per row (idle/walk/attack/death)
- hp, damage, move timings, chase/attack/activation ranges
- drop table

Current types:

- `statue` (stone sentinel)
- `shadow_assassin` (rogue-based enemy using `rogue.png`)

## Inventory and Equipment

Implemented in `inventory.py` and drawn/interacted in `main.py`.

### Storage model

- Slot list for inventory (`(item_id, count)` or `None`)
- Equipment dictionary for `weapon`, `head`, `chest`, `boots`, `shield`
- Hotbar is the first N inventory slots

### Interaction model

- Hover tooltips with item stats/effects
- Click to highlight slot
- Drag-and-drop swapping between slots
- Right-click equip/unequip
- Stack counts drawn with dark number badge for readability

### Consumables

- `F` uses selected hotbar consumable
- Potion consumption only applies when healing is possible

### Combat stat integration

- Weapon damage scales from base damage + attribute scaling in item defs
- Defense and stat bonuses aggregate from equipped items

## Items Data (`data/items.json`)

Each item supports fields like:

- `name`, `type`, `description`
- `stackable`, `max_stack`
- `slot` (for equipment)
- `base_damage`, `scaling_stat`, `scaling_factor`
- `defense`, `stat_bonus`
- `effect` (consumables)

Includes starter legionnaire gear and multiple weapon archetypes.

## Crafting and recipe discovery

Definitions live in `data/crafting.json` (loaded by `crafting.py`).

- **Weapon types** define **slot layouts** (e.g. sword: hilt, blade, handle, magic; dagger: blade, handle, magic).
- Each **recipe** has a stable `id`, `display_name`, optional `starts_known`, `discover_on_items` (recipe appears when you pick up those materials), `weapon_type`, `inputs` (slot → item id or `null`), and `output` (`item_id`, `count`).
- The **Craft** tab lists known recipes; drag items from the bag into the weapon-type slots, then craft.

### Crafting flow (Mermaid)

```mermaid
flowchart LR
  subgraph discovery["Discovery"]
    A[Pick up material] --> B{Item in discover_on_items?}
    B -->|yes| C[Recipe added to known list]
    B -->|no| D[No new recipe]
  end
  subgraph craft["Crafting"]
    E[Select recipe] --> F[Drag items into slots]
    F --> G{All required slots match?}
    G -->|yes| H[Craft outputs item]
    G -->|no| I[Cannot craft]
  end
  C --> E
```

## Classes, XP, leveling, and skill trees

- **Classes** are defined in `data/classes.json` (see `progression.py`). Each has `base_attrs`, per-level `level_growth`, `starting_inventory` (`items` + `equipment`), and a `skill_nodes` list (each node: `id`, `name`, `description`, `min_level`, optional `requires` node ids, `stat_bonus`).
- On **New World**, you choose a class; starting loadout and base stats follow that class.
- **XP** is granted when a mob dies (see `xp` on each mob in `data/mobs.json`). When current XP reaches the threshold for your level (`xp_for_next_level` in `progression.py`), you level up: **+1 skill point per level**, base attributes grow by class `level_growth`, and stats are recomputed.
- **Skill points** are spent on the **Skills** inventory tab; bonuses stack into `get_effective_attrs()` alongside equipment.

### Progression overview (Mermaid)

```mermaid
flowchart TD
  N1[New World: pick class] --> N2[Apply starting_inventory + base_attrs from classes.json]
  N2 --> P[Play]
  P --> K[Defeat mob]
  K --> X[+XP from data/mobs.json]
  X --> L{Enough XP to level?}
  L -->|yes| U[Level up: +1 skill point + class level_growth]
  U --> P
  L -->|no| P
  P --> S[Skills tab: unlock nodes from classes.json]
  S --> P
```

### Class arcs, lore, and item ties (Mermaid)

Each column mirrors `data/classes.json` (stats, growth, skill order) and names real `item_id`s from `data/items.json`. Crafting uses `data/crafting.json` (e.g. **Assassin’s Grace**). Drops reference `data/mobs.json` (Stone Sentinel, Shadow Assassin).

```mermaid
flowchart TB
  subgraph LEG["Legionnaire — relic of the forgotten empire’s line"]
    direction TB
    L_lore["Lore: drilled shield-wall fighter; the gladius is doctrine made steel"]
    L_start["Origin loadout: gladius + legion_helm + legion_cuirass + legion_boots + gold_coin + health_potion"]
    L_grow["Each level: +1 Strength, +1 Health attr — body hardens like old camp roads"]
    L_s1["Skill: Brutality — heavy blade habit"]
    L_s2["Skill: Discipline — camp endurance"]
    L_s3["Skill: Veteran — requires Brutality; campaign scars"]
    L_s4["Skill: Bulwark — requires Discipline; the wall holds"]
    L_drop["Trophy weapon: stone_hammer from statue mobs in mobs.json — sentinel strength torn loose"]
    L_end["Heirloom tier in items.json: pilum, lorica, galea, scutum — full legion panoply"]
    L_lore --> L_start
    L_start --> L_grow
    L_grow --> L_s1
    L_grow --> L_s2
    L_s1 --> L_s3
    L_s2 --> L_s4
    L_s3 --> L_drop
    L_s4 --> L_drop
    L_drop --> L_end
  end

  subgraph ASS["Assassin — dagger cult and shadow war"]
    direction TB
    A_lore["Lore: pugio is the assassin’s kiss; speed over plate"]
    A_start["Origin loadout: pugio + caligae + legion_helm + legion_cuirass + iron_scrap + potions + coin"]
    A_grow["Each level: +1 Dexterity — feet learn the caligae’s hobnailed dance"]
    A_s1["Skill: Blade Practice — edge time"]
    A_s2["Skill: Shadow Step — slip the line of sight"]
    A_s3["Skill: Lethal Focus — requires Blade Practice"]
    A_s4["Skill: Survivor — requires Shadow Step"]
    A_drop["Farm shadow_assassin (rogue.png): assassin_blade_shard + assassin_handle_wrap loot table"]
    A_craft["Craft assassins_grace in crafting.json from shard + wrap — discover_on_items unlocks recipe"]
    A_lore --> A_start
    A_start --> A_grow
    A_grow --> A_s1
    A_grow --> A_s2
    A_s1 --> A_s3
    A_s2 --> A_s4
    A_s3 --> A_drop
    A_s4 --> A_drop
    A_drop --> A_craft
  end

  subgraph ARC["Arcanist — scholar of residual focus"]
    direction TB
    R_lore["Lore: staff channels what the empire’s mages left in the stone"]
    R_start["Origin loadout: arcane_staff + lorica + legion_helm + legion_boots + arcane_sliver stockpile + potions"]
    R_grow["Each level: +1 Intelligence — read the dungeon’s dead symbols clearer"]
    R_s1["Skill: Arcane Focus — tighten the channel"]
    R_s2["Skill: Warding — body as brittle vessel, reinforced"]
    R_s3["Skill: Scholar — requires Arcane Focus"]
    R_s4["Skill: Mind Over Matter — requires Warding"]
    R_loop["Item loop: salvaging staves yields arcane_sliver per items.json — slivers feed study and economy"]
    R_staff["arcane_staff description: crackling ancient energy — matches sentinel-haunted depths theme"]
    R_lore --> R_start
    R_start --> R_grow
    R_grow --> R_s1
    R_grow --> R_s2
    R_s1 --> R_s3
    R_s2 --> R_s4
    R_s3 --> R_loop
    R_s4 --> R_loop
    R_loop --> R_staff
  end

  L_end -.->|shared world| A_drop
  L_end -.->|shared world| R_loop
```

**Reading the dashed links:** all three paths exist in the same dungeon economy (same mobs, merchants implied by gold_coin, shared materials like iron_scrap vs arcane_sliver). Solid arrows are *recommended* narrative progression inside each class; dotted lines are *cross-class* world ties, not hard gates.

## Levels, Doors, and Progression

Level files live in `levels/` and are loaded in order:

- `level1.txt` -> `level2.txt` -> `level3.txt`

### Supported map tiles

- `1` - wall
- `P` - player spawn
- `K` - checkpoint
- `M` - statue mob spawn
- `A` - shadow assassin mob spawn
- `N` - forward exit (locked until level clear)
- `R` - return exit (always available)
- `.` and other non-reserved chars - walkable floor

### Door/exit logic

- Forward exits (`N`) render as walls while locked.
- When all live mobs in level are cleared, exits unlock and become purple doorway tiles.
- Stepping on unlocked `N` loads next level.
- Stepping on `R` loads previous level.

## Checkpoint and Death Flow

- Checkpoint comes from `K` tile (or spawn fallback)
- On player HP <= 0:
  - switch to death screen
  - show respawn button
- Respawn:
  - move player to checkpoint
  - reset motion/attack state
  - restore effective full HP
  - resume gameplay

## Save System (Multi-World)

Implemented in `main.py` with per-world JSON saves in `saves/`.

### Files

- `saves/world_XXX.json` - each world save
- `saves/active_world.txt` - currently selected world id

### Saved data

- inventory slots
- equipment
- selected hotbar index
- player health
- current level
- per-level live mob snapshots (position, state, hp, type)
- `player_class_id`, `player_level`, `player_xp`, `skill_points`, `purchased_skill_nodes`
- `discovered_recipes` (unchanged)

### Title menu world controls

- `Start / Continue` - play active world
- `New World` - pick **class** (Legionnaire / Assassin / Arcanist), then create a new save and start with that role’s **starting gear**
- `Choose Save` - open picker and switch active world

Legacy migration:

- old `save_inventory.json` is auto-migrated into `saves/world_001.json` if needed.

## UI Screens

### Title screen

- Main menu with world actions and active save indicator
- optional save-picker overlay list

### Pause menu (`Esc`)

- Save Game
- Save & Quit to Title
- Resume

### HUD

- Health bar + values
- Level + XP bar toward next level
- Attack cooldown/readiness bar

### Inventory screen

- Tabs: **Character** | **Skills** | **Craft**
- Player preview
- Equipment slots + labels
- Stats and derived combat values (class + level growth + equipment + skills)
- **Skills**: spend skill points on class nodes (level + prerequisite gates)
- Inventory grid + hotbar highlighting
- Tooltips and drag ghost

## Running the Game

From project root:

```bash
python main.py
```

## Notes for Extending

- Add new mob types by editing `data/mobs.json` and placing spawn chars in level files (`main.py` parser).
- Add new items by editing `data/items.json`; inventory/UI/tooltips update automatically.
- Add levels by creating `levels/levelX.txt` and appending filename to `self.level_order` in `main.py`.
