# AAA Gameplay Area Design Specifications

> Deep research compiled from Elden Ring, Dark Souls, Diablo IV, The Witcher 3,
> God of War (2018/Ragnarok), Baldur's Gate 3, Monster Hunter World, Skyrim,
> and general AAA level design practice (GDC talks, Level Design Book, industry analysis).
>
> All dimensions in meters unless noted. Designed for procedural generation in Blender.

---

## 1. Boss Arena Design

### 1.1 Shape Language & Archetypes

| Archetype | Shape | Use Case | Reference |
|---|---|---|---|
| Classic Duel | Circular | 1v1 humanoid boss (Artorias, Malenia) | Dark Souls, Elden Ring |
| Cathedral Hall | Rectangular | Multi-phase bosses with spectacle (O&S, Radahn memory) | Dark Souls (Anor Londo) |
| Multi-Tier | Circular + elevated rim | Phase transitions via verticality (Mohg, Rennala) | Elden Ring |
| Pillared Arena | Circular/rect + pillars | Ranged bosses, divide-and-conquer (O&S) | Dark Souls |
| Hazard Arena | Irregular + hazard zones | Environmental bosses (Fire Giant, lava dragon) | Elden Ring, MHW |
| Open Field | Large irregular | Mounted/gigantic bosses (Radahn festival) | Elden Ring |
| Pit Arena | Circular, sunken center | Gravity-threat bosses, falling hazard | God of War berserkers |
| Multi-Platform | Floating/separated platforms | Aerial phase bosses, grapple-based | God of War Ragnarok |

### 1.2 Arena Dimensions

| Category | Diameter/Width | Height (ceiling) | Floor Area | Player Count |
|---|---|---|---|---|
| Small Boss (humanoid duel) | 20-30m | 8-12m | 315-710 m2 | Solo |
| Medium Boss (standard) | 40-60m | 12-20m | 1,260-2,830 m2 | Solo/Co-op |
| Large Boss (giant/dragon) | 80-120m | 25-40m (or open sky) | 5,030-11,310 m2 | Solo/Co-op |
| Raid Boss / Festival | 150-250m | Open sky | 17,670-49,090 m2 | Multi (4-16) |
| Tight Berserker (GoW) | 15-20m | 6-8m | 175-315 m2 | Solo |

**Aspect ratios for rectangular arenas:** 3:2 or 2:1. Cathedral halls typically 20-30m wide x 40-60m long.

### 1.3 Floor Patterns

```
FLOOR_PATTERNS = {
    "flat": {
        "slope": 0,
        "use_case": "Standard melee duel",
        "frequency": 0.4  # 40% of all arenas
    },
    "sloped_edges": {
        "rim_slope": 10-15,  # degrees
        "center_radius_ratio": 0.6,  # flat center = 60% of total radius
        "use_case": "Funnel player to center, rolling mechanic"
    },
    "pit_center": {
        "pit_depth": 3-5,  # meters below rim
        "pit_radius_ratio": 0.3,  # center 30% is lowered
        "use_case": "Gravity boss, adds falling danger"
    },
    "raised_platform": {
        "platform_height": 2-4,
        "platform_radius_ratio": 0.25,  # center 25% elevated
        "ramp_count": 2-4,
        "use_case": "Boss stands on platform, must be climbed"
    },
    "multi_platform": {
        "platform_count": 3-5,
        "platform_radius": 5-8,
        "gap_width": 3-6,  # meters between platforms
        "connection_type": ["bridge", "jump", "grapple"],
        "use_case": "Phase-transition boss, aerial combat"
    },
    "tiered_rings": {
        "ring_count": 2-3,
        "step_height": 1.5-2.5,
        "use_case": "Elevation advantage shifts during fight"
    }
}
```

### 1.4 Environmental Hazards

```
ARENA_HAZARDS = {
    "lava_pool": {
        "radius": 2-5,
        "damage_per_second": "10-20% max_hp",
        "placement": "edges or center pit",
        "growth_rate": "expands 0.5m per phase",  # boss phase mechanic
        "visual": "orange glow, particle embers, heat distortion"
    },
    "spike_trap": {
        "size": (2, 2),  # meters
        "activation_delay": 1.5,  # seconds after trigger
        "reset_time": 4.0,
        "damage": "25-40% max_hp",
        "placement": "grid pattern, 5-8m apart",
        "visual": "floor grate, subtle steam before activation"
    },
    "collapsible_floor": {
        "section_size": (4, 4),
        "collapse_delay": 2.0,  # seconds after boss slam
        "respawn_time": 15.0,  # or never (permanent)
        "void_depth": 10,  # instant kill
        "visual": "cracked stone, dust particles, slight sag"
    },
    "poison_gas_vent": {
        "radius": 3-4,
        "activation_interval": 8-12,  # seconds cycle
        "active_duration": 3-5,
        "damage": "5% max_hp/sec + DOT",
        "visual": "green-yellow fog, bubbling ground texture"
    },
    "breakable_pillar": {
        "hp_hits": 3-5,  # hits before destruction
        "debris_radius": 3,
        "debris_damage": "15% max_hp",
        "visual": "cracked stone, each hit adds cracks"
    },
    "electrified_water": {
        "depth": 0.1-0.3,
        "trigger": "boss lightning attack",
        "damage": "20% max_hp",
        "visual": "shallow water, sparks when active"
    }
}
```

### 1.5 Cover & Pillar Placement

```
COVER_RULES = {
    # For ranged boss fights (boss shoots projectiles)
    "pillar_ring": {
        "count": 4-6,
        "radius_ratio": 0.5-0.7,  # of arena radius
        "angular_spacing": "even",  # 360/count degrees apart
        "pillar_radius": 0.8-1.5,
        "pillar_height": 3-5,
        "breakable": True,  # 3-5 hits to destroy
        "material": "stone, cracked"
    },
    # For multi-phase boss (phase 1 with cover, phase 2 destroys it)
    "destructible_cover": {
        "count": 6-8,
        "spacing": 8-15,  # meters between pieces
        "types": ["pillar", "statue", "wall_segment", "altar"],
        "hp": "2-4 boss attacks to destroy",
        "debris_stays": True  # low cover after destruction
    },
    # For melee boss (minimal cover, mostly for healing windows)
    "sparse_obstacles": {
        "count": 2-3,
        "placement": "asymmetric",
        "purpose": "brief_line_of_sight_break",
        "spacing": 10-20
    },
    # Spacing rules (universal)
    "min_cover_distance": 8,   # meters - never closer than this
    "max_cover_distance": 15,  # meters - at least one cover within this range
    "cover_to_wall_min": 3,    # meters from arena edge
    "cover_height_low": 1.0,   # crouch cover
    "cover_height_high": 2.5   # full cover, blocks line of sight
}
```

### 1.6 Entrance & Exit Design

