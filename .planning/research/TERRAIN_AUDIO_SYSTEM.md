# Terrain Audio System Research

**Domain:** Terrain-based audio for dark fantasy action RPG
**Project:** VeilBreakers (procedural Blender terrain -> Unity 6 URP)
**Researched:** 2026-04-03
**Overall confidence:** HIGH (established patterns, well-documented domain)

---

## 1. Footstep Audio by Surface Type

### How AAA Games Map Terrain Materials to Footstep Sounds

The industry-standard approach uses a **three-layer detection system**:

1. **Terrain splatmap sampling** -- for Unity Terrain objects, read `TerrainData.GetAlphamaps()` at the player's world position to get per-texture blend weights (0.0-1.0 per layer).
2. **Physics Material matching** -- for non-terrain meshes (buildings, props), detect surface via `PhysicMaterial` name on the collider hit by a downward raycast.
3. **Tag/Layer fallback** -- if neither splatmap nor PhysicMaterial exists, fall back to GameObject tag or layer.

This is exactly what Assassin's Creed, Horizon Zero Dawn, and other AAA titles use: a raycast from player feet downward, then a lookup chain to determine surface type.

**Confidence:** HIGH -- verified via multiple implementation tutorials and AAA post-mortems.

### Surface Types for VeilBreakers

Based on the dark fantasy biome set (forest, swamp, mountain, cave, castle, corruption zone):

| Surface ID | Material Name | Biomes Where Used |
|------------|--------------|-------------------|
| 0 | grass | Forest, mountain meadow, town outskirts |
| 1 | dirt | Paths, forest floor, farmland |
| 2 | stone | Castle, ruins, mountain rock, cave |
| 3 | wood | Building interiors, bridges, docks |
| 4 | mud | Swamp, rain-soaked paths |
| 5 | water_shallow | Stream crossings, puddles, swamp |
| 6 | water_deep | Rivers, lakes (swimming) |
| 7 | sand | Riverbanks, desert edges |
| 8 | snow | Mountain peaks, winter zones |
| 9 | gravel | Roads, castle courtyards |
| 10 | metal | Forge, dungeon grates, chains |
| 11 | leaves | Dense forest floor, autumn zones |
| 12 | carpet | Castle interiors, noble rooms |
| 13 | corruption | Corruption zones (squelching, crystalline crunch) |

### Tagging Terrain with Audio Surface IDs

**For Unity Terrain (splatmap-based):**
The terrain splatmap already encodes which texture layers are painted where. Map each terrain layer index to a surface type:

```
Terrain Layer 0 -> "grass" (surface ID 0)
Terrain Layer 1 -> "dirt" (surface ID 1)
Terrain Layer 2 -> "stone" (surface ID 2)
...
```

Use `TerrainData.GetAlphamaps(x, z, 1, 1)` to sample the blend weights at any world position. The conversion from world position to alphamap coordinates:

```csharp
Vector3 relPos = worldPos - terrain.transform.position;
int mapX = (int)(relPos.x / terrain.terrainData.size.x * terrain.terrainData.alphamapWidth);
int mapZ = (int)(relPos.z / terrain.terrainData.size.z * terrain.terrainData.alphamapHeight);
float[,,] alphas = terrain.terrainData.GetAlphamaps(mapX, mapZ, 1, 1);
```

Each `alphas[0, 0, layerIndex]` returns a 0-1 blend weight. This enables **blended footstep audio** where standing on 60% grass + 40% dirt plays both sounds at proportional volumes.

**For non-terrain meshes (buildings, props):**
Use PhysicMaterial names matching surface types. The existing VB toolkit FootstepManager already does this via `hit.collider.sharedMaterial.name` matching.

**For Blender-exported meshes:**
Attach a `SurfaceType` MonoBehaviour component (or use custom FBX properties) to tag exported meshes with their audio surface ID during import.

### Footstep Variation Count

**Industry standard: 4-8 variations per foot per surface per movement type.**

From the Assassin's Creed post-mortem: 22 surface materials x 14 step intentions (walk, run, sneak, jump, land, pivot, etc.) x 3-8 variations each = 1,500+ total samples.

For VeilBreakers, a practical budget:

| Movement Type | Variations Per Surface | Notes |
|--------------|----------------------|-------|
| Walk | 6 per foot (L/R) | 12 total per surface |
| Run | 6 per foot | 12 total per surface |
| Sneak | 4 per foot | 8 total, quieter |
| Land (jump) | 3 | Impact sound |
| Slide/dodge | 2 | Scraping sound |

With 14 surfaces: 14 x (12+12+8+3+2) = **518 samples minimum**. This is achievable with a sound library like Krotos Ultimate Footsteps (8,000+ samples) or Sonniss GDC bundles (free).

### Movement Speed and Armor Weight

**Speed variation:** Control `footstepInterval` based on character velocity:
- Walk: 0.45s interval
- Run: 0.28s interval  
- Sprint: 0.22s interval
- Sneak: 0.65s interval

**Armor weight:** Apply volume and pitch modifiers:
- Light armor: volume x0.7, pitch x1.05 (softer, slightly higher)
- Medium armor: volume x1.0, pitch x1.0 (baseline)
- Heavy armor: volume x1.3, pitch x0.9 (louder, deeper), add metallic jingle overlay

This maps cleanly to the VB equipment system -- armor type is already tracked.

### Existing Toolkit Coverage

The VB toolkit (`audio_templates.py`) already has `VeilBreakers_FootstepManager` with:
- ScriptableObject sound bank per surface
- Raycast-based PhysicMaterial detection
- Pitch randomization (0.9-1.1)
- Cooldown timer

**Gap: No terrain splatmap detection.** The current system only checks `hit.collider.sharedMaterial`, which does not work on Unity Terrain objects. A splatmap sampling path must be added alongside the existing PhysicMaterial path.

**Gap: No movement type variation.** Current system uses a single `footstepInterval` with no walk/run/sneak distinction.

**Gap: No armor weight modifier.** No volume/pitch scaling by equipment.

---

## 2. Ambient Environmental Audio

### Per-Biome Ambient Sound Design

Each biome needs a **layered ambient soundscape** with 3-5 simultaneous audio layers that blend based on distance, time-of-day, and weather state.

#### Forest
| Layer | Sound | Volume | Loop | Notes |
|-------|-------|--------|------|-------|
| Base | Wind through leaves (gentle rustle) | 0.6 | Yes | Constant bed |
| Life | Bird calls (varied species) | 0.3 | Yes (randomized one-shots) | Daytime only, suppress at night |
| Life | Insect buzz/chirp | 0.2 | Yes | Increases at dusk/dawn |
| Detail | Distant animal (wolf howl, deer) | 0.15 | One-shot (random interval 30-90s) | Nighttime heavier |
| Weather | Wind gusts | 0.0-0.5 | Triggered | Intensity from weather system |

#### Swamp
| Layer | Sound | Volume | Notes |
|-------|-------|--------|-------|
| Base | Bubbling water, slow current | 0.5 | Constant |
| Life | Frog croaking chorus | 0.4 | Night-heavy, random timing |
| Life | Insect drone (mosquitoes, flies) | 0.35 | Constant, slightly nauseating buzz |
| Detail | Squelching, gas bubbles | 0.2 | Random one-shots |
| Dark | Low ominous hum | 0.15 | Adds unease, VeilBreakers flavor |

#### Mountain
| Layer | Sound | Volume | Notes |
|-------|-------|--------|-------|
| Base | Howling wind (constant, strong) | 0.7 | Louder than other biomes |
| Life | Distant eagle cry | 0.2 | Rare one-shot |
| Detail | Rock crumbling, small slides | 0.15 | Random one-shots |
| Acoustic | Echo/reverb tail | N/A | Applied via reverb zone, not a separate layer |

#### Cave
| Layer | Sound | Volume | Notes |
|-------|-------|--------|-------|
| Base | Dripping water (irregular rhythm) | 0.5 | Constant, slightly echoed |
| Acoustic | Resonant hum | 0.2 | Low frequency bed |
| Detail | Distant rumble | 0.15 | Random, suggests deep underground |
| Life | Bat wing flutter | 0.1 | Rare, startling |

#### Castle / Stone Interior
| Layer | Sound | Volume | Notes |
|-------|-------|--------|-------|
| Base | Wind through corridors | 0.4 | Muffled, directional |
| Detail | Creaking wood (doors, beams) | 0.2 | Random |
| Detail | Distant voices (murmuring) | 0.15 | Inhabited areas only |
| Detail | Chain clinks, metal | 0.1 | Dungeon areas |

