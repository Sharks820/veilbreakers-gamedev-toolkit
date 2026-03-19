"""Unit tests for rigging template bone definitions.

Tests TEMPLATE_CATALOG, LIMB_LIBRARY, and all 10 creature template bone dicts
for correct structure, valid bone data, and creature-specific bone counts.
All pure-logic -- no Blender required.
"""

import pytest


# ---------------------------------------------------------------------------
# Valid rigify type reference for validation
# ---------------------------------------------------------------------------

VALID_RIGIFY_TYPES = frozenset({
    "",
    "spines.super_spine",
    "spines.basic_tail",
    "limbs.super_limb",
    "limbs.arm",
    "limbs.leg",
    "limbs.paw",
    "limbs.front_paw",
    "limbs.rear_paw",
    "limbs.super_finger",
    "limbs.super_palm",
    "limbs.simple_tentacle",
    "basic.copy_chain",
    "basic.pivot",
    "basic.raw_copy",
    "basic.super_copy",
    "faces.super_face",
    "skin.basic_chain",
    "skin.stretchy_chain",
    "skin.anchor",
    "skin.glue",
})

REQUIRED_BONE_KEYS = {"head", "tail", "roll", "parent", "rigify_type"}


# ---------------------------------------------------------------------------
# TestTemplateDefinitions
# ---------------------------------------------------------------------------


class TestTemplateDefinitions:
    """Test that each of the 10 creature templates has valid bone structure."""

    @pytest.fixture
    def all_templates(self):
        from blender_addon.handlers.rigging_templates import TEMPLATE_CATALOG
        return TEMPLATE_CATALOG

    def _get_template(self, name):
        from blender_addon.handlers.rigging_templates import TEMPLATE_CATALOG
        return TEMPLATE_CATALOG[name]

    @pytest.mark.parametrize("template_name", [
        "humanoid", "quadruped", "bird", "insect", "serpent",
        "floating", "dragon", "multi_armed", "arachnid", "amorphous",
    ])
    def test_template_is_non_empty_dict(self, template_name):
        """Each template is a non-empty dict."""
        template = self._get_template(template_name)
        assert isinstance(template, dict)
        assert len(template) > 0

    @pytest.mark.parametrize("template_name", [
        "humanoid", "quadruped", "bird", "insect", "serpent",
        "floating", "dragon", "multi_armed", "arachnid", "amorphous",
    ])
    def test_template_bones_have_required_keys(self, template_name):
        """Every bone in each template has head, tail, roll, parent, rigify_type."""
        template = self._get_template(template_name)
        for bone_name, bone_def in template.items():
            missing = REQUIRED_BONE_KEYS - set(bone_def.keys())
            assert not missing, (
                f"Template '{template_name}', bone '{bone_name}' "
                f"missing keys: {missing}"
            )

    @pytest.mark.parametrize("template_name", [
        "humanoid", "quadruped", "bird", "insect", "serpent",
        "floating", "dragon", "multi_armed", "arachnid", "amorphous",
    ])
    def test_template_has_exactly_one_root_bone(self, template_name):
        """Each template has exactly one root bone (parent=None)."""
        template = self._get_template(template_name)
        roots = [
            name for name, bone in template.items()
            if bone["parent"] is None
        ]
        assert len(roots) == 1, (
            f"Template '{template_name}' has {len(roots)} root bones: {roots}"
        )

    @pytest.mark.parametrize("template_name", [
        "humanoid", "quadruped", "bird", "insect", "serpent",
        "floating", "dragon", "multi_armed", "arachnid", "amorphous",
    ])
    def test_bone_positions_are_3_tuples_of_floats(self, template_name):
        """Bone head and tail positions are 3-tuples of numeric values."""
        template = self._get_template(template_name)
        for bone_name, bone_def in template.items():
            for key in ("head", "tail"):
                pos = bone_def[key]
                assert len(pos) == 3, (
                    f"Template '{template_name}', bone '{bone_name}', "
                    f"'{key}' has {len(pos)} elements"
                )
                for i, val in enumerate(pos):
                    assert isinstance(val, (int, float)), (
                        f"Template '{template_name}', bone '{bone_name}', "
                        f"'{key}[{i}]' is {type(val).__name__}, expected number"
                    )

    @pytest.mark.parametrize("template_name", [
        "humanoid", "quadruped", "bird", "insect", "serpent",
        "floating", "dragon", "multi_armed", "arachnid", "amorphous",
    ])
    def test_bone_roll_is_float(self, template_name):
        """Bone roll is a float."""
        template = self._get_template(template_name)
        for bone_name, bone_def in template.items():
            assert isinstance(bone_def["roll"], (int, float)), (
                f"Template '{template_name}', bone '{bone_name}' "
                f"roll is {type(bone_def['roll']).__name__}"
            )

    @pytest.mark.parametrize("template_name", [
        "humanoid", "quadruped", "bird", "insect", "serpent",
        "floating", "dragon", "multi_armed", "arachnid", "amorphous",
    ])
    def test_rigify_type_is_valid_string(self, template_name):
        """All rigify_type values are valid Rigify type strings."""
        template = self._get_template(template_name)
        for bone_name, bone_def in template.items():
            rt = bone_def["rigify_type"]
            assert rt in VALID_RIGIFY_TYPES, (
                f"Template '{template_name}', bone '{bone_name}' "
                f"has invalid rigify_type: '{rt}'"
            )

    @pytest.mark.parametrize("template_name", [
        "humanoid", "quadruped", "bird", "insect", "serpent",
        "floating", "dragon", "multi_armed", "arachnid", "amorphous",
    ])
    def test_parent_references_valid_bone(self, template_name):
        """Every bone's parent (if not None) references an existing bone name."""
        template = self._get_template(template_name)
        bone_names = set(template.keys())
        for bone_name, bone_def in template.items():
            parent = bone_def["parent"]
            if parent is not None:
                assert parent in bone_names, (
                    f"Template '{template_name}', bone '{bone_name}' "
                    f"references non-existent parent '{parent}'"
                )


