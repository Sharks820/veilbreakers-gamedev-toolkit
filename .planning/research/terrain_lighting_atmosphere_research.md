# AAA Terrain Lighting and Atmospheric Effects -- Deep Research

**Research date:** 2026-04-02
**Domain:** Open world terrain lighting, atmospheric effects, dark fantasy aesthetic
**Target:** VeilBreakers dark fantasy action RPG (Unity 6 URP + Blender procedural toolkit)
**Games studied:** Elden Ring, Dark Souls III, Bloodborne, Demon's Souls, Ghost of Tsushima, Red Dead Redemption 2
**Confidence:** HIGH (cross-verified across official Unity docs, NVIDIA GPU Gems, and multiple AAA analyses)

---

## Executive Summary

Terrain visual quality is 50% lighting. The VeilBreakers toolkit already has solid foundations -- 8 time-of-day presets, light integration for props, and atmospheric volumes for 10 biomes -- but these systems need significant enhancement to reach AAA quality. The key gaps are: no sun color temperature progression based on real atmospheric scattering, no height fog or distance-based atmospheric perspective, no cascaded shadow map configuration, no post-processing stack setup, and no Adaptive Probe Volume (APV) configuration for terrain GI.

This research provides concrete values, formulas, and implementation patterns for each domain. All values are tuned for dark fantasy aesthetics: desaturated, cold-shifted, with oppressive atmosphere and dramatic contrast.

---

## 1. Time-of-Day Lighting Systems

### 1.1 Sun Angle and Color Temperature Progression

Real sun color changes follow Planck's law of black-body radiation. AAA games approximate this with a color temperature curve mapped to sun elevation angle.

**Sun color temperature by time of day (dark fantasy tuned):**

| Time | Hour | Sun Elevation | Color Temp (K) | RGB (linear) | Intensity | Notes |
|------|------|---------------|-----------------|--------------|-----------|-------|
| Dawn | 5:00 | 5-10 deg | 2200K | (1.0, 0.55, 0.22) | 0.3 | Deep orange, long shadows |
| Golden Hour | 6:30 | 10-15 deg | 2800K | (1.0, 0.68, 0.35) | 0.6 | Warm, dramatic |
| Morning | 8:00 | 25-35 deg | 4200K | (1.0, 0.82, 0.62) | 0.9 | Warming up |
| Noon | 12:00 | 55-70 deg | 5500K | (1.0, 0.95, 0.88) | 1.3 | Neutral white, dark fantasy: slightly desaturated |
| Afternoon | 15:00 | 35-45 deg | 5000K | (1.0, 0.90, 0.78) | 1.1 | Slight warmth returning |
| Golden Hour | 17:30 | 10-15 deg | 2500K | (1.0, 0.60, 0.28) | 0.5 | Rich amber |
| Blue Hour | 18:30 | -2 to 5 deg | 8000K | (0.55, 0.60, 0.85) | 0.15 | Cold blue, eerie |
| Dusk | 19:00 | -5 to -2 deg | 12000K | (0.35, 0.38, 0.65) | 0.08 | Deep blue-purple |
| Night | 22:00 | -30 deg | -- | (0.15, 0.18, 0.35) | 0.04 | Moonlight (blue-silver) |
| Midnight | 0:00 | -60 deg | -- | (0.08, 0.10, 0.22) | 0.02 | Near darkness |

**Color temperature to RGB conversion (simplified for real-time):**
```
For T in Kelvin:
  if T <= 6600K:
    R = 1.0
    G = 0.39 * ln(T/100) - 0.63
    B = 0.54 * ln(T/100 - 10) - 1.68
  else:
    R = 1.29 * (T/100 - 60)^(-0.1332)
    G = 1.29 * (T/100 - 60)^(-0.0755)
    B = 1.0
```

**Current toolkit gap:** `_WORLD_TIME_PRESETS` uses manually picked colors. Should be driven by color temperature curve for physical accuracy, then shifted toward cold/desaturated for dark fantasy feel.

### 1.2 Sky Gradient Progression

**Dawn/Dusk sky gradients (dark fantasy):**
```
Dawn gradient (horizon to zenith):
  Horizon: (1.0, 0.45, 0.15)  -- deep amber/crimson
  30 deg:  (0.65, 0.35, 0.45) -- muted purple-pink
  60 deg:  (0.25, 0.22, 0.45) -- deep violet
  Zenith:  (0.10, 0.12, 0.28) -- near-black blue

Noon gradient:
  Horizon: (0.55, 0.58, 0.65) -- hazy gray-blue (atmospheric perspective)
  30 deg:  (0.42, 0.48, 0.62) -- muted blue
  60 deg:  (0.30, 0.38, 0.58) -- deeper blue
  Zenith:  (0.22, 0.32, 0.52) -- dark fantasy: never pure bright blue

Night gradient:
  Horizon: (0.03, 0.04, 0.08) -- near black with slight blue
  Zenith:  (0.01, 0.02, 0.05) -- darkness
```