#### Corruption Zone (VeilBreakers-specific)
| Layer | Sound | Volume | Notes |
|-------|-------|--------|-------|
| Base | Low-frequency hum (sinister drone) | 0.6 | Constant, unsettling |
| Dark | Distorted whispers (reversed, pitched down) | 0.35 | Random timing, spatial |
| Detail | Crackling energy (like static discharge) | 0.25 | Random bursts |
| Effect | Heartbeat pulse | 0.2 | Increases as corruption exposure rises |

### Audio Zone Shapes

**Use trigger colliders, not custom shapes:**
- **Box colliders:** Rooms, buildings, corridors. Most common.
- **Sphere colliders:** Point sources (campfires, wells, shrines). Good for radial falloff.
- **Capsule colliders:** Corridors, tunnels (stretched sphere).
- **Spline-based (mesh collider from spline):** Rivers, roads, cliff edges. Generate a mesh collider from a Bezier spline with width, extrude to a volume.

For VeilBreakers, the compose_map pipeline already generates spline-based roads and rivers. These splines should also define audio zone volumes.

### Crossfade Between Zones

**Distance-based blend, never hard cut.** Implementation:

1. Each audio zone has an outer boundary (full blend-out) and inner boundary (full blend-in).
2. When the player enters the outer boundary, begin fading in the new zone's ambience.
3. When the player exits the old zone's outer boundary, fade it out completely.
4. Blend time: 2-4 seconds for small zones, 5-8 seconds for biome transitions.

Use `OnTriggerEnter`/`OnTriggerExit` with a `Mathf.SmoothDamp` volume curve. The existing VB `audio_zone_script` creates reverb zones but does not handle ambient sound crossfading -- this needs to be added as a companion system.

### Time-of-Day Audio Variation

Control via the existing VB day/night cycle system:

| Time | Audio Adjustments |
|------|-------------------|
| Dawn (5:00-7:00) | Bird chorus ramp up, insect fade, wolf howl fade |
| Day (7:00-17:00) | Full bird activity, wind base, no nocturnal sounds |
| Dusk (17:00-19:00) | Bird fade, insect ramp up, owl calls begin |
| Night (19:00-5:00) | Nocturnal animals (owl, wolf, cricket), no birds, lower wind |

Implementation: expose a `timeOfDay` float (0-24) parameter on ambient emitters. Each layer has min/max active hours and a fade duration.

---

## 3. Weather Audio

### Rain Progression System

Use a single continuous parameter `rainIntensity` (0.0-1.0) that drives all rain audio:

| Range | State | Audio Characteristics |
|-------|-------|----------------------|
| 0.0 | Clear | No rain audio |
| 0.0-0.2 | Light drizzle | Gentle pattering, widely spaced drops |
| 0.2-0.5 | Moderate rain | Steady patter, some heavier drops |
| 0.5-0.8 | Heavy rain | Dense curtain of sound, splashing |
| 0.8-1.0 | Thunderstorm | Roaring rain, thunder cracks, wind gusts |

**Implementation approach:** Use 3-4 looping rain layers with volume curves mapped to `rainIntensity`:
- Layer 1 (drizzle): peaks at 0.2, fades by 0.5
- Layer 2 (moderate): ramps 0.2-0.5, peaks at 0.6
- Layer 3 (heavy): ramps 0.4-0.8, stays to 1.0
- Layer 4 (storm bed): only above 0.7

### Rain on Different Surfaces

Place additional "rain surface" emitters on geometry:

| Surface | Rain Sound Character | Volume Modifier |
|---------|---------------------|-----------------|
| Stone | Sharp splashing, puddle forming | 1.0x |
| Grass | Soft muffled pattering | 0.6x |
| Metal | Pinging, tinkling | 0.8x (distinct timbre) |
| Wood | Dull thudding | 0.7x |
| Water | Distinctive splashing (additive to water sound) | 0.9x |

Implementation: attach `RainSurfaceEmitter` components to large surfaces. When rain is active, they play surface-specific rain loops at volumes proportional to `rainIntensity`.

### Wind System