# ---------------------------------------------------------------------------
# TestTemplateCatalog
# ---------------------------------------------------------------------------


class TestTemplateCatalog:
    """Test TEMPLATE_CATALOG mapping."""

    def test_catalog_has_10_entries(self):
        """TEMPLATE_CATALOG contains exactly 10 creature templates."""
        from blender_addon.handlers.rigging_templates import TEMPLATE_CATALOG
        assert len(TEMPLATE_CATALOG) == 10

    def test_catalog_keys_match_expected_names(self):
        """TEMPLATE_CATALOG keys are the expected creature type names."""
        from blender_addon.handlers.rigging_templates import TEMPLATE_CATALOG
        expected = {
            "humanoid", "quadruped", "bird", "insect", "serpent",
            "floating", "dragon", "multi_armed", "arachnid", "amorphous",
        }
        assert set(TEMPLATE_CATALOG.keys()) == expected

    def test_catalog_values_are_dicts(self):
        """Each value in TEMPLATE_CATALOG is a non-empty dict."""
        from blender_addon.handlers.rigging_templates import TEMPLATE_CATALOG
        for name, template in TEMPLATE_CATALOG.items():
            assert isinstance(template, dict), f"{name} is not a dict"
            assert len(template) > 0, f"{name} is empty"

    def test_catalog_references_match_module_level_dicts(self):
        """TEMPLATE_CATALOG values are the same objects as the module-level dicts."""
        from blender_addon.handlers.rigging_templates import (
            TEMPLATE_CATALOG,
            HUMANOID_BONES,
            QUADRUPED_BONES,
            BIRD_BONES,
            INSECT_BONES,
            SERPENT_BONES,
            FLOATING_BONES,
            DRAGON_BONES,
            MULTI_ARMED_BONES,
            ARACHNID_BONES,
            AMORPHOUS_BONES,
        )
        assert TEMPLATE_CATALOG["humanoid"] is HUMANOID_BONES
        assert TEMPLATE_CATALOG["quadruped"] is QUADRUPED_BONES
        assert TEMPLATE_CATALOG["bird"] is BIRD_BONES
        assert TEMPLATE_CATALOG["insect"] is INSECT_BONES
        assert TEMPLATE_CATALOG["serpent"] is SERPENT_BONES
        assert TEMPLATE_CATALOG["floating"] is FLOATING_BONES
        assert TEMPLATE_CATALOG["dragon"] is DRAGON_BONES
        assert TEMPLATE_CATALOG["multi_armed"] is MULTI_ARMED_BONES
        assert TEMPLATE_CATALOG["arachnid"] is ARACHNID_BONES
        assert TEMPLATE_CATALOG["amorphous"] is AMORPHOUS_BONES


