"""AAA character C# template and shader generators for Unity URP.

Provides:
- generate_cloth_setup_script: Unity Cloth component configuration (CHAR-07)
- generate_sss_skin_shader: Subsurface scattering skin shader (CHAR-08)
- generate_parallax_eye_shader: Parallax/refraction eye shader (CHAR-08)
- generate_micro_detail_normal_script: Micro-detail normal compositing (CHAR-08)

All shader functions return complete ShaderLab source strings.
Script functions return complete C# source strings.
"""

from __future__ import annotations

import re

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


_URP_CORE_INCLUDE = '#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"'
_URP_LIGHTING_INCLUDE = '#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"'


# ---------------------------------------------------------------------------
# Cloth type presets
# ---------------------------------------------------------------------------

_CLOTH_PRESETS: dict[str, dict[str, object]] = {
    "cape": {
        "stretching_stiffness": 0.8,
        "bending_stiffness": 0.5,
        "damping": 0.2,
        "world_velocity_scale": 0.5,
        "world_acceleration_scale": 0.3,
        "friction": 0.3,
        "collision_mass_scale": 0.0,
        "use_gravity": True,
        "external_acceleration_x": 0.0,
        "external_acceleration_y": 0.0,
        "external_acceleration_z": 0.0,
        "random_acceleration_x": 0.5,
        "random_acceleration_y": 0.0,
        "random_acceleration_z": 0.5,
    },
    "robe": {
        "stretching_stiffness": 0.9,
        "bending_stiffness": 0.6,
        "damping": 0.3,
        "world_velocity_scale": 0.4,
        "world_acceleration_scale": 0.2,
        "friction": 0.4,
        "collision_mass_scale": 0.0,
        "use_gravity": True,
        "external_acceleration_x": 0.0,
        "external_acceleration_y": 0.0,
        "external_acceleration_z": 0.0,
        "random_acceleration_x": 0.3,
        "random_acceleration_y": 0.0,
        "random_acceleration_z": 0.3,
    },
    "hair": {
        "stretching_stiffness": 0.7,
        "bending_stiffness": 0.3,
        "damping": 0.15,
        "world_velocity_scale": 0.6,
        "world_acceleration_scale": 0.4,
        "friction": 0.1,
        "collision_mass_scale": 0.0,
        "use_gravity": True,
        "external_acceleration_x": 0.0,
        "external_acceleration_y": 0.0,
        "external_acceleration_z": 0.0,
        "random_acceleration_x": 0.8,
        "random_acceleration_y": 0.2,
        "random_acceleration_z": 0.8,
    },
    "banner": {
        "stretching_stiffness": 0.95,
        "bending_stiffness": 0.7,
        "damping": 0.1,
        "world_velocity_scale": 0.8,
        "world_acceleration_scale": 0.5,
        "friction": 0.2,
        "collision_mass_scale": 0.0,
        "use_gravity": True,
        "external_acceleration_x": 2.0,
        "external_acceleration_y": 0.0,
        "external_acceleration_z": 0.0,
        "random_acceleration_x": 1.5,
        "random_acceleration_y": 0.3,
        "random_acceleration_z": 1.0,
    },
    "cloth_armor": {
        "stretching_stiffness": 0.95,
        "bending_stiffness": 0.8,
        "damping": 0.4,
        "world_velocity_scale": 0.3,
        "world_acceleration_scale": 0.1,
        "friction": 0.5,
        "collision_mass_scale": 0.0,
        "use_gravity": True,
        "external_acceleration_x": 0.0,
        "external_acceleration_y": 0.0,
        "external_acceleration_z": 0.0,
        "random_acceleration_x": 0.2,
        "random_acceleration_y": 0.0,
        "random_acceleration_z": 0.2,
    },
}


# ---------------------------------------------------------------------------
# CHAR-07: Cloth setup script
# ---------------------------------------------------------------------------