**Two-component model:**
1. **Base wind:** Constant looping audio with volume/pitch driven by `windSpeed` parameter (0.0-1.0)
2. **Wind gusts:** Random one-shot bursts with:
   - Random interval: 5-20 seconds
   - Random intensity spike: 1.5-3x base wind volume
   - Duration: 2-5 seconds with attack/release envelope
   - Directional panning (randomized L/R)

**Terrain interaction:**
- Canyon/narrow passage: Apply bandpass filter to simulate whistling. Trigger when player enters narrow corridor zones.
- Forest: Layer in leaf rustling that scales with `windSpeed`.
- Open field: Full-spectrum wind, no filtering.
- Interior: Heavy low-pass filter, reduced volume (wind heard through walls).

### Thunder

- Delay after lightning flash: `distance_km * 3.0` seconds (speed of sound approximation)
- Volume falloff: inverse square with distance
- Reverb: more reverb in open terrain, less in forest (trees absorb)
- Random interval: 15-60 seconds during thunderstorm state
- Bass rumble: closer thunder has more low-frequency content

### Snow Audio

- **Ambient:** Muffled world audio (apply global low-pass filter during snow)
- **Footsteps:** Crunching/squeaking underfoot (separate surface type, already in surface list)
- **Wind:** Softer, more hollow wind loops

---

## 4. Water Audio

### River Audio System

**Spline-based emitter placement.** Rivers in VeilBreakers are generated from splines in Blender. Export the spline control points and place audio emitters along the river path at regular intervals (every 5-10 meters).

| Flow Speed | Sound Character | Example |
|------------|----------------|---------|
| 0.0-0.3 (slow) | Gentle stream, babbling brook | Forest creek |
| 0.3-0.6 (moderate) | Steady flow, some splashing on rocks | River |
| 0.6-0.8 (fast) | Rushing rapids, white noise component | Mountain rapids |
| 0.8-1.0 (very fast) | Roaring torrent | Near waterfall |

**Implementation:** Each river segment has a `flowSpeed` property (set in Blender, exported as metadata). Place `RiverAudioEmitter` at spline intervals. Each emitter crossfades between 3 distance layers:
- Close (0-5m): detailed water sound with individual splashes
- Mid (5-20m): steady flow bed
- Far (20-50m): low rumble/white noise

### Waterfall Audio

Two-source model:
1. **Top source:** Constant flow sound, positioned at waterfall crest
2. **Bottom source:** Impact/splash sound, positioned at base pool
3. **Spray zone:** Misty ambient in a sphere around the base, separate AudioSource with low volume

Distance curve: logarithmic rolloff starting loud, audible from 50-80m. Waterfall is a landmark sound -- players should hear it before seeing it.

### Lake/Pond Audio

- Shoreline emitters placed along water edge (from Blender water body boundary)
- Gentle lapping sound, very quiet (volume 0.2-0.3)
- Wind-reactive: lapping increases with `windSpeed`

### Underwater Audio

When player submerges (water_deep surface detected or camera below water plane):
- Apply heavy low-pass filter (cutoff ~400Hz) to all world audio
- Add pressure hum loop
- Muffle footstep system (no footsteps underwater)
- Add bubble sounds on player movement

---

## 5. Blender-Side Audio Metadata

### What Data Blender Should Export

The Blender compose_map pipeline already generates terrain, water bodies, roads, and locations. Audio metadata should be exported as a **sidecar JSON file** alongside the FBX, not embedded in FBX custom properties (which have poor cross-engine support).

**Rationale for JSON sidecar over FBX custom properties:**
FBX custom property support is inconsistent -- Blender can write them, but Unity's FBX importer does not reliably read them. A JSON sidecar is engine-agnostic, human-readable, and trivially parsed in C#.

### Audio Metadata Schema

