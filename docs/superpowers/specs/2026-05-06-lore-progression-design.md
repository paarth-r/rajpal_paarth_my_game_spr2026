# Relictus — Lore & Progression Design
_2026-05-06_

---

## 1. Story Foundation

### The Sacrifice (64 AD)

Nero discovered Etruscan texts beneath the Palatine Hill — a pre-Roman civilization's ritual of apotheosis through mass sacrifice. He burned Rome deliberately. The deaths of tens of thousands poured into him during the Great Fire, beginning his transformation into something divine and terrible. Before the transformation could complete, the surviving Senate and loyal Legions performed a counter-ritual from the same texts and sealed Nero in the catacombs beneath the ash.

The empire survived — barely. It fractured, shrank, and eventually collapsed, but a secret military order called the **Vigiles Arcanum** endured across centuries, guarding the seals. Now the seals are weakening. Nero's corruption bleeds upward through stone and shadow. The player is the latest Vigiles agent sent to descend and permanently destroy him.

### Enemy Faction Logic

| Faction | Identity | Tier |
|---------|----------|------|
| **Stone Sentinels** | Etruscan golems — original guardians of the ritual texts, repurposed by Nero's corruption | Medium |
| **Shadow Assassins** | Nero's Praetorian Guard who descended with him voluntarily; centuries of exposure have made them shadow-touched | Medium |
| **Spectral Stalkers** | Elite Praetorians who died in the dungeon but were too devoted to stay dead — hardened tier above Assassins | High |

---

## 2. Arc Structure — 30 Total Levels

```
Arc 1: The Catacombs of the Burning    Levels  1–9   (existing)
Boss 1: The Warden's Hall              Level  10    NEW
Arc 2: The Outer Empire                Levels 11–20  NEW
Arc 3: The Etruscan Depths             Levels 21–29  NEW
Boss 2: The God That Burned            Level  30    NEW (Final)
```

---

## 3. Level Plan

### Arc 1 — The Catacombs (Levels 1–9, existing)
Setting: Beneath Rome. The initial descent through layers of corrupted catacombs.
Enemies: Stone Sentinels, Shadow Assassins, Spectral Stalkers.
Mechanics: Combat, chests, intro chest with starter gear.

---

### Level 10 — BOSS 1: The Warden's Hall

**Boss: Malarix, Praetorian Prefect**
The loyal general who voluntarily sealed himself in with Nero, believing it was his duty. Centuries of proximity have half-corrupted him — enormous, armored in blackened plate, barely recognizable as human.

- **Phase 1 (100%–50% HP):** Summons Shadow Assassins every 15 s; telegraphed charge across the room; heavy melee.
- **Phase 2 (50%–0%):** Armor shatters — speed doubles, defense halves; summons Spectral Stalkers; berserker melee.
- **Drops:** *Prefect's Sigil* (lore key item unlocking Arc 2 gate), *Warden's Halberd* (unique weapon).

---

### Arc 2 — The Outer Empire (Levels 11–20)

Nero's corruption has seeped through Roman roads and aqueducts into other imperial sites. Each level is a real Roman location now transformed into a dungeon.

| Lvl | Name | Setting | Key Mechanic | New Enemy Introduced |
|-----|------|---------|-------------|----------------------|
| 11 | Via Appia | Infected Roman road | **First locked door** — key found in a chest | — |
| 12 | Ostia Submersa | Flooded port city | **NPC ferryman** needs a *Rope* item to let you cross | Drowned Legionnaire |
| 13 | Balneum Ignis | The Scalding Baths | Steam-corridor maze; two-key puzzle | Scalded Attendant |
| 14 | Circus Infernalis | Corrupted arena | **Kill-gated door** — champion gladiator must be defeated | Corrupt Gladiator |
| 15 | Castra Rhenus | Rhine border fortress | **NPC wounded legionnaire** needs a *Health Potion* to give you the *Officer's Seal* | Siege Automaton |
| 16 | Pompeii Perpetua | Ash-frozen city | Key hidden in buried chest under ash tile variant | Ash Revenant |
| 17 | Crypta Senatus | Senate burial crypts | **NPC archivist** blocks archive door — needs *Sealed Wax Tablet* (Spectral Stalker drop here) | — |
| 18 | Templum Iovis | Temple of Jupiter | Three-key, three-door non-linear puzzle; rune drops elevated | Temple Sentinel |
| 19 | Collis Palatinus | Palatine Hill — the origin site | Heaviest enemy density yet; complex multi-room key puzzle; all existing enemy types | — |
| 20 | Limen Imperii | The Imperial Threshold | Pure combat gauntlet — every enemy type, no keys, transition to Arc 3 | — |