```
ARENA_ENTRANCE = {
    "chokepoint_entry": {
        "width": 3-4,          # meters - forces single-file entry
        "length": 5-8,         # approach corridor length
        "ceiling_height": 3-4,
        "visual_cues": ["torches flanking door", "blood trails on floor",
                       "weapon racks / warning totems", "NPC summon sign"]
    },
    "fog_gate": {
        "width": 3-4,
        "visual": "translucent white/gold mist barrier",
        "function": "locks after entry, prevents retreat",
        "telegraph_distance": 15-20  # visible from this far away
    },
    "arena_lock_mechanism": {
        "lock_delay": 2-3,     # seconds after player enters center zone
        "lock_type": ["fog_gate_seals", "portcullis_drops", "rubble_collapse",
                      "magic_barrier_forms"],
        "unlock_condition": "boss_defeated"
    },
    "boss_entrance_cinematic": {
        "camera_trigger_distance": 10-15,  # from boss spawn point
        "cinematic_duration": 3-8,         # seconds
        "player_invulnerable": True,       # during cinematic
        "types": ["boss_drops_from_above", "boss_emerges_from_ground",
                 "boss_walks_through_far_door", "boss_materializes"]
    }
}
```

### 1.7 Lighting Design

```
ARENA_LIGHTING = {
    "dramatic_spotlight": {
        "center_intensity": 1.0,
        "edge_intensity": 0.2-0.3,
        "falloff": "inverse_square",
        "source": "overhead opening / skylight / chandelier",
        "purpose": "draw player to center, boss silhouette"
    },
    "dark_edges_bright_center": {
        "center_radius_ratio": 0.5,
        "ambient_light": 0.1,
        "center_light": 0.8,
        "hazard_glow": 0.4,  # hazards self-illuminate
        "fog_density": 0.3
    },
    "colored_atmospheric": {
        "presets": {
            "fire_boss": {"color": (1.0, 0.4, 0.1), "fog": "warm_orange"},
            "ice_boss": {"color": (0.3, 0.5, 1.0), "fog": "cold_blue"},
            "poison_boss": {"color": (0.2, 0.8, 0.3), "fog": "sickly_green"},
            "void_boss": {"color": (0.4, 0.1, 0.6), "fog": "deep_purple"},
            "holy_boss": {"color": (1.0, 0.9, 0.6), "fog": "golden_haze"},
            "undead_boss": {"color": (0.5, 0.5, 0.6), "fog": "grey_mist"}
        }
    },
    "phase_transition_lighting": {
        "transition_duration": 2-4,  # seconds
        "effect": "lights_flicker_then_color_shift",
        "intensity_spike": 2.0,  # brief flash at phase change
        "new_color_lerp": 3.0    # seconds to blend to new color
    }
}
```

### 1.8 Verticality

```
ARENA_VERTICALITY = {
    "balcony_ring": {
        "height": 4-6,          # meters above arena floor
        "width": 3-4,           # walkable width
        "access": ["staircase", "ladder", "grapple_point", "boss_knockback"],
        "railing_gaps": 2-4,    # places player can fall/jump down
        "use_case": "Phase 2: boss jumps to balcony, ranged phase"
    },
    "destructible_platform": {
        "height": 3-5,
        "radius": 4-6,
        "collapse_trigger": "boss_slam_attack",
        "supports_visible": True,  # player can see breakable supports
        "use_case": "Arena shrinks over time"
    },
    "elevated_weak_point": {
        "height": 6-10,  # where boss weak spot is
        "access_method": ["climb_boss", "shoot_ranged", "use_environment",
                         "wait_for_stagger"],
        "platform_near_height": True,  # optional jumping platform
        "use_case": "Giant boss, must reach head/back"
    },
    "multi_level_arena": {
        "levels": 2-3,
        "level_height": 4-5,
        "connections": ["ramps", "elevators", "jump_pads", "holes_in_floor"],
        "boss_can_reach_all": True  # boss can attack any level
    }
}
```

---

## 2. Mob Encounter Zones

### 2.1 Patrol Path Generation

```
PATROL_PATTERNS = {
    "figure_eight": {
        "algorithm": "Two overlapping circles, waypoints at intersection",
        "loop_radius": 8-15,   # each circle radius
        "total_length": 50-95, # approximate path length
        "waypoint_count": 8-12,
        "pause_duration": 2-5, # seconds at each waypoint
        "use_case": "Guards covering two areas",
        "implementation": """
            center1 = spawn + (loop_radius, 0, 0)
            center2 = spawn - (loop_radius, 0, 0)
            points = sample_circle(center1, N/2) + sample_circle(center2, N/2)
            """
    },
    "circular": {
        "algorithm": "Single circle around center point",
        "radius": 5-20,
        "waypoint_count": 4-8,
        "pause_duration": 3-8,
        "facing": "outward",  # guards look outward from circle
        "use_case": "Camp perimeter guard"
    },
    "linear_waypoint": {
        "algorithm": "A-to-B path with optional intermediate stops",
        "length": 15-40,
        "waypoint_count": 2-6,
        "return_mode": "reverse",  # walk back same path
        "pause_at_ends": 5-10,     # seconds, longer pause at endpoints
        "use_case": "Road patrol, bridge guard"
    },
    "random_wander": {
        "algorithm": "Random point within radius, navmesh-constrained",
        "wander_radius": 8-15,
        "new_point_interval": 5-12,  # seconds between new targets
        "idle_chance": 0.3,          # 30% chance to idle instead of move
        "idle_duration": 3-8,
        "use_case": "Wildlife, passive mobs, grazing animals"
    },
    "sentinel": {
        "algorithm": "Stationary with periodic rotation",
        "rotation_angle": 90-180,    # degrees of scan arc
        "rotation_speed": 30,        # degrees per second
        "pause_at_extremes": 2-4,
        "alert_radius": 15-25,       # detection range
        "use_case": "Tower lookout, gate guard"
    }
}
```

### 2.2 Encounter Density by Area Type

```
# Density = enemies per 100m x 100m area (10,000 m2)
ENCOUNTER_DENSITY = {
    "wilderness_sparse": {
        "mobs_per_10k_m2": 1-3,
        "group_size": 1-2,
        "spacing_between_groups": 80-150,  # meters
        "examples": "open plains, high mountains, deep forest",
        "safe_path_exists": True
    },
    "wilderness_normal": {
        "mobs_per_10k_m2": 3-6,
        "group_size": 2-4,
        "spacing_between_groups": 50-80,
        "examples": "Limgrave fields, Velen countryside",
        "safe_path_exists": True
    },
    "road_patrolled": {
        "mobs_per_10k_m2": 0-1,
        "group_size": 2-3,
        "spacing_between_groups": 150-300,
        "examples": "main roads, trade routes",
        "safe_path_exists": True,
        "note": "Roads are intentionally safer in most ARPGs"
    },
    "road_dangerous": {
        "mobs_per_10k_m2": 2-4,
        "group_size": 3-5,
        "spacing_between_groups": 60-100,
        "examples": "bandit territory roads, corrupted paths",
        "safe_path_exists": False
    },
    "dungeon_corridors": {
        "mobs_per_room": 2-5,
        "room_size": "15x15 to 25x25",
        "spacing_between_encounters": 15-30,
        "examples": "dungeon hallways, crypt tunnels"
    },
    "dungeon_rooms": {
        "mobs_per_room": 3-8,
        "room_size": "20x20 to 40x40",
        "encounter_type": "contained_arena",
        "examples": "dungeon chambers, boss antechambers"
    },
    "settlement_outskirts": {
        "mobs_per_10k_m2": 2-5,
        "group_size": 3-6,
        "spacing_between_groups": 40-60,
        "examples": "ruined village perimeter, camp surroundings"
    },
    "stronghold": {
        "mobs_per_10k_m2": 8-15,
        "group_size": 4-8,
        "spacing_between_groups": 15-30,
        "examples": "Diablo IV strongholds, enemy forts",
        "has_boss": True,
        "elite_ratio": 0.2  # 20% are elites
    }
}
```

