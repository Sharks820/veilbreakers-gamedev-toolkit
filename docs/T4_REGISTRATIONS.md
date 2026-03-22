# T4 Handler Registrations

## New entries for COMMAND_HANDLERS in handlers/__init__.py

```python
from .settlement_generator import generate_settlement
from .map_composer import compose_world_map
```

```python
"generate_settlement": lambda params: generate_settlement(
    settlement_type=params.get("settlement_type", "village"),
    seed=params.get("seed"),
    center=(params.get("center_x", 0), params.get("center_y", 0)),
    radius=params.get("radius", 50.0),
),
"compose_world_map": lambda params: compose_world_map(
    width=params.get("width", 1000.0),
    height=params.get("height", 1000.0),
    poi_list=params.get("poi_list", []),
    seed=params.get("seed"),
    heightmap=params.get("heightmap"),
),
```

## New action Literals for blender_server.py blender_worldbuilding tool

Add to the `action` Literal type:
```
"generate_settlement" | "compose_world_map"
```

## New action Literals for blender_server.py blender_environment tool

The biome preset system is already integrated into `generate_terrain` — when `terrain_type` matches a VB biome name (e.g., "thornwood_forest"), the preset is auto-applied. No new action needed.

## New parameters for existing actions

### blender_worldbuilding generate_building
- `preset: str` — VB building preset name (shrine_minor, shrine_major, ruined_fortress_tower, abandoned_house, forge)

### blender_worldbuilding generate_dungeon / generate_multi_floor_dungeon
- `preset: str` — VB dungeon preset name (abandoned_prison, corrupted_cave, storm_peak, veil_tear_dungeon)

## Usage Examples

### Generate a complete town
```
blender_worldbuilding action=generate_settlement settlement_type=town seed=42 radius=80
```

### Generate a bandit camp
```
blender_worldbuilding action=generate_settlement settlement_type=bandit_camp seed=123 radius=30
```

### Compose a world map with POIs
```
blender_worldbuilding action=compose_world_map width=2000 height=2000 seed=7 poi_list=[{"type":"town","count":2},{"type":"village","count":5},{"type":"bandit_camp","count":4},{"type":"dungeon_entrance","count":6},{"type":"shrine","count":8},{"type":"castle","count":1}]
```

### Generate terrain with VB biome preset
```
blender_environment action=generate_terrain terrain_type=thornwood_forest seed=42
blender_environment action=generate_terrain terrain_type=corrupted_swamp seed=99
blender_environment action=generate_terrain terrain_type=veil_crack_zone seed=13
```

### Generate a VB building from preset
```
blender_worldbuilding action=generate_building preset=shrine_major
blender_worldbuilding action=generate_building preset=ruined_fortress_tower
```

### Generate a VB dungeon from preset
```
blender_worldbuilding action=generate_multi_floor_dungeon preset=veil_tear_dungeon num_floors=3
```

## Workflow: Building a Complete VeilBreakers Map

1. **Generate world map layout:**
   ```
   compose_world_map → get POI positions and road network
   ```

2. **Generate terrain for each region:**
   ```
   generate_terrain terrain_type=thornwood_forest → base heightmap
   ```

3. **Place settlements at POI positions:**
   ```
   generate_settlement type=town center=<poi_pos> seed=<poi_seed>
   ```

4. **Scatter vegetation and props:**
   ```
   scatter_vegetation → biome-appropriate plants and rocks
   ```

5. **View and verify:**
   ```
   blender_viewport action=screenshot → check overall composition
   blender_viewport action=contact_sheet object_name=<settlement> → multi-angle review
   ```

6. **Iterative refinement:**
   ```
   blender_object action=modify name=<building> position=[x,y,z] → adjust placement
   blender_mesh action=edit operation=extrude → add detail to mesh
   blender_material action=create → assign materials
   blender_texture action=create_pbr → generate textures
   ```