---

### Arc 3 — The Etruscan Depths (Levels 21–29)

Below Nero's sealing chamber lie the ruins of the Etruscan civilization whose texts he stole. Their ancient guardians still active. Older magic, darker atmosphere, harder enemies.

| Lvl | Name | Setting | Key Mechanic | New Enemy Introduced |
|-----|------|---------|-------------|----------------------|
| 21 | The Broken Descent | Collapsed access tunnels | Maze navigation; **NPC guide** needs a *Torch* item | Etruscan Shade |
| 22 | Necropolis Aeterna | Etruscan burial city | 4-key puzzle across separate wings; mass enemy density | — |
| 23 | The Oracle's Sanctum | Ancient oracle chamber | **NPC Oracle** opens inner sanctum only if given all 3 *Sacred Relics* found in Lvl 21–22 | Ritual Priest |
| 24 | Vulcan's Earthly Forge | Vulcan's physical workshop | Fire hazard floor tiles; forge-lock puzzle (needs *Forge Key* from Vault Colossus) | Vault Colossus |
| 25 | The Frozen Archive | Boreas' ice repository | Slow movement on ice tiles; **NPC frozen archivist** thawed by a *Vulcan Ember Rune* | — |
| 26 | The Storm Citadel | Jupiter's failed smite made physical | Storm hazard tiles; 3-key puzzle under heavy enemy pressure | — |
| 27 | Chamber of First Sacrifice | Original Etruscan ritual site | Environmental storytelling; hardest enemy composition yet; 5-key gauntlet | — |
| 28 | The Corruption Core | Nero's power radiating at full | All enemy types simultaneously; no keys — pure attrition; darkest palette | — |
| 29 | The Final Approach | Last gauntlet before Nero | Maximum enemy stats; **dying Vigiles NPC** gives you the *Vigiles Badge* lore item | — |

---

### Level 30 — BOSS 2 (FINAL): The God That Burned

**Boss: Nero, monstrous form — three phases.**

- **Phase 1 "The Burning Consul" (100%–66%):** Humanoid, robed, wreathed in fire. Summons fire-enhanced Stone Sentinels. Speaks — taunts the player using Vigiles lore. Telegraphed fire column attack.
- **Phase 2 "The Immolated God" (66%–33%):** Taller, melting, flowing form — face half-gone. Summons all mob types simultaneously. Fire AoE spreads across floor tiles. No longer speaks, only screams.
- **Phase 3 "The Eternal Flame" (33%–0%):** Barely recognizable as human. Massive. Rapid omnidirectional fire. Endless summoning. Room floor becomes fire-damage zones. The Etruscan ritual texts burn around him.
- **Drops:** *The Ash Crown* (legendary head armor), *Ignifer* (legendary weapon — "The fire that burned Rome"), endgame rune materials.

---

## 4. New Enemy Roster

| Enemy | HP | Damage | Style | Notable Drops |
|-------|----|----|-------|---------------|
| **Drowned Legionnaire** | 280 | 55 | Slow, high HP, poison AoE on death | Corroded Chain (mat), Brine Flask (mat), Brine Blade (rare) |
| **Scalded Attendant** | 120 | 30 | Fast, spawns in groups of 3–4, applies burn status | Burn Salve (mat), Ash Shard (mat) |
| **Corrupt Gladiator** | 350 | 75 | High damage, telegraphed heavy attack, stun on hit | Gladiator's Falx, Arena Cuirass, Gladiator's Guard |
| **Siege Automaton** | 400 | 65 | Ranged bolt attacks, slow, creates choke-point pressure | Iron Core (mat), Siege Maul (rare) |
| **Ash Revenant** | 180 | 40 | Spawns from ash-tile piles when player enters room; fast | Ash Mantle, Ash Shard (mat) |
| **Temple Sentinel** | 450 | 80 | Enhanced Stone Sentinel, divine-empowered, reflects 10% damage | Void Condenser (rare), Jupiterian Shard (rune upgrade mat) |
| **Etruscan Shade** | 380 | 70 | Soul-steals, short-range teleport, summons minor shades | Ancient Shard (mat), Etruscan Ceremonial Blade (rare) |
| **Vault Colossus** | 600 | 110 | Massive slow behemoth, AOE stomp, resists light weapons | Colossus Fragment (mat), Forge Key (quest), Colossus Arm (rare) |
| **Ritual Priest** | 300 | 55 | Heals other enemies, channels summons, priority target | Ritual Oil (mat), Sacred Relic (quest), Oracle's Staff (rare) |