### 2.3 Mob Group Composition

```
MOB_GROUP_TEMPLATES = {
    "scout_pack": {
        "composition": {"elite": 1, "fodder": 3-5},
        "formation": "elite_rear_fodder_front",
        "spacing": 3-5,        # meters between mobs
        "aggro_range": 15-20,
        "leash_range": 40-60,  # max chase distance
        "behavior": "elite commands, fodder charges first",
        "reference": "Dark Souls hollow soldiers + knight"
    },
    "ambush": {
        "composition": {"hidden": 3-6},
        "formation": "scattered_hidden",
        "trigger_radius": 5-8,
        "spawn_from": ["behind_rocks", "underground", "ceiling",
                      "disguised_as_corpse", "invisible_until_close"],
        "attack_delay_stagger": 0.5-1.5,  # seconds between each reveal
        "behavior": "surprise attack from multiple angles",
        "reference": "DS3 Irithyll slaves, Elden Ring Imps"
    },
    "patrol": {
        "composition": {"standard": 2-3},
        "formation": "line_or_vee",
        "spacing": 2-4,
        "patrol_pattern": "linear_waypoint",
        "alert_propagation": 10-15,  # meters - one alerts others
        "behavior": "synchronized movement, one spots = all aggro",
        "reference": "Witcher 3 drowner packs, DS knight patrols"
    },
    "nest_camp": {
        "composition": {"leader": 1, "standard": 3-5, "fodder": 3-5},
        "formation": "clustered_around_center",
        "center_object": ["campfire", "nest", "totem", "corpse_pile",
                         "treasure_hoard"],
        "cluster_radius": 6-10,
        "aggro_range": 12-18,
        "behavior": "idle animations at camp, all aggro together",
        "reference": "Elden Ring soldier camps, Witcher 3 monster nests"
    },
    "ranged_support": {
        "composition": {"ranged": 2-3, "melee_shield": 1-2},
        "formation": "ranged_elevated_melee_front",
        "elevation_difference": 3-5,
        "spacing": 4-6,
        "behavior": "ranged on high ground, melee blocks approach",
        "reference": "DS3 Lothric knights + crossbowmen"
    },
    "swarm": {
        "composition": {"weak_fodder": 8-15},
        "formation": "loose_cluster",
        "spacing": 1-2,
        "aggro_range": 8-12,
        "behavior": "overwhelm through numbers, low individual HP",
        "reference": "Diablo IV spider swarms, DS rats"
    },
    "mini_boss_guard": {
        "composition": {"mini_boss": 1, "elite": 2, "fodder": 3-4},
        "formation": "boss_center_guards_ring",
        "ring_radius": 5-8,
        "behavior": "guards engage first, mini-boss enters after 5-10sec",
        "reference": "Elden Ring field bosses with soldiers"
    }
}
```

### 2.4 Terrain Advantage Rules

```
TERRAIN_ADVANTAGE = {
    "high_ground_ranged": {
        "elevation": 3-6,        # meters above player approach path
        "platform_size": (3, 4), # meters, enough for 2-3 ranged mobs
        "visibility_cone": 120,  # degrees field of fire
        "approach_difficulty": "must_find_alternate_path_or_tank",
        "placement_rule": "At least 1 elevated position per encounter > 4 mobs"
    },
    "chokepoint_defense": {
        "passage_width": 2-3,     # forces single-file
        "defender_count": 1-2,    # shield enemies in choke
        "flanking_path": True,    # MUST exist but hidden/longer
        "flanking_path_length": "2-3x direct route length",
        "placement_rule": "Chokepoints should never be the ONLY path"
    },
    "flanking_positions": {
        "angle_from_player_entry": 60-120,  # degrees off main approach
        "distance_from_main_group": 10-20,
        "hidden_by": ["wall_corner", "foliage", "elevation_change"],
        "trigger": "player_engages_main_group",
        "delay": 3-5,  # seconds after main combat starts
        "placement_rule": "Max 1 flanking group per encounter"
    },
    "retreat_trap": {
        "placement": "behind_player_entry",
        "trigger": "player_retreats_past_threshold",
        "mob_count": 2-3,
        "purpose": "punish panic retreats, reward tactical play"
    }
}
```

### 2.5 Safe Path Design

```
SAFE_PATH_RULES = {
    "main_road_buffer": {
        "buffer_distance": 20-30,     # meters from road center
        "mob_density_in_buffer": 0,   # zero mobs within buffer
        "exceptions": ["scripted_ambush_quest", "boss_roadblock"],
        "visual_markers": ["road_markers", "torch_posts", "guard_towers"]
    },
    "stealth_route": {
        "width": 2-3,
        "concealment": ["tall_grass", "shadow", "water", "crawl_space"],
        "mob_awareness": "reduced",   # mobs face away from stealth route
        "length_multiplier": 1.5-2.0, # longer than direct path
        "placement": "flanks encounter zones"
    },
    "difficulty_signposting": {
        "easy_area_visual": "well-lit, flowers, birdsong, green grass",
        "medium_area_visual": "overcast, dead trees, crows, brown grass",
        "hard_area_visual": "dark fog, red sky, corrupted ground, silence",
        "deadly_area_visual": "ash, bone piles, ominous glow, no wildlife"
    }
}
```

### 2.6 Encounter Space Shapes

```
ENCOUNTER_SPACE_SHAPES = {
    "clearing": {
        "use": "standard melee combat",
        "shape": "circular or irregular oval",
        "size": "15-30m diameter",
        "terrain": "relatively flat, slight variation",
        "surrounding": "dense trees/rocks forming natural walls",
        "exits": 2-3
    },
    "elevated_platform": {
        "use": "ranged enemies with height advantage",
        "shape": "rectangular raised area",
        "size": "10-15m x 5-8m",
        "height": "3-6m above approach",
        "player_approach": "ramp or ladder, exposed during climb"
    },
    "narrow_corridor": {
        "use": "ambush encounters, linear gauntlets",
        "shape": "long rectangle",
        "size": "3-5m wide x 15-30m long",
        "cover": "alcoves every 5-8m on alternating sides",
        "mob_placement": "staggered depth"
    },
    "multi_room": {
        "use": "Diablo IV dungeon encounters",
        "shape": "connected chambers",
        "room_count": 2-4,
        "room_size": "10-20m each",
        "connection_width": 3-5,
        "encounter_flow": "room_by_room_progression"
    },
    "open_field": {
        "use": "mounted combat, large monster encounters",
        "shape": "large irregular area",
        "size": "60-120m across",
        "features": ["scattered_rocks", "elevation_changes", "water_features"],
        "reference": "Elden Ring open-world boss encounters"
    }
}
```

---

## 3. Settlement / City Mapping

### 3.1 District Generation

