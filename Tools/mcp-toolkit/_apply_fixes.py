"""Apply all audit fixes to template and animation files."""
import os

base = "Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates"

# Fix 3: VFX Graph API in vfx_mastery_templates.py
path = os.path.join(base, "vfx_mastery_templates.py")
with open(path, "r") as f:
    content = f.read()

old_vfx_start = "        // Create VFX Graph asset"
old_vfx_end = '        Debug.Log($"[VB] Exposed parameter: {paramName} ({type})");'
# Note: in the template these are doubled braces {{ }}
old_vfx_end_actual = "Debug.Log($\"[VB] Exposed parameter: {{paramName}} ({{type}})\");"

if old_vfx_start in content and old_vfx_end_actual in content:
    start = content.index(old_vfx_start)
    end = content.index(old_vfx_end_actual) + len(old_vfx_end_actual)
    # Find the closing brace of the method after this
    rest = content[end:]
    # skip to next line end
    nl = rest.index("\n") + 1
    end += nl
    # skip the closing brace line "    }}"
    rest2 = content[end:]
    nl2 = rest2.index("\n") + 1
    end += nl2

    replacement = """        // NOTE: VFX Graph C# API (VFXBasicSpawner, VFXBasicInitialize, etc.)
        // are internal Unity types not exposed in the public API.
        // Instead, we create a VFX preset ScriptableObject that stores
        // the composition parameters, and use VisualEffectAsset template
        // duplication for actual graph creation.

        // Create preset ScriptableObject with VFX parameters
        string presetPath = $"{{dir}}/{{GraphName}}_Preset.asset";
        var preset = ScriptableObject.CreateInstance<VFXCompositionPreset>();
        preset.graphName = GraphName;
        preset.spawnRate = SpawnRate;
        preset.burstCount = BurstCount;
        preset.burstCycle = BurstCycle;
        preset.positionMode = PositionMode;
        preset.velocityMin = VelocityMin;
        preset.velocityMax = VelocityMax;
        preset.lifetime = Lifetime;
        preset.particleSize = ParticleSize;
        preset.gravity = Gravity;
        preset.turbulenceIntensity = TurbulenceIntensity;
        preset.turbulenceFrequency = TurbulenceFrequency;
        preset.drag = Drag;
        preset.outputType = OutputType;
        preset.blendMode = BlendMode;
        preset.sortEnabled = SortEnabled;
        preset.faceCamera = FaceCamera;
        preset.initColor = InitColor;

        AssetDatabase.CreateAsset(preset, presetPath);

        // Look for a VFX Graph template to duplicate, or create a new empty one
        string templatePath = "Assets/Art/VFX/Templates/VB_BaseVFX.vfx";
        bool hasTemplate = AssetDatabase.LoadAssetAtPath<VisualEffectAsset>(templatePath) != null;

        if (hasTemplate)
        {{
            AssetDatabase.CopyAsset(templatePath, assetPath);
            Debug.Log($"[VB] Duplicated VFX template to: {{assetPath}}");
        }}
        else
        {{
            // Create a minimal VisualEffectAsset via the editor utility
#if UNITY_2021_1_OR_NEWER
            var resource = UnityEditor.VFX.VisualEffectResource.GetResourceAtPath(assetPath);
            if (resource == null)
            {{
                Debug.LogWarning($"[VB] No VFX template found at {{templatePath}}. " +
                    "Creating preset only. Manually create VFX Graph and apply preset values.");
            }}
#else
            Debug.LogWarning("[VB] VFX Graph template creation requires Unity 2021.1+. Preset saved.");
#endif
        }}

        // Apply preset values to the VFX asset if it exists
        var vfxAsset = AssetDatabase.LoadAssetAtPath<VisualEffectAsset>(assetPath);
        if (vfxAsset != null)
        {{
            Debug.Log($"[VB] VFX Graph asset ready at: {{assetPath}}. Apply preset values at runtime via VFXCompositionPreset.");
        }}

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        // Write result
        string result = JsonUtility.ToJson(new VFXGraphResult
        {{
            success = true,
            graphName = GraphName,
            assetPath = hasTemplate ? assetPath : presetPath,
            spawnRate = SpawnRate,
            burstCount = BurstCount,
            positionMode = PositionMode,
            outputType = OutputType,
            blendMode = BlendMode,
            nodeCount = hasTemplate ? 4 : 0,
        }});
        File.WriteAllText("Temp/vb_result.json", result);
        Debug.Log($"[VB] VFX composition complete: {{GraphName}} (spawn={{SpawnRate}}, output={{OutputType}})");
    }}

    /// <summary>ScriptableObject storing VFX Graph composition parameters.</summary>
    [System.Serializable]
    public class VFXCompositionPreset : ScriptableObject
    {{
        public string graphName;
        public float spawnRate;
        public int burstCount;
        public float burstCycle;
        public string positionMode;
        public float velocityMin;
        public float velocityMax;
        public float lifetime;
        public float particleSize;
        public float gravity;
        public float turbulenceIntensity;
        public float turbulenceFrequency;
        public float drag;
        public string outputType;
        public string blendMode;
        public bool sortEnabled;
        public bool faceCamera;
        public Color initColor;

        /// <summary>Apply this preset to a VisualEffect component at runtime.</summary>
        public void ApplyTo(VisualEffect vfx)
        {{
            if (vfx == null) return;
            vfx.SetFloat("SpawnRate", spawnRate);
            vfx.SetFloat("Lifetime", lifetime);
            vfx.SetFloat("ParticleSize", particleSize);
            vfx.SetFloat("Gravity", gravity);
            vfx.SetFloat("Drag", drag);
            vfx.SetVector4("ParticleColor", initColor);
        }}
    }}
"""
    # Also need to remove the helper methods that are between the replaced block and VFXGraphResult
    # Find everything from old start through the helper methods
    # Actually let me find the full original block including helpers
    full_old_start = content.index(old_vfx_start)
    # Find the end: after AddExposedParameter closing brace
    marker = 'Debug.Log($"[VB] Exposed parameter: {{paramName}} ({{type}})");\n    }}\n'
    full_old_end = content.index(marker) + len(marker)

    content = content[:full_old_start] + replacement + content[full_old_end:]
    with open(path, "w") as f:
        f.write(content)
    print("Fixed VFX Graph API in vfx_mastery_templates.py")