Boss enemy stats are tuned separately during implementation.

---

## 5. Weapon Progression by Class

Base cooldown assumed ~800 ms. `attack_speed_bonus` adds ms (positive = slower, negative = faster).

### 5a. Legionnaire (Strength scaling — heavy melee)

| Weapon | Lvl Range | Base DMG | Scaling | Speed Bonus | Source |
|--------|-----------|---------|---------|-------------|--------|
| Gladius | 1–5 | 30 | 0.50 STR | 0 | Starter |
| Stone Hammer | 3–8 | 45 | 0.70 STR | +40 | Sentinel drop |
| Pilum | 5–10 | 55 | 0.80 STR | +50 | Drop/craft |
| Falx | 10–16 | 72 | 0.90 STR | +65 | Corrupt Gladiator drop |
| Warden's Halberd ★ | 10 (boss) | 85 | 1.00 STR | +55 | L10 boss drop, unique |
| Siege Maul | 16–22 | 98 | 1.05 STR | +85 | Crafted from Iron Core |
| Colossus Arm | 22–27 | 120 | 1.10 STR | +100 | Vault Colossus drop |
| Ignifer ★★ | 30 (boss) | 155 | 1.30 STR | +70 | L30 boss drop, legendary, fire DoT |

Augmented versions (+5 base, same scaling, rune slot) available for: Gladius, Stone Hammer, Pilum, Falx, Siege Maul.

---

### 5b. Assassin (Dexterity scaling — fast melee + ranged)

| Weapon | Lvl Range | Base DMG | Scaling | Speed Bonus | Range | Source |
|--------|-----------|---------|---------|-------------|-------|--------|
| Pugio | 1–4 | 20 | 0.60 DEX | −30 | 2 | Starter |
| Assassin's Grace | 4–8 | 22 | 0.40 DEX | −220 | 3 | Craft |
| Assassin's Shortbow | 5–10 | 18 | 0.42 DEX | +45 | 5 | Craft, ranged |
| Soul Stealer | 8–14 | 30 | 0.50 DEX | −195 | 3 | Ghost drop, life-steal |
| Brine Blade | 12–18 | 38 | 0.65 DEX | −60 | 2 | Drowned Legionnaire drop, poison DoT |
| Etruscan Ceremonial Blade | 20–25 | 50 | 0.70 DEX | −80 | 2 | Etruscan Shade drop |
| Oracle's Shard | 24–28 | 42 | 0.58 DEX | +30 | 5 | Ritual Priest drop, ranged, status effects |
| Void Shard | 27–30 | 68 | 0.85 DEX | −50 | 2 | Crafted, costs 8 HP per hit |

Augmented versions available for: Pugio, Assassin's Grace, Assassin's Shortbow, Soul Stealer, Brine Blade.

---

### 5c. Arcanist (Intelligence scaling — ranged, fragile)

| Weapon | Lvl Range | Base DMG | Scaling | Speed Bonus | Range | Source |
|--------|-----------|---------|---------|-------------|-------|--------|
| Arcane Staff | 1–6 | 26 | 0.48 INT | +35 | 6 | Starter |
| Void Condenser | 8–14 | 40 | 0.62 INT | +30 | 5 | Temple Sentinel drop |
| Storm Lance | 14–20 | 55 | 0.75 INT | +25 | 6 | Crafted, chain lightning built-in |
| Oracle's Staff | 20–26 | 68 | 0.88 INT | +40 | 8 | Ritual Priest drop, longest range in game |
| Divine Remnant | 26–30 | 90 | 1.10 INT | +15 | 7 | Arc 3 late drop, all rune effects active simultaneously |