```
DISTRICT_TYPES = {
    "market": {
        "area_ratio": 0.08-0.12,    # fraction of total city area
        "building_types": ["shop", "stall", "warehouse", "inn", "tavern"],
        "road_density": "high",
        "open_space": 0.3-0.4,       # 30-40% open (market square + stall space)
        "placement": "central, near main gate",
        "NPC_density": "highest",
        "props": ["crates", "barrels", "market_stalls", "hanging_signs",
                 "lanterns", "carts"]
    },
    "residential": {
        "area_ratio": 0.25-0.35,
        "building_types": ["house_small", "house_medium", "house_large",
                          "apartment_row"],
        "road_density": "medium",
        "open_space": 0.1-0.2,
        "placement": "fills between other districts",
        "NPC_density": "medium",
        "garden_chance": 0.3
    },
    "religious": {
        "area_ratio": 0.05-0.10,
        "building_types": ["cathedral", "chapel", "graveyard", "monastery",
                          "shrine"],
        "road_density": "low",
        "open_space": 0.4-0.5,        # large churchyards
        "placement": "elevated or central landmark",
        "has_landmark": True,
        "height_dominance": "tallest buildings in city"
    },
    "military": {
        "area_ratio": 0.08-0.12,
        "building_types": ["barracks", "armory", "training_yard", "stable",
                          "watchtower", "gatehouse"],
        "road_density": "medium",
        "open_space": 0.3,             # parade grounds
        "placement": "near walls/gates",
        "wall_adjacent": True
    },
    "slums": {
        "area_ratio": 0.10-0.15,
        "building_types": ["shack", "lean_to", "hovel", "den"],
        "road_density": "very_high",   # maze-like narrow alleys
        "open_space": 0.05-0.1,
        "placement": "edge of city, outside inner walls",
        "building_condition": "dilapidated",
        "alley_width": 1.0-1.5        # barely passable
    },
    "noble_quarter": {
        "area_ratio": 0.10-0.15,
        "building_types": ["mansion", "estate", "garden", "fountain",
                          "private_chapel"],
        "road_density": "low",
        "open_space": 0.3-0.4,         # gardens, courtyards
        "placement": "inner city, near castle/keep",
        "building_size": "2-4x residential",
        "wall_enclosed": True           # inner wall separating from commoners
    },
    "docks": {
        "area_ratio": 0.05-0.10,
        "building_types": ["warehouse", "fishery", "shipyard", "sailor_inn",
                          "customs_house"],
        "road_density": "medium",
        "open_space": 0.2,
        "placement": "waterfront",
        "requires": "water_feature"
    },
    "craftsmen": {
        "area_ratio": 0.08-0.12,
        "building_types": ["forge", "tannery", "carpenter", "alchemist",
                          "weaver"],
        "road_density": "medium",
        "open_space": 0.15,
        "placement": "between market and residential",
        "smoke_vfx": True,
        "noise_level": "high"
    }
}
```

### 3.2 Road Hierarchy

```
ROAD_HIERARCHY = {
    "main_road": {
        "width": 5-6,           # meters
        "surface": "cobblestone",
        "connects": "gates to market square to castle/keep",
        "traffic": "heavy",
        "curb_height": 0.15,
        "drainage_gutter": True,
        "lamp_spacing": 15-20,   # meters between lamp posts
        "NPC_traffic": "constant flow"
    },
    "secondary_road": {
        "width": 3-4,
        "surface": "cobblestone or packed_dirt",
        "connects": "districts to main road",
        "traffic": "moderate",
        "curb_height": 0.1,
        "lamp_spacing": 25-35
    },
    "alley": {
        "width": 1.5-2.0,
        "surface": "dirt or uneven_stone",
        "connects": "buildings within districts",
        "traffic": "light",
        "no_curb": True,
        "lamp_spacing": "none or 40+",
        "can_be_dead_end": True,  # 20% chance
        "overhangs": True          # upper floors extend over alley
    },
    "path": {
        "width": 0.8-1.2,
        "surface": "dirt or grass",
        "connects": "gardens, shortcuts, back entrances",
        "traffic": "minimal",
        "note": "Player-only paths through gardens/between buildings"
    }
}
```

### 3.3 Building Density

```
BUILDING_DENSITY = {
    "urban_core": {
        "coverage": 0.80-0.90,    # 80-90% of ground covered by buildings
        "floor_count": 2-4,
        "setback": 0,              # buildings touch road edge
        "gap_between_buildings": 0-0.5,
        "reference": "Novigrad inner city, Leyndell main streets"
    },
    "inner_city": {
        "coverage": 0.60-0.80,
        "floor_count": 2-3,
        "setback": 0-1,
        "gap_between_buildings": 0.5-2
    },
    "suburbs": {
        "coverage": 0.40-0.60,
        "floor_count": 1-2,
        "setback": 2-5,
        "gap_between_buildings": 3-8,
        "has_yard": True
    },
    "village": {
        "coverage": 0.20-0.35,
        "floor_count": 1-2,
        "setback": 3-8,
        "gap_between_buildings": 5-15,
        "has_garden": True,
        "has_animal_pen": 0.3
    },
    "farmland": {
        "coverage": 0.05-0.15,
        "floor_count": 1,
        "field_size": "30x30 to 60x60",
        "farmhouse_count": "1 per field cluster",
        "barn_chance": 0.5
    }
}
```

### 3.4 NPC Placement Rules

```
NPC_PLACEMENT = {
    "shopkeeper": {
        "location": "behind_market_stall or inside_shop_doorway",
        "schedule": "dawn_to_dusk",
        "idle_animation": "bartering, arranging_goods",
        "spacing": "1 per shop/stall"
    },
    "guard": {
        "locations": ["gate_flanking", "intersection", "noble_quarter_entrance",
                     "castle_entrance", "wall_patrol"],
        "spacing_gates": "2 per gate (flanking)",
        "spacing_intersections": "1 per major intersection",
        "spacing_walls": "1 per 30-50m of wall",
        "patrol_pattern": "linear_waypoint or sentinel",
        "alert_radius": 20
    },
    "civilian": {
        "locations": ["roads", "market_square", "parks", "tavern_interior"],
        "density_market": "8-15 per market square",
        "density_road": "2-5 per 100m of main road",
        "density_residential": "1-3 per 100m",
        "behavior": ["walking", "talking_pair", "sitting", "shopping",
                    "carrying_goods"],
        "schedule": True  # day/night behavior
    },
    "quest_giver": {
        "location": "high_traffic area with clear sightlines",
        "visual_indicator": "unique_outfit or icon_marker",
        "spacing": "30-50m between quest givers minimum",
        "never_in": "back alleys, hidden areas"
    },
    "blacksmith": {
        "location": "craftsmen_district or near_military",
        "props_required": ["forge", "anvil", "weapon_rack"],
        "sound_radius": 15  # hammer sounds audible from this far
    }
}
```

### 3.5 Landmark Placement

```
LANDMARK_RULES = {
    "visibility": {
        "min_visible_angles": 3,         # visible from at least 3 approaches
        "visible_distance": 200-500,     # meters
        "height_above_surroundings": "1.5-3x tallest nearby building",
        "silhouette_unique": True         # distinct outline at distance
    },
    "placement": {
        "at_road_intersection": True,     # major landmarks at intersections
        "elevated_position": True,        # on hill, raised platform, or tall
        "near_district_boundary": True,   # marks transition between areas
        "spacing": 150-300                # meters between major landmarks
    },
    "types": {
        "cathedral_tower": {"height": 25-40, "visible_from": "entire_city"},
        "castle_keep": {"height": 20-35, "position": "highest_ground"},
        "market_fountain": {"height": 5-8, "position": "market_center"},
        "city_gate": {"height": 10-15, "position": "wall_entry"},
        "bridge": {"span": 20-50, "position": "over_river"},
        "monument_statue": {"height": 8-15, "position": "plaza_center"}
    },
    "reference_cities": {
        "Novigrad": "Cathedral dominates skyline, docks visible from heights, "
                    "temple island as focal point, hierarchical bridge network",
        "Beauclair": "Palace on hill visible from everywhere, vineyard terraces "
                    "creating visual layers, color-coded districts (warm south, "
                    "cool north), grand tournament arena as secondary landmark",
        "Leyndell": "Erdtree as ultimate landmark visible from entire map, "
                    "tiered vertical city built on/around massive tree roots, "
                    "dragon corpses as organic landmarks, collapsed sections "
                    "creating exploration puzzles"
    }
}
```

