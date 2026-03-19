---
phase: 04-rigging
plan: 01
status: complete
completed: 2026-03-19
tests_passed: 131 new (349 total suite)
handler_count: 43 -> 46
---

## What was built

### rigging_templates.py (new)
- 10 creature template bone definition dicts: HUMANOID_BONES (18 bones), QUADRUPED_BONES (21 bones), BIRD_BONES (21 bones), INSECT_BONES (27 bones), SERPENT_BONES (10 bones), FLOATING_BONES (15 bones), DRAGON_BONES (32 bones), MULTI_ARMED_BONES (24 bones), ARACHNID_BONES (35 bones), AMORPHOUS_BONES (12 bones)
- TEMPLATE_CATALOG mapping 10 template names to bone dicts
- LIMB_LIBRARY with 9 mix-and-match limb segment functions: arm_pair, leg_pair, paw_leg_pair, wing_pair, tail_chain, head_chain, jaw, tentacle_chain, insect_leg_pair
- _create_template_bones helper for metarig bone creation (two-pass: create then parent)
- _generate_rig helper for Rigify generation
- _fix_deform_hierarchy helper for DEF bone re-parenting (Unity FBX export)
- VALID_RIGIFY_TYPES frozenset for validation

### rigging.py (new)
- _analyze_proportions: pure-logic mesh proportion analyzer with template recommendation
- _validate_custom_rig_config: pure-logic custom rig config validator
- handle_analyze_for_rigging (RIG-01): mesh analysis via bmesh for rig recommendation
- handle_apply_rig_template (RIG-02): apply Rigify creature rig from TEMPLATE_CATALOG
- handle_build_custom_rig (RIG-03): assemble limbs from LIMB_LIBRARY into custom rig

### handlers/__init__.py (modified)
- Registered 3 new handlers: rig_analyze, rig_apply_template, rig_build_custom (43 -> 46 total)

### test_rigging_templates.py (new, 108 tests)
- TestTemplateDefinitions: 70 parametrized tests across all 10 templates (non-empty, required keys, root bone, position tuples, roll float, rigify type validity, parent references)
- TestTemplateCatalog: 4 tests (10 entries, expected names, dict values, reference identity)
- TestTemplateStructure: 20 tests (bone counts, L/R pairs, creature-specific features)
- TestLimbLibrary: 14 tests (expected keys, callable values, each function returns valid bones)

### test_rigging_handlers.py (new, 23 tests)
- TestMeshAnalysis: 13 tests (humanoid/serpent/quadruped recommendations, return structure, edge cases)
- TestCustomRigValidation: 10 tests (valid/invalid limbs, empty lists, bone estimates)

## Key decisions
- Each bone def is a plain dict with head/tail/roll/parent/rigify_type -- no classes, maximally testable
- Proportion analysis uses aspect ratio (height/width) as primary classifier with depth as secondary
- Custom rig builder always includes a 4-bone spine as root before merging limb bones
- All rigify_type assignments happen in object mode (not edit mode) per Blender API requirement
- DEF hierarchy fix uses ORG bone parentage as reference for re-parenting
