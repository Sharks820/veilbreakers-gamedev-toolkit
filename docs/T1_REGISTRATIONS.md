# T1 Handler Registrations

New handler functions and action literals created by Terminal 1 (Rigging Audit).
These need to be integrated into `handlers/__init__.py` and `blender_server.py` after all terminals merge.

## New entries for COMMAND_HANDLERS in handlers/__init__.py

```python
from .rigging_weights import handle_enforce_weight_limit

"rig_enforce_weight_limit": handle_enforce_weight_limit,
```

## New action Literals for blender_server.py blender_rig tool

```python
# Add to blender_rig action Literal:
"enforce_weight_limit"
```

## New pure-logic functions (no registration needed, used internally)

### rigging_weights.py
- `_enforce_weight_limit_pure(vertex_weights, max_influences)` - Weight limit logic
- `_enhanced_rig_validation(...)` - Extended validation checks

### rigging_advanced.py
- `_validate_facial_rig_params(expressions, facs_units, visemes)` - Facial rig param validation
- `_compute_spring_chain_forces(...)` - Spring bone physics simulation
- `_validate_spring_dynamics_params(mass, stiffness, damping, gravity_factor)` - Dynamics param validation
- `_validate_corrective_shape_config(joint_name, axis, threshold, strength)` - Corrective shape validation

### rigging.py
- `_generate_multi_arm_bones(arm_count)` - Multi-armed creature bone generation
- `_validate_monster_rig_config(monster_id)` - VB monster rig config validation
- `_get_status_effect_socket(template_name, socket_name)` - Status VFX attachment lookup
- `_get_corruption_stage(corruption_pct)` - Corruption morph stage lookup

## New data constants (no registration needed)

### rigging_advanced.py
- `FACS_ACTION_UNITS` - 17 Facial Action Coding System units
- `VISEME_SHAPES` - 15 viseme shapes for lip sync
- `CORRECTIVE_SHAPE_DEFS` - 5 corrective blend shape definitions

### rigging.py
- `MONSTER_TEMPLATE_MAP` - 20 VB monsters mapped to rig templates
- `STATUS_EFFECT_SOCKETS` - VFX bone attachment points per template
- `CORRUPTION_MORPH_STAGES` - 4-stage corruption progression

### rigging_templates.py
- Twist bones added to humanoid, quadruped, bird, dragon, multi_armed templates
- Wing membrane bones added to dragon template
- Shoulder (shoulder.L/R), finger (thumb.XX, f_index.XX, etc.), and toe bones added to humanoid template
- Forearm bone rolls set to +/-1.5708 rad (90 deg) across all applicable templates