### 3.6 City Generation Algorithm

```
CITY_GENERATION_STEPS = [
    {
        "step": 1,
        "name": "Define Boundary & Terrain",
        "actions": [
            "Place city center point (keep/castle/market)",
            "Generate city wall polygon (irregular circle, 200-800m diameter)",
            "Identify water features (river, coast)",
            "Mark elevation (hills for noble/religious, low for slums/docks)",
            "Place 2-4 gates in walls (on major road axes)"
        ]
    },
    {
        "step": 2,
        "name": "Road Network Generation",
        "algorithm": "L-system or agent-based road growth",
        "actions": [
            "Connect gates with main roads through city center",
            "Branch secondary roads from main roads (30-60 degree angles)",
            "Fill remaining space with alleys (organic/irregular)",
            "Ensure all areas reachable (connectivity check)",
            "Add dead-ends in slums (10-20% of alleys)"
        ]
    },
    {
        "step": 3,
        "name": "District Assignment",
        "algorithm": "Voronoi + constraint satisfaction",
        "actions": [
            "Noble quarter: near castle, on high ground",
            "Market: at main road intersection, near gate",
            "Religious: elevated or central, away from slums",
            "Military: adjacent to walls/gates",
            "Slums: outer ring, downhill, near docks/industry",
            "Residential: fills remaining space",
            "Craftsmen: between market and residential"
        ]
    },
    {
        "step": 4,
        "name": "Building Placement",
        "algorithm": "Parcel subdivision + template selection",
        "actions": [
            "Subdivide road-bounded blocks into building parcels",
            "Select building template by district + parcel size",
            "Orient buildings facing road (front door to nearest road)",
            "Apply density rules per district type",
            "Add setbacks and gaps per density tier",
            "Generate gardens/yards for low-density parcels"
        ]
    },
    {
        "step": 5,
        "name": "Props & Detail",
        "actions": [
            "Place lamp posts along roads (per spacing rules)",
            "Add market stalls in market district",
            "Place barrels, crates, carts along trade roads",
            "Add vegetation (trees in noble quarter, weeds in slums)",
            "Place signs on shop buildings",
            "Add well/fountain per district (1-2 per district)"
        ]
    },
    {
        "step": 6,
        "name": "NPC Population",
        "actions": [
            "Place guards at gates and intersections",
            "Place shopkeepers at market stalls",
            "Distribute civilians on roads (density per type)",
            "Place quest givers at high-traffic locations",
            "Add ambient NPCs (beggars in slums, nobles in quarter)",
            "Generate patrol routes for guard NPCs"
        ]
    }
]
```

---

## 4. Dungeon Entrance Design

### 4.1 Visual Language by Type

```
DUNGEON_ENTRANCE_TYPES = {
    "cave_mouth": {
        "width": 4-8,
        "height": 3-6,
        "shape": "irregular_arch",
        "surface": "natural_rock",
        "props": ["stalactites", "moss", "cobwebs", "bones_at_threshold"],
        "lighting": "dark_interior_vs_bright_exterior",
        "sound": "wind_echo, dripping_water",
        "terrain_around": "rocky_hillside, narrow_approach_path",
        "difficulty_tier": "any"
    },
    "ruined_doorway": {
        "width": 3-5,
        "height": 4-6,
        "shape": "pointed_arch or round_arch",
        "surface": "crumbling_stone, overgrown_ivy",
        "props": ["broken_door_hinges", "fallen_masonry", "torch_sconces_empty"],
        "lighting": "shadowed_interior",
        "sound": "creaking_wood, distant_moans",
        "terrain_around": "ruined_walls_flanking, rubble_approach",
        "difficulty_tier": "medium"
    },
    "descending_staircase": {
        "width": 2-4,
        "step_count": 12-30,
        "step_height": 0.2,
        "step_depth": 0.3,
        "total_descent": 2.4-6.0,
        "shape": "straight or spiral",
        "surface": "worn_stone",
        "props": ["wall_torches_every_5_steps", "carved_runes", "blood_drips"],
        "lighting": "decreasing_with_depth",
        "sound": "echoing_footsteps",
        "difficulty_tier": "medium-hard"
    },
    "portal": {
        "width": 3-4,
        "height": 4-5,
        "shape": "arch with magical frame",
        "surface": "carved_stone_with_runes",
        "vfx": ["swirling_energy", "particle_ring", "color_based_on_element"],
        "lighting": "self_illuminated",
        "sound": "humming_energy, otherworldly_whispers",
        "terrain_around": "ritual_circle, standing_stones",
        "difficulty_tier": "hard-deadly"
    },
    "fog_gate": {
        "width": 3-4,
        "height": 4-5,
        "shape": "translucent_barrier",
        "surface": "glowing_mist",
        "interaction": "walk_through_with_confirmation",
        "lighting": "diffuse_glow",
        "sound": "ethereal_hum",
        "reference": "Dark Souls / Elden Ring fog walls",
        "difficulty_tier": "boss_behind"
    },
    "grand_gate": {
        "width": 6-10,
        "height": 8-12,
        "shape": "massive_double_door",
        "surface": "reinforced_wood_and_iron",
        "props": ["skull_knocker", "chains", "guard_statues",
                 "warning_inscriptions"],
        "lighting": "torches_flanking",
        "sound": "heavy_creak_on_open",
        "terrain_around": "wide_approach_plaza",
        "difficulty_tier": "hard"
    }
}
```

### 4.2 Approach Path Design

```
APPROACH_PATH = {
    "narrowing_path": {
        "start_width": 8-12,       # meters, at approach start
        "end_width": 3-5,          # at entrance
        "length": 30-60,           # total approach
        "narrowing_curve": "gradual",  # not sudden
        "terrain_change": "open_to_enclosed",
        "vegetation_change": "healthy_to_dead",
        "lighting_change": "bright_to_dim"
    },
    "environmental_storytelling": {
        "distance_30m": ["warning_sign", "skull_totem", "bloodstains"],
        "distance_20m": ["abandoned_campfire", "corpse_of_adventurer",
                        "broken_weapons"],
        "distance_10m": ["fresh_blood", "claw_marks", "destroyed_barricade"],
        "distance_5m": ["eerie_silence", "cold_draft", "flickering_light"],
        "principle": "escalating_dread"
    },
    "enemy_preview": {
        "at_30m": "none or distant silhouette",
        "at_20m": "weakest mobs (scouts, rats)",
        "at_10m": "standard mobs (guard encounter)",
        "at_entrance": "mini-boss or gate guardian (optional)",
        "purpose": "preview dungeon mob types before committing"
    }
}
```

### 4.3 Transition Space (Buffer Zone)

