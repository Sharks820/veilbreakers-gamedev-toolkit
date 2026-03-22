# Expert Review Gaps — 3-Agent Ultrathink Findings

150+ items from environment artist, character artist, and technical artist reviews.

## TERRAIN (19 missing features)
- Swamp/wetland preset (flat + hummocks + waterlogged depressions)
- Coastal/beach preset (gradient falloff, wave erosion, sand dunes)
- Frozen/tundra preset (wind ridges, frost-heave polygonal ground)
- River valley preset (parabolic cross-section, meander curves)
- Cavern/underground (floor + ceiling dual-surface heightmaps)
- Island/archipelago (radial falloff, broken coastline)
- Cliff face carving (vertical drop with overhang noise)
- Cave entrance carving (arch boolean into cliff)
- Waterfall shelves (step-down + wet rock + splash emitter)
- Lava flows (wide shallow channels, cooled edge/hot center)
- Frozen lake basins (flat depression + ice material + crack noise)
- Fog valley shaping (concave below fog altitude)
- Mountain tunnels (boolean cylinder through ridge)
- Crater stamp at specific coordinates
- River delta/estuary (branching channels + sediment)
- Terrain-integrated stairs/ramps (carved steps)
- Rock arches/overhangs (separate blended meshes)
- Erosion gullies (particle-based hydraulic)
- Underwater terrain (smoother, kelp/coral scatter)

## ATMOSPHERE (8 missing systems)
- Procedural sky (Nishita model, time-of-day params)
- Time-of-day presets: Dawn, Noon, Dusk, Night, Overcast, Blood Moon
- Cloud layer plane (noise alpha, animated drift, shadow casting)
- Volumetric fog volumes (density/color/height/falloff)
- God rays (EEVEE bloom + volumetric scatter settings)
- Per-biome ambient color
- Interior light shafts through windows
- Bioluminescence point lights

## VEGETATION (8 missing features)
- L-system recursive branching (3-5 levels)
- Branch curvature via Bezier (phototropism + gravitropism)
- Leaf card billboards at twig termini
- Wind vertex color preparation (R=dist, G=height, B=level)
- Root system integration
- Seasonal variants (autumn, winter, corrupted)
- Missing species: palm, bamboo, swamp cypress, birch, baobab
- Bark UV auto-assignment (V axis follows trunk)

## BUILDINGS (4 missing systems)
- Connection socket definitions per modular piece
- Interior vs exterior wall face distinction
- Continuous integrity parameter (1.0→0.0, not binary)
- Missing elements: arches, buttresses, balconies, galleries, moats, wells, fountains

## CHARACTER TOPOLOGY (5 fixes)
- Shoulder: 5-7 loops (not 3)
- Wrist: 3-4 loops (not 2)
- Ankle: 3 loops (not 2)
- Fingers: 2 loops per knuckle
- Face: 4 eye rings, 3-4 mouth rings, unbroken nasolabial loop, forehead loops, nostril loops

## CHARACTER SYSTEM FIXES (4 critical)
- Shape key composition breaks — use rig-driven bone scaling for height
- Outfit fitting: SurfaceDeform per body type (75 combinations)
- Face variation: 30-40 FACS shapes (not 540 combinatorial)
- Consider modular body parts (head/torso/arms/legs snap at seams)

## BLEND SHAPES (38 minimum, not 12)
Jaw (4), Lips (12), Cheeks (4), Brows (6), Eyes (8), Nose (4)

## MISSING DYNAMIC FEATURES (8)
- Eye meshes + eye target bone + pupil dilation
- Breathing idle (chest sine wave, weight shift, blink cycle)
- Cloth sim topology specs (uniform quads, pin groups)
- Damage states (limb stumps, wound decal zones)
- Corrective blend shapes (deltoid, bicep, knee)
- Teeth + tongue + gum/palate
- Accessory jiggle bones (earrings, pouches, chains)
- Foot IK contact points

## MISSING MONSTER TEMPLATES (6)
- Avian/Winged Bipedal
- Aquatic/Semi-Aquatic
- Centauroid
- Floating/Ethereal
- Colossal/Titan (inverted LOD)
- Parasitic/Symbiotic

## BOSS SPECIFICS (7)
- 200K-400K tri budget
- UDIM multi-tile textures
- Arena integration meshes
- Phase transition shape keys
- Animation mass_scale (3x = 0.6x speed)
- Internal glow focal point lighting
- Ground deformation contact zone

## WEAPONS (3 critical fixes)
- 4 geometry groups per brand cluster (not just material swap) = ~88 meshes
- VFX attachment points per weapon (blade_tip, blade_root, guard_center, pommel, edge_L/R)
- Enchantment rune emission maps (10 brand patterns)

## ARMOR (expand to 9 slots)
- Add Belt/Waist (4 variants)
- Add Neck/Gorget (4 variants)
- Add Tabard/Surcoat
- Total: 30 base pieces (was 22)

## MATERIALS (expand to 65-70)
- 5 leather variants (new, worn, hardened, suede, dyed)
- 5 fabric types (silk, wool, burlap, velvet, linen)
- 6 crystal/gem varieties (ruby, sapphire, emerald, amethyst, diamond, dark crystal)
- 5 enchantment effects (pulsing glow, flowing energy, crackling, frost, flame)

## TEXTURE PIPELINE (6 critical fixes)
- Baking must be automated first-class (not Phase 7 afterthought)
- Procedural materials DO NOT survive FBX/glTF export — MUST bake
- Add ID map bake (step 2.5)
- Add thickness map + bent normal map
- Albedo must be FLAT (no baked lighting)
- Channel packing: Unity HDRP Mask Map convention

## UV QUALITY TIERS
- Tier 1 (Smart UV): background props, LOD2+
- Tier 2 (xatlas): armor, weapons, common monsters
- Tier 3 (manual+xatlas): heroes, bosses, legendary weapons

## MISSING ITEMS (8 categories)
- Ammunition (arrows 5 types, bolts 3, throwing weapons)
- Rings (6 base meshes)
- Amulets/pendants (6 base meshes)
- Scrolls (rolled, unfurled, recipe/blueprint)
- Deployable traps (bear trap, tripwire, mine, ward)
- Trophies (mounted heads, relics, tokens)
- Camp items (bedroll, cooking kit, repair kit, map table)
- Musical instruments (lute, drum, flute)

## MISSING ANIMALS (8 species)
- Boar, raven, vulture, lizard/salamander
- Visible insects (moths, dragonflies, centipedes)
- Livestock (pig, cow, goat)
- Songbirds, worms/maggots

## QUALITY GATE (expanded metrics)
Mesh: tri budget, quad%, non-manifold=0, degenerate=0, UV overlap=0%, texel density std
Material: all PBR channels, roughness range>0.15, metallic near-binary, albedo 30-240 sRGB
Visual: silhouette at 3 distances, 8-angle contact sheet, mipmap stability
Gameplay: brand recognition at game distance, rarity visual distinction