Augmented versions available for: Arcane Staff, Void Condenser, Storm Lance, Oracle's Staff.

---

### 5d. Cross-Class & Universal Notes

- **Trident** (DEX/STR, Lvl 14–20, 60 base, 0.65 STR or 0.65 DEX whichever higher, range 3, pierces through enemies) — crafted from Arena drops. Both Legionnaire and Assassin can use it effectively.
- **Augmented weapons** all gain +5 base damage and a rune slot. New rune types drop in Arc 3.
- Two new **Arc 3 runes** (see §7): Neptunian Tide and Plutonian Shadow.

---

## 6. Armor Progression

Defense values are additive across all equipped slots.

### Head

| Item | Tier | Lvl | Defense | Stat Bonus | Source |
|------|------|-----|---------|-----------|--------|
| Legion Helm | 1 | 1 | 8 | — | Starter |
| Galea | 2 | 3 | 14 | — | Sentinel drop |
| Gladiator's Helm | 3 | 14 | 22 | +1 STR | Corrupt Gladiator drop |
| Rhine Iron Helm | 4 | 18 | 30 | +2 STR | Crafted (Iron Core) |
| Etruscan Death Mask | 5 | 23 | 40 | +3 INT | Etruscan Shade drop |
| Ash Crown ★★ | 6 | 30 | 55 | +5 all stats | L30 boss drop, legendary |

### Chest

| Item | Tier | Lvl | Defense | Stat Bonus | Source |
|------|------|-----|---------|-----------|--------|
| Legion Cuirass | 1 | 1 | 10 | — | Starter |
| Lorica Segmentata | 2 | 4 | 18 | — | Starter (Arcanist) / chest drop |
| Arena Cuirass | 3 | 14 | 28 | +1 STR | Corrupt Gladiator drop |
| Ash Mantle | 3 | 16 | 22 | fire resist | Ash Revenant drop |
| Brine-Treated Mail | 4 | 18 | 32 | +1 DEX | Crafted (Corroded Chain) |
| Etruscan Burial Wraps | 5 | 22 | 42 | +2 INT | Necropolis chest |
| Vault-Forged Plate | 5 | 24 | 50 | +3 STR | Vault Colossus drop |
| Eternal Flame Cloak | 6 | 28 | 48 | +4 INT | Arc 3 late chest drop |

### Boots

| Item | Tier | Lvl | Defense | Stat Bonus | Source |
|------|------|-----|---------|-----------|--------|
| Legion Boots | 1 | 1 | 5 | — | Starter |
| Caligae | 2 | 3 | 8 | +1 DEX | Starter (Assassin) |
| Rhine Greaves | 3 | 15 | 16 | +1 STR | Crafted (Iron Core) |
| Ashen Treads | 3 | 16 | 14 | +1 DEX | Pompeii chest drop |
| Shade Wraps | 4 | 22 | 20 | +2 DEX | Etruscan Shade drop |
| Colossus Treads | 5 | 24 | 28 | +2 STR | Vault Colossus drop |

### Shields

| Item | Tier | Lvl | Special | Source |
|------|------|-----|---------|--------|
| Scutum | 1 | 1 | Basic defense | Starter |
| Lichenward Strap | 2 | 8 | Trails to nearest mob | Drop |
| Gladiator's Guard | 3 | 14 | +1 STR | Circus Infernalis chest |
| Rhine Tower Shield | 4 | 18 | +2 STR, high defense | Rhine Fortress chest |
| Etruscan Ward | 5 | 23 | +2 INT, partial spell absorption | Oracle's Sanctum |
| Divine Bulwark | 6 | 28 | +3 all stats, fire resist | Arc 3 chest drop |

---

## 7. New Runes

| Rune | Name | Effect | Source |
|------|------|--------|--------|
| **neptune_rune** | Neptunian Tide | Applies drowning slow + poison DoT on hit | Drowned Legionnaire drop (rare) |
| **pluto_rune** | Plutonian Shadow | Amplified life-steal: 40% of hit damage returned as HP | Etruscan Shade drop (rare) |