**Dark fantasy rule:** Sky is NEVER bright or cheerful. Even at noon, maintain a slightly overcast, desaturated, cold look. Maximum sky brightness ~60% of a "normal" game.

### 1.3 Night Lighting

**Moonlight configuration (dark fantasy):**
- Color: (0.15, 0.18, 0.35) -- blue-silver, slightly purple
- Intensity: 0.03-0.06 (very low, areas should feel DARK)
- Direction: Opposite or offset from sun path by 180 degrees
- Shadow: Soft shadows enabled, very low resolution (saves perf, looks ethereal)

**Torch/Fire lighting radius table:**

| Source | Color | Intensity | Range | Shadow | Flicker Frequency |
|--------|-------|-----------|-------|--------|-------------------|
| Wall torch | (1.0, 0.72, 0.32) | 40-60 | 5-8m | Yes | 3-5 Hz |
| Campfire | (1.0, 0.65, 0.25) | 80-120 | 8-12m | Yes | 2-4 Hz |
| Lantern | (1.0, 0.85, 0.60) | 20-35 | 3-5m | Optional | 1-2 Hz |
| Brazier | (1.0, 0.55, 0.18) | 60-90 | 6-9m | Yes | 2-4 Hz |
| Bonfire/pyre | (1.0, 0.58, 0.20) | 120-180 | 12-18m | Yes | 1-3 Hz |
| Candle | (1.0, 0.82, 0.55) | 8-15 | 2-3m | No | 4-8 Hz |

**Current toolkit status:** `LIGHT_PROP_MAP` in `light_integration.py` has 8 props -- good foundation but needs the expanded table above and intensity/range tuning for dark fantasy (current values are slightly too bright).

---

## 2. Atmospheric Scattering

### 2.1 Rayleigh Scattering (Sky Color)

Rayleigh scattering occurs when light interacts with atmospheric molecules much smaller than the light wavelength. It scatters shorter wavelengths (blue) more than longer wavelengths (red), which is why the sky appears blue.

**Rayleigh scattering coefficient:**
```
beta_R(lambda) = (8 * pi^3 * (n^2 - 1)^2) / (3 * N * lambda^4)

Where:
  n = refractive index of air (1.0003)
  N = number density of atmosphere (~2.545e25 per m^3)
  lambda = wavelength in meters

Standard Rayleigh coefficients (sea level):
  Red   (680nm): beta_R = 3.8e-6 per meter
  Green (550nm): beta_R = 13.5e-6 per meter
  Blue  (440nm): beta_R = 33.1e-6 per meter
```

**For dark fantasy:** Increase Rayleigh scattering coefficients by 1.3-1.5x to make atmosphere thicker, more oppressive. This deepens sunset colors and makes the world feel heavy.

### 2.2 Mie Scattering (Haze/Fog)

Mie scattering occurs with larger particles (dust, water droplets, pollution). It scatters all wavelengths roughly equally, creating white/gray haze.

**Mie scattering parameters:**
```
beta_M = concentration * 2.0e-5  (adjustable)

Henyey-Greenstein phase function:
  P(theta) = (1 - g^2) / (4*pi * (1 + g^2 - 2*g*cos(theta))^(3/2))

Where g = asymmetry parameter:
  g = 0.76  -- typical atmosphere (forward-heavy scattering)
  g = 0.85  -- hazy/polluted (more forward scattering, visible sun disk halo)
  g = 0.60  -- dark fantasy mist (more diffuse scattering, eerie feel)
```

**Dark fantasy Mie settings:**
- g = 0.55-0.65 (more diffuse than reality, creates ethereal glow around light sources)
- Concentration: 2-4x normal (heavy particles in air, world feels thick)
- Color tint: Slight blue-gray or purple shift for corrupted areas

### 2.3 Height Fog (Valley Fog, Mountain Clarity)

Height fog uses exponential density falloff with altitude. This is one of the most important effects for open world terrain -- valleys fill with fog while peaks stay clear.

**Exponential height fog formula:**
```
density(h) = density_base * exp(-height_falloff * (h - sea_level))

Where:
  density_base = 0.02 - 0.08 (dark fantasy: higher end)
  height_falloff = 0.01 - 0.05 per meter
  sea_level = reference altitude (typically 0)

Final fog factor along view ray:
  fog = 1.0 - exp(-integral of density along ray)

Simplified analytical solution for uniform height fog:
  fog = 1.0 - exp(-(density_base / height_falloff) * 
        (exp(-height_falloff * camera_y) - exp(-height_falloff * (camera_y + dir_y * distance))) 
        / dir_y)
```

**Height fog configuration by biome:**

