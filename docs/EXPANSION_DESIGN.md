# Relictus — expansion design (lore, progression, content, economy)

This document plans how to **lengthen** the game, **deepen** lore and story, and **give coins a job**. It is written against the current codebase: linear `level_order` in `main.py`, “clear all mobs → exit unlocks,” `data/mobs.json`, `data/items.json`, `data/classes.json`, crafting, and XP/skill progression in `progression.py`.

---

## 1. Where the game is today (audit)

| System | Current state |
|--------|----------------|
| **Levels** | Three files: `level1.txt` → `level2.txt` → `level3.txt`; forward exit `E`, return `R`, checkpoint `K`, gated tile `N` until all mobs dead. |
| **Mobs** | Two archetypes: **Stone Sentinel** (`statue`), **Shadow Assassin** (`shadow_assassin`). |
| **Assets on disk** | Additional sprites exist (`Ghost.png`, `knight.png`, etc.) but are not wired as mobs yet — natural expansion hooks. |
| **Progression** | Per-class base stats, `level_growth`, four skill nodes each, XP on kill (`xp` in `mobs.json`), curve `xp_for_next_level` in `progression.py`. |
| **Crafting** | One weapon recipe (`assassins_grace`); many material ids in `items.json` are underused (`leather_strip`, `wood_splinter`, `stone_chip`, `rusty_key`). |
| **Coins** | `gold_coin` stacks in inventory; **no spend loop** yet — only accumulation and **death tax** (`DEATH_GOLD_LOSS_PCT` in `settings.py`). |

**Design implication:** length must come from **more levels**, **more encounters**, **reasons to revisit** (hub, keys, branches), and **sinks** that make gold and materials matter — not from inflating a single floor’s mob count alone.

---

## 2. Design pillars (what “longer” should mean)

1. **Places, not padding** — Each new level has a readable purpose (story beat, biome, mechanic introduction, or optional reward route).
2. **Lore is gameplay** — Item descriptions, mob names, and NPC/shrine one-liners explain *why* the empire’s junk is here and what the dungeon “wants.”
3. **Three class fantasies stay legible** — Legionnaire (armor, reach, endurance), Assassin (tempo, crits, craft dagger), Arcanist (staff, slivers, brittle power).
4. **Economy closes the loop** — Gold and materials move: **earn → spend or craft → lose on death → recover** — so risk stays meaningful.
5. **Acts, not endless grind** — Target a **10–20 hour** first playthrough with optional depth (side dungeons, recipe completion, harder variants).

---

## 3. Lore bible (canonical spine)

**Setting name:** *Relictus* — the ruin-body of a continent-scale empire whose legions, assassin cadres, and war-mages all fell together.

**The dungeon** is not random caves: it is a **buried war infrastructure** — training vaults, reliquary armories, punishment oubliettes, and **focus conduits** where mages siphoned battlefield terror into weapons and sentinels. When the empire broke, the conduits **kept drinking fear**; the dead were re-enacted as stone and shadow.

**Tone:** melancholy military gothic — discipline without empire, blades without paymasters, magic without ethics.

**Factions (environmental, not necessarily allied NPCs):**

| Faction | Role in dungeon | Mob / item tie-ins |
|---------|------------------|-------------------|
| **Line Legions** | Drill halls, statues, pilum/scutum/galea | Sentinels, heavy drops, `stone_hammer` as “trophy of broken drill.” |
| **Shadow Cadre** | Infiltration warrens, mirror-smoke | `shadow_assassin`, shard/wrap → `assassins_grace`. |
| **Arcane Corps** | Scriptoria, cracked staves, sliver caches | `arcane_staff`, `arcane_sliver`, future “wraith” or “bound scholar” enemies. |
| **The Relict (optional late-game)** | Hungry substrate of the conduits | Boss-tier entity: “the dungeon’s immune response.” |

**Player fantasy:** you are a **grave-robber of doctrine** — whichever class you pick, you inherit a *method* the empire perfected and then abandoned.

---

## 4. Story arcs (three acts)

Structure maps cleanly onto **hub + branching depths** and escalating mob tiers.

### Act I — *The Breach* (tutorial + first truth)

- **Beat 1:** Surface breach → shallow catacombs (current level 1–2 tone). Learn movement, checkpoint, clear-gate exits.
- **Beat 2:** First **Sentinel** as “this was training, not invasion.” Environmental text: drill marks on floors, Latinoid graffiti.
- **Beat 3:** First **Shadow Assassin** as “the war never ended — it went underground.”
- **Act climax:** Reach a **shrine or ledger** (inspectable tile / modal) revealing: conduits still active; coins are **pay tokens** minted for dead campaigns (explains `gold_coin` flavor).

**Player level target:** ~4–6 by end of Act I if pacing is tuned (see §7).

### Act II — *The Ledger and the Warren*