Both work in the existing augment system alongside Ember, Frost, and Storm runes.

---

## 8. Quest Items (non-equippable, consumed or stored)

| Item ID | Name | Purpose | Found |
|---------|------|---------|-------|
| `rope` | Coil of Rope | Give to NPC ferryman (L12) | L11 chest or L12 enemy drop |
| `officer_seal` | Officer's Seal | Received from wounded NPC legionnaire (L15) after giving him a health potion | L15 NPC reward |
| `sealed_wax_tablet` | Sealed Wax Tablet | Give to NPC archivist (L17) | Spectral Stalker drop in L17 |
| `torch` | Soldier's Torch | Give to NPC guide (L21) | L20 chest drop |
| `sacred_relic` | Sacred Relic | Collect 3; give to NPC Oracle (L23) | L21–22 chest/drop |
| `forge_key` | Forge Key | Dropped by Vault Colossus; opens fire-lock in L24 | Vault Colossus drop |
| `vigiles_badge` | Vigiles Badge | Story item from dying NPC (L29); lore payoff | L29 NPC |

---

## 9. New Crafting Materials

| Item ID | Name | Source |
|---------|------|--------|
| `corroded_chain` | Corroded Chain | Drowned Legionnaire drop |
| `brine_flask` | Brine Flask | Drowned Legionnaire drop |
| `burn_salve` | Burn Salve | Scalded Attendant drop |
| `ash_shard` | Ash Shard | Scalded Attendant / Ash Revenant drop |
| `iron_core` | Iron Core | Siege Automaton drop |
| `ritual_oil` | Ritual Oil | Ritual Priest drop |
| `colossus_fragment` | Colossus Fragment | Vault Colossus drop |
| `ancient_shard` | Ancient Shard | Etruscan Shade drop |
| `jupiterian_shard` | Jupiterian Shard | Temple Sentinel drop (rune upgrade material) |

---

## 10. Sprite Requirement List

A color is assigned for placeholder use. All sprites are 32×32 px or match the existing spritesheet format.

### Enemies (full spritesheets — idle/walk/attack/death rows)

| Enemy | Placeholder Color |
|-------|------------------|
| Drowned Legionnaire | `(40, 80, 120)` — dark teal-blue |
| Scalded Attendant | `(210, 100, 30)` — burnt orange |
| Corrupt Gladiator | `(140, 40, 40)` — dark blood red |
| Siege Automaton | `(110, 110, 120)` — iron grey |
| Ash Revenant | `(190, 185, 175)` — pale ash |
| Temple Sentinel | `(210, 185, 80)` — divine gold |
| Etruscan Shade | `(90, 40, 160)` — deep violet |
| Vault Colossus | `(85, 70, 55)` — dark stone brown |
| Ritual Priest | `(40, 90, 50)` — ritual dark green |
| Malarix (Boss L10) | `(20, 20, 30)` — blackened plate |
| Nero Phase 1 (Boss L30) | `(180, 60, 20)` — burning crimson |
| Nero Phase 2 (Boss L30) | `(140, 30, 10)` — deep charred red |
| Nero Phase 3 (Boss L30) | `(255, 120, 0)` — raw fire orange |

### Weapons

| Item | Placeholder Color |
|------|------------------|
| Falx | `(80, 80, 90)` — dark curved steel |
| Warden's Halberd | `(20, 20, 25)` — black iron, gold trim |
| Siege Maul | `(100, 95, 90)` — dark grey massive |
| Colossus Arm | `(75, 65, 50)` — stone brown |
| Ignifer (legendary) | `(220, 60, 0)` — crimson fire blade |
| Brine Blade | `(50, 160, 140)` — corroded teal |
| Etruscan Ceremonial Blade | `(160, 120, 50)` — ancient bronze |
| Oracle's Shard | `(160, 100, 200)` — violet-purple |
| Void Shard | `(40, 10, 60)` — deep void purple |
| Void Condenser | `(100, 50, 180)` — arcane purple crystal |
| Storm Lance | `(80, 140, 230)` — electric blue |
| Oracle's Staff | `(230, 220, 160)` — pale gold-white |
| Divine Remnant (legendary) | `(255, 245, 180)` — bright divine gold |
| Trident | `(160, 170, 185)` — silver-blue marine |

