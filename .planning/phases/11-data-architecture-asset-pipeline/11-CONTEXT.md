# Phase 11: Data Architecture & Asset Pipeline - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning
**Source:** Auto-generated (--auto flag, recommended defaults selected)

<domain>
## Phase Boundary

Data-driven game architecture using ScriptableObjects, JSON configs, and localization. Asset pipeline management with Git LFS configuration, normal map baking workflow, sprite atlasing, AssetPostprocessor scripts, Unity Presets for reusable config, TextMeshPro setup, and AAA quality standards enforcement (albedo de-lighting, poly budgets, material palette validation, master material library, texture quality validation).

Requirements: DATA-01, DATA-02, DATA-03, DATA-04, IMP-03, IMP-04, BUILD-06, TWO-03, PIPE-08, AAA-01, AAA-02, AAA-03, AAA-04, AAA-06.

</domain>

<decisions>
## Implementation Decisions

### ScriptableObject Architecture (DATA-02, DATA-04)
- **Category-based folder structure**: Assets/Data/{Category}/ with PascalCase naming (e.g. Assets/Data/Items/, Assets/Data/Monsters/, Assets/Data/Abilities/)
- **SO definitions + .asset instantiation**: Generate both the C# ScriptableObject class definition AND create .asset instances populated with data
- **Game data authoring tools**: Generate custom editor windows for batch-creating/editing SO assets (item databases, stat tables, ability configs)
- **VeilBreakers game project already uses JSON** for monster/hero/skill data in Assets/Resources/Data/ — SO architecture should complement JSON (not replace) for data that benefits from Unity references (prefab refs, sprite refs, audio clips)

### JSON/XML Configuration (DATA-01)
- **JSON validation**: Generate validators that check game config files (difficulty, balance, progression) against schemas
- **Config file creation**: Generate properly formatted JSON/XML with comments explaining each field
- **Runtime loading**: Generate config loaders that deserialize JSON into typed C# classes — complement existing GameDatabase async loader

### Localization (DATA-03)
- **Unity Localization package**: Generate string table setup, locale assets, and localized variant configurations
- **Default locale**: English (en) as base, with infrastructure for adding more
- **Generate localization keys**: Create key naming convention matching VeilBreakers patterns (UI.MainMenu.StartGame, Combat.Brand.Iron, etc.)

### AAA Quality Standards (AAA-01 through AAA-04, AAA-06)
- **Strict enforcement with auto-fix**: Don't just report issues — fix them when possible
- **Albedo de-lighting** (AAA-01): Remove baked-in lighting from AI-generated textures (Tripo3D output)
- **Per-asset-type poly budgets** (AAA-02): hero: 30-50k, mob: 8-15k, weapon: 3-8k, prop: 500-6k, building: 5-15k — auto-retopo if over budget
- **Dark fantasy material palette** (AAA-03): Saturation caps, color temperature rules, PBR roughness variation enforcement
- **Master material library** (AAA-04): Base materials (stone, wood, iron, moss, bone, cloth, leather) that all assets reference
- **Texture quality validation** (AAA-06): Texel density 10.24 px/cm, micro-detail normals, proper M/R/AO channel packing

### Asset Pipeline (IMP-03, IMP-04, BUILD-06, TWO-03, PIPE-08)
- **Git LFS configuration** (IMP-03): Generate .gitattributes tracking *.fbx, *.png, *.wav, *.psd, *.tga, *.exr, *.hdr, *.mp3, *.ogg, *.ttf, *.otf, *.asset (large binary). Generate .gitignore for Unity standard ignores
- **Normal map baking** (IMP-04): High-to-low poly baking with cage generation in Blender, single-step workflow
- **Sprite atlasing** (BUILD-06): Sprite sheet packing, texture atlas generation, sprite animation setup
- **Sprite Editor configuration** (TWO-03): Custom physics shapes, pivot points, 9-slice borders
- **AssetPostprocessor scripts** (PIPE-08): Custom import pipeline scripts that auto-configure assets on import based on folder conventions

### Claude's Discretion
- JSON schema format (JSON Schema draft or custom)
- Localization key auto-detection from existing UXML/code
- De-lighting algorithm specifics
- Master material library shader graph structure
- Sprite atlas packing algorithm configuration
- TextMeshPro font asset creation details

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### VeilBreakers Game Project
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Resources/Data/` — Existing JSON game data (monsters.json, heroes.json, skills.json, items.json)
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Core/GameDatabase.cs` — Existing async JSON loader (complement, don't replace)
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Resources/CharacterSelect/HeroDisplayConfigs/` — Existing ScriptableObject pattern

### Toolkit Implementation
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` — Add unity_data compound tool
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/` — Template generator pattern
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/asset_templates.py` — Existing import config generators (extend for AAA validation)
- `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py` — Blender tools for normal map baking, mesh analysis

### Requirements
- `.planning/REQUIREMENTS.md` — DATA-01 through DATA-04, IMP-03, IMP-04, BUILD-06, TWO-03, PIPE-08, AAA-01 through AAA-04, AAA-06

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 9 `unity_assets` tool: Import config, asmdef management, Unity Presets — extend for AAA validation
- Phase 10 `unity_code` tool: Generate SO class definitions, custom editors
- Phase 9 `unity_prefab` `reflect_component`: Discover SO fields for data authoring tools
- Blender server `blender_mesh` action=`game_check`: Existing poly budget checking
- Blender server `blender_texture` action=`bake`: Normal map baking capability
- Blender server `blender_mesh` action=`retopo`: Retopology for auto-fix when over budget

### Established Patterns
- Compound tool + template generator pattern (11 template modules exist)
- Two-step execution: write C# → recompile → execute menu item
- Enhanced result JSON with changed_assets, warnings, validation_status
- VeilBreakers namespace conventions (VeilBreakers.[Category])

### Integration Points
- New `unity_data` compound tool for SO/JSON/localization
- Extend existing Blender tools for normal map baking workflow
- AAA quality tools may be a new compound tool or extend `unity_assets`
- Git LFS configuration is file-system level (not Unity-specific)

</code_context>

<specifics>
## Specific Ideas

- VeilBreakers already has 4 HeroDisplayConfig ScriptableObjects — follow that pattern for new SO data
- GameDatabase uses async parallel JSON loading — SO architecture should not break this pattern
- The game has 60+ monsters defined in JSON — SO authoring tools should be able to batch-import from existing JSON
- Dark fantasy aesthetic is the anchor — AAA-03 palette validation must enforce the game's visual identity
- Tripo3D outputs need de-lighting before they match the rest of the game's art style

</specifics>

<deferred>
## Deferred Ideas

None — auto-mode stayed within phase scope

</deferred>

---

*Phase: 11-data-architecture-asset-pipeline*
*Context gathered: 2026-03-20 via auto-mode*