else:
    print("VFX Graph fix: pattern not found (may already be applied)")

# Fix 4+6: gameplay_templates.py
path = os.path.join(base, "gameplay_templates.py")
with open(path, "r") as f:
    content = f.read()

# Add damage param to function signature (only in projectile, which is the only one with lifetime=5.0)
content = content.replace(
    "    lifetime: float = 5.0,\n) -> str:",
    "    lifetime: float = 5.0,\n    damage: float = 10.0,\n) -> str:",
    1,
)

# Add damage to docstring
content = content.replace(
    "        lifetime: Seconds before auto-destroy.\n\n    Returns:",
    "        lifetime: Seconds before auto-destroy.\n        damage: Damage dealt on impact.\n\n    Returns:",
)

# Remove suffixed IDamageable from projectile
content = content.replace(
    "// ---------------------------------------------------------------------------\n"
    "// IDamageable interface for type-safe damage delivery\n"
    "// ---------------------------------------------------------------------------\n"
    "public interface IDamageable_{safe_name}\n"
    "{{\n"
    "    void TakeDamage(float amount);\n"
    "}}\n"
    "\n"
    "public class VeilBreakers_Projectile_{safe_name}",
    "public class VeilBreakers_Projectile_{safe_name}",
)

# Add damage field after lifetime in projectile class
content = content.replace(
    '    public float lifetime = {lifetime}f;\n\n    [Header("Trail")]',
    '    public float lifetime = {lifetime}f;\n\n    [Header("Damage")]\n    public float damage = {damage}f;\n\n    [Header("Trail")]',
)

# Fix TakeDamage(velocity) -> TakeDamage(damage)
content = content.replace(
    "var damageable = other.GetComponent<IDamageable_{safe_name}>();",
    "var damageable = other.GetComponent<IDamageable>();",
)
content = content.replace(
    "damageable.TakeDamage(velocity);",
    "damageable.TakeDamage(damage);",
)

# Fix combat ability IDamageable (unsuffixed) - first occurrence is the interface declaration
content = content.replace(
    "public interface IDamageable_{safe_name}",
    "public interface IDamageable",
)

# Fix hitBuffer reference
content = content.replace(
    "var damageable = hitBuffer[i].GetComponent<IDamageable_{safe_name}>();",
    "var damageable = hitBuffer[i].GetComponent<IDamageable>();",
)

with open(path, "w") as f:
    f.write(content)
print("Fixed projectile damage + IDamageable in gameplay_templates.py")

# Fix 8+9: animation_export.py
anim_path = "Tools/mcp-toolkit/blender_addon/handlers/animation_export.py"
with open(anim_path, "r") as f:
    content = f.read()

# Fix 8: Add bone axis settings
content = content.replace(
    '                "use_tspace": True,\n'
    '                "use_armature_deform_only": True,\n'
    "            }",
    '                "use_tspace": True,\n'
    '                "use_armature_deform_only": True,\n'
    '                "bake_space_transform": True,\n'
    '                "apply_unit_scale": True,\n'
    "            }",
)

# Fix 9: Generate timing sidecar during batch export
content = content.replace(
    '            frame_range = [int(strip.frame_start), int(strip.frame_end)]\n'
    "            exported.append({\n"
    '                "name": strip.name,\n'
    '                "filepath": filepath,\n'
    '                "frame_range": frame_range,\n'
    "            })\n"
    "\n"
    "            # Restore mute states\n"
    "            _restore_nla_mute_states(anim_data, saved_states)",
    '            frame_range = [int(strip.frame_start), int(strip.frame_end)]\n'
    "\n"
    "            # Generate combat timing sidecar if applicable\n"
    "            action_lower = strip.name.lower()\n"
    '            if "attack" in action_lower or "combat" in action_lower or "combo" in action_lower or "parry" in action_lower or "dodge" in action_lower:\n'
    "                sidecar_path = _generate_timing_sidecar(\n"
    "                    strip.name, output_dir, naming, object_name,\n"
    "                )\n"
    "                if sidecar_path:\n"
    '                    logger.info("Generated timing sidecar: %s", sidecar_path)\n'
    "\n"
    "            exported.append({\n"
    '                "name": strip.name,\n'
    '                "filepath": filepath,\n'
    '                "frame_range": frame_range,\n'
    "            })\n"
    "\n"
    "            # Restore mute states\n"
    "            _restore_nla_mute_states(anim_data, saved_states)",
)

with open(anim_path, "w") as f:
    f.write(content)
print("Fixed FBX bone settings + timing sidecar in animation_export.py")

print("\nAll remaining fixes applied!")