### Armor — Head

| Item | Placeholder Color |
|------|------------------|
| Gladiator's Helm | `(130, 80, 40)` — dark bronze-red |
| Rhine Iron Helm | `(70, 70, 75)` — dark iron |
| Etruscan Death Mask | `(140, 110, 50)` — hollow-eyed bronze |
| Ash Crown (legendary) | `(50, 45, 40)` — black-grey crown |

### Armor — Chest

| Item | Placeholder Color |
|------|------------------|
| Arena Cuirass | `(150, 100, 50)` — leather-bronze |
| Ash Mantle | `(170, 165, 158)` — pale grey ash |
| Brine-Treated Mail | `(55, 120, 120)` — dark teal mail |
| Etruscan Burial Wraps | `(130, 115, 80)` — grey-gold linen |
| Vault-Forged Plate | `(60, 55, 50)` — near-black stone plate |
| Eternal Flame Cloak | `(160, 40, 20)` — deep crimson-orange |

### Armor — Boots

| Item | Placeholder Color |
|------|------------------|
| Rhine Greaves | `(75, 75, 80)` — iron grey |
| Ashen Treads | `(175, 170, 160)` — light ash |
| Shade Wraps | `(60, 30, 90)` — dark purple |
| Colossus Treads | `(80, 68, 55)` — stone brown |

### Shields

| Item | Placeholder Color |
|------|------------------|
| Gladiator's Guard | `(140, 95, 45)` — bronze round shield |
| Rhine Tower Shield | `(65, 65, 70)` — dark rectangular iron |
| Etruscan Ward | `(120, 100, 50)` — ancient bronze glow |
| Divine Bulwark | `(220, 210, 130)` — golden-white divine |

### Runes

| Item | Placeholder Color |
|------|------------------|
| Neptunian Tide | `(30, 90, 160)` — deep ocean blue |
| Plutonian Shadow | `(50, 10, 70)` — void purple-black |

### Crafting Materials

| Item | Placeholder Color |
|------|------------------|
| Corroded Chain | `(80, 110, 80)` — rusty green |
| Brine Flask | `(60, 150, 160)` — teal blue vial |
| Burn Salve | `(200, 120, 40)` — orange-amber |
| Ash Shard | `(185, 180, 172)` — pale grey chip |
| Iron Core | `(70, 68, 72)` — dark metallic grey |
| Ritual Oil | `(40, 80, 45)` — dark swamp green |
| Colossus Fragment | `(90, 78, 62)` — stone grey chunk |
| Ancient Shard | `(120, 60, 190)` — violet-purple crystal |
| Jupiterian Shard | `(200, 195, 80)` — charged gold-yellow |

### Quest Items

| Item | Placeholder Color |
|------|------------------|
| Rope | `(130, 100, 60)` — rough brown |
| Officer's Seal | `(210, 175, 50)` — gold disc |
| Sealed Wax Tablet | `(180, 140, 100)` — tan tablet, red wax dot |
| Soldier's Torch | `(200, 140, 40)` — warm orange-amber |
| Sacred Relic | `(230, 230, 255)` — soft glowing white |
| Forge Key | `(220, 110, 20)` — bright hot orange |
| Vigiles Badge | `(180, 185, 195)` — silver shield |

---

## 11. Skill Tree Extension Note

Current skill trees cap out at player level 15–16. With 30 levels, each class needs approximately 6–8 additional skill nodes covering levels 17–30, focused on the new weapons and Arc 3 power fantasy. Specific node design is deferred to a follow-up spec.

---

## 12. Implementation Order (suggested)

1. Add all new items to `data/items.json` (weapons, armor, materials, quest items, runes)
2. Add all new enemies to `data/mobs.json` with placeholder sprite colors
3. Extend `game/systems/world_ops.py` to support locked-door tile (`L`) and NPC tile (`V`)
4. Build levels 10–30 as `.txt` map files
5. Implement boss logic (Malarix L10, Nero L30 three-phase)
6. Extend class skill trees in `data/classes.json`
7. Commission/create sprites — enemies first, then weapons, then armor