| Biome | density_base | height_falloff | color | max_height |
|-------|-------------|----------------|-------|------------|
| dark_forest | 0.06 | 0.03 | (0.35, 0.38, 0.42) | 15m |
| corrupted_swamp | 0.12 | 0.02 | (0.30, 0.25, 0.35) | 8m |
| volcanic_wastes | 0.04 | 0.04 | (0.45, 0.30, 0.20) | 25m |
| frozen_peaks | 0.02 | 0.05 | (0.75, 0.78, 0.85) | 5m |
| haunted_moor | 0.10 | 0.02 | (0.28, 0.25, 0.30) | 10m |
| enchanted_glade | 0.03 | 0.03 | (0.40, 0.50, 0.45) | 12m |
| bone_desert | 0.01 | 0.06 | (0.60, 0.55, 0.45) | 3m |
| crystal_caverns | 0.05 | 0.01 | (0.25, 0.35, 0.50) | 20m |
| blood_marsh | 0.08 | 0.02 | (0.35, 0.15, 0.15) | 10m |
| ancient_ruins | 0.04 | 0.03 | (0.40, 0.38, 0.35) | 15m |

**Current toolkit gap:** `atmospheric_volumes.py` only has ground fog as a flat box. Needs exponential height-based density with per-biome configuration.

### 2.4 Volumetric Fog Techniques