```json
{
  "version": "1.0",
  "terrain": {
    "splatmap_surface_mapping": [
      { "layer_index": 0, "surface_type": "grass", "surface_id": 0 },
      { "layer_index": 1, "surface_type": "dirt", "surface_id": 1 },
      { "layer_index": 2, "surface_type": "stone", "surface_id": 2 },
      { "layer_index": 3, "surface_type": "mud", "surface_id": 4 }
    ]
  },
  "audio_zones": [
    {
      "name": "ForestAmbient_01",
      "type": "forest",
      "shape": "box",
      "position": [120.0, 5.0, 80.0],
      "size": [60.0, 20.0, 60.0],
      "rotation": [0, 0, 0],
      "parameters": {
        "density": 0.8,
        "time_variant": true
      }
    },
    {
      "name": "CaveEntrance_01",
      "type": "cave",
      "shape": "sphere",
      "position": [200.0, 10.0, 150.0],
      "radius": 15.0,
      "parameters": {
        "reverb_preset": "cave",
        "drip_intensity": 0.6
      }
    }
  ],
  "water_bodies": [
    {
      "name": "River_Main",
      "type": "river",
      "spline_points": [
        { "position": [10, 0, 50], "flow_speed": 0.3, "width": 4.0, "depth": 1.2 },
        { "position": [30, -2, 80], "flow_speed": 0.5, "width": 6.0, "depth": 2.0 },
        { "position": [50, -5, 110], "flow_speed": 0.8, "width": 8.0, "depth": 3.0 }
      ],
      "has_waterfall": true,
      "waterfall_position": [50, -5, 110],
      "waterfall_height": 12.0
    },
    {
      "name": "Lake_01",
      "type": "lake",
      "boundary_points": [[100, 0, 200], [120, 0, 220], [140, 0, 200]],
      "depth": 5.0,
      "surface_area": 1200.0
    }
  ],
  "reverb_zones": [
    {
      "name": "CaveInterior_01",
      "preset": "cave",
      "position": [200, 8, 150],
      "min_distance": 5.0,
      "max_distance": 30.0
    }
  ]
}
```

### Integration with Existing Pipeline

The `compose_map` action in `asset_pipeline` already generates terrain, water, roads, and locations. The audio metadata JSON should be:

1. **Generated automatically** during `compose_map` -- each water body, biome zone, and building already has position/type data.
2. **Exported alongside FBX** as `{map_name}_audio_metadata.json`.
3. **Consumed by Unity importer** that reads the JSON and auto-places audio zone GameObjects, reverb zones, river audio emitters, etc.

This is a clean extension point: the Blender side already knows terrain types, water flow, and building locations. It just needs to serialize that knowledge for audio.

---

## 6. Unity Implementation

### Audio Middleware Recommendation: FMOD

**Use FMOD, not Wwise or Unity built-in.** Rationale:

| Criterion | FMOD | Wwise | Unity Built-in |
|-----------|------|-------|----------------|
| Indie licensing | Free under $500K budget | Complex tier pricing | Free (included) |
| Learning curve | Moderate, intuitive UI | Steep, enterprise-oriented | Low but limited |
| Unity integration | Excellent, first-class | Good but heavier | Native |
| Labeled parameters | Yes (surface types, weather) | Yes (switches/states) | No equivalent |
| Spatial audio | Good with Resonance plugin | Excellent (built-in propagation) | Requires Steam Audio |
| Community resources | Strong, many Unity tutorials | Smaller indie community | Abundant but basic |
| Used by | Hollow Knight, Celeste, Fortnite | Assassin's Creed, Halo | Casual/mobile games |

**Why not Wwise:** Overkill for a 1-2 person team. Licensing is more complex. The structured container-based workflow is designed for dedicated audio teams at large studios.

**Why not Unity built-in:** Lacks labeled parameters (critical for surface type switching), lacks event-based architecture, no built-in audio LOD, limited dynamic mixing capabilities.

**However:** The existing VB toolkit generates C# scripts using Unity's built-in AudioSource/AudioMixer APIs. Adding FMOD as an optional layer on top (rather than replacing the existing system) is the pragmatic path. The footstep manager, audio zones, and ambient systems should work with both Unity native and FMOD via an abstraction interface.

### Unity Audio Mixer Group Hierarchy

```
Master
  |-- Music
  |     |-- Exploration
  |     |-- Combat
  |     |-- Boss
  |     |-- Ambient Music
  |
  |-- SFX
  |     |-- Footsteps
  |     |-- Combat SFX (weapons, impacts)
  |     |-- UI SFX
  |     |-- Foley (clothing, equipment)
  |
  |-- Environment
  |     |-- Ambience (biome loops)
  |     |-- Weather (rain, wind, thunder)
  |     |-- Water (rivers, waterfalls, lakes)
  |     |-- Reverb Send
  |
  |-- Voice
  |     |-- Dialogue
  |     |-- Barks (combat shouts)
  |     |-- Narration
```