# ---------------------------------------------------------------------------
# TestTemplateStructure -- creature-specific bone count requirements
# ---------------------------------------------------------------------------


class TestTemplateStructure:
    """Test that creature templates have the expected bone counts and structure."""

    def test_humanoid_at_least_15_bones(self):
        """Humanoid template has at least 15 bones (spine, 2 arms, 2 legs, head)."""
        from blender_addon.handlers.rigging_templates import HUMANOID_BONES
        assert len(HUMANOID_BONES) >= 15

    def test_quadruped_at_least_18_bones(self):
        """Quadruped template has at least 18 bones (spine, 4 legs, tail, head)."""
        from blender_addon.handlers.rigging_templates import QUADRUPED_BONES
        assert len(QUADRUPED_BONES) >= 18

    def test_dragon_at_least_20_bones(self):
        """Dragon template has at least 20 bones (spine, 4 legs, wings, tail, head)."""
        from blender_addon.handlers.rigging_templates import DRAGON_BONES
        assert len(DRAGON_BONES) >= 20

    def test_serpent_at_least_10_bones(self):
        """Serpent template has at least 10 bones (long spine, head, jaw)."""
        from blender_addon.handlers.rigging_templates import SERPENT_BONES
        assert len(SERPENT_BONES) >= 10

    def test_humanoid_has_lr_arm_pairs(self):
        """Humanoid has L/R arm bone pairs."""
        from blender_addon.handlers.rigging_templates import HUMANOID_BONES
        assert "upper_arm.L" in HUMANOID_BONES
        assert "upper_arm.R" in HUMANOID_BONES
        assert "forearm.L" in HUMANOID_BONES
        assert "forearm.R" in HUMANOID_BONES
        assert "hand.L" in HUMANOID_BONES
        assert "hand.R" in HUMANOID_BONES

    def test_humanoid_has_lr_leg_pairs(self):
        """Humanoid has L/R leg bone pairs."""
        from blender_addon.handlers.rigging_templates import HUMANOID_BONES
        assert "thigh.L" in HUMANOID_BONES
        assert "thigh.R" in HUMANOID_BONES
        assert "shin.L" in HUMANOID_BONES
        assert "shin.R" in HUMANOID_BONES
        assert "foot.L" in HUMANOID_BONES
        assert "foot.R" in HUMANOID_BONES

    def test_quadruped_has_four_leg_roots(self):
        """Quadruped has 4 leg root bones (2 front, 2 rear)."""
        from blender_addon.handlers.rigging_templates import QUADRUPED_BONES
        assert "upper_arm.L" in QUADRUPED_BONES
        assert "upper_arm.R" in QUADRUPED_BONES
        assert "thigh.L" in QUADRUPED_BONES
        assert "thigh.R" in QUADRUPED_BONES

    def test_quadruped_has_tail(self):
        """Quadruped has tail bones."""
        from blender_addon.handlers.rigging_templates import QUADRUPED_BONES
        tail_bones = [n for n in QUADRUPED_BONES if n.startswith("tail")]
        assert len(tail_bones) >= 2

    def test_dragon_has_wings(self):
        """Dragon has L/R wing bones."""
        from blender_addon.handlers.rigging_templates import DRAGON_BONES
        assert "wing_upper.L" in DRAGON_BONES
        assert "wing_upper.R" in DRAGON_BONES
        assert "wing_fore.L" in DRAGON_BONES
        assert "wing_fore.R" in DRAGON_BONES

    def test_dragon_has_jaw(self):
        """Dragon has a jaw bone."""
        from blender_addon.handlers.rigging_templates import DRAGON_BONES
        assert "jaw" in DRAGON_BONES

    def test_insect_has_six_legs(self):
        """Insect has 6 legs (3 pairs)."""
        from blender_addon.handlers.rigging_templates import INSECT_BONES
        leg_roots = [
            n for n in INSECT_BONES
            if n.startswith("leg_") and not n.endswith(("_lower.L", "_lower.R", "_foot.L", "_foot.R", ".001"))
        ]
        # Should have at least 6 leg root bones (3 pairs x L/R)
        assert len(leg_roots) >= 6

    def test_insect_has_mandibles(self):
        """Insect has L/R mandibles."""
        from blender_addon.handlers.rigging_templates import INSECT_BONES
        assert "mandible.L" in INSECT_BONES
        assert "mandible.R" in INSECT_BONES

    def test_insect_has_antennae(self):
        """Insect has L/R antennae."""
        from blender_addon.handlers.rigging_templates import INSECT_BONES
        assert "antenna.L" in INSECT_BONES
        assert "antenna.R" in INSECT_BONES

    def test_serpent_has_long_spine(self):
        """Serpent has at least 8 spine bones."""
        from blender_addon.handlers.rigging_templates import SERPENT_BONES
        spine_bones = [n for n in SERPENT_BONES if n.startswith("spine")]
        assert len(spine_bones) >= 8

    def test_serpent_has_jaw(self):
        """Serpent has a jaw bone."""
        from blender_addon.handlers.rigging_templates import SERPENT_BONES
        assert "jaw" in SERPENT_BONES

    def test_floating_has_tentacles(self):
        """Floating template has tentacle bones."""
        from blender_addon.handlers.rigging_templates import FLOATING_BONES
        tentacle_bones = [n for n in FLOATING_BONES if "tentacle" in n]
        assert len(tentacle_bones) >= 4

    def test_multi_armed_has_four_or_more_arm_roots(self):
        """Multi-armed template has 4+ arm root bones."""
        from blender_addon.handlers.rigging_templates import MULTI_ARMED_BONES
        arm_roots = [
            n for n in MULTI_ARMED_BONES
            if "upper_arm" in n and not n.endswith((".001", ".002"))
        ]
        assert len(arm_roots) >= 4

    def test_arachnid_has_eight_leg_roots(self):
        """Arachnid has 8 legs (4 pairs)."""
        from blender_addon.handlers.rigging_templates import ARACHNID_BONES
        leg_roots = [
            n for n in ARACHNID_BONES
            if n.startswith("leg_") and not ("_lower" in n or "_foot" in n)
        ]
        assert len(leg_roots) >= 8

    def test_arachnid_has_mandibles(self):
        """Arachnid has L/R mandibles."""
        from blender_addon.handlers.rigging_templates import ARACHNID_BONES
        assert "mandible.L" in ARACHNID_BONES
        assert "mandible.R" in ARACHNID_BONES

    def test_amorphous_has_tentacles(self):
        """Amorphous template has tentacle bones."""
        from blender_addon.handlers.rigging_templates import AMORPHOUS_BONES
        tentacle_bones = [n for n in AMORPHOUS_BONES if "tentacle" in n]
        assert len(tentacle_bones) >= 4