```
TRANSITION_ZONE = {
    "length": 10-20,              # meters between outside and first room
    "purpose": [
        "Loading buffer for streaming",
        "Atmosphere transition (sound, light, temperature)",
        "Point of no return warning",
        "Equipment check area (safe from combat)"
    ],
    "layout": {
        "shape": "corridor narrowing slightly",
        "width_start": 4-6,
        "width_end": 3-4,
        "ceiling_height": 3-5,
        "bend": "slight_curve",    # prevents seeing first room from outside
        "lighting": "torches decreasing in frequency"
    },
    "features": {
        "checkpoint": True,         # save point / respawn anchor
        "lore_item": 0.5,          # 50% chance of note/book/inscription
        "equipment_prep": True,     # safe space to change gear
        "shortcut_door": True,      # locked from this side, opens later
        "map_marker": True          # reveals on world map
    },
    "audio_transition": {
        "outdoor_ambient_fadeout": 5,  # meters to fade outdoor sounds
        "indoor_ambient_fadein": 8,    # meters for indoor echo to reach full
        "reverb_increase": "gradual",
        "music_transition": "crossfade over 10m"
    }
}
```

### 4.4 Difficulty Signaling

```
DIFFICULTY_SIGNALS = {
    "tier_1_easy": {
        "color_palette": "warm browns, greens",
        "entrance_size": "wide, inviting",
        "corpse_count": 0,
        "warning_signs": [],
        "ambient_sound": "gentle wind, birds nearby",
        "mob_preview": "passive creatures visible"
    },
    "tier_2_medium": {
        "color_palette": "grey stone, muted tones",
        "entrance_size": "standard",
        "corpse_count": 1-2,
        "warning_signs": ["old bloodstains", "scratched walls"],
        "ambient_sound": "distant growls, dripping water",
        "mob_preview": "1-2 weak mobs near entrance"
    },
    "tier_3_hard": {
        "color_palette": "dark grey, red accents",
        "entrance_size": "imposing, oversized",
        "corpse_count": 3-5,
        "warning_signs": ["skull_totems", "impaled_corpses",
                         "glowing_runes", "corrupted_vegetation"],
        "ambient_sound": "ominous_drone, distant_screams",
        "mob_preview": "tough mobs guarding approach"
    },
    "tier_4_deadly": {
        "color_palette": "black, crimson, otherworldly glow",
        "entrance_size": "massive or tiny (both signal extremes)",
        "corpse_count": "many, recent",
        "warning_signs": ["boss_shadow_visible", "ground_tremors",
                         "magic_barrier_barely_containing",
                         "NPC_warning_you_directly"],
        "ambient_sound": "heartbeat_bass, silence_then_roar",
        "mob_preview": "mini-boss at entrance"
    }
}
```

---

## 5. Points of Interest (POI)

### 5.1 POI Type Definitions

```
POI_TYPES = {
    "treasure_cache": {
        "subtypes": ["hidden_alcove", "chest_on_pedestal", "underwater_cache",
                    "buried_treasure", "locked_room", "trapped_chest"],
        "size": "3-5m radius interaction area",
        "visibility_from_distance": "low",  # reward exploration
        "discovery_method": ["exploration", "map_clue", "NPC_hint",
                           "environmental_clue"],
        "loot_quality": "scales with distance from safe_zone",
        "guard_chance": 0.4,  # 40% have a guardian mob
        "frequency": "highest"
    },
    "lore_location": {
        "subtypes": ["ruined_shrine", "ancient_monument", "battlefield_remains",
                    "ghost_encounter", "inscription_wall", "library_fragment"],
        "size": "5-15m radius",
        "visibility_from_distance": "medium",
        "discovery_method": ["unique_silhouette", "atmospheric_change",
                           "NPC_reference"],
        "reward": "lore_text + minor_item",
        "ambient_change": True,  # unique ambient sound/lighting
        "frequency": "medium"
    },
    "resource_node": {
        "subtypes": ["herb_garden", "mining_deposit", "fishing_spot",
                    "lumber_grove", "crystal_formation", "alchemy_ingredients"],
        "size": "3-8m radius",
        "visibility_from_distance": "medium",
        "visual_beacon": "distinct_color (herbs=green, ore=metallic_glint, etc)",
        "respawn_time": "3-5 in-game_days",
        "clustering": "2-4 nodes within 20m radius",
        "frequency": "highest"
    },
    "puzzle_location": {
        "subtypes": ["pressure_plates", "rotating_statues", "light_beam_puzzle",
                    "sequence_lock", "environmental_riddle", "hidden_switch"],
        "size": "10-25m radius",
        "visibility_from_distance": "medium-high",
        "complexity_time": "30sec to 5min",
        "reward": "unique_item or shortcut_access",
        "hint_system": "environmental clues within 10m",
        "frequency": "low"
    },
    "combat_challenge": {
        "subtypes": ["monster_nest", "bandit_camp", "cursed_ground",
                    "summoning_circle", "mini_boss_lair"],
        "size": "15-30m radius",
        "visibility_from_distance": "high",
        "visual_beacon": "smoke, red glow, circling_birds",
        "enemy_count": 5-12,
        "has_elite": True,
        "reward": "combat_loot + area_cleared_bonus",
        "respawn": "only_on_rest or never",
        "frequency": "medium-high"
    },
    "vista_point": {
        "subtypes": ["cliff_overlook", "tower_top", "treetop_platform"],
        "size": "5-10m radius",
        "visibility_from_distance": "high (elevated)",
        "reward": "map_reveal + fast_travel_unlock",
        "purpose": "orientation + reward + beauty",
        "always_safe": True,
        "frequency": "low"
    },
    "NPC_encounter": {
        "subtypes": ["wandering_merchant", "quest_giver", "lore_keeper",
                    "prisoner_to_rescue", "ambush_NPC"],
        "size": "5-10m radius",
        "visibility_from_distance": "low-medium",
        "campfire_chance": 0.5,
        "escort_quest_chance": 0.2,
        "frequency": "low-medium"
    },
    "environmental_hazard": {
        "subtypes": ["poison_swamp", "lava_field", "bottomless_pit",
                    "magical_anomaly", "cursed_fog"],
        "size": "20-50m radius",
        "visibility_from_distance": "high",
        "traversal_method": "specific item/ability required",
        "reward": "unique_item hidden within",
        "damage_type": "continuous_DOT",
        "frequency": "low"
    }
}
```

### 5.2 POI Spacing Rules