**Ducking rules:**
- Dialogue ducks Music by -6dB and Environment by -3dB
- Combat SFX ducks Exploration Music by -4dB
- Boss Music ducks Ambience by -6dB

The existing VB toolkit `setup_audio_mixer` action already generates a mixer with groups. It needs the Environment sub-groups (Weather, Water) added.

### Audio Occlusion

**Raycast-based occlusion** (already implemented in VB toolkit AUDM-01):
- Cast rays from listener to each audio source
- Each wall hit reduces volume by `occlusionFactorPerHit` (default 0.35)
- Apply low-pass filter proportional to total occlusion

The existing `generate_spatial_audio_script` in `audio_middleware_templates.py` already implements this with configurable occlusion layers, factor per hit, and low-pass filter. This is production-ready.

### Reverb Zones

The VB toolkit already generates reverb zones for cave, outdoor, indoor, dungeon, and forest presets. Gaps to address:

- **Missing presets:** castle corridor, corruption zone, underwater
- **No nested zone blending:** When player is in overlapping reverb zones, Unity blends by priority. Need to set priority values correctly.
- **No dynamic reverb:** Reverb should change based on room size detection (small room vs large hall). This can be approximated by placing different reverb zones.

### Audio LOD

The VB toolkit AUDM-06 (`setup_audio_lod`) already implements distance-based quality tiers. The three-tier model:

| Tier | Distance | Behavior |
|------|----------|----------|
| High | 0-15m | Full quality, all variations, spatial processing |
| Medium | 15-40m | Reduced variations, simplified spatial |
| Low | 40m+ | Mono, no effects, volume-only falloff |
| Culled | 60m+ | Not playing at all |

---

## 7. Implementation Priorities for VeilBreakers

### Phase 1: Foundation (must-have before any audio work)
1. Add terrain splatmap detection to FootstepManager (alongside existing PhysicMaterial path)
2. Expand surface list from 5 to 14 types
3. Add movement speed variation (walk/run/sneak intervals)
4. Define JSON sidecar schema for audio metadata export from Blender

### Phase 2: Ambient System
1. Ambient zone manager with crossfading
2. Per-biome ambient layer definitions (forest, swamp, mountain, cave, castle, corruption)
3. Time-of-day parameter integration
4. Spline-based audio zones for rivers/roads

### Phase 3: Weather Audio
1. Rain intensity parameter system with layered loops
2. Wind base + gust model
3. Rain-on-surface emitters
4. Thunder with distance-based delay

### Phase 4: Water Audio
1. River spline audio emitter placement (from Blender metadata)
2. Waterfall two-source model
3. Lake shoreline emitters
4. Underwater audio filter system

### Phase 5: Polish
1. Armor weight footstep modifiers
2. Audio LOD tuning
3. FMOD integration layer (optional, for teams wanting middleware)
4. Dynamic reverb for procedurally generated interiors

---

## 8. Pitfalls and Warnings

### Critical: Terrain vs Mesh Detection
The biggest gotcha in Unity terrain audio is that `Physics.Raycast` against a Terrain collider returns a `TerrainCollider`, which has NO `sharedMaterial` (PhysicMaterial). The footstep system MUST check `hit.collider is TerrainCollider` first and branch to splatmap sampling. Mixing these two paths incorrectly causes silent footsteps on terrain.

### Critical: Audio Source Limits
Unity has a default limit of 32 simultaneous AudioSources. Ambient zones with 5 layers each, plus footsteps, weather, water, and combat audio can easily exceed this. The VB audio pool manager (AUD-09) addresses this, but it must be configured with appropriate priority: Footsteps > Combat > Dialogue > Ambient > Weather > Water (distant).

### Moderate: Splatmap Resolution Mismatch
The alphamap resolution might not match the terrain heightmap resolution. Always use `terrainData.alphamapWidth/Height` for coordinate conversion, never `terrainData.heightmapResolution`.

### Moderate: One-Shot Spam
Playing `AudioSource.PlayOneShot()` per footstep per blended surface can stack up (e.g., 4 blended textures = 4 simultaneous one-shots per step). Set a minimum blend threshold (e.g., only play surface sounds for textures with >0.15 blend weight) and cap at 2 simultaneous surface blends.