# ---------------------------------------------------------------------------
# TestLimbLibrary
# ---------------------------------------------------------------------------


class TestLimbLibrary:
    """Test LIMB_LIBRARY functions return valid bone dicts."""

    def test_limb_library_has_expected_keys(self):
        """LIMB_LIBRARY has all expected limb type keys."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        expected = {
            "arm_pair", "leg_pair", "paw_leg_pair", "wing_pair",
            "tail_chain", "head_chain", "jaw", "tentacle_chain",
            "insect_leg_pair",
        }
        assert set(LIMB_LIBRARY.keys()) == expected

    def test_limb_library_values_are_callable(self):
        """Every LIMB_LIBRARY value is callable."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        for name, fn in LIMB_LIBRARY.items():
            assert callable(fn), f"LIMB_LIBRARY['{name}'] is not callable"

    def test_arm_pair_returns_valid_bones(self):
        """arm_pair returns a dict with L/R arm bones."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        bones = LIMB_LIBRARY["arm_pair"]()
        assert isinstance(bones, dict)
        assert "upper_arm.L" in bones
        assert "upper_arm.R" in bones
        assert len(bones) == 6  # 3 bones per side
        for bone_def in bones.values():
            assert REQUIRED_BONE_KEYS.issubset(bone_def.keys())

    def test_leg_pair_returns_valid_bones(self):
        """leg_pair returns a dict with L/R leg bones."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        bones = LIMB_LIBRARY["leg_pair"]()
        assert isinstance(bones, dict)
        assert "thigh.L" in bones
        assert "thigh.R" in bones
        assert len(bones) == 6
        for bone_def in bones.values():
            assert REQUIRED_BONE_KEYS.issubset(bone_def.keys())

    def test_wing_pair_returns_valid_bones(self):
        """wing_pair returns a dict with L/R wing bones."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        bones = LIMB_LIBRARY["wing_pair"]()
        assert isinstance(bones, dict)
        assert "wing_upper.L" in bones
        assert "wing_upper.R" in bones
        assert len(bones) == 6
        for bone_def in bones.values():
            assert REQUIRED_BONE_KEYS.issubset(bone_def.keys())

    def test_tail_chain_returns_valid_bones(self):
        """tail_chain returns a dict with sequential tail bones."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        bones = LIMB_LIBRARY["tail_chain"]()
        assert isinstance(bones, dict)
        assert "tail" in bones
        assert len(bones) >= 3
        for bone_def in bones.values():
            assert REQUIRED_BONE_KEYS.issubset(bone_def.keys())

    def test_tail_chain_custom_length(self):
        """tail_chain accepts length parameter."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        bones = LIMB_LIBRARY["tail_chain"](length=5)
        assert len(bones) == 5

    def test_head_chain_returns_valid_bones(self):
        """head_chain returns neck + head bones."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        bones = LIMB_LIBRARY["head_chain"]()
        assert isinstance(bones, dict)
        assert len(bones) >= 2
        for bone_def in bones.values():
            assert REQUIRED_BONE_KEYS.issubset(bone_def.keys())

    def test_jaw_returns_valid_bones(self):
        """jaw returns a single jaw bone."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        bones = LIMB_LIBRARY["jaw"]()
        assert isinstance(bones, dict)
        assert "jaw" in bones
        assert REQUIRED_BONE_KEYS.issubset(bones["jaw"].keys())

    def test_tentacle_chain_returns_valid_bones(self):
        """tentacle_chain returns tentacle bones."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        bones = LIMB_LIBRARY["tentacle_chain"]()
        assert isinstance(bones, dict)
        assert len(bones) >= 4  # default count=4, 2 bones each = 8
        for bone_def in bones.values():
            assert REQUIRED_BONE_KEYS.issubset(bone_def.keys())

    def test_insect_leg_pair_returns_valid_bones(self):
        """insect_leg_pair returns L/R insect leg bones."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        bones = LIMB_LIBRARY["insect_leg_pair"]()
        assert isinstance(bones, dict)
        assert len(bones) == 6  # 3 bones per side
        for bone_def in bones.values():
            assert REQUIRED_BONE_KEYS.issubset(bone_def.keys())

    def test_paw_leg_pair_front_returns_valid_bones(self):
        """paw_leg_pair('front') returns front paw leg bones."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        bones = LIMB_LIBRARY["paw_leg_pair"](side="front")
        assert isinstance(bones, dict)
        assert len(bones) == 6
        # Front paws use upper_arm naming
        assert "upper_arm.L" in bones
        assert "upper_arm.R" in bones

    def test_paw_leg_pair_rear_returns_valid_bones(self):
        """paw_leg_pair('rear') returns rear paw leg bones."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        bones = LIMB_LIBRARY["paw_leg_pair"](side="rear")
        assert isinstance(bones, dict)
        assert len(bones) == 6
        # Rear paws use thigh naming
        assert "thigh.L" in bones
        assert "thigh.R" in bones

    def test_all_limb_bones_have_valid_rigify_types(self):
        """All bones from all limb functions have valid rigify_type strings."""
        from blender_addon.handlers.rigging_templates import LIMB_LIBRARY
        for limb_name, limb_fn in LIMB_LIBRARY.items():
            bones = limb_fn()
            for bone_name, bone_def in bones.items():
                rt = bone_def.get("rigify_type", "")
                assert rt in VALID_RIGIFY_TYPES, (
                    f"LIMB_LIBRARY['{limb_name}'], bone '{bone_name}' "
                    f"has invalid rigify_type: '{rt}'"
                )
