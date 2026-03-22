"""VeilBreakers game data constants extracted from VeilBreakers3DCurrent.

These values are sourced directly from the game's JSON data files and C# systems.
Used by template generators to produce game-accurate C# code.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Brand System (from BrandSystem.cs)
# ---------------------------------------------------------------------------

BRAND_NAMES = [
    "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
    "LEECH", "GRACE", "MEND", "RUIN", "VOID",
]

HYBRID_BRANDS = {
    "BLOODIRON": "IRON",
    "RAVENOUS": "SAVAGE",
    "CORROSIVE": "VENOM",
    "TERRORFLUX": "DREAD",
    "VENOMSTRIKE": "VENOM",
    "NIGHTLEECH": "LEECH",
}

BRAND_ARCHETYPES = {
    "IRON": "Defensive Wall",
    "SAVAGE": "Berserker",
    "SURGE": "Artillery",
    "VENOM": "Poison Master",
    "DREAD": "Fear Mage",
    "LEECH": "Lifesteal Bruiser",
    "GRACE": "Combat Medic",
    "MEND": "Shield Support",
    "RUIN": "Explosion Mage",
    "VOID": "Reality Warper",
}

# Primary colors (rgba 0-1) from BrandSystem.cs
BRAND_COLORS = {
    "IRON":   (0.55, 0.59, 0.65, 1.0),
    "SAVAGE": (0.71, 0.18, 0.18, 1.0),
    "SURGE":  (0.24, 0.55, 0.86, 1.0),
    "VENOM":  (0.31, 0.71, 0.24, 1.0),
    "DREAD":  (0.47, 0.24, 0.63, 1.0),
    "LEECH":  (0.55, 0.16, 0.31, 1.0),
    "GRACE":  (0.86, 0.86, 0.94, 1.0),
    "MEND":   (0.78, 0.67, 0.31, 1.0),
    "RUIN":   (0.86, 0.47, 0.16, 1.0),
    "VOID":   (0.16, 0.08, 0.24, 1.0),
}

BRAND_GLOW = {
    "IRON":   (0.71, 0.75, 0.80, 1.0),
    "SAVAGE": (0.86, 0.27, 0.27, 1.0),
    "SURGE":  (0.39, 0.71, 1.00, 1.0),
    "VENOM":  (0.47, 0.86, 0.39, 1.0),
    "DREAD":  (0.63, 0.39, 0.78, 1.0),
    "LEECH":  (0.71, 0.24, 0.43, 1.0),
    "GRACE":  (1.00, 1.00, 1.00, 1.0),
    "MEND":   (0.94, 0.82, 0.47, 1.0),
    "RUIN":   (1.00, 0.63, 0.31, 1.0),
    "VOID":   (0.39, 0.24, 0.55, 1.0),
}

BRAND_DARK = {
    "IRON":   (0.31, 0.35, 0.39, 1.0),
    "SAVAGE": (0.47, 0.10, 0.10, 1.0),
    "SURGE":  (0.12, 0.31, 0.55, 1.0),
    "VENOM":  (0.16, 0.39, 0.12, 1.0),
    "DREAD":  (0.27, 0.12, 0.39, 1.0),
    "LEECH":  (0.35, 0.08, 0.20, 1.0),
    "GRACE":  (0.63, 0.63, 0.71, 1.0),
    "MEND":   (0.55, 0.43, 0.16, 1.0),
    "RUIN":   (0.63, 0.27, 0.08, 1.0),
    "VOID":   (0.06, 0.02, 0.10, 1.0),
}

# Brand effectiveness matrix: BRAND_EFFECTIVENESS[attacker][defender] = multiplier
BRAND_EFFECTIVENESS = {
    "IRON":   {"SURGE": 2.0, "DREAD": 2.0, "SAVAGE": 0.5, "RUIN": 0.5},
    "SAVAGE": {"IRON": 2.0, "MEND": 2.0, "LEECH": 0.5, "GRACE": 0.5},
    "SURGE":  {"VENOM": 2.0, "LEECH": 2.0, "IRON": 0.5, "VOID": 0.5},
    "VENOM":  {"GRACE": 2.0, "MEND": 2.0, "SURGE": 0.5, "RUIN": 0.5},
    "DREAD":  {"SAVAGE": 2.0, "GRACE": 2.0, "IRON": 0.5, "VOID": 0.5},
    "LEECH":  {"SAVAGE": 2.0, "RUIN": 2.0, "SURGE": 0.5, "VENOM": 0.5},
    "GRACE":  {"VOID": 2.0, "RUIN": 2.0, "SAVAGE": 0.5, "VENOM": 0.5},
    "MEND":   {"VOID": 2.0, "LEECH": 2.0, "SAVAGE": 0.5, "VENOM": 0.5},
    "RUIN":   {"IRON": 2.0, "VENOM": 2.0, "LEECH": 0.5, "GRACE": 0.5},
    "VOID":   {"SURGE": 2.0, "DREAD": 2.0, "GRACE": 0.5, "MEND": 0.5},
}

# ---------------------------------------------------------------------------
# Path System (from PathSystem.cs)
# ---------------------------------------------------------------------------

PATHS = {
    "IRONBOUND": {
        "primary_stat": "DEFENSE",
        "role": "Tank/Defender",
        "color": (0.6, 0.6, 0.7, 1.0),
        "strong_brands": ["IRON", "MEND", "LEECH"],
        "weak_brands": ["VOID", "SAVAGE", "RUIN"],
    },
    "FANGBORN": {
        "primary_stat": "ATTACK",
        "role": "Attacker/Hunter",
        "color": (0.8, 0.3, 0.2, 1.0),
        "strong_brands": ["SAVAGE", "VENOM", "RUIN"],
        "weak_brands": ["GRACE", "MEND", "IRON"],
    },
    "VOIDTOUCHED": {
        "primary_stat": "MAGIC",
        "role": "Mage/Caster",
        "color": (0.4, 0.2, 0.7, 1.0),
        "strong_brands": ["VOID", "DREAD", "SURGE"],
        "weak_brands": ["IRON", "GRACE", "MEND"],
    },
    "UNCHAINED": {
        "primary_stat": "LUCK",
        "role": "Wildcard/Hybrid",
        "color": (0.9, 0.7, 0.2, 1.0),
        "strong_brands": [],
        "weak_brands": [],
    },
}

# ---------------------------------------------------------------------------
# Corruption System (from CorruptionSystem.cs)
# ---------------------------------------------------------------------------

CORRUPTION_TIERS = {
    "ASCENDED":  {"range": (0, 10),   "stat_mult": 1.25, "color": (1.0, 0.9, 0.4, 1.0)},
    "PURIFIED":  {"range": (11, 25),  "stat_mult": 1.10, "color": (0.6, 0.9, 0.7, 1.0)},
    "UNSTABLE":  {"range": (26, 50),  "stat_mult": 1.00, "color": (0.8, 0.8, 0.5, 1.0)},
    "CORRUPTED": {"range": (51, 75),  "stat_mult": 0.90, "color": (0.7, 0.4, 0.6, 1.0)},
    "ABYSSAL":   {"range": (76, 100), "stat_mult": 0.80, "color": (0.3, 0.1, 0.3, 1.0)},
}

# ---------------------------------------------------------------------------
# Heroes (from heroes.json)
# ---------------------------------------------------------------------------

HEROES = {
    "vex": {
        "name": "Vex", "title": "The Warden",
        "path": "IRONBOUND", "brand": "IRON", "role": "TANK",
        "resource": "GUARD", "starter_monster": "skitter_teeth",
    },
    "seraphina": {
        "name": "Seraphina", "title": "The Thornspeaker",
        "path": "FANGBORN", "brand": "SAVAGE", "role": "DPS",
        "resource": "FURY", "starter_monster": "grimthorn",
    },
    "orion": {
        "name": "Orion", "title": "The Conductor",
        "path": "VOIDTOUCHED", "brand": "RUIN", "role": "MAGE",
        "resource": "MANA", "starter_monster": "voltgeist",
    },
    "nyx": {
        "name": "Nyx", "title": "The Shadow That Drinks",
        "path": "UNCHAINED", "brand": "VOID", "role": "HYBRID",
        "resource": "CHAOS", "starter_monster": "bloodshade",
    },
}

# ---------------------------------------------------------------------------
# Monsters (from monsters.json)
# ---------------------------------------------------------------------------

MONSTER_NAMES = [
    "bloodshade", "chainbound", "corrodex", "crackling", "flicker",
    "gluttony_polyp", "grimthorn", "hollow", "ironjaw", "mawling",
    "needlefang", "ravener", "skitter_teeth", "sporecaller",
    "the_broodmother", "the_bulwark", "the_congregation",
    "the_vessel", "the_weeping", "voltgeist",
]

MONSTER_BRANDS = {
    "bloodshade": "VOID", "chainbound": "IRON", "corrodex": "GRACE",
    "crackling": "SURGE", "flicker": "SURGE", "gluttony_polyp": "DREAD",
    "grimthorn": "SAVAGE", "hollow": "VENOM", "ironjaw": "LEECH",
    "mawling": "SAVAGE", "needlefang": "MEND", "ravener": "SAVAGE",
    "skitter_teeth": "IRON", "sporecaller": "SAVAGE",
    "the_broodmother": "SAVAGE", "the_bulwark": "IRON",
    "the_congregation": "DREAD", "the_vessel": "DREAD",
    "the_weeping": "VENOM", "voltgeist": "RUIN",
}

MONSTER_HABITATS = {
    "bloodshade": "Battlefields, hospitals, shadowed pools",
    "chainbound": "Abandoned prisons, old dungeons",
    "corrodex": "Ruined castles, poisoned battlefields",
    "crackling": "Storm-touched areas, lightning strikes",
    "flicker": "Open skies, windy passes, Veil cracks",
    "gluttony_polyp": "Fertile areas, forests, meadows",
    "grimthorn": "Corrupted forests, poisoned swamps",
    "hollow": "Near death/grief, abandoned places",
    "ironjaw": "Mountain passes, ruined forges",
    "mawling": "Near Veil cracks, dark areas",
    "needlefang": "Dense undergrowth, canyon walls",
    "ravener": "Hunting grounds near apex predators",
    "skitter_teeth": "Battlefields, graveyards",
    "sporecaller": "Corrupted forests, swamps",
    "the_broodmother": "Dark caves, abandoned structures",
    "the_bulwark": "Ruined fortresses, fallen castles",
    "the_congregation": "Abandoned Village (Tutorial Boss)",
    "the_vessel": "Places of worship, hospitals",
    "the_weeping": "Dark places, violence scenes",
    "voltgeist": "Storm-struck peaks, electrical anomalies",
}

MONSTER_AI_PATTERNS = [
    "aggressive", "defensive", "support", "healer", "tank",
    "speed", "assassin", "debuffer", "summoner", "boss_congregation",
]

# ---------------------------------------------------------------------------
# Biomes / World Zones
# ---------------------------------------------------------------------------

BIOME_TYPES = [
    "thornwood_forest",
    "corrupted_swamp",
    "mountain_pass",
    "ruined_fortress",
    "abandoned_village",
    "veil_crack_zone",
    "underground_dungeon",
    "sacred_shrine",
    "battlefield",
    "cemetery",
]

# ---------------------------------------------------------------------------
# Game Constants (from Constants.cs)
# ---------------------------------------------------------------------------

MAX_PARTY_SIZE = 3
MAX_LEVEL = 100
MAX_CORRUPTION = 100
BASE_EXP_REQUIRED = 100
EXP_GROWTH_RATE = 1.15
BASE_CRIT_RATE = 0.05
BASE_CRIT_DAMAGE = 1.5
BASE_CAPTURE_RATE = 0.1
LOW_HP_CAPTURE_BONUS = 0.3
STATUS_CAPTURE_BONUS = 0.1

# ---------------------------------------------------------------------------
# Rarity Tiers
# ---------------------------------------------------------------------------

RARITY_TIERS = ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTHIC"]

RARITY_COLORS = {
    "COMMON":    (0.6, 0.6, 0.6, 1.0),
    "UNCOMMON":  (0.2, 0.8, 0.2, 1.0),
    "RARE":      (0.2, 0.4, 1.0, 1.0),
    "EPIC":      (0.6, 0.2, 0.8, 1.0),
    "LEGENDARY": (1.0, 0.8, 0.0, 1.0),
    "MYTHIC":    (1.0, 0.2, 0.2, 1.0),
}

# ---------------------------------------------------------------------------
# Equipment Slots
# ---------------------------------------------------------------------------

EQUIPMENT_SLOTS = ["WEAPON", "ARMOR", "ACCESSORY", "RING"]

# ---------------------------------------------------------------------------
# Ability Slots
# ---------------------------------------------------------------------------

ABILITY_SLOTS = [
    "BASIC_ATTACK", "DEFEND",
    "SKILL_1", "SKILL_2", "SKILL_3",
    "ULTIMATE",
]

# ---------------------------------------------------------------------------
# Monster Body Type Presets (for 3D mesh generation)
# ---------------------------------------------------------------------------

MONSTER_BODY_TYPES = {
    "bloodshade": {
        "rig_template": "humanoid",
        "body_type": "wraith",
        "scale": (1.0, 1.8, 0.8),
        "description": "Shadow entity with elongated limbs, semi-transparent body, dripping darkness",
        "key_features": ["flowing_cape", "glowing_eyes", "shadow_tendrils"],
        "brand": "VOID",
    },
    "chainbound": {
        "rig_template": "humanoid",
        "body_type": "heavy",
        "scale": (1.2, 1.5, 1.2),
        "description": "Humanoid bound in chains, heavy iron padlocks, armored torso",
        "key_features": ["chains", "padlocks", "broken_shackles"],
        "brand": "IRON",
    },
    "corrodex": {
        "rig_template": "humanoid",
        "body_type": "knight",
        "scale": (1.0, 1.7, 1.0),
        "description": "Corroded knight in acid-eaten armor, green acid dripping from joints",
        "key_features": ["corroded_armor", "acid_drip", "rusty_sword"],
        "brand": "GRACE",
    },
    "crackling": {
        "rig_template": "humanoid",
        "body_type": "small_child",
        "scale": (0.5, 0.7, 0.5),
        "description": "Small electrical child-like creature, sparking constantly, translucent skin showing lightning veins",
        "key_features": ["lightning_veins", "sparks", "translucent_skin"],
        "brand": "SURGE",
    },
    "flicker": {
        "rig_template": "insect",
        "body_type": "dragonfly",
        "scale": (0.4, 0.3, 0.6),
        "description": "Insectoid blur creature, iridescent wings, compound eyes, extremely fast",
        "key_features": ["iridescent_wings", "compound_eyes", "blurred_afterimage"],
        "brand": "SURGE",
    },
    "gluttony_polyp": {
        "rig_template": "amorphous",
        "body_type": "blob",
        "scale": (1.5, 0.8, 1.5),
        "description": "Digestive sac creature, translucent membrane showing consumed matter, tentacle feeders",
        "key_features": ["translucent_membrane", "digestive_sac", "feeding_tentacles"],
        "brand": "DREAD",
    },
    "grimthorn": {
        "rig_template": "quadruped",
        "body_type": "vine_beast",
        "scale": (1.2, 1.0, 1.8),
        "description": "Vine-covered quadruped, thorny body, poison barbs, flower-like head with fangs",
        "key_features": ["thorns", "vines", "poison_barbs", "flower_head"],
        "brand": "SAVAGE",
    },
    "hollow": {
        "rig_template": "humanoid",
        "body_type": "ethereal",
        "scale": (0.8, 1.6, 0.6),
        "description": "Shadow entity, hollow chest cavity, empty eye sockets emitting dark mist",
        "key_features": ["hollow_chest", "dark_mist_eyes", "fading_edges"],
        "brand": "VENOM",
    },
    "ironjaw": {
        "rig_template": "quadruped",
        "body_type": "bear_trap",
        "scale": (1.5, 1.0, 2.0),
        "description": "Metal bear with iron jaw trap for a mouth, rusted metal plating, chain tail",
        "key_features": ["iron_jaw_trap", "metal_plating", "chain_tail"],
        "brand": "LEECH",
    },
    "mawling": {
        "rig_template": "quadruped",
        "body_type": "wolf",
        "scale": (0.8, 0.7, 1.2),
        "description": "Feral wolf-like predator with oversized jaw, matted fur, glowing eyes",
        "key_features": ["oversized_jaw", "matted_fur", "glowing_eyes"],
        "brand": "SAVAGE",
    },
    "needlefang": {
        "rig_template": "serpent",
        "body_type": "snake",
        "scale": (0.3, 0.3, 3.0),
        "description": "Venomous needle serpent, needle-like fangs, iridescent scales, hood with eye markings",
        "key_features": ["needle_fangs", "iridescent_scales", "cobra_hood"],
        "brand": "MEND",
    },
    "ravener": {
        "rig_template": "quadruped",
        "body_type": "raptor",
        "scale": (1.0, 1.2, 1.5),
        "description": "Raptor-like predator, muscular build, razor claws, armored head crest",
        "key_features": ["razor_claws", "armored_crest", "predator_stance"],
        "brand": "SAVAGE",
    },
    "skitter_teeth": {
        "rig_template": "arachnid",
        "body_type": "ribcage_spider",
        "scale": (0.8, 0.5, 1.0),
        "description": "Crawling ribcage with spider legs, teeth lining the open cavity, bone structure",
        "key_features": ["ribcage_body", "bone_legs", "teeth_lining"],
        "brand": "IRON",
    },
    "sporecaller": {
        "rig_template": "quadruped",
        "body_type": "deer",
        "scale": (1.0, 1.2, 1.3),
        "description": "Fungal deer, antlers replaced with mushroom clusters, spore-releasing back, mossy hide",
        "key_features": ["mushroom_antlers", "spore_sacs", "mossy_hide"],
        "brand": "SAVAGE",
    },
    "the_broodmother": {
        "rig_template": "arachnid",
        "body_type": "giant_spider",
        "scale": (2.5, 1.5, 3.0),
        "description": "Massive spider-wasp hybrid, egg sac abdomen, venomous mandibles, armored carapace",
        "key_features": ["egg_sac", "mandibles", "armored_carapace", "wasp_wings"],
        "brand": "SAVAGE",
    },
    "the_bulwark": {
        "rig_template": "humanoid",
        "body_type": "golem",
        "scale": (2.0, 2.5, 1.5),
        "description": "Fused armor guardian, multiple shields melded into body, glowing rune core",
        "key_features": ["fused_shields", "rune_core", "massive_frame"],
        "brand": "IRON",
    },
    "the_congregation": {
        "rig_template": "amorphous",
        "body_type": "mass_of_souls",
        "scale": (3.0, 4.0, 3.0),
        "description": "BOSS — mass of absorbed souls, writhing faces in darkness, central eye, reality-warping presence",
        "key_features": ["writhing_faces", "central_eye", "soul_tendrils", "darkness_aura"],
        "brand": "DREAD",
    },
    "the_vessel": {
        "rig_template": "humanoid",
        "body_type": "spirit_healer",
        "scale": (0.8, 1.5, 0.8),
        "description": "Floating healer entity, porcelain mask, gentle glow, trailing robes of light",
        "key_features": ["porcelain_mask", "healing_glow", "light_robes"],
        "brand": "DREAD",
    },
    "the_weeping": {
        "rig_template": "amorphous",
        "body_type": "floating_eyes",
        "scale": (1.0, 1.2, 1.0),
        "description": "Mass of floating eyes connected by tendons, weeping dark ichor, vision distortion aura",
        "key_features": ["floating_eyes", "dark_ichor", "tendon_connections"],
        "brand": "VENOM",
    },
    "voltgeist": {
        "rig_template": "humanoid",
        "body_type": "ghost",
        "scale": (1.0, 1.5, 0.8),
        "description": "Lightning ghost, electrical skeleton visible through translucent body, constant discharge",
        "key_features": ["electrical_skeleton", "translucent_body", "lightning_discharge"],
        "brand": "RUIN",
    },
}

# Map rig templates to body descriptions for Blender mesh generation prompts
MONSTER_MESH_PROMPTS = {
    name: f"{data['description']}, dark fantasy style, game-ready topology"
    for name, data in MONSTER_BODY_TYPES.items()
}