### Minor: Audio Memory Budget
518+ footstep samples at 16-bit 44.1kHz mono, ~0.5-1.0 seconds each = roughly 20-40MB uncompressed. Use Vorbis compression in Unity (quality 70%) to reduce to ~4-8MB. Load common surfaces (grass, stone, dirt) at startup; lazy-load rare surfaces (corruption, carpet, metal).

---

## Sources

### Implementation Tutorials
- [Implementing Footsteps with FMOD in Unity -- Alessandro Fama](https://alessandrofama.com/tutorials/fmod/unity/footsteps) -- FMOD event setup, labeled parameters, C# raycast detection
- [Terrain Footsteps in Unity -- John Leonard French](https://johnleonardfrench.music/terrain-footsteps-in-unity-how-to-detect-different-textures/) -- Splatmap sampling, GetAlphamaps API, blend-based audio
- [Multi-surface footsteps script (Viking Village)](https://gist.github.com/WickedJumper/bd44ed1c67080ecc3b98073b75a25bbd) -- Complete working Unity script

### Audio Middleware
- [Wwise or FMOD Guide -- The Game Audio Co](https://www.thegameaudioco.com/wwise-or-fmod-a-guide-to-choosing-the-right-audio-tool-for-every-game-developer) -- Comprehensive comparison
- [FMOD Unity Tutorial 2025](https://generalistprogrammer.com/tutorials/fmod-unity-complete-game-audio-integration-tutorial) -- Current FMOD-Unity integration guide
- [FMOD vs Wwise -- Slant](https://www.slant.co/versus/5973/5974/~fmod-studio_vs_wwise) -- Community comparison

### Environmental Audio
- [GDC 2025: Creating Believable Worlds with Ambience](https://schedule.gdconf.com/session/audio-summit-creating-believable-worlds-with-ambience/908517) -- Malin Blondal (Avatar, Star Wars Outlaws)
- [GDC 2024: Dial Up the Diegetics: Sounds of Nature](https://www.gamedeveloper.com/audio/gdc-2024-dial-up-the-diegetics-sounds-of-nature) -- Nature sound design
- [Procedural River Sound (Fab)](https://www.fab.com/listings/aa57cc4d-23d6-4906-97e4-65f5b5de6ad2) -- Spline-based river audio

### Unity Audio
- [Unity Audio Mixer Manual](https://docs.unity3d.com/6000.3/Documentation/Manual/AudioMixer.html) -- Official mixer docs
- [Unity Reverb Zones Manual](https://docs.unity3d.com/Manual/class-AudioReverbZone.html) -- Official reverb zone docs
- [Steam Audio Unity Guide](https://valvesoftware.github.io/steam-audio/doc/unity/guide.html) -- Spatial audio with occlusion
- [Shaped Audio Reverb Zones (GitHub)](https://github.com/naelstrof/ShapedAudioReverbZones) -- Non-spherical reverb zones

### Weather Audio
- [Creating Dynamic Weather Systems in Unity](https://devsourcehub.com/creating-dynamic-weather-systems-in-unity-enhancing-game-immersion/) -- Weather audio implementation
- [Weather Control in ADX](https://blog.criware.com/index.php/2025/11/27/weather-control-in-adx/) -- Parameter-driven weather audio

### Industry Standards
- [Footsteps: Informal Game Sound Study](http://blog.lostchocolatelab.com/2010/03/footsteps-informal-game-sound-study.html) -- Assassin's Creed 1,500+ samples analysis
- [Krotos Ultimate Footsteps Library](https://www.krotosaudio.com/products/ultimate-footsteps-sound-effects-library/) -- 8,000+ AAA footstep samples
- [Sonniss GDC 2024 Audio Bundle](https://gdc.sonniss.com/gdc-2024-game-audio-bundle/) -- Free 27.5GB game audio library

### Blender Export
- [FBX Custom Properties -- Blender Projects](https://projects.blender.org/blender/blender-addons/issues/104677) -- FBX custom property limitations
- [FBX Asset Metadata Pipeline -- Unreal](https://docs.unrealengine.com/4.27/en-US/WorkingWithContent/Importing/FBX/AssetMetadataPipeline) -- Engine-side metadata import