def generate_cloth_setup_script(
    mesh_name: str = "CharacterCloth",
    cloth_type: str = "cape",
    stiffness: float | None = None,
    damping: float | None = None,
    wind_main: float = 1.0,
    wind_turbulence: float = 0.5,
    collision_spheres: list[dict] | None = None,
) -> str:
    """Generate C# editor script to configure Unity Cloth component.

    Creates a menu item that adds/configures Cloth on the named mesh,
    sets up collision spheres, wind response, and vertex weights from
    cloth_type presets.

    Args:
        mesh_name: Name of the target GameObject in the scene.
        cloth_type: Preset type: cape, robe, hair, banner, cloth_armor.
        stiffness: Override stretching stiffness (0-1). None = use preset.
        damping: Override damping (0-1). None = use preset.
        wind_main: WindZone main wind strength multiplier.
        wind_turbulence: WindZone turbulence multiplier.
        collision_spheres: List of collision sphere dicts with
                          'transform_name' and 'radius' keys.

    Returns:
        Complete C# source string for editor script.
    """
    safe_name = sanitize_cs_identifier(mesh_name) or "CharacterCloth"
    safe_type = sanitize_cs_string(cloth_type)

    preset = _CLOTH_PRESETS.get(cloth_type, _CLOTH_PRESETS["cape"])

    stretch_val = stiffness if stiffness is not None else preset["stretching_stiffness"]
    bend_val = preset["bending_stiffness"]
    damp_val = damping if damping is not None else preset["damping"]
    wv_scale = preset["world_velocity_scale"]
    wa_scale = preset["world_acceleration_scale"]
    friction = preset["friction"]
    use_grav = "true" if preset["use_gravity"] else "false"

    ext_x = preset["external_acceleration_x"]
    ext_y = preset["external_acceleration_y"]
    ext_z = preset["external_acceleration_z"]
    rand_x = preset["random_acceleration_x"]
    rand_y = preset["random_acceleration_y"]
    rand_z = preset["random_acceleration_z"]

    # Collision sphere setup code
    sphere_lines = []
    if collision_spheres:
        sphere_lines.append("            // Setup collision spheres")
        sphere_lines.append("            var spherePairs = new System.Collections.Generic.List<ClothSphereColliderPair>();")
        for i, sphere in enumerate(collision_spheres):
            t_name = sanitize_cs_string(sphere.get("transform_name", "Hips"))
            radius = sphere.get("radius", 0.1)
            sphere_lines.append(f'            var sphere{i}Obj = GameObject.Find("{t_name}");')
            sphere_lines.append(f"            if (sphere{i}Obj != null)")
            sphere_lines.append("            {")
            sphere_lines.append(f"                var sc{i} = sphere{i}Obj.GetComponent<SphereCollider>();")
            sphere_lines.append(f"                if (sc{i} == null) sc{i} = sphere{i}Obj.AddComponent<SphereCollider>();")
            sphere_lines.append(f"                sc{i}.radius = {radius}f;")
            sphere_lines.append(f"                sc{i}.isTrigger = true;")
            sphere_lines.append(f'                spherePairs.Add(new ClothSphereColliderPair(sc{i}));')
            sphere_lines.append("            }")
        sphere_lines.append("            cloth.sphereColliders = spherePairs.ToArray();")
    sphere_code = "\n".join(sphere_lines)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_ClothSetup_{safe_name}
{{
    [MenuItem("VeilBreakers/Character/Setup Cloth - {safe_name}")]
    public static void Execute()
    {{
        try
        {{
            var target = GameObject.Find("{sanitize_cs_string(mesh_name)}");
            if (target == null)
            {{
                Debug.LogError("[VeilBreakers] Cannot find GameObject: {sanitize_cs_string(mesh_name)}");
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"cloth_setup\\", \\"message\\": \\"GameObject not found: {sanitize_cs_string(mesh_name)}\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                return;
            }}

            var smr = target.GetComponent<SkinnedMeshRenderer>();
            if (smr == null)
            {{
                Debug.LogError("[VeilBreakers] No SkinnedMeshRenderer on: {sanitize_cs_string(mesh_name)}");
                string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"cloth_setup\\", \\"message\\": \\"No SkinnedMeshRenderer on target\\"}}";
                File.WriteAllText("Temp/vb_result.json", json);
                return;
            }}

            Undo.RecordObject(target, "Setup Cloth Component");

            // Add or get Cloth component
            var cloth = target.GetComponent<Cloth>();
            if (cloth == null)
                cloth = Undo.AddComponent<Cloth>(target);

            // Configure cloth physics -- preset: {safe_type}
            cloth.stretchingStiffness = {stretch_val}f;
            cloth.bendingStiffness = {bend_val}f;
            cloth.damping = {damp_val}f;
            cloth.worldVelocityScale = {wv_scale}f;
            cloth.worldAccelerationScale = {wa_scale}f;
            cloth.friction = {friction}f;
            cloth.useGravity = {use_grav};
            cloth.externalAcceleration = new Vector3({ext_x}f, {ext_y}f, {ext_z}f);
            cloth.randomAcceleration = new Vector3({rand_x}f, {rand_y}f, {rand_z}f);

            // Auto-weight vertices: pin top 20% (weight=0), free bottom 50% (weight=1),
            // gradient in between
            var mesh = smr.sharedMesh;
            if (mesh != null)
            {{
                var vertices = mesh.vertices;
                var coefficients = new ClothSkinningCoefficient[vertices.Length];
                float minY = float.MaxValue, maxY = float.MinValue;
                foreach (var v in vertices)
                {{
                    if (v.y < minY) minY = v.y;
                    if (v.y > maxY) maxY = v.y;
                }}
                float range = maxY - minY;
                if (range < 0.001f) range = 1f;
                for (int i = 0; i < vertices.Length; i++)
                {{
                    float t = (vertices[i].y - minY) / range;
                    // Top vertices pinned, bottom vertices free
                    float maxDist = t < 0.8f ? Mathf.Lerp(0f, 1f, (0.8f - t) / 0.8f) : 0f;
                    coefficients[i] = new ClothSkinningCoefficient
                    {{
                        maxDistance = maxDist,
                        collisionSphereDistance = 0.01f
                    }};
                }}
                cloth.coefficients = coefficients;
            }}

{sphere_code}

            // Setup wind zone if not present
            var windZones = Object.FindObjectsByType<WindZone>(FindObjectsSortMode.None);
            if (windZones.Length == 0)
            {{
                var windObj = new GameObject("VB_WindZone");
                Undo.RegisterCreatedObjectUndo(windObj, "Create WindZone");
                var wind = windObj.AddComponent<WindZone>();
                wind.windMain = {wind_main}f;
                wind.windTurbulence = {wind_turbulence}f;
                wind.windPulseFrequency = 0.5f;
                wind.windPulseMagnitude = 0.3f;
                Debug.Log("[VeilBreakers] Created WindZone for cloth simulation");
            }}

            EditorUtility.SetDirty(target);
            string resultJson = "{{\\"status\\": \\"success\\", \\"action\\": \\"cloth_setup\\", \\"cloth_type\\": \\"{safe_type}\\", \\"mesh_name\\": \\"{sanitize_cs_string(mesh_name)}\\", \\"stretching_stiffness\\": {stretch_val}, \\"damping\\": {damp_val}}}";
            File.WriteAllText("Temp/vb_result.json", resultJson);
            Debug.Log("[VeilBreakers] Cloth configured on {sanitize_cs_string(mesh_name)} (type: {safe_type})");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"cloth_setup\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Cloth setup failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# CHAR-08: SSS Skin Shader
# ---------------------------------------------------------------------------


def generate_sss_skin_shader(
    sss_color: tuple[float, float, float, float] = (0.8, 0.3, 0.2, 1.0),
    sss_power: float = 3.0,
    sss_distortion: float = 0.5,
    sss_scale: float = 1.0,
) -> str:
    """Generate URP subsurface scattering approximation shader for character skin.

    Uses a wrapped diffuse + back-scattered light approximation for real-time
    SSS without ray tracing. Includes albedo, normal map, thickness map,
    and SSS color/power controls.

    Args:
        sss_color: RGBA color for subsurface scatter tint.
        sss_power: Falloff power for SSS effect (higher = tighter).
        sss_distortion: Normal distortion for back-scatter direction.
        sss_scale: Overall SSS intensity scale.

    Returns:
        Complete ShaderLab source string.
    """
    r, g, b, a = sss_color

    return f'''Shader "VeilBreakers/Character/SSS_Skin"
{{
    Properties
    {{
        _MainTex ("Albedo", 2D) = "white" {{}}
        _BumpMap ("Normal Map", 2D) = "bump" {{}}
        _BumpScale ("Normal Scale", Range(0, 2)) = 1.0
        _ThicknessMap ("Thickness Map", 2D) = "white" {{}}
        _SSSColor ("SSS Color", Color) = ({r}, {g}, {b}, {a})
        _SSSPower ("SSS Power", Range(0.1, 10)) = {sss_power}
        _SSSDistortion ("SSS Distortion", Range(0, 1)) = {sss_distortion}
        _SSSScale ("SSS Scale", Range(0, 5)) = {sss_scale}
        _Smoothness ("Smoothness", Range(0, 1)) = 0.3
        _Metallic ("Metallic", Range(0, 1)) = 0.0
        _OcclusionMap ("Occlusion", 2D) = "white" {{}}
        _DetailNormalMap ("Detail Normal", 2D) = "bump" {{}}
        _DetailNormalScale ("Detail Normal Scale", Range(0, 2)) = 0.5
        _DetailTiling ("Detail Tiling", Float) = 10.0
    }}

    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        LOD 300

        Pass
        {{
            Name "ForwardLit"
            Tags {{ "LightMode"="UniversalForward" }}

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT

            {_URP_CORE_INCLUDE}
            {_URP_LIGHTING_INCLUDE}

            struct Attributes
            {{
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
                float3 normalOS : NORMAL;
                float4 tangentOS : TANGENT;
            }};

            struct Varyings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 positionWS : TEXCOORD1;
                float3 normalWS : TEXCOORD2;
                float3 tangentWS : TEXCOORD3;
                float3 bitangentWS : TEXCOORD4;
                float4 shadowCoord : TEXCOORD5;
            }};

            TEXTURE2D(_MainTex);            SAMPLER(sampler_MainTex);
            TEXTURE2D(_BumpMap);            SAMPLER(sampler_BumpMap);
            TEXTURE2D(_ThicknessMap);       SAMPLER(sampler_ThicknessMap);
            TEXTURE2D(_OcclusionMap);       SAMPLER(sampler_OcclusionMap);
            TEXTURE2D(_DetailNormalMap);    SAMPLER(sampler_DetailNormalMap);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float _BumpScale;
                float4 _SSSColor;
                float _SSSPower;
                float _SSSDistortion;
                float _SSSScale;
                float _Smoothness;
                float _Metallic;
                float _DetailNormalScale;
                float _DetailTiling;
            CBUFFER_END

            // Subsurface scattering approximation
            // Based on GDC 2011 "Fast Subsurface Scattering" approach
            half3 SubsurfaceScatter(half3 lightDir, half3 viewDir, half3 normal,
                                     half thickness, half3 sssColor)
            {{
                // Distort light direction by surface normal
                half3 scatterDir = lightDir + normal * _SSSDistortion;
                half VdotL = saturate(dot(viewDir, -scatterDir));
                half sss = pow(VdotL, _SSSPower) * _SSSScale;

                // Modulate by thickness (thinner = more scatter)
                sss *= thickness;

                return sssColor * sss;
            }}

            Varyings vert(Attributes input)
            {{
                Varyings output;
                VertexPositionInputs posInputs = GetVertexPositionInputs(input.positionOS.xyz);
                VertexNormalInputs normInputs = GetVertexNormalInputs(input.normalOS, input.tangentOS);

                output.positionCS = posInputs.positionCS;
                output.positionWS = posInputs.positionWS;
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                output.normalWS = normInputs.normalWS;
                output.tangentWS = normInputs.tangentWS;
                output.bitangentWS = normInputs.bitangentWS;
                output.shadowCoord = GetShadowCoord(posInputs);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                // Sample textures
                half4 albedo = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv);
                half3 normalTS = UnpackNormalScale(
                    SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, input.uv), _BumpScale);
                half thickness = SAMPLE_TEXTURE2D(_ThicknessMap, sampler_ThicknessMap, input.uv).r;
                half occlusion = SAMPLE_TEXTURE2D(_OcclusionMap, sampler_OcclusionMap, input.uv).r;

                // Detail normal blending
                half2 detailUV = input.uv * _DetailTiling;
                half3 detailNormal = UnpackNormalScale(
                    SAMPLE_TEXTURE2D(_DetailNormalMap, sampler_DetailNormalMap, detailUV),
                    _DetailNormalScale);
                normalTS = normalize(half3(
                    normalTS.xy + detailNormal.xy, normalTS.z));

                // Transform normal to world space
                half3x3 tbn = half3x3(input.tangentWS, input.bitangentWS, input.normalWS);
                half3 normalWS = normalize(mul(normalTS, tbn));

                // Main light
                Light mainLight = GetMainLight(input.shadowCoord);
                half NdotL = saturate(dot(normalWS, mainLight.direction));

                // Wrapped diffuse for softer skin lighting
                half wrappedNdotL = saturate((dot(normalWS, mainLight.direction) + 0.5) / 1.5);

                // View direction
                half3 viewDir = normalize(GetWorldSpaceViewDir(input.positionWS));

                // SSS contribution
                half3 sss = SubsurfaceScatter(
                    mainLight.direction, viewDir, normalWS,
                    thickness, _SSSColor.rgb);

                // Specular (simple Blinn-Phong for skin)
                half3 halfDir = normalize(mainLight.direction + viewDir);
                half NdotH = saturate(dot(normalWS, halfDir));
                half specular = pow(NdotH, lerp(1.0, 256.0, _Smoothness)) * _Smoothness;

                // Combine
                half3 diffuse = albedo.rgb * wrappedNdotL * mainLight.color * mainLight.shadowAttenuation;
                half3 sssContrib = sss * mainLight.color * mainLight.shadowAttenuation;
                half3 spec = specular * mainLight.color * mainLight.shadowAttenuation;

                // Additional lights
                uint additionalLightCount = GetAdditionalLightsCount();
                for (uint i = 0u; i < additionalLightCount; i++)
                {{
                    Light addLight = GetAdditionalLight(i, input.positionWS);
                    half addNdotL = saturate((dot(normalWS, addLight.direction) + 0.5) / 1.5);
                    diffuse += albedo.rgb * addNdotL * addLight.color * addLight.distanceAttenuation * addLight.shadowAttenuation;
                    sssContrib += SubsurfaceScatter(addLight.direction, viewDir, normalWS,
                                                     thickness, _SSSColor.rgb) * addLight.color * addLight.distanceAttenuation;
                }}

                half3 ambient = SampleSH(normalWS) * albedo.rgb * occlusion;
                half3 finalColor = ambient + diffuse + sssContrib + spec;

                return half4(finalColor, 1.0);
            }}
            ENDHLSL
        }}

        // Shadow caster pass
        Pass
        {{
            Name "ShadowCaster"
            Tags {{ "LightMode"="ShadowCaster" }}
            ZWrite On
            ZTest LEqual
            ColorMask 0

            HLSLPROGRAM
            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag

            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            struct ShadowAttributes
            {{
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
            }};

            struct ShadowVaryings
            {{
                float4 positionCS : SV_POSITION;
            }};

            float3 _LightDirection;

            ShadowVaryings ShadowVert(ShadowAttributes input)
            {{
                ShadowVaryings output;
                float3 posWS = TransformObjectToWorld(input.positionOS.xyz);
                float3 normWS = TransformObjectToWorldNormal(input.normalOS);
                output.positionCS = TransformWorldToHClip(ApplyShadowBias(posWS, normWS, _LightDirection));
                return output;
            }}

            half4 ShadowFrag(ShadowVaryings input) : SV_Target
            {{
                return 0;
            }}
            ENDHLSL
        }}
    }}

    FallBack "Universal Render Pipeline/Lit"
}}
'''


# ---------------------------------------------------------------------------
# CHAR-08: Parallax Eye Shader
# ---------------------------------------------------------------------------


def generate_parallax_eye_shader(
    iris_depth: float = 0.3,
    pupil_scale: float = 0.3,
    ior: float = 1.33,
) -> str:
    """Generate URP parallax/refraction eye shader with iris depth.

    Creates a physically-inspired eye shader with:
    - Cornea refraction approximation via parallax offset
    - Iris depth (parallax mapping for depth illusion)
    - Pupil dilation control
    - Sclera, iris, and limbal ring color zones
    - Specular highlight for wet cornea look

    Args:
        iris_depth: Depth of iris parallax effect (0=flat, 1=deep).
        pupil_scale: Default pupil size (0=tiny, 1=fully dilated).
        ior: Index of refraction for cornea (water=1.33).

    Returns:
        Complete ShaderLab source string.
    """
    return f'''Shader "VeilBreakers/Character/ParallaxEye"
{{
    Properties
    {{
        _IrisTex ("Iris Texture", 2D) = "white" {{}}
        _ScleraTex ("Sclera Texture", 2D) = "white" {{}}
        _BumpMap ("Normal Map", 2D) = "bump" {{}}
        _IrisColor ("Iris Color", Color) = (0.3, 0.5, 0.2, 1.0)
        _ScleraColor ("Sclera Color", Color) = (0.95, 0.93, 0.90, 1.0)
        _PupilColor ("Pupil Color", Color) = (0.02, 0.02, 0.02, 1.0)
        _LimbalRingColor ("Limbal Ring", Color) = (0.1, 0.08, 0.05, 1.0)
        _LimbalRingWidth ("Limbal Ring Width", Range(0, 0.2)) = 0.05
        _IrisRadius ("Iris Radius", Range(0.1, 0.5)) = 0.35
        _PupilScale ("Pupil Scale", Range(0, 1)) = {pupil_scale}
        _IrisDepth ("Iris Depth", Range(0, 1)) = {iris_depth}
        _CorneaSmoothness ("Cornea Smoothness", Range(0.5, 1)) = 0.95
        _CorneaSpecular ("Cornea Specular", Range(0, 2)) = 1.5
        _IOR ("Index of Refraction", Range(1.0, 2.0)) = {ior}
    }}

    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        LOD 200

        Pass
        {{
            Name "ForwardLit"
            Tags {{ "LightMode"="UniversalForward" }}

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS

            {_URP_CORE_INCLUDE}
            {_URP_LIGHTING_INCLUDE}

            struct Attributes
            {{
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
                float3 normalOS : NORMAL;
                float4 tangentOS : TANGENT;
            }};

            struct Varyings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 positionWS : TEXCOORD1;
                float3 normalWS : TEXCOORD2;
                float3 tangentWS : TEXCOORD3;
                float3 bitangentWS : TEXCOORD4;
                float3 viewDirTS : TEXCOORD5;
            }};

            TEXTURE2D(_IrisTex);     SAMPLER(sampler_IrisTex);
            TEXTURE2D(_ScleraTex);   SAMPLER(sampler_ScleraTex);
            TEXTURE2D(_BumpMap);     SAMPLER(sampler_BumpMap);

            CBUFFER_START(UnityPerMaterial)
                float4 _IrisTex_ST;
                float4 _IrisColor;
                float4 _ScleraColor;
                float4 _PupilColor;
                float4 _LimbalRingColor;
                float _LimbalRingWidth;
                float _IrisRadius;
                float _PupilScale;
                float _IrisDepth;
                float _CorneaSmoothness;
                float _CorneaSpecular;
                float _IOR;
            CBUFFER_END

            Varyings vert(Attributes input)
            {{
                Varyings output;
                VertexPositionInputs posInputs = GetVertexPositionInputs(input.positionOS.xyz);
                VertexNormalInputs normInputs = GetVertexNormalInputs(input.normalOS, input.tangentOS);

                output.positionCS = posInputs.positionCS;
                output.positionWS = posInputs.positionWS;
                output.uv = TRANSFORM_TEX(input.uv, _IrisTex);
                output.normalWS = normInputs.normalWS;
                output.tangentWS = normInputs.tangentWS;
                output.bitangentWS = normInputs.bitangentWS;

                // View direction in tangent space for parallax
                float3 viewDirWS = GetWorldSpaceViewDir(posInputs.positionWS);
                float3x3 tbnMatrix = float3x3(normInputs.tangentWS,
                                                normInputs.bitangentWS,
                                                normInputs.normalWS);
                output.viewDirTS = mul(tbnMatrix, viewDirWS);

                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                // Parallax offset for iris depth (cornea refraction approximation)
                float3 viewTS = normalize(input.viewDirTS);
                float2 parallaxOffset = viewTS.xy / max(viewTS.z, 0.001) * _IrisDepth * 0.02;

                // Apply refraction-based offset
                float refractionFactor = 1.0 / _IOR;
                float2 refractedUV = input.uv + parallaxOffset * refractionFactor;

                // Distance from center (assumes eye UV centered at 0.5, 0.5)
                float2 centerOffset = refractedUV - float2(0.5, 0.5);
                float distFromCenter = length(centerOffset);

                // Iris/sclera boundary
                float irisEdge = smoothstep(_IrisRadius, _IrisRadius - 0.02, distFromCenter);

                // Pupil
                float pupilRadius = _PupilScale * _IrisRadius * 0.6;
                float pupilEdge = smoothstep(pupilRadius, pupilRadius - 0.01, distFromCenter);

                // Limbal ring (dark ring at iris/sclera boundary)
                float limbalInner = _IrisRadius - _LimbalRingWidth;
                float limbalEdge = smoothstep(limbalInner, limbalInner + 0.01, distFromCenter)
                                 * smoothstep(_IrisRadius + 0.01, _IrisRadius - 0.01, distFromCenter);

                // Sample textures
                half4 irisSample = SAMPLE_TEXTURE2D(_IrisTex, sampler_IrisTex, refractedUV);
                half4 scleraSample = SAMPLE_TEXTURE2D(_ScleraTex, sampler_ScleraTex, input.uv);

                // Compose eye color
                half3 irisCol = irisSample.rgb * _IrisColor.rgb;
                half3 scleraCol = scleraSample.rgb * _ScleraColor.rgb;
                half3 eyeColor = lerp(scleraCol, irisCol, irisEdge);
                eyeColor = lerp(eyeColor, _PupilColor.rgb, pupilEdge);
                eyeColor = lerp(eyeColor, _LimbalRingColor.rgb, limbalEdge * 0.7);

                // Normal mapping
                half3 normalTS = UnpackNormal(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, input.uv));
                half3x3 tbn = half3x3(input.tangentWS, input.bitangentWS, input.normalWS);
                half3 normalWS = normalize(mul(normalTS, tbn));

                // Lighting
                Light mainLight = GetMainLight();
                half NdotL = saturate(dot(normalWS, mainLight.direction));
                half3 viewDir = normalize(GetWorldSpaceViewDir(input.positionWS));

                // Specular (sharp highlight for wet cornea)
                half3 halfDir = normalize(mainLight.direction + viewDir);
                half NdotH = saturate(dot(normalWS, halfDir));
                half specPower = lerp(64.0, 512.0, _CorneaSmoothness);
                half specular = pow(NdotH, specPower) * _CorneaSpecular;

                // Fresnel for cornea rim
                half fresnel = pow(1.0 - saturate(dot(viewDir, normalWS)), 4.0) * 0.3;

                half3 ambient = SampleSH(normalWS) * eyeColor;
                half3 diffuse = eyeColor * NdotL * mainLight.color;
                half3 spec = specular * mainLight.color;

                half3 finalColor = ambient + diffuse + spec + fresnel;

                return half4(finalColor, 1.0);
            }}
            ENDHLSL
        }}
    }}

    FallBack "Universal Render Pipeline/Lit"
}}
'''


# ---------------------------------------------------------------------------
# CHAR-08: Micro-detail normal compositor script
# ---------------------------------------------------------------------------


def generate_micro_detail_normal_script(
    base_normal_property: str = "_BumpMap",
    detail_normal_property: str = "_DetailNormalMap",
    detail_tiling: float = 10.0,
    detail_strength: float = 0.5,
) -> str:
    """Generate C# editor script for micro-detail normal map compositing.

    Creates a runtime component that composites base normal + micro-detail
    normal at configurable tiling and strength. Used for AAA character heads
    with pore-level detail.

    Args:
        base_normal_property: Shader property name for base normal map.
        detail_normal_property: Shader property name for detail normal.
        detail_tiling: UV tiling for micro-detail normal overlay.
        detail_strength: Blend strength of micro-detail layer (0-1).

    Returns:
        Complete C# source string for runtime component.
    """
    safe_base = sanitize_cs_string(base_normal_property)
    safe_detail = sanitize_cs_string(detail_normal_property)

    return f'''using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Runtime component that manages micro-detail normal map compositing
/// for AAA character head rendering. Allows per-material control of
/// detail tiling and strength at runtime.
/// </summary>
[ExecuteAlways]
[RequireComponent(typeof(Renderer))]
public class MicroDetailNormalCompositor : MonoBehaviour
{{
    [Header("Normal Map References")]
    [Tooltip("Base normal map (face-level detail)")]
    public Texture2D baseNormalMap;

    [Tooltip("Micro-detail normal map (pore/wrinkle level)")]
    public Texture2D detailNormalMap;

    [Header("Detail Settings")]
    [Tooltip("UV tiling for micro-detail overlay")]
    [Range(1f, 50f)]
    public float detailTiling = {detail_tiling}f;

    [Tooltip("Blend strength of micro-detail layer")]
    [Range(0f, 1f)]
    public float detailStrength = {detail_strength}f;

    [Header("Shader Properties")]
    [Tooltip("Shader property name for base normal")]
    public string baseNormalProperty = "{safe_base}";

    [Tooltip("Shader property name for detail normal")]
    public string detailNormalProperty = "{safe_detail}";

    [Tooltip("Shader property name for detail tiling")]
    public string detailTilingProperty = "_DetailTiling";

    [Tooltip("Shader property name for detail strength")]
    public string detailStrengthProperty = "_DetailNormalScale";

    private Renderer _renderer;
    private MaterialPropertyBlock _mpb;
    private int _baseNormalId;
    private int _detailNormalId;
    private int _detailTilingId;
    private int _detailStrengthId;

    void OnEnable()
    {{
        _renderer = GetComponent<Renderer>();
        _mpb = new MaterialPropertyBlock();
        CachePropertyIds();
        ApplyProperties();
    }}

    void CachePropertyIds()
    {{
        _baseNormalId = Shader.PropertyToID(baseNormalProperty);
        _detailNormalId = Shader.PropertyToID(detailNormalProperty);
        _detailTilingId = Shader.PropertyToID(detailTilingProperty);
        _detailStrengthId = Shader.PropertyToID(detailStrengthProperty);
    }}

    /// <summary>
    /// Apply current settings to the material via MaterialPropertyBlock.
    /// Call this after changing any properties at runtime.
    /// </summary>
    public void ApplyProperties()
    {{
        if (_renderer == null) return;

        _renderer.GetPropertyBlock(_mpb);

        if (baseNormalMap != null)
            _mpb.SetTexture(_baseNormalId, baseNormalMap);
        if (detailNormalMap != null)
            _mpb.SetTexture(_detailNormalId, detailNormalMap);

        _mpb.SetFloat(_detailTilingId, detailTiling);
        _mpb.SetFloat(_detailStrengthId, detailStrength);

        _renderer.SetPropertyBlock(_mpb);
    }}

    /// <summary>
    /// Set detail strength at runtime (e.g., for distance-based LOD fading).
    /// </summary>
    public void SetDetailStrength(float strength)
    {{
        detailStrength = Mathf.Clamp01(strength);
        ApplyProperties();
    }}

    /// <summary>
    /// Set detail tiling at runtime.
    /// </summary>
    public void SetDetailTiling(float tiling)
    {{
        detailTiling = Mathf.Max(1f, tiling);
        ApplyProperties();
    }}

    void OnValidate()
    {{
        if (_renderer != null)
        {{
            CachePropertyIds();
            ApplyProperties();
        }}
    }}

    void OnDisable()
    {{
        // Clear property block to restore original material values
        if (_renderer != null)
        {{
            _renderer.SetPropertyBlock(null);
        }}
    }}
}}

#if UNITY_EDITOR
[CustomEditor(typeof(MicroDetailNormalCompositor))]
public class MicroDetailNormalCompositorEditor : Editor
{{
    public override void OnInspectorGUI()
    {{
        DrawDefaultInspector();

        var comp = (MicroDetailNormalCompositor)target;
        EditorGUILayout.Space();
        if (GUILayout.Button("Apply Properties"))
        {{
            comp.ApplyProperties();
        }}

        EditorGUILayout.HelpBox(
            "This component composites a micro-detail normal map over the base " +
            "normal map for AAA-quality character skin rendering. The detail map " +
            "adds pore-level and wrinkle detail at a higher tiling rate.",
            MessageType.Info);
    }}
}}
#endif
'''