- **Beat 1:** Optional **hub** (Camp of the Fallen Banner — see §5): first **merchant** takes imperial coins “at face value” (gameplay: buy potions, keys, recipe hints).
- **Beat 2:** Branch A — **Legion vault** (more sentinels, pilum/scutum as room rewards). Branch B — **Assassin maze** (rogues, traps or line-of-sight puzzles).
- **Beat 3:** Branch C — **Arcane shaft** (new int-focused mobs, sliver nodes, environmental damage or silence zones).
- **Act climax:** Obtain **master key** or **conduit map** (quest item) that opens Act III entrance — not just “next txt file.”

**Player level target:** ~10–14.

### Act III — *The Conduit*

- **Beat 1:** Descent; mixed factions; higher density and **elite** variants (same mob id + `elite` flag in JSON: +HP, +drop tier).
- **Beat 2:** **Mini-boss** per branch theme (e.g. “First Spear” sentinel, “Silence” assassin captain, “Index” arcanist shell).
- **Beat 3:** **Relict** confrontation — multi-phase fight or “survive the conduit surge” (timer + waves) depending on engine scope.
- **Resolution:** Seal, escape, or usurp the conduit (multiple endings = replay hook).

**Player level target:** ~18–25 for “comfortable” clear; optional postgame for 30+.

---

## 5. World structure: hub, dungeons, and backtracking

Today, `level_order` is a **list**. For expansion, plan a **directed graph** (still representable as JSON: `level_id → [next_ids]` + `type: hub|linear|branch`).

### Proposed high-level map

```text
Surface_Breach
    └── Catacomb_Main (hub unlock after Act I)
            ├── Vault_Legion_1 → Vault_Legion_2 → (mini-boss)
            ├── Warren_Shadow_1 → Warren_Shadow_2 → (mini-boss)
            ├── Shaft_Arcane_1 → Shaft_Arcane_2 → (mini-boss)
            └── Conduit_Approach → Conduit_Core (Act III)
```

- **Hub level** (`Catacomb_Main`): safe-ish loop, **merchant tile**, stash chest (optional), return doors from branches, one “story” interactable.
- **Branches** need not be completed in order; **Act III gate** requires *N* of 3 sigils / keys from mini-bosses (player choice and replayability).
- **Return tiles (`R`)** already exist — use them to **stitch** branch ends back to hub without new engine concepts.

**Save format extension (later):** `quests: { "legion_sigil": true, ... }`, `flags: { "met_merchant": true }`, `unlocked_exits: [...]` so level order can be non-linear without breaking loads.

---

## 6. Level plan (concrete file-level roadmap)

Each row is a plausible `levels/*.txt` + theme + primary mobs + purpose.

| Stage | File (example) | Theme | Mobs (primary) | Purpose |
|-------|----------------|-------|----------------|--------|
| I-a | `level1_surface.txt` | wind, broken stairs | light mix or empty + fodder | teach loop |
| I-b | `level2_catacomb.txt` | ossuaries | sentinels + 1 rogue | first difficulty spike |
| I-c | `level3_shrine.txt` | conduit shrine | mixed | Act I story object |
| II-hub | `hub_banner_camp.txt` | tents, braziers | none or 1 neutral “wanderer” | merchant, routing |
| II-L1 | `vault_legion_1.txt` | drill hall | sentinels, elite statue | STR gear, stone chips |
| II-L2 | `vault_legion_2.txt` | armory | sentinels + pilum reward room | gate to mini-boss |
| II-S1 | `warren_shadow_1.txt` | tight corridors | assassins | DEX patterns |
| II-S2 | `warren_shadow_2.txt` | “smoke” rooms (LOS) | assassins + trap tiles (future) | shard economy |
| II-A1 | `shaft_arcane_1.txt` | cracked crystal | new arcane mob | INT threats |
| II-A2 | `shaft_arcane_2.txt` | library stacks | arcane + sentinel patrol | sliver glut |
| III-a | `conduit_approach.txt` | all factions | mixed elites | resource check |
| III-b | `conduit_core.txt` | boss arena | Relict + adds | ending |

**Gate variety (reduce “always clear map” fatigue):**

- **Kill quota** (current): keep for combat arenas.
- **Key gate:** `rusty_key` / `iron_key` opens `N` tile — item already in `items.json`.
- **Boss gate:** defeat named mob → flips flag (serialize boss `dead` in save).
- **Optional:** “conduit charge” — deposit *N* `arcane_sliver` at shrine to open shortcut (gold/material sink).

---

## 7. Progression pacing (XP, skills, items)

### XP budget (rough)

With `xp_for_next_level(L) = max(35, 45 + (L-1)*40)`, leveling slows linearly in *threshold* but mob XP can scale by act.

| Act | Suggested mob XP band | Kills per level (order of mag.) |
|-----|------------------------|----------------------------------|
| I | 25–60 | several |
| II | 60–120 | many |
| III | 120–250 | many; elites worth 2× |

Tune by playtesting: **target** ~1 level per 20–35 minutes of exploration + combat in Act II.

### Skill trees

Current: **4 nodes / class**. Expansion path:

- **Tier 2 (Act II):** 2–3 nodes each with `requires` chaining from existing capstones (e.g. Veteran → “First Rank” morale passive).
- **Tier 3 (Act III):** one **capstone** with `min_level` 12+ and dual prerequisites.
- Optional: **cross-class** *relic* nodes unlocked by quest flags (one point each), sold for heavy gold — gives coins a late sink without homogenizing classes.

### Item tiers

Align drops to acts:

- **Act I:** common legion + basic consumables.
- **Act II:** `pilum`, `lorica`, `galea`, `scutum` as **room chests** or merchant; crafting expands (second sword recipe, staff repair).
- **Act III:** unique relic weapons with empire names; elite-only materials for best craft.

---

## 8. Mob roster expansion

Use **data-driven** entries in `mobs.json`; reuse animation patterns from existing mobs where possible.

| Planned id | Sprite (existing asset) | Role | Notes |
|------------|-------------------------|------|--------|
| `legion_ghost` | `Ghost.png` | Act II–III skirmisher | Low HP, phases through walls *or* high evade — pick one for engine cost. |
| `legion_knight` | `knight.png` | Elite / mini-boss add | Heavy melee, drops `iron_scrap`, `leather_strip`. |
| `arcane_wisp` or `bound_clerk` | new sheet or recolor | INT counterplay | Ranged or silence pulse; drops `arcane_sliver`. |
| `statue_elite` | same `statue.png` | Variant | JSON copy with `elite: true`, higher stats — minimal art cost. |
| `relict_avatar` | boss sheet | Final encounter | Multi-phase scripted in `main.py` or `sprites.py`. |

**Lore blurbs** (one sentence each in `mobs.json` or README) tie each to Act §4 beats so players feel *why* this enemy exists.

---

## 9. Coin usage (economy sinks and faucets)

**Faucets** (already): mob drops, chests (if added), quest rewards.

**Sinks** (to implement over time):

| Sink | Purpose | Implementation sketch |
|------|---------|------------------------|
| **Merchant** | Potion restock, basic gear, **material packs** | NPC tile + `ShopState`; prices in `data/shop.json`. |
| **Keys & maps** | Progression + optional shortcuts | Buy `rusty_key` / reveal branch entrance. |
| **Recipe / lore purchases** | Crafting depth | Pay gold to unlock `starts_known` recipes or hints (`crafting.json` flags). |
| **Shrine donations** | Temporary buff or checkpoint upgrade | Pay *X* gold → +max HP until death or next level. |
| **Gambler / augury** (optional) | Risk — reroll next rare drop | High gold cost, seed-based outcome. |
| **Death tax** | Already in game | Keep; optionally **insurance** bought with gold (one death without coin loss). |

**Pricing philosophy:** early potions cheap; mid-game keys and recipes expensive enough that **farming a branch** feels worthwhile; late-game gold dump on relics.

**Materials** should parallel gold: merchants sell **leather_strip** / **wood_splinter** at premium so salvaging from `knight` and environment stays attractive.

---

## 10. Crafting and items (content hooks)

- Add recipes that consume **underused** mats: `stone_chip` + `iron_scrap` → crude mace; `wood_splinter` + `leather_strip` → improved grip (weapon mod if system exists, else trinket).
- **Keys** in loot tables for specific `N` doors (per-level key id in map metadata — future: `door_key: rusty_key` in comment or sidecar JSON).
- **Set bonuses** (optional): wearing 3 legion pieces → small DR — rewards branch completion.

---

## 11. Narrative delivery (low implementation cost)

Without full dialog engine:

- **`?` or `L` tiles** — “lore plates” (modal text from `data/lore_strings.json` keyed by level + tile).
- **Item descriptions** — already in JSON; expand for emotional beats.
- **Boss kill** — push one line to HUD log or pause banner.

---

## 12. Implementation phases (suggested order)

1. **Content pass A:** Add 2–3 levels + 1 hub stub; extend `level_order` or introduce simple branch list; wire `Ghost` / `knight` as mobs.
2. **Economy v1:** `data/shop.json` + merchant UI + 5–8 buyables; tune drop rates so gold matters by Act II.
3. **Gates v1:** `rusty_key` opens specific `N`; save `inventory` already supports keys.
4. **Act structure:** quest flags in save; Act III entrance requires 2 of 3 sigils.
5. **Boss v1:** single mini-boss mob + scripted room; then Relict for Act III.
6. **Polish:** elite variants, set bonuses, optional roguelike “conduit surge” mode.

---

## 13. Success metrics (playtest)

- **Time to Act II hub:** 45–90 minutes for new player.
- **Gold:** player should **want** to spend before max stack (avoid hoarding-only equilibrium).
- **Class differentiation:** each class has at least one **branch** where their kit feels advantaged (Legion in vault, Assassin in warren, Arcanist in shaft).

---

*This document is a living design spec; trim or reorder phases to match assignment deadlines and art bandwidth.*