**Real-time volumetric fog (froxel-based):**
The modern standard (used by Assassin's Creed, Unreal Engine, HDRP) divides the view frustum into a 3D grid of "froxels" (frustum voxels) and ray-marches through them.

**For Unity 6 URP:** Volumetric fog is NOT built-in to URP. Options:
1. **Third-party asset: Buto** -- Volumetric fog + volumetric lighting for URP (Asset Store, production-ready)
2. **Third-party asset: HAZE** -- Volumetric fog + lighting for URP (released 2025)
3. **Third-party asset: AERO** -- Volumetric fog and mist for URP
4. **Open source: Unity-URP-Volumetric-Light** -- GitHub package by CristianQiu, compatible with Unity 6 render graph
5. **Custom full-screen pass** -- Use URP Renderer Features to add a custom fog pass

**Recommendation for VeilBreakers:** Use exponential height fog as the base (cheap, effective), add per-biome fog volumes for localized effects. For AAA quality, integrate a volumetric lighting solution (Buto or the open-source package).

### 2.5 Distance-Based Atmospheric Perspective

Objects farther away appear blue-shifted and lower contrast due to atmospheric scattering between viewer and object. This is critical for open world terrain.

**Atmospheric perspective formula:**
```
final_color = lerp(object_color, fog_color, fog_factor)
fog_factor = 1.0 - exp(-distance * extinction_coefficient)

For dark fantasy:
  extinction_coefficient = 0.001 - 0.005 (higher = more fog)
  fog_color at distance = blend of horizon color and ambient
  
  At 100m: ~10% fogged
  At 500m: ~40% fogged  
  At 1000m: ~60% fogged
  At 2000m: ~85% fogged (mountains barely visible, silhouette only)
```

**Dark fantasy key insight:** Distant terrain should fade to a cold blue-gray, NOT white. This creates the oppressive feeling of a world swallowed by darkness. Color shifts from warm near-field to cold far-field.

---

## 3. Shadow Systems for Terrain

### 3.1 Cascaded Shadow Maps (CSM) Configuration

CSM divides the view frustum into cascades, each with its own shadow map. Near cascades get higher resolution, far cascades get lower.

**Recommended cascade configuration for open world:**

| Preset | Cascades | Split Distances | Shadow Distance | Map Resolution | Use Case |
|--------|----------|-----------------|-----------------|----------------|----------|
| Ultra | 4 | 8m, 25m, 60m, 150m | 150m | 4096 | PC High-end |
| High | 4 | 6m, 20m, 50m, 120m | 120m | 2048 | PC Medium / Console |
| Medium | 3 | 8m, 30m, 80m | 80m | 2048 | Console budget |
| Low | 2 | 15m, 50m | 50m | 1024 | Mobile / Low-end |

**Split distance ratios (logarithmic):**
```
For N cascades with max distance D:
  split[i] = D * (near/far)^((N-i)/N) * lambda + D * i/N * (1-lambda)

Where lambda = 0.75 (blend between logarithmic and linear)
This is the "practical split scheme" used by most AAA games.
```

**Unity 6 URP configuration:**
- Set in URP Asset: Shadows > Cascade Count (1-4)
- Shadow Distance: Controls maximum shadow rendering distance
- Split ratios: Adjustable per cascade
- Depth Bias: 1.0-2.0 (prevent acne on terrain)
- Normal Bias: 0.5-1.5 (prevent acne on angled surfaces)

### 3.2 Shadow Bias Configuration

**Shadow acne vs peter-panning tradeoff:**

| Surface Type | Depth Bias | Normal Bias | Notes |
|-------------|-----------|-------------|-------|
| Flat terrain | 1.0 | 0.5 | Minimal bias needed |
| Steep slopes | 1.5 | 1.0 | More bias to prevent acne |
| Vegetation | 2.0 | 1.5 | Alpha-tested geometry needs more |
| Buildings | 1.0 | 0.75 | Standard |
| Characters | 0.5 | 0.5 | Tight bias for detail |

**Dark fantasy bias tuning:** Slightly higher normal bias (0.75-1.0 base) to prevent shadow acne on rough terrain, but not so high that shadows detach from casters. Terrain with displacement maps is particularly prone to acne.

### 3.3 Shadow Quality Settings

**Shadow softness comparison:**

| Method | Quality | Performance Cost | Best For |
|--------|---------|-----------------|----------|
| Hard | Low | Cheapest | Mobile, stylized games |
| PCF (2x2) | Medium | Low | Budget builds |
| PCF (5x5) | Good | Medium | Standard quality |
| PCSS | Excellent | High | Physically correct (soft near, sharp far) |
| VSM | Very Good | Medium-High | Large outdoor scenes |

**Unity 6 URP supports:** Soft Shadows (PCF-based), configurable in URP Asset under Shadows > Soft Shadows. PCSS is not natively supported in URP; requires custom renderer features or HDRP.

**For VeilBreakers:** Use PCF soft shadows at medium-high quality. The dark, moody aesthetic actually benefits from slightly harder shadows in key areas (dramatic contrast).

### 3.4 Contact Shadows

Contact shadows use screen-space ray marching to add small-scale shadow detail that cascaded shadows miss (grass blades, small rocks, character feet on ground).

**Implementation in Unity 6 URP:**
- Not built-in to URP (HDRP has it natively)
- Can be added as a custom renderer feature using screen-space ray marching
- Alternatively: use SSAO with aggressive settings to simulate contact darkening

**Parameters:**
- Ray length: 0.05-0.15 (world units)
- Step count: 8-16 steps
- Thickness: 0.01-0.05
- Fade distance: 20-50m (disable for distant objects)

---

## 4. Global Illumination for Terrain

### 4.1 Adaptive Probe Volumes (APV) -- Unity 6

APV is the recommended GI solution for Unity 6 URP. It replaces manual Light Probe Groups with automatically placed probes based on geometry density.

**How APV works:**
- Scene is divided into "bricks" -- 3D grid cells
- Each brick contains 64 probes in a 4x4x4 arrangement
- Brick size adapts: 1m spacing near dense geometry, up to 27m in open areas
- Per-pixel probe sampling (superior to per-object Light Probe Groups)
- Supports streaming for large open worlds

**APV configuration for open world terrain:**

| Setting | Value | Reason |
|---------|-------|--------|
| Min Brick Size | 1m | Detail in settlements/dungeons |
| Max Brick Size | 27m | Open terrain, performance |
| Dilation Iterations | 3 | Fill gaps in sparse areas |
| Virtual Offset | Enabled | Prevents light leaks through thin geometry |
| Sky Occlusion | Enabled | Runtime sky lighting updates |
| Scenario Blending | Enabled if needed | Day/night baked lighting swap |

**Terrain-specific considerations:**
- Terrain height variation creates natural valleys that need denser probes
- Forest canopy areas need probes both above and below tree line
- Cave entrances need transition probes (outdoor to indoor lighting)
- Place an Adaptive Probe Volume large enough to cover entire playable area
- Use multiple volumes with different densities for settlements vs wilderness

### 4.2 Screen-Space Global Illumination (SSGI)

SSGI provides real-time bounce lighting using screen-space data. It adds color bleeding from terrain materials to nearby objects.

**Unity 6 URP status:** SSGI is NOT natively available in URP. Options:
- HDRP has built-in SSGI
- Third-party solutions exist for URP
- APV baked GI + SSAO is the recommended URP approach

### 4.3 Baked vs Real-Time GI Tradeoffs

| Approach | Quality | Performance | Flexibility | Best For |
|----------|---------|-------------|-------------|----------|
| Fully Baked (APV) | Excellent | No runtime cost | Static only | Terrain, buildings |
| APV + Scenario Blending | Excellent | Low runtime cost | Day/night swap | Time-of-day |
| Real-time GI (Lumen) | Outstanding | High | Fully dynamic | Not available in Unity |
| APV + SSAO | Very Good | Low-Medium | Partially dynamic | VeilBreakers approach |

**Recommendation for VeilBreakers:** Use APV baked GI with 2-3 lighting scenarios (Day, Dusk, Night). Blend between scenarios as time progresses. Supplement with SSAO for real-time contact lighting.

### 4.4 Valley Bounce Lighting

Valleys naturally accumulate bounced light from surrounding terrain. Without GI, valleys appear uniformly dark which looks flat and unrealistic.

**Techniques to simulate valley bounce:**
1. **APV baked GI** handles this automatically when terrain is marked as GI contributor
2. **Ambient probes** with trilight mode: different ambient color for sky, equator, ground
3. **Terrain-colored ambient boost:** Sample terrain albedo at probe positions, tint ambient
4. **Fake bounce lights:** Place dim, wide-radius lights in valley floors

**Dark fantasy valley lighting:**
- Valleys should feel like light gets trapped and dies
- Use cold blue-green ambient rather than warm bounce
- Add fog to valleys to sell the effect
- Slight greenish tint in forest valleys (light filtering through canopy)

---

## 5. Post-Processing for Terrain Visuals

### 5.1 Color Grading for Dark Fantasy

**The dark fantasy color palette:**
- Desaturated by 20-40% from natural
- Cold-shifted (blue shadows, slightly warm highlights)
- High contrast ratio (deep blacks, controlled highlights)
- Muted midtones with punchy specular highlights

**Unity 6 URP Color Adjustments settings:**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Post Exposure | -0.3 to -0.5 | Overall darker image |
| Contrast | 15-25 | Enhanced contrast for drama |
| Color Filter | (0.92, 0.90, 0.95) | Slight cool tint |
| Hue Shift | 0 | Keep neutral |
| Saturation | -15 to -25 | Desaturated feel |

**Lift / Gamma / Gain (shadows/mids/highlights):**

| Channel | Lift (Shadows) | Gamma (Midtones) | Gain (Highlights) |
|---------|---------------|-------------------|-------------------|
| Red | -0.02 | 0.0 | +0.02 |
| Green | -0.01 | -0.01 | 0.0 |
| Blue | +0.05 | +0.02 | -0.01 |
| Master | -0.05 | -0.02 | +0.05 |

This creates: blue-ish shadows (cold, dead feel), neutral midtones, slightly warm highlights (fire, sun).

**Split toning:**
- Shadows: Hue 220 (blue), Saturation 15-20
- Highlights: Hue 35 (amber), Saturation 8-12
- Balance: -20 (bias toward shadow coloring)

### 5.2 Tone Mapping

**ACES Filmic (recommended for dark fantasy):**

ACES (Academy Color Encoding System) is the industry standard. Its Reference Rendering Transform (RRT) naturally:
- Desaturates extreme values (prevents neon-bright colors)
- Rolls off highlights smoothly (filmic, not clipped)
- Compresses shadows (detail preserved in darks)
- Has a slight S-curve (more contrast than neutral)

**Simplified ACES curve (Narkowicz approximation):**
```
float ACESFilm(float x) {
    float a = 2.51;
    float b = 0.03;
    float c = 2.43;
    float d = 0.59;
    float e = 0.14;
    return saturate((x * (a * x + b)) / (x * (c * x + d) + e));
}
```

**Unity 6 URP configuration:**
- Tonemapping override > Mode: ACES
- This is the recommended mode for dark fantasy

**Alternative: Neutral tone mapping** provides less contrast and more color accuracy, but lacks the filmic punch that suits dark fantasy.

### 5.3 Bloom

**Bloom for dark fantasy terrain:**
- Fire sources, sunlight on water, magical effects should bloom
- Environmental bloom should be subtle, not overblown

| Parameter | Value | Notes |
|-----------|-------|-------|
| Threshold | 1.0-1.2 | Only HDR-bright pixels bloom |
| Intensity | 0.15-0.3 | Subtle, not overwhelming |
| Scatter | 0.6-0.7 | Medium spread |
| Clamp | 65472 | Prevent firefly artifacts |
| High Quality Filtering | On (PC) / Off (mobile) | Quality toggle |
| Tint | (1.0, 0.95, 0.9) | Slight warm tint |

**Dark fantasy bloom rules:**
- Fire/torches: Allow strong bloom (intensity 0.3-0.5 in local volumes)
- Sunlight: Moderate bloom (0.2)
- Night: Very low bloom on moon/stars (0.1)
- Corrupted areas: Add slight purple bloom tint (0.9, 0.85, 1.0)

### 5.4 Ambient Occlusion

**SSAO in Unity 6 URP:**
URP has a built-in SSAO renderer feature.

| Parameter | Value | Notes |
|-----------|-------|-------|
| Intensity | 1.5-2.5 | Dark fantasy: heavier than default |
| Radius | 0.3-0.5 | Medium radius for terrain |
| Sample Count | Medium/High | 8-16 samples |
| Direct Lighting Strength | 0.3-0.5 | AO visible even in lit areas |
| Downsample | Half (console) / Full (PC) | Performance toggle |

**For terrain specifically:**
- SSAO darkens crevices, rock bases, tree roots
- Increase intensity in valley/forest areas via local volumes
- Use "After Opaque" rendering to affect terrain

### 5.5 Depth of Field

**Usage for VeilBreakers:**
- Primarily for cinematic camera/photo mode, not gameplay
- Gaussian DoF for performance, Bokeh DoF for quality

| Parameter | Gameplay | Cinematic |
|-----------|----------|-----------|
| Mode | Off | Bokeh |
| Focus Distance | -- | 10-30m |
| Aperture | -- | f/2.8-f/5.6 |
| Max Radius | -- | 4-6 |

---

## 6. Dark Fantasy Specific Techniques

### 6.1 The Soulsborne Lighting Formula

Analysis of FromSoftware's lighting across Dark Souls, Bloodborne, and Elden Ring reveals consistent patterns:

**Core principles:**
1. **Single dominant light source** -- Sun, moon, or fire. Rarely multiple competing directional lights.
2. **Deep, inky shadows** -- Shadows are near-black, not softly illuminated. Ambient light is very low.
3. **Warm light islands in cold darkness** -- Bonfires, torches create warm pools surrounded by cold ambient.
4. **Color contrast through temperature** -- Warm (fire) vs cold (moonlight/ambient) creates visual tension.
5. **Fog as narrative tool** -- Fog increases in dangerous/corrupted areas. Clear air = relative safety.
6. **Desaturated world, saturated effects** -- World colors are muted, but fire/magic/blood is vivid.

**Elden Ring specific:**
- Open world uses a subtle time-of-day system with 7-8 distinct lighting states
- Each major region has a unique ambient tint (Limgrave green, Caelid red, Liurnia blue)
- God rays in forests and ruins (volumetric light shafts)
- Distance fog heavily used to hide LOD transitions and create depth

**Bloodborne specific:**
- Permanently night-time (no day/night cycle in most areas)
- Orange sodium-vapor street lamp aesthetic
- Heavy use of fog at ground level
- Moon provides cold fill light, lamps provide warm key light
- Chromatic aberration and film grain for horror texture

### 6.2 Veil Corruption Visual Effects

For VeilBreakers' "Veil" corruption mechanic:

**Corruption atmosphere layers:**
```
Layer 1: Dark fog (ground level)
  Color: (0.15, 0.08, 0.20)  -- deep purple-black
  Density: scales with corruption_level (0.0 to 0.15)
  Height: 2-4m above ground
  Animation: slow drift, direction toward corruption source

Layer 2: Particle motes
  Color: (0.40, 0.15, 0.55)  -- purple emissive
  Count: corruption_level * 50 per 100m^2
  Size: 0.05-0.15m
  Behavior: float upward, fade, respawn
  Emission: 2-5 (visible in darkness)

Layer 3: Sky desaturation
  As corruption increases:
    sky_saturation = lerp(base_saturation, 0.1, corruption_level)
    sky_brightness = lerp(base_brightness, 0.3, corruption_level)
    ambient_color = lerp(base_ambient, (0.06, 0.03, 0.08), corruption_level)

Layer 4: Color grading shift
  Shadows shift toward purple: hue += 20 * corruption_level
  Saturation drops: sat -= 30 * corruption_level
  Post-exposure drops: exposure -= 0.5 * corruption_level
```

### 6.3 Torch/Fire Interior and Town Lighting

**Light falloff model for fire sources:**
```
Inverse-square falloff with warm color shift at distance:
  intensity(d) = base_intensity / (1 + d^2 / radius^2)
  color(d) = lerp(fire_color, ambient_color, smoothstep(radius*0.3, radius, d))
```

**Town lighting zones:**
- Streets: Torches every 8-12m, overlapping radii for continuous light
- Interiors: 1-3 light sources max (fireplace dominant, candles accent)
- Doorways: Warm light spilling outward (area light facing out)
- Windows: Faint warm glow from inside (low-intensity area lights)

**Performance rule:** Maximum 8-12 shadow-casting lights per screen. Non-shadow lights can be more numerous. Merge nearby lights under 2m apart.

### 6.4 Biome-Specific Lighting Moods

| Biome | Ambient Color | Fog Tint | Sun Tint | Mood |
|-------|--------------|----------|----------|------|
| dark_forest | (0.08, 0.10, 0.06) | (0.15, 0.18, 0.12) | Green filter | Claustrophobic, muted |
| corrupted_swamp | (0.06, 0.04, 0.08) | (0.20, 0.12, 0.25) | Purple | Toxic, alien |
| volcanic_wastes | (0.12, 0.05, 0.02) | (0.35, 0.15, 0.05) | Orange-red | Infernal, harsh |
| frozen_peaks | (0.10, 0.12, 0.15) | (0.60, 0.65, 0.75) | Cool white | Bleak, exposed |
| haunted_moor | (0.05, 0.05, 0.07) | (0.12, 0.10, 0.15) | Washed gray | Eerie, lonely |
| enchanted_glade | (0.06, 0.10, 0.08) | (0.20, 0.30, 0.22) | Emerald filter | Mystical, serene |
| bone_desert | (0.12, 0.10, 0.06) | (0.45, 0.40, 0.30) | Warm/harsh | Scorching, desolate |
| crystal_caverns | (0.05, 0.08, 0.12) | (0.15, 0.25, 0.40) | Blue glow | Otherworldly |
| blood_marsh | (0.08, 0.03, 0.03) | (0.25, 0.08, 0.08) | Red-tinted | Nightmarish, violent |
| ancient_ruins | (0.08, 0.07, 0.06) | (0.25, 0.22, 0.18) | Dust-filtered | Solemn, decayed |

---

## 7. Performance Considerations

### 7.1 Lighting Quality Presets

**Complete quality preset table for VeilBreakers:**

| Setting | Ultra | High | Medium | Low |
|---------|-------|------|--------|-----|
| Shadow Distance | 150m | 100m | 60m | 30m |
| Shadow Cascades | 4 | 4 | 3 | 2 |
| Shadow Resolution | 4096 | 2048 | 2048 | 1024 |
| Shadow Softness | PCF 5x5 | PCF 3x3 | PCF 2x2 | Hard |
| SSAO Samples | 16 | 12 | 8 | Off |
| SSAO Resolution | Full | Half | Half | Off |
| Bloom | HQ On | HQ On | HQ Off | HQ Off |
| Color Grading | HDR | HDR | LDR | LDR |
| Volumetric Fog | Full | Half | Off | Off |
| Height Fog | Analytical | Analytical | Analytical | Simplified |
| Light Probes | Per-pixel APV | Per-pixel APV | Per-object | Per-object |
| Max Realtime Lights | 32 | 16 | 8 | 4 |
| Max Shadow Lights | 8 | 4 | 2 | 1 |

### 7.2 Shadow Distance Scaling

**Dynamic shadow distance based on camera speed:**
```
When camera is stationary or moving slowly:
  shadow_distance = preset_max

When camera is moving fast (mounted travel, fast travel zoom):
  shadow_distance = preset_max * 0.5  (reduce during motion)

Transition speed: lerp over 1-2 seconds
```

This saves significant GPU time during traversal when the player isn't focusing on shadow detail.

### 7.3 Volumetric Fog Quality Settings

| Setting | Ultra | High | Medium | Low |
|---------|-------|------|--------|-----|
| Resolution | 1/2 screen | 1/4 screen | 1/8 screen | Off (use analytical) |
| Step Count | 64 | 32 | 16 | N/A |
| Temporal Reprojection | Yes | Yes | No | N/A |
| Max Distance | 200m | 100m | 50m | N/A |

### 7.4 Light Count Budgets

**Per-frame light budgets (from AAA standards):**

| Category | Budget | Notes |
|----------|--------|-------|
| Main directional (sun/moon) | 1 | Always shadow-casting |
| Shadow-casting point/spot | 4-8 | Most expensive lights |
| Non-shadow point/spot | 16-32 | Much cheaper without shadows |
| Baked lights (probes) | Unlimited | Pre-computed, free at runtime |
| Particle lights | 4-8 | Emissive particles as light |

**URP Forward+ rendering path:** Supports many more lights per screen than Forward (no per-object light limit, uses tile-based light culling). Recommended for VeilBreakers.

**Light culling strategy:**
- Shadow lights: Only within shadow distance
- Point/spot lights: Cull by range + screen coverage
- Tiny lights (candles): Convert to emissive materials beyond 15m
- Merge clusters of small lights into single larger light

---

## 8. Implementation Priorities for VeilBreakers Toolkit

### 8.1 What Exists (Current State)

| System | File | Status |
|--------|------|--------|
| Time-of-day presets (8) | `world_templates.py` | Has values but not physically based |
| Day/night cycle runtime | `world_templates.py` (RPG-10) | Lerp between presets, functional |
| Prop light integration | `light_integration.py` | 8 props, good foundation |
| Atmospheric volumes | `atmospheric_volumes.py` | 7 types, 10 biomes, placement logic |
| Dungeon lighting | `world_templates.py` (RPG-12) | Torch + fog, basic |
| Environment setup | `world_templates.py` (SCNE-05) | Skybox + basic GI trigger |
| Scene lights | `scene.py` | Add light, add camera, configure |

### 8.2 What Needs Enhancement

| Gap | Priority | Impact | Effort |
|-----|----------|--------|--------|
| Height fog system | HIGH | Transforms terrain depth perception | Medium |
| Biome-specific lighting moods | HIGH | Each area feels unique | Medium |
| Post-processing preset system | HIGH | Instant mood enhancement | Low |
| CSM configuration per quality | HIGH | Shadow quality/perf balance | Low |
| Color temperature curve for sun | MEDIUM | More realistic time progression | Low |
| APV setup automation | MEDIUM | Proper terrain GI | Medium |
| Atmospheric perspective (distance fog) | MEDIUM | Open world depth | Low |
| Corruption visual overlay | MEDIUM | Core game mechanic | Medium |
| Volumetric fog integration | LOW | AAA polish, needs third-party | High |
| Contact shadows | LOW | Detail enhancement | Medium |

### 8.3 Recommended Implementation Order

1. **Post-processing presets** -- Biggest visual bang for least effort. Set up Volume with Color Grading, Tonemapping (ACES), Bloom, SSAO.
2. **Height fog per biome** -- Add exponential height fog to atmospheric_volumes system.
3. **Biome lighting moods** -- Enhance time-of-day presets with biome-specific ambient/fog overrides.
4. **Shadow configuration** -- CSM cascade setup per quality preset in settings templates.
5. **Color temperature sun** -- Replace hardcoded sun colors with temperature-based curve.
6. **APV terrain setup** -- Automate Adaptive Probe Volume configuration for terrain scenes.
7. **Atmospheric perspective** -- Distance-based fog color shift in post-processing or shader.
8. **Corruption overlay** -- Layer veil corruption effects on top of base lighting.

---

## 9. Blender Viewport Preview Lighting

For the Blender side of the toolkit (procedural terrain generation + preview), matching the intended Unity look:

**Blender EEVEE settings for dark fantasy preview:**
```python
# World settings
world.use_nodes = True
bg_color = (0.02, 0.02, 0.04)  # Near-black with blue tint
world_strength = 0.3  # Low ambient

# Sun lamp (directional)
sun_color = (1.0, 0.82, 0.62)  # Morning default
sun_energy = 3.0
sun_angle = 0.02  # Soft shadows

# EEVEE settings
eevee.use_bloom = True
eevee.bloom_threshold = 0.8
eevee.bloom_intensity = 0.1
eevee.use_ssr = True  # Screen space reflections
eevee.use_volumetric_shadows = True
eevee.volumetric_tile_size = '4'  # Higher quality
eevee.shadow_cube_size = '1024'
eevee.shadow_cascade_size = '2048'
```

**Current toolkit status:** `scene.py` `handle_setup_world` already sets dark fantasy defaults (strength 0.3, dark background). Good foundation but doesn't configure EEVEE shadow/bloom settings.

---

## Sources

### PRIMARY (HIGH confidence)
- Unity 6 docs: Shadow Cascades configuration -- https://docs.unity3d.com/6000.3/Documentation/Manual/shadow-cascades-use.html
- Unity 6 docs: Adaptive Probe Volumes -- https://docs.unity3d.com/6000.3/Documentation/Manual/urp/probevolumes-concept.html
- Unity 6 docs: Post-processing in URP -- https://docs.unity3d.com/6000.3/Documentation/Manual/urp/integration-with-post-processing.html
- Unity 6 docs: Shadows in URP -- https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@14.0/manual/Shadows-in-URP.html
- NVIDIA GPU Gems 2 Ch.16: Accurate Atmospheric Scattering -- https://developer.nvidia.com/gpugems/gpugems2/part-ii-shading-lighting-and-shadows/chapter-16-accurate-atmospheric-scattering
- NVIDIA GPU Gems 3 Ch.13: Volumetric Light Scattering -- https://developer.nvidia.com/gpugems/gpugems3/part-ii-light-and-shadows/chapter-13-volumetric-light-scattering-post-process
- ACES Filmic Tone Mapping Curve (Narkowicz) -- https://knarkowicz.wordpress.com/2016/01/06/aces-filmic-tone-mapping-curve/
- Unity Blog: GI in Unity 6 -- https://unity.com/blog/engine-platform/new-ways-of-applying-global-illumination-in-unity-6
- Gamasutra: Atmospheric Scattering and Volumetric Fog -- https://www.gamedeveloper.com/programming/atmospheric-scattering-and-volumetric-fog-algorithm-part-1

### SECONDARY (MEDIUM confidence)
- 80 Level: Lighting Environments Tips (Soulsborne analysis) -- https://80.lv/articles/lighting-environments-tips-and-tricks
- 80 Level: Dark Fantasy Canyon in Unreal -- https://80.lv/articles/how-to-set-up-cinematic-dark-fantasy-canyon-in-unreal-engine
- Crimson Desert BlackSpace Engine atmospheric features -- https://crimsondesert.pearlabyss.com/en-us/News/Notice/Detail?_boardNo=40
- Unity URP Volumetric Light (open source) -- https://github.com/CristianQiu/Unity-URP-Volumetric-Light
- Unity SSAO forum discussion -- https://discussions.unity.com/t/ssao-with-urp-on-2022-3-lts/1554926

### TERTIARY (LOW confidence -- extrapolated from training data)
- Specific Elden Ring/Bloodborne internal values are reverse-engineered approximations, not official
- Color temperature to RGB conversion is a simplified approximation of Planck's curve
- Per-frame light budgets are industry guidelines, not hard limits

---

## Codebase Cross-Reference

Files that will need modification or new files needed:

| File | Change Needed |
|------|--------------|
| `world_templates.py` | Enhance `_WORLD_TIME_PRESETS` with color temperature curve, add post-processing preset generator, add CSM config generator |
| `atmospheric_volumes.py` | Add height fog system, atmospheric perspective, biome-specific fog density curves |
| `light_integration.py` | Expand light prop table, add corruption lighting overlay |
| `settings_templates.py` | Add `generate_graphics_settings_script` enhancement for shadow/fog quality presets |
| `scene.py` | Add EEVEE bloom/shadow configuration for Blender preview |
| NEW: `post_processing_presets.py` | Unity post-processing Volume setup (Color Grading, Bloom, SSAO, TonemapACES) |
| NEW: `terrain_lighting_moods.py` | Per-biome lighting mood definitions with time-of-day interaction |