```
POI_SPACING = {
    # The 40-Second Rule (CD Projekt RED / Witcher 3):
    # Player should encounter something interesting every ~40 seconds of travel.
    # At average run speed (~6 m/s), this equals ~240m between POIs.
    # At horse/mount speed (~12 m/s), this equals ~480m.

    "dense_zone": {
        "poi_spacing": 100-200,       # meters between POIs
        "poi_per_km2": 25-50,
        "area_type": "settled lands, quest hubs, dungeon areas",
        "diversity_rule": "no 2 same-type POIs within 300m",
        "travel_time_between": "15-30 seconds on foot"
    },
    "normal_zone": {
        "poi_spacing": 200-350,
        "poi_per_km2": 10-25,
        "area_type": "standard wilderness, road networks",
        "diversity_rule": "no 2 same-type POIs within 500m",
        "travel_time_between": "30-60 seconds on foot"
    },
    "sparse_zone": {
        "poi_spacing": 350-500,
        "poi_per_km2": 4-10,
        "area_type": "deep wilderness, mountains, sea",
        "diversity_rule": "no 2 same-type POIs within 800m",
        "travel_time_between": "60-90 seconds on foot"
    },
    "forbidden_zone": {
        "poi_spacing": 500-1000,
        "poi_per_km2": 1-4,
        "area_type": "endgame areas, desolate wastelands",
        "purpose": "emptiness IS the design, builds tension",
        "travel_time_between": "90-180 seconds"
    },

    # Horizon Line Rule (MY.GAMES):
    # From any position, 2-3 POIs should be visible, each offering
    # different gameplay types.

    "visibility_rules": {
        "min_visible_pois": 2,
        "max_visible_pois": 5,
        "different_types_required": 2,  # at least 2 different types visible
        "line_of_sight_check": True,
        "landmark_always_visible": True  # major landmarks pierce fog
    }
}
```

### 5.3 Visual Beacon Design

```
VISUAL_BEACONS = {
    "light_source": {
        "types": ["campfire_glow", "magical_aura", "bioluminescence",
                 "torch_cluster", "will_o_wisp"],
        "visible_distance": 100-300,
        "effective_at": "night or dark_weather",
        "implementation": "point_light + particle_emitter"
    },
    "unique_silhouette": {
        "types": ["lone_tall_tree", "rock_spire", "ruined_tower",
                 "dead_tree_with_hanged", "giant_skeleton"],
        "visible_distance": 200-500,
        "effective_at": "day (against sky/horizon)",
        "implementation": "distinct_mesh_outline, taller than surroundings"
    },
    "particle_effect": {
        "types": ["column_of_light", "circling_birds", "rising_smoke",
                 "magical_sparkles", "swarm_of_insects"],
        "visible_distance": 150-400,
        "effective_at": "any conditions",
        "implementation": "particle_system, billboard optional"
    },
    "color_contrast": {
        "types": ["red_flowers_in_green_field", "blue_crystal_in_brown_cave",
                 "golden_glow_in_dark_ruin"],
        "visible_distance": 50-150,
        "effective_at": "close-medium range",
        "implementation": "material_color contrasting with biome palette"
    },
    "sound_beacon": {
        "types": ["singing", "hammering", "roaring", "chanting",
                 "music_box", "bell_tolling"],
        "audible_distance": 50-100,
        "effective_at": "close range, guides final approach",
        "implementation": "spatial_audio_source with distance_falloff"
    }
}
```

---

## 6. Transition Zones Between Areas

### 6.1 Biome Blending

```
BIOME_TRANSITION = {
    "transition_width": 50-150,       # meters of gradual blend
    "blend_algorithm": "linear_interpolation with noise distortion",
    "noise_params": {
        "octaves": 4-6,
        "persistence": 0.5,
        "lacunarity": 2.0,
        "distortion_scale": 0.3       # how jagged the border is
    },
    "blend_layers": {
        "terrain_height": "blend heightmaps",
        "ground_texture": "blend ground materials with noise mask",
        "vegetation_density": "gradual decrease/increase",
        "vegetation_type": "mix species from both biomes",
        "rock_formations": "transition_specific rocks (e.g., mossy in forest>desert)",
        "atmospheric": "fog color, ambient light color blend"
    },
    "transition_features": {
        "forest_to_desert": {
            "width": 100-150,
            "features": ["dead_trees", "sandy_patches", "dried_riverbed",
                        "sparse_grass"],
            "terrain": "soil_erosion, sand_creep"
        },
        "forest_to_swamp": {
            "width": 60-100,
            "features": ["waterlogged_ground", "dying_trees", "moss_increase",
                        "fog_thickening"],
            "terrain": "elevation_drops, water_table_rises"
        },
        "plains_to_mountains": {
            "width": 100-200,
            "features": ["rocky_outcrops", "slope_increase", "tree_line",
                        "wind_increase"],
            "terrain": "gradual_elevation_gain, 5-15_degree_slopes"
        },
        "settled_to_corrupted": {
            "width": 50-80,
            "features": ["dying_crops", "blackened_trees", "red_sky_tint",
                        "corrupted_wildlife", "abandoned_structures"],
            "terrain": "ground_cracks, dark_material_blend"
        }
    }
}
```

### 6.2 Difficulty Gradient

```
DIFFICULTY_GRADIENT = {
    "visual_signals": {
        "safe_zone": {
            "sky": "clear blue or warm sunset",
            "vegetation": "lush, green, flowers",
            "wildlife": "deer, rabbits, birds",
            "sound": "birdsong, gentle wind, water",
            "lighting": "warm, bright, high_ambient"
        },
        "moderate_zone": {
            "sky": "overcast, grey clouds",
            "vegetation": "sparse, browning, some dead trees",
            "wildlife": "crows, wolves in distance",
            "sound": "reduced birdsong, occasional growl",
            "lighting": "cooler, slightly dimmer"
        },
        "dangerous_zone": {
            "sky": "dark clouds, red tint",
            "vegetation": "dead, twisted, thorny",
            "wildlife": "none or hostile only",
            "sound": "ominous drone, distant screams, silence",
            "lighting": "dark, cold, low_ambient, red_accent"
        },
        "lethal_zone": {
            "sky": "unnatural color, swirling vortex",
            "vegetation": "corrupted, crystallized, or absent",
            "wildlife": "only boss-tier creatures",
            "sound": "heartbeat_bass, reality_distortion",
            "lighting": "extreme contrast, otherworldly_glow"
        }
    },
    "mob_level_scaling": {
        "algorithm": "base_level + (distance_from_safe_zone / gradient_distance) * level_range",
        "gradient_distance": 200-500,  # meters per difficulty tier
        "level_range": 5-10,           # levels per tier
        "elite_spawn_rate": "increases 5% per tier"
    }
}
```

### 6.3 Chokepoint Design

```
CHOKEPOINTS = {
    "natural_river": {
        "crossing_options": ["bridge (3-5m wide)", "ford (shallow, slow movement)",
                           "fallen_tree (narrow, 1m wide)", "boat"],
        "bridge_spacing": 300-600,  # meters between crossings
        "purpose": "funnels player to bridge = encounter opportunity",
        "guard_placement": "2-4 mobs at bridge, 1 at ford",
        "river_width": 10-30
    },
    "cliff_pass": {
        "pass_width": 5-15,
        "cliff_height": 20-50,
        "length": 30-100,
        "purpose": "one route between regions, ambush territory",
        "mob_placement": "elevated + corridor",
        "landmark": "visible from approach to signal 'this way'"
    },
    "ravine": {
        "width": 15-40,
        "depth": 10-30,
        "crossing": "single_bridge or jump_sequence",
        "purpose": "region boundary, difficulty wall",
        "visual": "dramatic_depth, fog_at_bottom"
    },
    "wall_gate": {
        "gate_width": 4-8,
        "wall_height": 6-12,
        "approach_plaza": "20-30m open area before gate",
        "purpose": "settlement boundary, boss_gate, region_divide",
        "guard_placement": "flanking + above_on_wall"
    },
    "forest_path": {
        "path_width": 2-4,
        "canopy_closure": 0.9,     # 90% overhead cover
        "length": 50-150,
        "visibility": "10-15m max",
        "purpose": "atmospheric transition, ambush territory",
        "mob_placement": "hidden in trees, triggered by proximity"
    }
}
```

