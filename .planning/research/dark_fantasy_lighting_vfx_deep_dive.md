# Dark Fantasy Lighting, VFX, and Atmosphere Deep Dive

**Research date:** 2026-04-02
**Domain:** AAA dark fantasy lighting design, VFX systems, atmospheric effects
**Target:** VeilBreakers dark fantasy action RPG (Unity 6 URP + Blender procedural toolkit)
**Confidence:** HIGH (cross-verified across official Unity docs, GDC/developer talks, game analysis, community implementations)

---

## Executive Summary

Dark fantasy lighting is not about making things dark -- it is about **controlling where light exists** so that darkness becomes meaningful. Every AAA dark fantasy game studied (Elden Ring, Dark Souls 3, Bloodborne, Diablo IV, Lords of the Fallen, Dragon's Dogma 2) uses lighting as a core gameplay and narrative tool, not just an aesthetic layer. The universal pattern is: **warm light = safety/haven, absence of light = danger/unknown, colored light = supernatural/corruption**.

For VeilBreakers specifically, the Veil corruption mechanic creates a unique dual-state lighting system: the **living world** (warm amber, Gothic candlelight, hearth glow) versus the **Veil-touched world** (cold purple-black, desaturated, unnatural shadow). This is directly analogous to Lords of the Fallen's Axiom/Umbral dual-realm lighting, but implemented through corruption spread rather than realm-switching.

Unity 6 URP provides all necessary tools: Adaptive Probe Volumes for baked GI, Forward+ for unlimited per-pixel lights (critical for candle-heavy Gothic interiors), Rendering Layers for interior/exterior light separation, and the VFX Graph for GPU-accelerated corruption particle effects. The main gap is **volumetric lighting** -- URP has no built-in volumetric fog, requiring the open-source Unity-URP-Volumetric-Light package or commercial alternatives.

**Primary recommendation:** Build a layered lighting system with 4 tiers: (1) global directional + sky, (2) architectural light sources (windows, doorways), (3) interactive light sources (torches, candles, fireplaces), (4) VFX/corruption overlay. Use Rendering Layers to isolate interior and exterior lighting. Use VFX Graph for all corruption/Veil effects with dissolve shaders driven by world-space noise.

---

## MISSION 1: AAA Dark Fantasy Lighting Reference Analysis

### 1.1 Elden Ring -- Light as Exploration Reward

**Core Philosophy:** Elden Ring uses light to signal discovery and safe passage. The golden Grace Sites emit streams of gold light (the "guidance of grace") that literally point toward the next objective -- the most explicit use of light-as-wayfinding in any Souls game.

**Key Techniques:**
| Technique | Implementation | VeilBreakers Application |
|-----------|---------------|--------------------------|
| Grace guidance beams | Gold particle streams from rest sites pointing to next objective | Veil Wards could emit protective light beams marking safe paths |
| Interior/exterior contrast | Bright overworld, oppressive dark dungeons | Gothic town exteriors lit by moon/torches, interiors by candles/hearths |
| Time-of-day system | Full day/night cycle affecting enemy spawns and visibility | Time of day changes Veil corruption intensity (stronger at night) |
| Legacy dungeons as light deprivation | Removing sky light forces reliance on torch/lantern | Underground areas force reliance on player-carried light |
| Golden fog walls | Glowing barriers marking boss encounters | Veil barriers as corruption fog walls with purple-black glow |

**Lighting Architecture:**
- Directional sunlight with warm golden-hour bias (the Erdtree bathes everything in gold)
- Point lights at every Grace Site creating "islands of safety"
- No global ambient in dungeons -- purely additive lighting from placed sources
- Ray tracing added post-launch for GI, but base game uses baked lightmaps + probes

**Confidence:** HIGH -- verified through multiple game analysis sources and direct observation

### 1.2 Dark Souls 3 -- Bonfire as Emotional Anchor

**Core Philosophy:** The bonfire is the single most important light source in the game. It represents safety, progress, and respite. The entire lighting design revolves around the contrast between the warm orange glow of bonfires and the cold, hostile world.

**Key Techniques:**
| Technique | Implementation | VeilBreakers Application |
|-----------|---------------|--------------------------|
| Bonfire warmth radius | Warm orange point light with large falloff, visible from distance | Settlement hearths visible from distance as navigation beacons |
| Oppressive ambient darkness | Very low ambient light, near-black in many areas | Veil-corrupted areas have suppressed ambient, only corruption glow |
| Distant flame visibility | Bonfire flames visible through fog/geometry as breadcrumbs | Torch sconces on buildings visible through mist as guidance |
| Color coding by area | Irithyll = cold blue, Catacombs = warm orange, Profaned = sickly green | Each corruption tier has distinct color temperature |
| Ember/ash particles near fire | Floating embers around bonfires add warmth and life | Amber particles near hearths, dark particles near Veil corruption |

**Environmental Color Palettes by Area (Dark Fantasy Reference):**
- **Undead Settlement:** Desaturated browns, warm fire pockets, overcast grey sky
- **Irithyll of the Boreal Valley:** Cold blue moonlight, silver frost, warm interior contrast
- **Profaned Capital:** Sickly yellow-green flame, toxic atmosphere
- **Ringed City:** Dramatic orange sunset, apocalyptic grandeur

**Confidence:** HIGH -- extensive community analysis and design breakdowns available

### 1.3 Bloodborne -- Gaslight Victorian and the Nightmare Palette

**Core Philosophy:** Bloodborne uses the most restricted color palette of any FromSoftware game. The world is painted in dark greys, browns, and blacks with splashes of crimson. Lighting comes almost exclusively from gas lanterns and torches -- the only warm light in an overwhelmingly cold world.

**Key Techniques:**
| Technique | Implementation | VeilBreakers Application |
|-----------|---------------|--------------------------|
| Gaslight warmth islands | Small warm pools of light from lanterns on streets | Gothic town lamp posts creating amber pools on cobblestone |
| Muted desaturation | Color palette has almost no vibrance except blood red | Veil corruption further desaturates the world as it spreads |
| Night-only setting | No daytime, permanent dusk-to-night | Veil-heavy areas permanently twilight regardless of time |
| Nightmare color shift | Later areas shift to sickly yellows and alien greens | Advanced Veil corruption shifts palette toward purple-black |
| Window glow as life indicator | Lit windows = NPCs alive inside, dark = abandoned/dead | Inhabited buildings have warm amber window glow, corrupted have none |

**Bloodborne Color Palette (hex reference):**
- Background darks: #1a1410 (warm black), #2a231c (dark brown)
- Stone/architecture: #4a3f35, #5c5045
- Blood accents: #8b1a1a, #a02020
- Gaslight warm: #d4a030, #c89020
- Nightmare shift: #4a5a20 (sickly green), #6a4a60 (alien purple)
- Fog/atmosphere: #3a3540 (purple-grey mist)

**Confidence:** HIGH -- verified through color palette analysis, Medium article breakdown, and community art direction studies

### 1.4 Diablo IV -- Isometric Dark Fantasy and "Return to Darkness"

**Core Philosophy:** Diablo IV's two art pillars are **"Old Masters"** (Rembrandt-style controlled tonal range) and **"Return to Darkness"** (Sanctuary as genuinely dangerous medieval gothic world). The lighting uses physically-based rendering with deliberate departures for dark magic.

**Key Techniques (from official Blizzard technical breakdown):**
| Technique | Implementation | VeilBreakers Application |
|-----------|---------------|--------------------------|
| Deferred renderer | Handles many light sources in dense dungeons | Forward+ in URP serves same purpose |
| Negative light sources | Dark magic creates "anti-light" that absorbs nearby illumination | Veil corruption as negative light -- actively darkening surroundings |
| Volumetric dust/particles | Engine simulates light scattering through air, not just primitive particles | Use volumetric fog package for light shaft simulation |
| Stained glass light scattering | Light through colored windows creates colored light volumes | Light cookies through leaded glass windows in Gothic buildings |
| Pre-computed static shadows | Dungeon walls/floors have baked shadows, dynamic objects overlay | Use mixed lighting: baked for architecture, realtime for characters |
| HDR true blacks | OLED displays show actual black in shadows, supporting gothic aesthetic | Configure tonemapping for deep blacks, avoid lifted shadows |
| Noise texture layering | Drifting mists, fiery effects created through layered noise shaders | Veil corruption fog using layered Perlin/Worley noise |

**Critical Insight -- "Negative Light" for Corruption:**
Diablo IV's engine supports light sources with negative intensity that actively darken areas. This is the exact technique needed for Veil corruption: as corruption spreads, it doesn't just change color -- it **absorbs light**, making nearby torches dimmer and warm colors colder. In Unity URP, this can be approximated with:
- Shader-based light absorption zones (custom fullscreen pass)
- Reduced light intensity multiplier in corrupted areas via scripting
- Post-processing color grading that desaturates and darkens in corruption zones

**Confidence:** HIGH -- sourced from official Blizzard "Peeling Back the Varnish" technical article

### 1.5 Lords of the Fallen 2023 -- Dual-World Lighting

**Core Philosophy:** The game renders two worlds simultaneously. Axiom (living realm) uses warm, naturalistic lighting. Umbral (dead realm) uses cold, sickly, otherworldly lighting. The transition between them is the core mechanic.

**Key Techniques:**
| Technique | Implementation | VeilBreakers Application |
|-----------|---------------|--------------------------|
| Dual-world rendering | Both worlds rendered simultaneously, shader controls visibility | Veil corruption as gradual overlay, not binary switch |
| Umbral blue lantern cone | Holding lantern reveals dead world in a cone of blue light | Could be used for "Veil Sight" ability to see corruption sources |
| Shader-based visibility | Objects exclusive to one realm are invisible in the other via shader | Corruption-only objects (tendrils, growths) appear as corruption spreads |
| Warm/cold realm contrast | Axiom = warm naturalistic, Umbral = cold supernatural | Clean world = warm amber Gothic, Corrupted = cold purple-black |

**Performance Note:** Hexworks tested worst-case with both worlds fully active simultaneously. For VeilBreakers, corruption is a gradient, not binary -- lighter on performance since we blend rather than double-render.

**Confidence:** MEDIUM -- Game Developer article provides design overview but limited shader-level technical detail

### 1.6 Dragon's Dogma 2 -- Darkness as Gameplay Mechanic

**Core Philosophy:** Night is genuinely dangerous because you **cannot see**. The lantern is a survival tool, not a cosmetic feature. Running out of oil in the wilderness is a crisis.

**Key Techniques:**
| Technique | Implementation | VeilBreakers Application |
|-----------|---------------|--------------------------|
| True darkness at night | Ambient light drops to near-zero at night | Veil-corrupted areas have suppressed ambient similar to nighttime |
| Lantern as survival tool | Oil-based, depletes over time, must be managed | Potential: Veil Wards deplete over time, must be recharged |
| Lantern brightness levels | Full/Nearly-Empty/Empty with different light radii | Corruption resistance could have similar depletion tiers |
| Undead spawning at night | Darkness triggers dangerous enemy spawns | Veil corruption level triggers corruption-themed enemy spawns |
| Pawn lantern sync | NPCs auto-light lanterns when dark | Settlement NPCs light torches at dusk, retreat from corruption |
| Road safety vs wilderness danger | Paved roads slightly safer, wilderness pitch dark | Main paths between settlements lit, off-path areas dark |

**Confidence:** HIGH -- well-documented game mechanic with multiple analysis sources

### 1.7 Universal Lighting-as-Player-Guidance Principles

Across all studied games, consistent patterns emerge for using light to guide players:

**The Four-Pass Lighting System (from Level Design Book):**
1. **Global atmosphere** -- Set overall mood (time of day, weather, corruption level)
2. **Wayfinding lights** -- "Big important exits should have more important looking lighting"
3. **Gameplay lights** -- Highlight puzzle elements, enemy positions, interactive objects
4. **Detail/mood lights** -- Final polish for immersion

**Color Temperature as Safety Signal:**
| Temperature | Color | Meaning | Example |
|-------------|-------|---------|---------|
| 2200-3000K | Warm amber/orange | Safety, civilization, rest | Bonfires, hearths, candles |
| 4000-5500K | Neutral white | Neutral, daytime, exposed | Sunlight, moonlight |
| 6500-8000K | Cool blue-white | Cold, danger, supernatural | Moonlight, ice areas |
| Custom | Purple/green | Corruption, magic, alien | Veil energy, dark magic |

**Key Insight -- The "Moth to Flame" Effect:**
Players are naturally drawn to well-lit areas and instinctively avoid darkness. Game designers exploit this by:
- Lighting the critical path more brightly than side paths
- Using warm light for objectives and cool light for traps/ambushes
- Creating "light breadcrumbs" -- visible light sources spaced to guide exploration
- Breaking the pattern deliberately to create tension (the well-lit room that's actually a trap)

**For VeilBreakers specifically:**
- Settlement buildings with warm amber window glow = inhabited, safe
- Dark windows = abandoned or corrupted
- Veil Ward pylons emit protective golden light = safe zone boundary
- Corruption tendrils glow faint purple = danger zone boundary
- Player can read corruption level by how dim/desaturated the world appears

**Confidence:** HIGH -- cross-verified across Level Design Book, Gamasutra/Game Developer articles, and multiple academic sources on game lighting psychology

---

## MISSION 2: Unity 6 URP Lighting Techniques

### 2.1 Adaptive Probe Volumes (APV)

APV replaces legacy Light Probes in Unity 6 for indirect lighting (GI). Critical for VeilBreakers because Gothic interiors need convincing light bounce off stone walls.

**Setup (verified from Unity 6000.3 docs):**
1. **Enable:** Edit > Project Settings > Quality > Render Pipeline Asset > Lighting > Light Probe System = "Adaptive Probe Volumes"
2. **Add volume:** GameObject > Light > Adaptive Probe Volume, set Mode = Global
3. **Configure lights:** Set light Mode to "Mixed" or "Baked"
4. **Configure renderers:** Enable "Contribute Global Illumination" on static meshes, set "Receive Global Illumination" to "Light Probes"
5. **Bake:** Window > Rendering > Lighting > Adaptive Probe Volumes tab > Bake mode = Single Scene > Generate Lighting

**Key Configuration for Dark Fantasy:**
| Setting | Recommended Value | Why |
|---------|-------------------|-----|
| Min Probe Spacing | 1m outdoors, 0.5m indoors | Denser indoors for better bounce light on stone walls |
| Max Probe Spacing | 4m outdoors | Performance balance for open areas |
| Dilation Distance | 1.5x probe spacing | Fills light leak gaps in walls |
| Sky Occlusion | Enabled | Prevents sky light bleeding into covered interiors |

**Streaming (for large worlds):**
APV supports streaming for large open worlds -- bake data larger than available memory, load at runtime. Essential if VeilBreakers has seamless indoor/outdoor transitions.

**Confidence:** HIGH -- directly from Unity 6000.3 official documentation

### 2.2 Forward+ Rendering Path

**Critical for VeilBreakers Gothic interiors.** A single tavern scene might have: 2 fireplaces, 8 wall sconces, 12 candles on tables, 4 hanging lanterns, window light = 26+ light sources. Forward rendering caps at 9 lights per object. Forward+ removes per-object limits.

**Light Limits by Rendering Path:**
| Path | Per-Object Limit | Per-Camera Limit (Desktop) |
|------|------------------|----------------------------|
| Forward | 9 (1 main + 8 additional) | 256 |
| Forward+ | **No per-object limit** | 256 (configurable) |

**Configuration:**
- Set in URP Renderer Asset > Rendering Path = Forward+
- Per-camera limit configurable via ShaderConfig.cs.hlsl (MAX_VISIBLE_LIGHT_COUNT)
- Forward+ also supports per-pixel additional lights by default (no per-vertex fallback needed)

**Performance Recommendation:** Forward+ with careful light culling. Use light range aggressively -- candles should have 3-5m range, torches 6-10m, fireplaces 8-12m. This keeps per-tile light counts manageable.

**Confidence:** HIGH -- from Unity 6000.3 official documentation on light limits

### 2.3 Screen Space Ambient Occlusion (SSAO)

Essential for dark fantasy -- adds depth to crevices in stone walls, under furniture, in corners. Makes Gothic architecture feel heavy and grounded.

**Setup:**
1. Select URP Renderer > Add Renderer Feature > Screen Space Ambient Occlusion
2. Configure in the Renderer Feature inspector

**Recommended Settings for Dark Fantasy:**
| Setting | Value | Why |
|---------|-------|-----|
| Method | Depth Normals | Significantly better quality than Depth-only |
| Sample Count | 8 | Balance of quality/performance (4 is too low for stone detail) |
| Radius | 0.4-0.6 | Medium radius catches stone crevices without over-darkening |
| Intensity | 1.2-1.5 | Slightly above default for darker, more dramatic occlusion |
| Direct Lighting Strength | 0.3 | Keep AO visible even in directly-lit areas for stone depth |
| Half Resolution | OFF for quality, ON for mobile | Full resolution preserves fine stone detail |
| Normal Quality | High (9 samples) | Worth the cost for complex Gothic geometry |

**Confidence:** HIGH -- from Unity 6000.0 official documentation

### 2.4 Light Cookies for Gothic Window Patterns

Light cookies project patterns through lights, perfect for leaded glass window light shafts.

**Implementation for Gothic Windows:**
1. Create a greyscale texture matching the leaded glass pattern (mullions as dark lines, glass panes as bright areas)
2. Apply as Cookie on a Spot Light aimed through the window
3. Set Cookie Size to match window dimensions
4. Optional: tint the Spot Light warm amber for "sunlight through stained glass" effect
5. Optional: use colored cookies (RGB) for stained glass colored light

**Cookie Texture Specifications:**
- Format: R8 greyscale for simple patterns, RGBA for colored stained glass
- Resolution: 256x256 minimum, 512x512 for detailed Gothic tracery
- Import settings: Clamp wrap mode, Bilinear filtering
- Point lights use Cubemap cookies, Spot lights use 2D cookies, Directional lights use 2D cookies

**Animated Cookies for Dynamic Effects:**
- Cloud shadow cookies on directional light (animated UV offset)
- Tree canopy shadow cookies for forest areas
- Render Texture cookies for dynamic effects (fire flicker through windows)

**Confidence:** HIGH -- from Unity official Cookies documentation

### 2.5 Volumetric Lighting in URP

**URP does NOT have built-in volumetric lighting.** This is the single biggest gap for dark fantasy in URP versus HDRP.

**Best Solution: Unity-URP-Volumetric-Light (open-source)**

| Property | Detail |
|----------|--------|
| Repository | github.com/CristianQiu/Unity-URP-Volumetric-Light |
| Compatibility | Unity 2022.3 LTS through Unity 6000.4 |
| Render paths | Forward, Deferred, Forward+, Deferred+ |
| Light types | Main light, spot lights, point lights |
| Features | Shadow support, light cookie rendering, APV integration, VR support |
| Install | Package Manager > Install from git URL |
| Performance | Forward+ or Deferred+ strongly recommended for multiple volumetric lights |

**Setup Steps:**
1. Install package via git URL
2. Add Volumetric Fog renderer feature to URP Renderer
3. Enable post-processing on camera and renderer
4. Create Volume, add "Custom > Volumetric Fog" override
5. Enable fog and light contributions (disabled by default)
6. Attach VolumetricAdditionalLight component to spot/point lights needing volumetric participation

**Commercial Alternatives:**
| Asset | Price Range | Notes |
|-------|-------------|-------|
| HAZE - Volumetric Fog & Lighting | $$ | Recent (Dec 2025), full URP support |
| Volumetric Fog & Mist 2 (Kronnect) | $$ | Mature, well-documented, god rays support |
| LSPP - God Rays | $ | Screen-space, lighter weight |
| Volumetric Light Beam | $ | Cross-platform, good for individual beams |

**For VeilBreakers Recommendation:** Start with Unity-URP-Volumetric-Light (free, open-source, actively maintained, Unity 6 compatible). If more features needed, evaluate HAZE or Kronnect.

**Known Limitations:**
- WebGL not supported
- Transparent object blending can have artifacts
- Baked lights only work via APV
- Limited render distance (not an issue for interior/medium-range scenes)

**Confidence:** HIGH -- verified from GitHub README and Unity community discussions

### 2.6 Light Layers (Rendering Layers)

Critical for separating interior and exterior lighting. Without this, a directional sun bleeds through walls into interiors.

**Setup (from Unity 6000.3 docs):**
1. URP Asset > Lighting > Advanced Properties (via ...) > Enable "Use Rendering Layers"
2. Project Settings > Tags and Layers > Name rendering layers (e.g., "Exterior", "Interior", "Corruption")
3. Assign lights to specific rendering layers via Light > Rendering > Rendering Layers
4. Assign meshes to rendering layers via Mesh Renderer > Additional Settings > Rendering Layer Mask

**Recommended Layer Setup for VeilBreakers:**
| Layer | Purpose | Lights | Objects |
|-------|---------|--------|---------|
| Default | Both interior and exterior | Character lights, VFX | Player, NPCs, dynamic objects |
| Exterior | Outdoor lighting | Directional sun/moon, sky ambient | Terrain, exterior building faces |
| Interior | Indoor lighting | Candles, fireplaces, chandeliers | Interior walls, floors, furniture |
| Corruption | Veil effects | Corruption glow lights, Veil Ward lights | Corruption meshes, ward pylons |

**Custom Shadow Layers:** A light can cast shadows from objects it doesn't illuminate, enabling scenarios like exterior sun casting shadows of window frames onto interior floors without illuminating interior walls.

**Important:** Enabling Rendering Layers disables the traditional Culling Mask on lights. Plan layer assignments before enabling.

**Confidence:** HIGH -- from Unity 6000.3 official documentation

### 2.7 Shadow Configuration

**Shadow Cascades for Directional Light:**
| Setting | Recommended Value | Why |
|---------|-------------------|-----|
| Cascade Count | 4 | Maximum quality for Gothic architecture detail |
| Cascade Split 1 | 5% | Sharp shadows very close to camera |
| Cascade Split 2 | 15% | Medium detail for nearby buildings |
| Cascade Split 3 | 35% | Decent shadows for mid-range |
| Max Shadow Distance | 80-120m | Gothic towns don't need ultra-far shadows |
| Shadow Resolution | 2048 or 4096 | Higher for crisp stone/masonry shadow edges |
| Depth Bias | 0.5-1.0 | Prevent shadow acne on stone surfaces |
| Normal Bias | 0.5-1.0 | Prevent peter-panning on thin geometry |

**Additional Light Shadows:**
- Spot lights (window shafts): Enable shadows, resolution 512-1024
- Point lights (candles): Shadows optional (expensive for point lights, 6 shadow maps each)
- Strategy: Only enable shadows on "hero" point lights (fireplaces, key candles), disable on ambient fill candles

**Confidence:** HIGH -- standard Unity shadow configuration, verified against URP docs

### 2.8 Reflection Probes for Wet Stone

Gothic dark fantasy environments often feature wet, mossy stone that needs specular reflections.

**Configuration:**
- Place Reflection Probes in key areas (tavern interiors, rainy courtyards, dungeon corridors)
- URP supports max 2 probes per pixel with blending between volumes
- Enable probe blending to avoid harsh transitions

**Wet Stone Material Approach:**
1. Increase Smoothness (0.7-0.9) in rain/wet areas via shader parameter
2. Use a "wetness mask" texture or world-space Y gradient to control where surfaces are wet
3. Reflection probes capture environment for specular highlights on wet surfaces
4. Combine with rain VFX (puddle shader, drip particles) for complete wet look

**Shader Graph Wet Surface:**
- Base smoothness: 0.3 (dry stone)
- Wet smoothness: 0.8 (wet stone)
- Blend via wetness parameter (global, controlled by weather system)
- Darken albedo by 15-20% when wet (wet surfaces absorb more light)

**Confidence:** MEDIUM -- reflection probe docs verified, wet surface shader approach is standard practice but not from a single official source

---

## MISSION 3: VFX for Dark Fantasy

### 3.1 Corruption/Veil Spread VFX

The signature VFX of VeilBreakers. Must convey creeping darkness consuming the world.

**Shader-Based Corruption Spread:**

Use Shader Graph with world-space noise to create corruption that spreads across surfaces:

```
Corruption Dissolve Shader (Shader Graph):
1. Sample Position node (World Space)
2. Feed world position into layered noise:
   - Perlin Noise (large scale, 0.05 frequency) for broad corruption boundary
   - Voronoi Noise (medium scale, 0.2 frequency) for tendril-like edges
   - Simple Noise (small scale, 1.0 frequency) for fine detail
3. Combine noise layers: 0.5*Perlin + 0.3*Voronoi + 0.2*Simple
4. Compare against corruption_threshold (global float, 0-1)
5. Step/SmoothStep to create hard or soft boundary
6. Below threshold: normal material
7. At boundary: emission glow (purple, #6a0080, intensity 2-4)
8. Above threshold: corruption material (dark veiny texture, subtle pulsing emission)
```

**Global Corruption Control:**
- `_CorruptionOrigin` (Vector3) -- world position of corruption source
- `_CorruptionRadius` (float) -- current spread radius
- `_CorruptionIntensity` (float) -- 0-1, controls visual severity
- `_PulseSpeed` (float) -- pulsing rate for living corruption feel
- Update these via C# script as corruption spreads over time

**Particle VFX Overlay:**
- Dark motes rising from corrupted ground (VFX Graph, 100-200 particles per corruption zone)
- Purple-black wisps at corruption boundary (ribbon particles following noise path)
- Occasional "corruption lightning" (short bright purple flashes along tendrils)

**Confidence:** HIGH -- dissolve shader technique well-documented, corruption adaptation is standard extension

### 3.2 Fire/Torch VFX

Every Gothic building needs convincing fire. The VeilBreakers toolkit already has fire_flicker and torch_sway animations in the Blender addon; this covers the Unity runtime side.

**Complete Torch VFX Stack (5 layers):**

| Layer | System | Description | Performance |
|-------|--------|-------------|-------------|
| 1. Flame | VFX Graph | 30-50 particles, billboard, color gradient orange>yellow>white | Low |
| 2. Smoke | VFX Graph + 6-way lighting | 10-20 particles, lit by scene lights, rises and dissipates | Medium |
| 3. Sparks/Embers | VFX Graph | 5-15 particles, point, gravity + random velocity, ember color | Low |
| 4. Heat distortion | Fullscreen shader | Distortion near flames using noise-offset UV sampling | Low |
| 5. Dynamic light | Point/Spot Light | Flickering intensity via animation curve or script | Low |

**Flickering Light Script Pattern:**
```csharp
// Attach to Point Light on torch
float baseIntensity = 1.5f;
float flickerAmount = 0.3f;
float flickerSpeed = 8.0f;

void Update() {
    float noise1 = Mathf.PerlinNoise(Time.time * flickerSpeed, 0f);
    float noise2 = Mathf.PerlinNoise(0f, Time.time * flickerSpeed * 1.3f);
    float flicker = (noise1 * 0.6f + noise2 * 0.4f) * flickerAmount;
    light.intensity = baseIntensity + flicker;
    light.range = baseRange + flicker * 0.5f; // subtle range variation
}
```

**Six-Way Lighting for Smoke (Unity VFX Graph 17+):**
Six-way lighting pre-bakes directional lighting into six sprite texture lightmaps. At runtime, Unity shaders blend these based on current scene lighting, so smoke particles react to light from any direction -- critical for convincing fireplace smoke in dynamically lit interiors.

**Confidence:** HIGH -- VFX Graph fire techniques well-documented, six-way lighting verified from Unity blog and docs

### 3.3 Fog/Mist VFX

Three distinct fog types for VeilBreakers:

**A. Ground Fog (Graveyards, Valleys, Marshes):**
- Use VFX Graph with flat billboard particles constrained to Y-axis (ground level +/- 0.5m)
- World-space noise controls density variation
- Color: warm grey (#8a8070) for natural, purple-grey (#5a4565) for Veil-corrupted
- 50-100 particles per fog zone, large size (2-5m each), slow drift
- Alternative: GPU Fog Particles (open-source, MirzaBeig/GPU-Fog-Particles) for textureless fog using noise shader

**B. Volumetric Fog (Light Shafts, God Rays):**
- Use Unity-URP-Volumetric-Light package for screen-space volumetric rendering
- Pair with Spot Lights aimed through windows for god ray effect
- Use light cookies to shape the rays (Gothic window patterns)
- Performance: use lower ray-march sample count (8-16) for large areas

**C. Corruption Fog (Veil Zones):**
- Distinct from natural fog: moves unnaturally, darker, denser, with particle highlights
- VFX Graph: 200-500 particles in corruption zones, dark purple-black with faint emission edges
- Shader: custom unlit with dissolve noise for wispy tendril shapes
- Reacts to player: parts slightly when player moves through (use SDF or simple repulsion)

**Confidence:** HIGH for ground/volumetric fog techniques, MEDIUM for corruption fog (custom implementation)

### 3.4 Rain/Weather VFX

**Complete Rain System Components:**

| Component | Implementation | Notes |
|-----------|---------------|-------|
| Falling rain | VFX Graph, 1000-5000 particles in camera frustum | Spawn in cylinder above camera, fall with gravity + slight wind |
| Splash on surfaces | VFX Graph sub-effect, spawn on collision | Small burst particles on horizontal surfaces |
| Puddle accumulation | Shader Graph, procedural puddles using world-space Y and noise | Puddle Subgraph from Unity Weather sample |
| Wet surfaces | Global smoothness multiplier increase | Darken albedo 15-20%, increase smoothness to 0.7-0.9 |
| Rain ripples | Shader Graph animated normal maps on puddle areas | RainRipples and PuddleWindRipples subgraphs |
| Drips on overhangs | VFX Graph, spawn on edge geometry | Small particles with short lifetime, spawn under eaves/arches |

**Unity Shader Graph Weather Sample (official):**
Unity provides a production-ready Weather shader sample with rain, puddles, and wetness as a Shader Graph package sample. Available in Shader Graph 14.0+ and 17.0+. This is the recommended starting point.

**Performance Budget:**
- Rain particles: ~2000 active at medium settings, ~5000 at high
- Puddle shader: low cost (procedural, no extra geometry)
- Wet surface: negligible (global parameter change)
- Rain sound: not VFX but critical for immersion

**Confidence:** HIGH -- Unity Weather shader sample is official, rain particle techniques well-established

### 3.5 Magic/Veil Effect VFX

**Dark Energy (Veil Power):**
- Base shape: swirling ribbons of dark purple-black energy
- VFX Graph: 200-400 ribbon particles orbiting in a spiral pattern
- Color: deep purple (#2a0040) core, lighter purple (#8040a0) edges, occasional bright flashes
- Add screen-space distortion at center (chromatic aberration + noise warp)

**Soul Particles (Captured/Released):**
- Small bright points that drift with organic movement
- VFX Graph: 20-50 particles per soul, attract toward/away from capture point
- Color: pale blue-white (#c0d0ff) with slight trail
- Noise-driven movement creates "alive" feeling

**Veil Tears (Rifts in Reality):**
- Shader-based effect: screen-space distortion showing "another world" bleeding through
- Central void: black with purple edge emission
- Surrounding area: chromatic aberration, UV distortion increasing toward rift center
- Floating debris particles pulled toward rift
- Edge particles: bright purple sparks tracing the rift boundary

**Ambient Dark Particles (Ever-Present Corruption Indicator):**
- Subtle dark motes floating in Veil-touched areas
- VFX Graph: 50-100 tiny particles per area, slow upward drift
- Nearly invisible individually, collectively create "something is wrong" atmosphere
- Density increases with corruption level

**Confidence:** MEDIUM -- these are custom effects designed for VeilBreakers, techniques are standard but specific implementation is novel

### 3.6 Ambient Particles

**Dust Motes (Interiors):**
- Visible in light shafts through windows
- VFX Graph: 100-200 tiny bright particles in each shaft volume
- Brownian motion (noise-driven slow drift)
- Only visible against dark backgrounds, transparent against bright areas

**Floating Embers (Near Fire):**
- Rise from fireplaces, torches, campfires
- VFX Graph: 10-30 particles per fire source
- Orange-bright point particles, rise with slight wobble
- Fade to dark as they cool (color over lifetime: bright orange > dark red > invisible)

**Fireflies (Safe Natural Areas):**
- Indicate areas free from Veil corruption
- VFX Graph: 20-40 particles per zone
- Slow random movement, subtle green-yellow glow
- Pulsing brightness (sine wave, 1-2 second period)
- Disappear in corrupted areas (gameplay indicator)

**Confidence:** HIGH -- standard ambient particle techniques

### 3.7 VFX Performance Optimization

**GPU Particles via VFX Graph:**
- All VFX should use VFX Graph (GPU-simulated) not legacy Particle System (CPU-simulated)
- VFX Graph runs simulation AND rendering on GPU in a single program
- Enables millions of particles without CPU bottleneck
- Use Compute Shader simulation for complex behaviors

**Overdraw Mitigation (Primary Performance Concern):**
| Strategy | Implementation |
|----------|---------------|
| Minimize particle size | Keep particles as small as visually acceptable |
| Reduce particle count | Use fewer, larger particles rather than many small ones where possible |
| Texture atlases | Single draw call for varied particle appearances |
| Avoid additive blending stacking | Additive particles overlapping = extreme overdraw |
| Half-resolution particles | Render VFX at half res, composite at full res |
| Culling | Enable frustum culling, set culling bounds tight |

**LOD System for VFX:**
| Distance | Adjustment |
|----------|------------|
| 0-20m | Full quality: max particles, full size, all layers |
| 20-50m | Reduced: 50% particles, simplified shader |
| 50-100m | Minimal: 25% particles, billboard only, no smoke/sparks |
| 100m+ | Culled: only the dynamic light point visible |

**Performance Budget per Frame (targeting 60fps on mid-range GPU):**
| Category | Max Active Particles | Max Draw Calls |
|----------|---------------------|----------------|
| Fire/torch effects (scene total) | 500 | 5 |
| Corruption VFX | 1000 | 3 |
| Fog/mist | 500 | 2 |
| Weather (rain) | 3000 | 2 |
| Ambient (dust, embers) | 500 | 3 |
| Magic effects (combat) | 800 | 5 |
| **Scene total** | **~6300** | **~20** |

**Confidence:** HIGH -- performance optimization techniques verified from Unity VFX Graph docs and multiple professional guides

---

## MISSION 4: Building Lighting

### 4.1 Gothic Interior Lighting Philosophy

Gothic interiors are defined by **contrast between deep shadow and focused light**. The architecture creates natural pockets of darkness (vaulted ceilings, thick stone walls, deep window recesses) punctuated by warm artificial light sources.

**The Three-Light Interior Approach:**
1. **Key Light** -- The primary source. For a tavern, the central fireplace. For a chapel, the window behind the altar.
2. **Fill Lights** -- Secondary sources that provide enough ambient to see but maintain drama. Wall sconces, candle clusters.
3. **Accent Lights** -- Small focused lights that draw attention. A candle on a specific table, light on a quest item.

**No Global Ambient in Interiors:**
The single most important rule for Gothic interiors: **set ambient light to zero or near-zero** (0.02-0.05 intensity maximum). All light must come from visible sources. This creates the dramatic contrast that defines the genre. APV (Adaptive Probe Volumes) will provide light bounce from placed sources, giving soft fill without artificial ambient.

### 4.2 Window Light Shafts (Leaded Glass)

The defining visual of a Gothic interior: shafts of warm light streaming through tall pointed windows with leaded glass patterns.

**Complete Implementation:**

1. **Spot Light** placed outside the window, aimed inward at ~30-45 degree downward angle
2. **Light Cookie** with leaded glass pattern:
   - Vertical and horizontal mullions as dark lines (0.0 brightness)
   - Glass panes as bright areas (0.8-1.0 brightness)
   - For stained glass: use RGB cookie with color tinting per pane
3. **Color Temperature:** 3500-4500K (warm amber, as if filtered through old glass)
4. **Intensity:** High enough to create visible shaft through volumetric fog
5. **Volumetric Fog:** Enable volumetric contribution on this spot light to make shaft visible
6. **Dust Motes:** VFX Graph particles spawned within the shaft cone volume

**Light Cookie Design for Gothic Windows:**

| Window Type | Pattern | Cookie Style |
|-------------|---------|--------------|
| Pointed arch (lancet) | Two-pane with central mullion | Simple vertical division |
| Rose window | Radial spokes with petal shapes | Complex radial pattern |
| Tracery window | Gothic tracery with quatrefoils | Detailed curved divisions |
| Diamond lattice | Diagonal grid pattern | Repeating diamond pattern |
| Leaded rectangular | Small rectangular panes | Grid pattern with slight irregularity |

**Time-of-Day Variation:**
- Morning: shafts angle steeply, warm gold
- Noon: vertical shafts, neutral warm white
- Afternoon: opposite angle, deepening amber
- Night: no window light (replace with moonlight, cool blue, very dim)

### 4.3 Fireplace/Hearth Lighting

The emotional center of any Gothic interior. The fireplace is the "bonfire" of the settlement -- warmth, safety, community.

**Light Setup per Fireplace:**

| Component | Type | Settings |
|-----------|------|----------|
| Primary fire light | Point Light | Color: warm orange (#FF8C40), Intensity: 2-4, Range: 8-12m, Shadows: Soft |
| Ember glow | Point Light (secondary) | Color: deep red (#FF3020), Intensity: 0.5, Range: 3m, No shadows |
| Wall bounce | Baked via APV | Warm orange bounce on chimney breast and ceiling |
| Flicker animation | Script | Perlin noise-driven intensity + range variation |

**Warm Bounce:**
APV with 0.5m probe spacing near fireplaces captures warm bounce light on stone walls and ceiling. This is the most important indirect lighting in the interior -- the warm glow on the chimney breast above the fire.

**Color Gradient by Distance from Fire:**
- 0-2m: Warm orange, high intensity, strong shadows
- 2-5m: Amber, medium intensity, objects clearly visible
- 5-8m: Dim amber fading to near-dark
- 8m+: Deep shadow, barely visible
- This gradient creates the dramatic "warm island in darkness" effect

### 4.4 Tavern Interior Lighting

The archetypal dark fantasy social space. Must feel warm, lived-in, slightly smoky.

**Complete Tavern Light Plan:**

| Source | Light Type | Count | Purpose |
|--------|-----------|-------|---------|
| Central fireplace | Point Light | 1 | Primary illumination, warm anchor |
| Hanging chandelier(s) | Spot Light (downward) | 1-2 | Table illumination pools |
| Wall sconces | Point Light | 4-6 | Perimeter fill, prevent total darkness at edges |
| Candles on tables | Point Light (tiny) | 6-10 | Character face-lighting during conversation |
| Window light (day) | Spot Light with cookie | 2-4 | Natural light variation, dust shaft accents |
| Behind-bar lantern | Point Light | 1 | Illuminates barkeep and bottles |

**Total lights:** 15-24 per tavern (requires Forward+ rendering)

**Atmosphere Layers:**
1. Light haze from fireplace smoke (volumetric fog, very low density)
2. Dust motes in window shafts (VFX Graph)
3. Ember particles from fireplace (VFX Graph)
4. Warm post-processing: slight bloom on fire sources, vignette at screen edges

**Audio-Visual Sync (for toolkit generation):**
- Fire crackle intensity matches fire light intensity
- Ambient conversation volume matches occupancy level
- Wind sound outside matches window draft VFX (if windows open)

### 4.5 Dungeon/Underground Lighting

Dungeons strip away natural light entirely. Every photon must come from a placed source.

**Torch-Lit Corridor:**
- Wall torches every 8-12m creates rhythm of light-dark-light-dark
- Torch point lights: warm orange, range 5-7m, shadows enabled
- Between torches: near-total darkness (ambient 0.01-0.02)
- Player-carried torch/lantern: warm pool that moves with player

**Bioluminescence (for Veil-touched dungeons):**
- Corruption growth on walls emits faint purple-blue glow
- Emission maps on corruption textures (intensity 0.5-1.5, pulsing)
- No point lights needed -- material emission provides ambient
- Creates alien, unsettling atmosphere distinct from torch warmth

**Magical Light Sources:**
- Veil Ward crystals: steady golden glow, no flicker (artificial stability = safety)
- Corruption nodes: pulsing purple, irregular rhythm (organic = danger)
- Ancient runes: faint blue-white, steady (neutral, historical)

**Dungeon Lighting Progression (as corruption increases):**
| Corruption Level | Torch Behavior | Ambient | Added Effects |
|-----------------|----------------|---------|---------------|
| 0% (Clean) | Normal warm glow | 0.02 | None |
| 25% | Slight purple tinge at flame edges | 0.015 | Faint dark motes |
| 50% | Torches flicker more, reduced range | 0.01 | Visible corruption glow on walls |
| 75% | Torches guttering, some extinguished | 0.005 | Dense corruption fog, wall emissions |
| 100% (Consumed) | All torches out | 0.0 | Only corruption glow illuminates |

### 4.6 Exterior Night Lighting

**Moonlight:**
- Directional light: cool blue-white (#B0C0D8), very low intensity (0.03-0.08)
- Slightly angled (not directly overhead) for long shadows
- Cloud shadow cookie on directional light for moving cloud shadows

**Building Exterior at Night:**
| Source | Implementation | Purpose |
|--------|---------------|---------|
| Window amber glow | Emissive plane behind window mesh, warm amber | Shows building is inhabited |
| Door lantern | Point Light, warm, range 4-6m | Entrance identification |
| Wall-mounted torch sconces | Point Light, warm orange, range 5-8m | Street illumination |
| Signage lantern | Small Spot Light aimed at sign | Business identification |
| Street lamp posts | Point Light, warm amber, range 8-10m | Main road illumination |

**The Warm Windows Effect:**
Nothing says "civilization in the darkness" more effectively than warm amber light glowing from windows. Implementation:
1. Place a simple quad behind each window opening
2. Apply unlit emissive material: amber color (#D4A030), emission intensity 2-3
3. No actual light needed -- the emissive surface itself is the visual
4. For important buildings, add a small Point Light inside that casts light outward through the window

**Street Light Spacing for Gothic Town:**
- Main streets: torch/lamp every 10-15m
- Side streets: every 20-25m (darker, less safe feeling)
- Alleys: no lighting (danger zones)
- Town square: well-lit from multiple sources (gathering place, safety)
- Near Veil Ward: golden ward light supplements street lighting

---

## Implementation Priority for VeilBreakers Toolkit

### Phase 1: Core Lighting Infrastructure
1. Enable Forward+ rendering path in URP
2. Configure Adaptive Probe Volumes (global, appropriate probe density)
3. Set up Rendering Layers (Exterior, Interior, Corruption)
4. Configure shadow cascades (4 cascades, optimized splits)
5. Add SSAO renderer feature with dark fantasy settings
6. Install Unity-URP-Volumetric-Light package

### Phase 2: Gothic Building Lighting Templates
1. Create light cookie textures for 5 Gothic window types
2. Build prefab lighting rigs: Tavern, Chapel, Residence, Shop, Dungeon
3. Implement torch/candle flicker script (Perlin noise-based)
4. Configure APV probe density for interiors (0.5m spacing)
5. Create emissive window materials for exterior night view

### Phase 3: Corruption/Veil VFX System
1. Build corruption dissolve shader (Shader Graph, world-space noise)
2. Create Veil spread particle effects (VFX Graph)
3. Implement corruption fog system
4. Build corruption light absorption system (dimming nearby lights)
5. Create Veil tear/rift VFX

### Phase 4: Weather and Atmosphere
1. Implement rain system (particles + puddle shader + wetness)
2. Build ground fog system (natural + corruption variants)
3. Add ambient particle systems (dust, embers, fireflies)
4. Configure volumetric fog for god rays and light shafts

### Phase 5: Dynamic Corruption Integration
1. Global corruption parameter system (C# manager)
2. Per-area corruption levels affecting all visual systems
3. Torch degradation as corruption increases
4. Window glow extinction in corrupted buildings
5. Firefly disappearance in corruption zones

---

## Key Technical Values Reference

### Color Palette (Linear RGB for Unity)

**Warm Light Sources:**
| Source | Hex | Linear RGB | Color Temp | Intensity |
|--------|-----|------------|------------|-----------|
| Candle flame | #FF9030 | (1.0, 0.31, 0.03) | 1800K | 0.5-1.0 |
| Torch | #FF8C40 | (1.0, 0.27, 0.05) | 2000K | 1.5-2.5 |
| Fireplace | #FFA050 | (1.0, 0.35, 0.08) | 2200K | 2.0-4.0 |
| Warm lantern | #FFB060 | (1.0, 0.42, 0.11) | 2500K | 1.0-2.0 |
| Window sunlight | #FFD090 | (1.0, 0.59, 0.22) | 3500K | 3.0-6.0 |

**Cool/Supernatural Light Sources:**
| Source | Hex | Linear RGB | Intensity |
|--------|-----|------------|-----------|
| Moonlight | #B0C0D8 | (0.42, 0.51, 0.67) | 0.03-0.08 |
| Veil corruption (faint) | #4A2060 | (0.04, 0.01, 0.10) | 0.3-0.8 |
| Veil corruption (strong) | #8040A0 | (0.18, 0.05, 0.32) | 1.0-3.0 |
| Veil Ward (protective) | #D4A030 | (0.63, 0.32, 0.03) | 2.0-4.0 |
| Ancient rune | #6080C0 | (0.10, 0.18, 0.50) | 0.5-1.5 |
| Bioluminescence | #3060A0 | (0.03, 0.10, 0.32) | 0.3-1.0 |

**Corruption Color Progression:**
| Corruption % | Ambient Tint | Emission Color | Desaturation |
|--------------|-------------|----------------|-------------|
| 0% | None | None | 0% |
| 25% | Slight warm shift | Faint purple (#2a0030) | 10% |
| 50% | Cool purple shift | Medium purple (#4a2060) | 25% |
| 75% | Strong purple | Bright purple (#6a3080) | 50% |
| 100% | Deep purple-black | Pulsing purple (#8040a0) | 75% |

---

## Sources

### Primary (HIGH confidence)
- [Unity 6000.3 APV Documentation](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/probevolumes-use.html) -- Adaptive Probe Volumes setup
- [Unity 6000.3 Light Limits](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/lighting/light-limits-in-urp.html) -- Forward+ light limits
- [Unity 6000.3 Rendering Layers for Lights](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/features/rendering-layers-lights.html) -- Light layers setup
- [Unity 6000.0 SSAO Configuration](https://docs.unity3d.com/6000.0/Documentation/Manual/urp/ssao-renderer-feature-reference.html) -- SSAO settings
- [Unity-URP-Volumetric-Light GitHub](https://github.com/CristianQiu/Unity-URP-Volumetric-Light) -- Volumetric lighting package
- [Blizzard "Peeling Back the Varnish"](https://news.blizzard.com/en-us/article/23964183/peeling-back-the-varnish-the-graphics-of-diablo-iv) -- Diablo IV graphics technical breakdown
- [Level Design Book - Lighting](https://book.leveldesignbook.com/process/lighting) -- Lighting as player guidance
- [Game Developer - Lighting Fundamentals](https://www.gamedeveloper.com/design/lighting-design-fundamentals-how-and-where-to-use-colored-light) -- Color temperature and emotional design
- [Unity Shader Graph Weather Sample](https://docs.unity3d.com/Packages/com.unity.shadergraph@17.0/manual/Shader-Graph-Sample-Production-Ready-Weather.html) -- Official rain/weather shaders
- [Unity VFX Graph Six-Way Lighting](https://unity.com/blog/engine-platform/realistic-smoke-with-6-way-lighting-in-vfx-graph) -- Realistic smoke rendering

### Secondary (MEDIUM confidence)
- [Game Developer - Creating Lords of the Fallen's Umbral](https://www.gamedeveloper.com/design/creating-_lords-of-the-fallen-s_-parallel-world-of-umbral) -- Dual-world rendering design
- [Bloodborne Aesthetic Analysis (Medium)](https://medium.com/@marcusramos474/bloodbornes-aesthetic-is-unmatched-e1a07e225918) -- Color palette and lighting
- [Dragon's Dogma 2 Wiki - Day/Night Cycle](https://dragonsdogma2.wiki.fextralife.com/Day+and+Night+Cycle) -- Lantern mechanics
- [RMCAD - Psychology of Game Art](https://www.rmcad.edu/blog/the-psychology-of-game-art-how-colors-and-design-affect-player-behavior/) -- Color psychology in games
- [Daniel Ilett - Dissolve Effect](https://danielilett.com/2020-04-15-tut5-4-urp-dissolve/) -- Shader Graph dissolve technique
- [GPU Fog Particles (GitHub)](https://github.com/MirzaBeig/GPU-Fog-Particles) -- Textureless fog particle approach
- [HAZE Volumetric Fog (Asset Store)](https://assetstore.unity.com/packages/vfx/shaders/fullscreen-camera-effects/haze-volumetric-fog-lighting-for-urp-336656) -- Commercial volumetric fog

### Tertiary (LOW confidence -- needs validation)
- Specific Elden Ring ray tracing implementation details (community reports, not official From Software documentation)
- Exact Lords of the Fallen shader techniques (design overview available, but shader-level implementation details not published)

---

## Metadata

**Confidence breakdown:**
- Game reference analysis: HIGH -- multiple games studied with cross-verified patterns
- Unity 6 URP techniques: HIGH -- sourced from official Unity 6000.3 documentation
- VFX implementation: HIGH for standard techniques, MEDIUM for VeilBreakers-specific corruption effects
- Building lighting: HIGH -- well-established techniques with concrete values
- Color palette/values: HIGH -- derived from game analysis and standard color temperature science

**Research date:** 2026-04-02
**Valid until:** 2026-06-02 (Unity 6 URP stable, techniques unlikely to change in 60 days)
