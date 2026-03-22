# T2 Handler Registrations

New handlers and action literals created by Terminal 2 that need integration
into `handlers/__init__.py` and `blender_server.py` by Terminal 4.

## New entries for COMMAND_HANDLERS in handlers/__init__.py

### Spell-Cast Handlers (animation_spellcast.py)
```python
from .animation_spellcast import generate_channel_keyframes
from .animation_spellcast import generate_release_keyframes
from .animation_spellcast import generate_sustain_keyframes
from .animation_spellcast import validate_spellcast_params
from .animation_spellcast import get_spellcast_timing
```

### Combat Command Handlers (animation_combat.py)
```python
from .animation_combat import generate_combat_command_keyframes
from .animation_combat import validate_combat_command_params
from .animation_combat import generate_command_receive_keyframes
from .animation_combat import generate_combat_idle_keyframes
from .animation_combat import generate_approach_keyframes
from .animation_combat import generate_return_to_formation_keyframes
from .animation_combat import generate_guard_keyframes
from .animation_combat import generate_flee_keyframes
from .animation_combat import generate_target_switch_keyframes
from .animation_combat import generate_synergy_activation_keyframes
from .animation_combat import generate_ultimate_windup_keyframes
from .animation_combat import generate_victory_pose_keyframes
from .animation_combat import generate_defeat_collapse_keyframes
```

### Hover System Handlers (animation_hover.py)
```python
from .animation_hover import generate_hover_keyframes
from .animation_hover import validate_hover_params
from .animation_hover import generate_hover_idle_keyframes
from .animation_hover import generate_hover_move_keyframes
from .animation_hover import generate_wing_flap_keyframes
from .animation_hover import generate_tentacle_float_keyframes
```

### Amorphous Creature Handlers (animation_blob.py)
```python
from .animation_blob import generate_blob_keyframes
from .animation_blob import validate_blob_params
from .animation_blob import generate_blob_locomotion_keyframes
from .animation_blob import generate_pseudopod_reach_keyframes
from .animation_blob import generate_blob_idle_keyframes
from .animation_blob import generate_blob_attack_keyframes
from .animation_blob import generate_blob_split_keyframes
```

### IK Foot Placement (animation_ik.py)
```python
from .animation_ik import validate_ik_foot_params
from .animation_ik import compute_foot_correction
from .animation_ik import compute_hip_correction
from .animation_ik import generate_ik_corrected_keyframes
from .animation_ik import smooth_corrections
```

## New action Literals for blender_server.py blender_animation tool

```python
# Spell-cast actions
"generate_channel" | "generate_release" | "generate_sustain"

# Combat command actions
"generate_command_receive" | "generate_combat_idle" | "generate_approach" |
"generate_return_to_formation" | "generate_guard" | "generate_flee" |
"generate_target_switch" | "generate_synergy_activation" |
"generate_ultimate_windup" | "generate_victory_pose" | "generate_defeat_collapse"

# Hover system actions
"generate_hover_idle" | "generate_hover_move" | "generate_wing_flap" |
"generate_tentacle_float"

# Amorphous creature actions
"generate_blob_locomotion" | "generate_pseudopod_reach" | "generate_blob_idle" |
"generate_blob_attack" | "generate_blob_split"

# IK foot placement actions
"apply_ik_foot_placement"
```

### Brand Ability Handlers (animation_abilities.py)
```python
from .animation_abilities import generate_ability_keyframes
from .animation_abilities import validate_ability_params
from .animation_abilities import generate_brand_basic_attack
from .animation_abilities import generate_brand_defend
from .animation_abilities import generate_brand_skill
from .animation_abilities import generate_brand_ultimate
from .animation_abilities import generate_status_effect_keyframes
from .animation_abilities import generate_combo_keyframes
from .animation_abilities import generate_creature_combat_idle
from .animation_abilities import validate_status_effect_params
```

## New action Literals for blender_animation (abilities)

```python
# Brand ability slot actions
"generate_brand_attack" | "generate_brand_defend" | "generate_brand_skill" | "generate_brand_ultimate"

# Status effects
"generate_status_effect"

# Combo system
"generate_combo"

# Creature-type combat idle
"generate_creature_idle"
```

## New speed literals for blender_animation walk/run

VALID_SPEEDS now includes: `"walk"` | `"run"` | `"trot"` | `"canter"` | `"gallop"`

## New constants added

### _combat_timing.py
- `BRAND_TIMING_MODIFIERS`: Per-brand timing scale factors for all 10 VeilBreakers brands
- `apply_brand_timing()`: Function to apply brand modifiers to timing config

### animation_gaits.py
- `QUADRUPED_TROT_CONFIG`: 2-beat diagonal pair gait
- `QUADRUPED_CANTER_CONFIG`: 3-beat asymmetric gait
- `QUADRUPED_GALLOP_CONFIG`: 4-beat fastest gait with suspension
- Multi-harmonic support in `generate_cycle_keyframes()` via `"harmonics"` key

### animation_export.py
- 30 finger bone mappings added to `MIXAMO_TO_RIGIFY`
- `COPY_LOCATION` constraint added for hip in Mixamo retarget
- `_generate_timing_sidecar()`: JSON sidecar generation for FBX export