### 6.4 Fast Travel Point Placement

```
FAST_TRAVEL_RULES = {
    "spacing": {
        "min_distance": 300,      # meters between fast travel points
        "max_distance": 800,
        "target_distance": 500,   # ideal spacing
        "near_landmark": True,    # always within 30m of a landmark
        "near_safe_zone": True,   # no enemies within 30m radius
    },
    "placement_priorities": [
        "At dungeon entrances (outside, before transition zone)",
        "At settlement gates",
        "At major road intersections",
        "At boss arena entrances",
        "At vista points / elevated positions",
        "At region boundaries / chokepoints"
    ],
    "unlock_conditions": {
        "discovery": "must physically reach the point first",
        "activation": "interact with object (bonfire, shrine, waypoint)",
        "cost": "free or minor_resource",
        "restriction": "not_in_combat, not_in_dungeon_interior"
    },
    "visual_design": {
        "always_visible": True,           # glow, particle effect
        "visible_distance": 50-100,
        "unique_prop": "bonfire, shrine, obelisk, waystone",
        "minimap_icon": True,
        "safe_radius": 20-30             # no mobs spawn within this radius
    },
    "density_by_region": {
        "starter_area": "1 per 200-300m",
        "mid_game": "1 per 400-500m",
        "endgame": "1 per 500-800m",
        "rationale": "endgame = more exploration expected between points"
    }
}
```

---

## 7. Implementation Reference: Existing Toolkit Integration

These specs are designed to integrate with the existing VeilBreakers MCP toolkit:

| Spec Section | Existing Handler | Status |
|---|---|---|
| Boss Arenas | `encounter_spaces.py` (arena_circle template) | Extend with full spec |
| Mob Encounters | `encounter_spaces.py` (8 templates) | Add density/patrol rules |
| Settlements | `settlement_generator.py` + `_settlement_grammar.py` | Add district generation |
| Dungeon Entrances | `worldbuilding.py` + `dungeon_themes.py` | Add entrance templates |
| POIs | `map_composer.py` (location placement) | Add POI type system |
| Transition Zones | `environment.py` + `_terrain_noise.py` | Add biome blending |
| Fast Travel | `world_map.py` | Add placement algorithm |

### Skyrim Modular Kit Reference (Burgess GDC 2013)

Skyrim's dungeon system used 7 modular kits to create 400+ dungeon cells:
- **Team**: 2 kit artists + 8 level designers
- **Production**: ~2.5 years
- **Kit pieces**: floors, ceilings, walls, single/double doorways, windows, corners
- **Floor thickness**: substantial (mass like walls, not paper-thin)
- **Glue pieces**: off-angle connectors for interior kits
- **Texture variants**: reduce art fatigue without re-testing geometry

### Player Character Reference Metrics

| Engine | Bounding Box | Eye Height |
|---|---|---|
| Unity | 1.0 x 1.8m (or 1.0 x 2.0m) | 1.5-1.7m |
| Unreal | 0.6 x 1.76m | 1.52m |
| God of War (Kratos) | ~1.0 x 2.0m | ~1.7m |

### Key Architectural Metrics for Third-Person Action RPG

| Element | Dimension | Notes |
|---|---|---|
| Door width (main) | 1.5-2.5m | Double door for main entrances |
| Door width (side) | 1.0-1.5m | Half of main door |
| Corridor width (min) | 2.5-3.0m | Camera needs room in 3rd person |
| Corridor width (combat) | 4-6m | Room for dodge rolls |
| Ceiling height (interior) | 3.5-5.0m | Higher than realistic for camera |
| Stair slope | 30-35 degrees | Standard comfortable climb |
| Step height | 0.15-0.20m | |
| Step depth | 0.25-0.30m | |
| Jump gap (easy) | 2-3m | |
| Jump gap (hard) | 4-5m | |
| Dodge roll distance | 3-4m | Standard i-frame roll |
| Melee attack range | 2-4m | Sword/axe range |
| Cover height (low) | 1.0m | Crouch cover |
| Cover height (full) | 2.0-2.5m | Standing cover |

---

## Sources

- [The Level Design Book - Metrics](https://book.leveldesignbook.com/process/blockout/metrics)
- [The Level Design Book - Classic Combat](https://book.leveldesignbook.com/learning/projects/classic-combat)
- [Dark Souls Director Miyazaki on Boss Design](https://www.gamedeveloper.com/design/-i-dark-souls-i-director-miyazaki-offers-his-philosophy-on-boss-design)
- [World Design Lessons from FromSoftware](https://medium.com/@Jamesroha/world-design-lessons-from-fromsoftware-78cadc8982df)
- [Souls-like Level Design Methodology](https://medium.com/@bramasolejm030206/preface-ec08bc1459d0)
- [POI Diversity Rule (MY.GAMES)](https://medium.com/my-games-company/how-to-make-an-exciting-open-world-the-pois-diversity-rule-90de6d748eac)
- [God of War Level Design Case Study](https://www.gamedeveloper.com/design/level-design-case-study---recreating-the-first-level-in-god-of-war-2018-)
- [God of War Ragnarok Combat Arenas](https://gamerant.com/god-of-war-ragnaroks-combat-improvements-good/)
- [Level Design for Combat (Gamasutra)](https://www.gamedeveloper.com/design/level-design-for-combat)
- [Engaging Combat Level Design Pt 3](https://www.gamedeveloper.com/design/engaging-level-design-for-combat---pt-3)
- [Procedural Medieval City Generation](https://www.gamedeveloper.com/design/to-what-extent-can-architectural-constructs-act-as-a-foundation-for-the-procedural-generation-of-medieval-villages-)
- [Medieval Fantasy City Generator (Watabou)](https://watabou.itch.io/medieval-fantasy-city-generator)
- [Skyrim Modular Level Design GDC 2013 (Joel Burgess)](https://www.slideshare.net/JoelBurgess/gdc2013-kit-buildingfinal)
- [Biome Diversity Procedural Generation](https://peerdh.com/blogs/programming-insights/procedural-generation-techniques-for-biome-diversity-in-terrain-algorithms)
- [RPG Dungeon Design Analysis](https://felipepepe.medium.com/what-makes-a-good-rpg-dungeon-505180c69d00)
- [Elden Ring Map Scale Analysis](https://www.pcgamer.com/games/rpg/elden-ring-geographer-tests-rigorous-calculation-against-weed-fueled-horse-math-to-determine-the-exact-size-of-the-lands-between/)
- [Diablo IV Procedural Dungeon Generation](https://us.forums.blizzard.com/en/d4/t/the-procedural-generation-of-d4-dungeons/124538)
- [Witcher 3 POI Overcrowding Admission](https://www.nintendolife.com/news/2022/07/witcher-3-dev-admits-he-overcrowded-one-map-with-too-many-points-of-interest)
- [Genshin Impact 40-Second Rule Study (PDF)](https://uu.diva-portal.org/smash/get/diva2:1764361/FULLTEXT01.pdf)
- [Monster Hunter World Living Ecosystem](https://www.monsterhunter.com/wilds/en-us/living-world/)
- [Patrolling AI Systems in Video Games (ResearchGate)](https://www.researchgate.net/publication/364090728_Patrolling_AI_Systems_in_Video_Games)
