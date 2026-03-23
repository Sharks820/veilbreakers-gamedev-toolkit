"""HLSL shader template generators for Unity URP.

Each function returns a complete ShaderLab source string (.shader file)
targeting the Universal Render Pipeline. Generated shaders follow the
pattern:

    Shader "VeilBreakers/{Name}" {
        Properties { ... }
        SubShader {
            Tags { ... }
            Pass { HLSLPROGRAM ... ENDHLSL }
        }
    }

All shaders include the URP Core.hlsl include path.

Exports:
    generate_corruption_shader      -- VFX-06: corruption amount 0-1
    generate_dissolve_shader        -- VFX-07: noise-based dissolve with edge glow
    generate_force_field_shader     -- VFX-07: fresnel + intersection highlight
    generate_water_shader           -- VFX-07: wave displacement + transparency
    generate_foliage_shader         -- VFX-07: wind sway vertex animation
    generate_outline_shader         -- VFX-07: two-pass outline rendering
    generate_damage_overlay_shader  -- VFX-07: fullscreen damage overlay
    generate_arbitrary_shader       -- SHDR-01: configurable HLSL/ShaderLab shader
    generate_renderer_feature       -- SHDR-02: URP ScriptableRendererFeature + RenderGraph pass
    generate_anisotropic_hair_shader -- AAA: Kajiya-Kay anisotropic hair shading
    generate_terrain_blend_shader    -- AAA: height-based terrain material blending
    generate_ice_crystal_shader      -- AAA: stylized ice/crystal shader (SURGE/GRACE)
"""

from __future__ import annotations

import re

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier

_URP_CORE_INCLUDE = '#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"'


def _safe_type(type_str: str) -> str:
    """Sanitize a C# type expression to prevent code injection.

    Allows alphanumerics, underscores, angle brackets (generics), square
    brackets (arrays), dots (namespaces), commas (generic params), and
    ``?`` (nullable).
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_<>\[\].,?]", "", type_str)
    return sanitized or "object"


_CS_RESERVED = frozenset({
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char",
    "checked", "class", "const", "continue", "decimal", "default", "delegate",
    "do", "double", "else", "enum", "event", "explicit", "extern", "false",
    "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit",
    "in", "int", "interface", "internal", "is", "lock", "long", "namespace",
    "new", "null", "object", "operator", "out", "override", "params", "private",
    "protected", "public", "readonly", "ref", "return", "sbyte", "sealed",
    "short", "sizeof", "stackalloc", "static", "string", "struct", "switch",
    "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked",
    "unsafe", "ushort", "using", "virtual", "void", "volatile", "while",
})


def _safe_namespace(ns: str) -> str:
    """Sanitize a C# namespace to prevent code injection.

    Valid C# namespaces allow only letters, digits, underscores, and dots.
    Segments starting with a digit get a ``_`` prefix, and segments that
    are C# reserved words get an ``@`` prefix.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_.]", "", ns)
    sanitized = re.sub(r"\.{2,}", ".", sanitized).strip(".")
    if not sanitized:
        return "Generated"
    segments = sanitized.split(".")
    fixed: list[str] = []
    for seg in segments:
        if not seg:
            continue
        if seg[0].isdigit():
            seg = f"_{seg}"
        if seg in _CS_RESERVED:
            seg = f"@{seg}"
        fixed.append(seg)
    return ".".join(fixed) or "Generated"


# ---------------------------------------------------------------------------
# VFX-06: Corruption shader
# ---------------------------------------------------------------------------


def generate_corruption_shader(
    corruption_color: tuple[float, float, float, float] = (0.2, 0.0, 0.4, 1.0),
    vein_scale: float = 5.0,
) -> str:
    """Generate HLSL corruption shader with _CorruptionAmount property.

    Lerps base albedo toward corruption color based on _CorruptionAmount (0-1).
    Adds noise-based vein pattern that intensifies with corruption level.

    Args:
        corruption_color: RGBA color at full corruption.
        vein_scale: Scale factor for noise-based vein pattern.

    Returns:
        Complete ShaderLab source string.
    """
    r, g, b, a = corruption_color

    return f'''Shader "VeilBreakers/Corruption"
{{
    Properties
    {{
        _MainTex ("Base Texture", 2D) = "white" {{}}
        _CorruptionAmount ("Corruption Amount", Range(0, 1)) = 0
        _CorruptionColor ("Corruption Color", Color) = ({r}, {g}, {b}, {a})
        _VeinScale ("Vein Pattern Scale", Float) = {vein_scale}
        _VeinIntensity ("Vein Intensity", Range(0, 1)) = 0.5
        _PulseSpeed ("Pulse Speed", Float) = 2.0
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
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT

            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

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
                float3 viewDirWS : TEXCOORD3;
                float4 shadowCoord : TEXCOORD4;
            }};

            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float _CorruptionAmount;
                float4 _CorruptionColor;
                float _VeinScale;
                float _VeinIntensity;
                float _PulseSpeed;
            CBUFFER_END

            // Simple noise function for vein pattern
            float hash(float2 p)
            {{
                return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453);
            }}

            float noise(float2 p)
            {{
                float2 i = floor(p);
                float2 f = frac(p);
                f = f * f * (3.0 - 2.0 * f);
                float a = hash(i);
                float b = hash(i + float2(1.0, 0.0));
                float c = hash(i + float2(0.0, 1.0));
                float d = hash(i + float2(1.0, 1.0));
                return lerp(lerp(a, b, f.x), lerp(c, d, f.x), f.y);
            }}

            Varyings vert(Attributes input)
            {{
                Varyings output;
                VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);
                output.positionCS = vertexInput.positionCS;
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                output.positionWS = vertexInput.positionWS;
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.viewDirWS = GetWorldSpaceNormalizeViewDir(vertexInput.positionWS);
                output.shadowCoord = GetShadowCoord(vertexInput);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                // Sample base texture
                half4 baseColor = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv);

                // Generate noise-based vein pattern
                float2 veinUV = input.uv * _VeinScale;
                float veinNoise = noise(veinUV + _Time.y * _PulseSpeed * 0.1);
                float veinPattern = smoothstep(0.4, 0.6, veinNoise) * _VeinIntensity;

                // Lerp toward corruption color based on _CorruptionAmount
                half4 corruptedColor = lerp(baseColor, _CorruptionColor, _CorruptionAmount);

                // Add vein pattern scaled by corruption amount
                corruptedColor.rgb += veinPattern * _CorruptionAmount * _CorruptionColor.rgb;

                // URP Lighting
                float3 normalWS = normalize(input.normalWS);
                Light mainLight = GetMainLight(input.shadowCoord);
                float NdotL = saturate(dot(normalWS, mainLight.direction));
                half3 diffuse = mainLight.color * NdotL * mainLight.shadowAttenuation * mainLight.distanceAttenuation;
                half3 ambient = SampleSH(normalWS);

                // Corruption emissive glow from veins
                half3 emissive = veinPattern * _CorruptionAmount * _CorruptionColor.rgb * 2.0;

                // Specular highlight (Blinn-Phong)
                float3 halfDir = normalize(mainLight.direction + normalize(input.viewDirWS));
                float spec = pow(saturate(dot(normalWS, halfDir)), 32.0) * mainLight.shadowAttenuation;
                half3 specular = mainLight.color * spec * 0.3;

                // Additional lights
                uint additionalLightCount = GetAdditionalLightsCount();
                for (uint li = 0u; li < additionalLightCount; li++)
                {{
                    Light addLight = GetAdditionalLight(li, input.positionWS);
                    float addNdotL = saturate(dot(normalWS, addLight.direction));
                    diffuse += addLight.color * addNdotL * addLight.shadowAttenuation * addLight.distanceAttenuation;
                }}

                half3 finalColor = corruptedColor.rgb * (diffuse + ambient) + specular + emissive;
                return half4(finalColor, corruptedColor.a);
            }}
            ENDHLSL
        }}

        // ShadowCaster pass -- objects cast shadows
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
                #if UNITY_REVERSED_Z
                output.positionCS.z = min(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #else
                output.positionCS.z = max(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                return output;
            }}

            half4 ShadowFrag(ShadowVaryings input) : SV_TARGET
            {{
                return 0;
            }}
            ENDHLSL
        }}

        // DepthOnly pass for depth prepass
        Pass
        {{
            Name "DepthOnly"
            Tags {{ "LightMode"="DepthOnly" }}
            ZWrite On
            ColorMask R

            HLSLPROGRAM
            #pragma vertex DepthVert
            #pragma fragment DepthFrag

            {_URP_CORE_INCLUDE}

            struct DepthAttributes
            {{
                float4 positionOS : POSITION;
            }};

            struct DepthVaryings
            {{
                float4 positionCS : SV_POSITION;
            }};

            DepthVaryings DepthVert(DepthAttributes input)
            {{
                DepthVaryings output;
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                return output;
            }}

            half4 DepthFrag(DepthVaryings input) : SV_TARGET
            {{
                return 0;
            }}
            ENDHLSL
        }}

        Pass
        {{
            Name "ShadowCaster"
            Tags {{ "LightMode" = "ShadowCaster" }}
            ZWrite On
            ColorMask 0

            HLSLPROGRAM
            #pragma vertex ShadowPassVertex
            #pragma fragment ShadowPassFragment
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/ShadowCasterPass.hlsl"
            ENDHLSL
        }}
    }}

    FallBack "Universal Render Pipeline/Lit"
}}
'''


# ---------------------------------------------------------------------------
# VFX-07: Dissolve shader
# ---------------------------------------------------------------------------


def generate_dissolve_shader(
    edge_color: tuple[float, float, float, float] = (1.0, 0.5, 0.0, 1.0),
    edge_width: float = 0.05,
) -> str:
    """Generate HLSL dissolve shader with noise-based clip and edge glow.

    Args:
        edge_color: RGBA color for dissolve edge glow.
        edge_width: Width of the glowing dissolve edge.

    Returns:
        Complete ShaderLab source string.
    """
    r, g, b, a = edge_color

    return f'''Shader "VeilBreakers/Dissolve"
{{
    Properties
    {{
        _MainTex ("Base Texture", 2D) = "white" {{}}
        _NoiseTex ("Noise Texture", 2D) = "white" {{}}
        _DissolveAmount ("Dissolve Amount", Range(0, 1)) = 0
        _EdgeWidth ("Edge Width", Float) = {edge_width}
        _EdgeColor ("Edge Color", Color) = ({r}, {g}, {b}, {a})
        _EdgeEmission ("Edge Emission Strength", Float) = 3.0
    }}

    SubShader
    {{
        Tags {{ "RenderType"="TransparentCutout" "RenderPipeline"="UniversalPipeline" "Queue"="AlphaTest" }}
        LOD 200

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
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Attributes
            {{
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
                float3 normalOS : NORMAL;
            }};

            struct Varyings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 positionWS : TEXCOORD2;
                float3 viewDirWS : TEXCOORD3;
                float4 shadowCoord : TEXCOORD4;
            }};

            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);
            TEXTURE2D(_NoiseTex);
            SAMPLER(sampler_NoiseTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float4 _NoiseTex_ST;
                float _DissolveAmount;
                float _EdgeWidth;
                float4 _EdgeColor;
                float _EdgeEmission;
            CBUFFER_END

            Varyings vert(Attributes input)
            {{
                Varyings output;
                VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);
                output.positionCS = vertexInput.positionCS;
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.positionWS = vertexInput.positionWS;
                output.viewDirWS = GetWorldSpaceNormalizeViewDir(vertexInput.positionWS);
                output.shadowCoord = GetShadowCoord(vertexInput);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                half4 baseColor = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv);
                float noiseVal = SAMPLE_TEXTURE2D(_NoiseTex, sampler_NoiseTex, input.uv).r;

                // Clip pixels below dissolve threshold
                float dissolveThreshold = noiseVal - _DissolveAmount;
                clip(dissolveThreshold);

                // Edge glow -- pixels near the dissolve boundary
                float edgeFactor = 1.0 - smoothstep(0.0, _EdgeWidth, dissolveThreshold);
                half3 edgeGlow = _EdgeColor.rgb * edgeFactor * _EdgeEmission;

                // URP Lighting
                float3 normalWS = normalize(input.normalWS);
                Light mainLight = GetMainLight(input.shadowCoord);
                float NdotL = saturate(dot(normalWS, mainLight.direction));
                half3 diffuse = mainLight.color * NdotL * mainLight.shadowAttenuation * mainLight.distanceAttenuation;
                half3 ambient = SampleSH(normalWS);

                // Specular
                float3 halfDir = normalize(mainLight.direction + normalize(input.viewDirWS));
                float spec = pow(saturate(dot(normalWS, halfDir)), 32.0) * mainLight.shadowAttenuation;
                half3 specular = mainLight.color * spec * 0.2;

                // Additional lights
                uint additionalLightCount = GetAdditionalLightsCount();
                for (uint li = 0u; li < additionalLightCount; li++)
                {{
                    Light addLight = GetAdditionalLight(li, input.positionWS);
                    float addNdotL = saturate(dot(normalWS, addLight.direction));
                    diffuse += addLight.color * addNdotL * addLight.shadowAttenuation * addLight.distanceAttenuation;
                }}

                half3 finalColor = baseColor.rgb * (diffuse + ambient) + specular + edgeGlow;
                return half4(finalColor, baseColor.a);
            }}
            ENDHLSL
        }}

        // ShadowCaster pass with dissolve clip
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

            TEXTURE2D(_NoiseTex);
            SAMPLER(sampler_NoiseTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float4 _NoiseTex_ST;
                float _DissolveAmount;
                float _EdgeWidth;
                float4 _EdgeColor;
                float _EdgeEmission;
            CBUFFER_END

            struct ShadowAttributes
            {{
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float2 uv : TEXCOORD0;
            }};

            struct ShadowVaryings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
            }};

            float3 _LightDirection;

            ShadowVaryings ShadowVert(ShadowAttributes input)
            {{
                ShadowVaryings output;
                float3 posWS = TransformObjectToWorld(input.positionOS.xyz);
                float3 normWS = TransformObjectToWorldNormal(input.normalOS);
                output.positionCS = TransformWorldToHClip(ApplyShadowBias(posWS, normWS, _LightDirection));
                #if UNITY_REVERSED_Z
                output.positionCS.z = min(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #else
                output.positionCS.z = max(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                output.uv = input.uv * _NoiseTex_ST.xy + _NoiseTex_ST.zw;
                return output;
            }}

            half4 ShadowFrag(ShadowVaryings input) : SV_TARGET
            {{
                float noiseVal = SAMPLE_TEXTURE2D(_NoiseTex, sampler_NoiseTex, input.uv).r;
                clip(noiseVal - _DissolveAmount);
                return 0;
            }}
            ENDHLSL
        }}

        Pass
        {{
            Name "ShadowCaster"
            Tags {{ "LightMode" = "ShadowCaster" }}
            ZWrite On
            ColorMask 0

            HLSLPROGRAM
            #pragma vertex ShadowPassVertex
            #pragma fragment ShadowPassFragment
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/ShadowCasterPass.hlsl"
            ENDHLSL
        }}
    }}

    FallBack "Universal Render Pipeline/Lit"
}}
'''


# ---------------------------------------------------------------------------
# VFX-07: Force field shader
# ---------------------------------------------------------------------------


def generate_force_field_shader(
    field_color: tuple[float, float, float, float] = (0.2, 0.6, 1.0, 0.5),
    fresnel_power: float = 3.0,
) -> str:
    """Generate HLSL force field shader with fresnel and depth-based intersection.

    Args:
        field_color: RGBA color for the force field.
        fresnel_power: Exponent for fresnel rim effect.

    Returns:
        Complete ShaderLab source string.
    """
    r, g, b, a = field_color

    return f'''Shader "VeilBreakers/ForceField"
{{
    Properties
    {{
        _FieldColor ("Field Color", Color) = ({r}, {g}, {b}, {a})
        _FresnelPower ("Fresnel Power", Float) = {fresnel_power}
        _IntersectionWidth ("Intersection Width", Float) = 0.5
        _IntersectionColor ("Intersection Color", Color) = (1, 1, 1, 1)
        _PulseSpeed ("Pulse Speed", Float) = 1.0
        _DistortionStrength ("Distortion", Float) = 0.02
    }}

    SubShader
    {{
        Tags {{ "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" }}
        LOD 200
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        Pass
        {{
            Name "ForwardLit"
            Tags {{ "LightMode"="UniversalForward" }}

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile_fog

            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"

            struct Attributes
            {{
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float2 uv : TEXCOORD0;
            }};

            struct Varyings
            {{
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 viewDirWS : TEXCOORD2;
                float4 screenPos : TEXCOORD3;
            }};

            CBUFFER_START(UnityPerMaterial)
                float4 _FieldColor;
                float _FresnelPower;
                float _IntersectionWidth;
                float4 _IntersectionColor;
                float _PulseSpeed;
                float _DistortionStrength;
            CBUFFER_END

            Varyings vert(Attributes input)
            {{
                Varyings output;
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.positionWS = TransformObjectToWorld(input.positionOS.xyz);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.viewDirWS = GetWorldSpaceNormalizeViewDir(output.positionWS);
                output.screenPos = ComputeScreenPos(output.positionCS);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                // Fresnel rim effect
                float fresnel = pow(1.0 - saturate(dot(input.normalWS, input.viewDirWS)), _FresnelPower);

                // Scene depth intersection highlight
                float2 screenUV = input.screenPos.xy / input.screenPos.w;
                float sceneDepth = LinearEyeDepth(SampleSceneDepth(screenUV), _ZBufferParams);
                float fragDepth = input.screenPos.w;
                float depthDiff = abs(sceneDepth - fragDepth);
                float intersection = 1.0 - saturate(depthDiff / _IntersectionWidth);

                // Combine fresnel and intersection
                float pulse = sin(_Time.y * _PulseSpeed) * 0.5 + 0.5;
                half4 col = _FieldColor;
                col.a *= fresnel + intersection * 0.5;
                col.rgb += _IntersectionColor.rgb * intersection;
                col.rgb += _FieldColor.rgb * pulse * 0.2;

                return col;
            }}
            ENDHLSL
        }}

        Pass
        {{
            Name "ShadowCaster"
            Tags {{ "LightMode" = "ShadowCaster" }}
            ZWrite On
            ColorMask 0

            HLSLPROGRAM
            #pragma vertex ShadowPassVertex
            #pragma fragment ShadowPassFragment
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/ShadowCasterPass.hlsl"
            ENDHLSL
        }}
    }}

    FallBack Off
}}
'''


# ---------------------------------------------------------------------------
# VFX-07: Water shader
# ---------------------------------------------------------------------------


def generate_water_shader(
    water_color: tuple[float, float, float, float] = (0.1, 0.3, 0.5, 0.8),
    wave_speed: float = 1.0,
    wave_amplitude: float = 0.2,
) -> str:
    """Generate HLSL water shader with wave vertex displacement and transparency.

    Args:
        water_color: RGBA base water color.
        wave_speed: Speed of wave animation.
        wave_amplitude: Height of wave displacement.

    Returns:
        Complete ShaderLab source string.
    """
    r, g, b, a = water_color

    return f'''Shader "VeilBreakers/Water"
{{
    Properties
    {{
        _WaterColor ("Water Color", Color) = ({r}, {g}, {b}, {a})
        _WaveSpeed ("Wave Speed", Float) = {wave_speed}
        _WaveAmplitude ("Wave Amplitude", Float) = {wave_amplitude}
        _WaveFrequency ("Wave Frequency", Float) = 2.0
        _NormalTex ("Normal Map", 2D) = "bump" {{}}
        _Transparency ("Transparency", Range(0, 1)) = 0.7
        _RefractionStrength ("Refraction Strength", Float) = 0.1
    }}

    SubShader
    {{
        Tags {{ "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" }}
        LOD 200
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off

        Pass
        {{
            Name "ForwardLit"
            Tags {{ "LightMode"="UniversalForward" }}

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile_fog

            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Attributes
            {{
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
                float3 normalOS : NORMAL;
            }};

            struct Varyings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 positionWS : TEXCOORD1;
                float3 normalWS : TEXCOORD2;
                float3 viewDirWS : TEXCOORD3;
            }};

            TEXTURE2D(_NormalTex);
            SAMPLER(sampler_NormalTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _WaterColor;
                float _WaveSpeed;
                float _WaveAmplitude;
                float _WaveFrequency;
                float4 _NormalTex_ST;
                float _Transparency;
                float _RefractionStrength;
            CBUFFER_END

            Varyings vert(Attributes input)
            {{
                Varyings output;

                // Wave vertex displacement on Y axis
                float3 worldPos = TransformObjectToWorld(input.positionOS.xyz);
                float wave1 = sin(worldPos.x * _WaveFrequency + _Time.y * _WaveSpeed) * _WaveAmplitude;
                float wave2 = cos(worldPos.z * _WaveFrequency * 0.7 + _Time.y * _WaveSpeed * 0.8) * _WaveAmplitude * 0.5;
                input.positionOS.y += wave1 + wave2;

                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.uv = TRANSFORM_TEX(input.uv, _NormalTex);
                output.positionWS = TransformObjectToWorld(input.positionOS.xyz);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.viewDirWS = GetWorldSpaceNormalizeViewDir(output.positionWS);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                // Animated normal map for surface detail
                float2 uvOffset1 = input.uv + _Time.y * _WaveSpeed * 0.05;
                float2 uvOffset2 = input.uv * 1.5 - _Time.y * _WaveSpeed * 0.03;
                half3 normal1 = UnpackNormal(SAMPLE_TEXTURE2D(_NormalTex, sampler_NormalTex, uvOffset1));
                half3 normal2 = UnpackNormal(SAMPLE_TEXTURE2D(_NormalTex, sampler_NormalTex, uvOffset2));
                half3 combinedNormal = normalize(normal1 + normal2);

                // Perturb world normal with tangent-space normal map
                float3 normalWS = normalize(input.normalWS + combinedNormal * 0.5);

                // URP Lighting
                Light mainLight = GetMainLight();
                float NdotL = saturate(dot(normalWS, mainLight.direction));
                half3 diffuse = mainLight.color * NdotL;
                half3 ambient = SampleSH(normalWS);

                // Water specular highlights (GGX-style sharp reflections)
                float3 halfDir = normalize(mainLight.direction + normalize(input.viewDirWS));
                float spec = pow(saturate(dot(normalWS, halfDir)), 128.0);
                half3 specular = mainLight.color * spec * 1.5;

                // Fresnel for edge transparency / refraction approximation
                float fresnel = pow(1.0 - saturate(dot(normalWS, normalize(input.viewDirWS))), 4.0);

                // Final water color with lighting
                half4 col = _WaterColor;
                col.rgb = col.rgb * (diffuse + ambient) + specular;
                col.rgb += fresnel * 0.3;
                col.a = lerp(_Transparency, 1.0, fresnel);

                return col;
            }}
            ENDHLSL
        }}

        Pass
        {{
            Name "ShadowCaster"
            Tags {{ "LightMode" = "ShadowCaster" }}
            ZWrite On
            ColorMask 0

            HLSLPROGRAM
            #pragma vertex ShadowPassVertex
            #pragma fragment ShadowPassFragment
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/ShadowCasterPass.hlsl"
            ENDHLSL
        }}
    }}

    FallBack "Universal Render Pipeline/Lit"
}}
'''


# ---------------------------------------------------------------------------
# VFX-07: Foliage shader
# ---------------------------------------------------------------------------


def generate_foliage_shader(
    wind_strength: float = 0.1,
    wind_speed: float = 1.5,
) -> str:
    """Generate HLSL foliage shader with wind sway vertex animation.

    Uses _Time and sin/cos for procedural wind animation on vertices,
    with optional subsurface scattering approximation for leaves.

    Args:
        wind_strength: Maximum vertex displacement from wind.
        wind_speed: Speed of wind oscillation.

    Returns:
        Complete ShaderLab source string.
    """
    return f'''Shader "VeilBreakers/Foliage"
{{
    Properties
    {{
        _MainTex ("Base Texture", 2D) = "white" {{}}
        _WindStrength ("Wind Strength", Float) = {wind_strength}
        _WindSpeed ("Wind Speed", Float) = {wind_speed}
        _WindDirection ("Wind Direction", Vector) = (1, 0, 0.5, 0)
        _SubsurfaceColor ("Subsurface Color", Color) = (0.4, 0.6, 0.1, 1)
        _SubsurfaceStrength ("Subsurface Strength", Range(0, 1)) = 0.3
        _Cutoff ("Alpha Cutoff", Range(0, 1)) = 0.5
    }}

    SubShader
    {{
        Tags {{ "RenderType"="TransparentCutout" "RenderPipeline"="UniversalPipeline" "Queue"="AlphaTest" }}
        LOD 200
        Cull Off

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
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Attributes
            {{
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
                float3 normalOS : NORMAL;
                float4 color : COLOR;  // Vertex color: R = wind influence weight
            }};

            struct Varyings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 positionWS : TEXCOORD2;
                float3 viewDirWS : TEXCOORD3;
                float4 shadowCoord : TEXCOORD4;
            }};

            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float _WindStrength;
                float _WindSpeed;
                float4 _WindDirection;
                float4 _SubsurfaceColor;
                float _SubsurfaceStrength;
                float _Cutoff;
            CBUFFER_END

            Varyings vert(Attributes input)
            {{
                Varyings output;

                // Wind sway using _Time, sin, and cos
                float windWeight = input.color.r;  // vertex color R channel
                float3 worldPos = TransformObjectToWorld(input.positionOS.xyz);

                float windPhase = _Time.y * _WindSpeed;
                float swayX = sin(windPhase + worldPos.x * 0.5) * _WindStrength * windWeight;
                float swayZ = cos(windPhase * 0.7 + worldPos.z * 0.3) * _WindStrength * windWeight * 0.5;

                float3 windOffset = normalize(_WindDirection.xyz) * swayX;
                windOffset.z += swayZ;
                input.positionOS.xyz += mul(unity_WorldToObject, float4(windOffset, 0)).xyz;

                VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);
                output.positionCS = vertexInput.positionCS;
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.positionWS = vertexInput.positionWS;
                output.viewDirWS = GetWorldSpaceNormalizeViewDir(vertexInput.positionWS);
                output.shadowCoord = GetShadowCoord(vertexInput);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                half4 baseColor = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv);
                clip(baseColor.a - _Cutoff);

                float3 normalWS = normalize(input.normalWS);

                // URP main light with shadows
                Light mainLight = GetMainLight(input.shadowCoord);
                float NdotL = dot(normalWS, mainLight.direction);

                // Diffuse lighting (wrapped for softer foliage look)
                float wrappedNdotL = saturate(NdotL * 0.5 + 0.5);
                half3 diffuse = mainLight.color * wrappedNdotL * mainLight.shadowAttenuation * mainLight.distanceAttenuation;
                half3 ambient = SampleSH(normalWS);

                // Subsurface scattering approximation (light through leaves)
                float subsurface = saturate(-NdotL) * _SubsurfaceStrength;
                half3 sssColor = _SubsurfaceColor.rgb * subsurface * mainLight.color * mainLight.shadowAttenuation;

                // Additional lights
                uint additionalLightCount = GetAdditionalLightsCount();
                for (uint li = 0u; li < additionalLightCount; li++)
                {{
                    Light addLight = GetAdditionalLight(li, input.positionWS);
                    float addNdotL = saturate(dot(normalWS, addLight.direction) * 0.5 + 0.5);
                    diffuse += addLight.color * addNdotL * addLight.shadowAttenuation * addLight.distanceAttenuation;
                }}

                half3 finalColor = baseColor.rgb * (diffuse + ambient) + sssColor;
                return half4(finalColor, baseColor.a);
            }}
            ENDHLSL
        }}

        // ShadowCaster pass with alpha clip for foliage
        Pass
        {{
            Name "ShadowCaster"
            Tags {{ "LightMode"="ShadowCaster" }}
            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull Off

            HLSLPROGRAM
            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag

            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float _WindStrength;
                float _WindSpeed;
                float4 _WindDirection;
                float4 _SubsurfaceColor;
                float _SubsurfaceStrength;
                float _Cutoff;
            CBUFFER_END

            struct ShadowAttributes
            {{
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float2 uv : TEXCOORD0;
                float4 color : COLOR;
            }};

            struct ShadowVaryings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
            }};

            float3 _LightDirection;

            ShadowVaryings ShadowVert(ShadowAttributes input)
            {{
                ShadowVaryings output;
                // Apply wind to shadow as well
                float windWeight = input.color.r;
                float3 worldPos = TransformObjectToWorld(input.positionOS.xyz);
                float windPhase = _Time.y * _WindSpeed;
                float swayX = sin(windPhase + worldPos.x * 0.5) * _WindStrength * windWeight;
                float3 windOffset = normalize(_WindDirection.xyz) * swayX;
                input.positionOS.xyz += mul(unity_WorldToObject, float4(windOffset, 0)).xyz;

                float3 posWS = TransformObjectToWorld(input.positionOS.xyz);
                float3 normWS = TransformObjectToWorldNormal(input.normalOS);
                output.positionCS = TransformWorldToHClip(ApplyShadowBias(posWS, normWS, _LightDirection));
                #if UNITY_REVERSED_Z
                output.positionCS.z = min(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #else
                output.positionCS.z = max(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                output.uv = input.uv * _MainTex_ST.xy + _MainTex_ST.zw;
                return output;
            }}

            half4 ShadowFrag(ShadowVaryings input) : SV_TARGET
            {{
                half4 tex = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv);
                clip(tex.a - _Cutoff);
                return 0;
            }}
            ENDHLSL
        }}
    }}

    FallBack "Universal Render Pipeline/Lit"
}}
'''


# ---------------------------------------------------------------------------
# VFX-07: Outline shader
# ---------------------------------------------------------------------------


def generate_outline_shader(
    outline_color: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
    outline_width: float = 0.02,
) -> str:
    """Generate HLSL outline shader with two-pass rendering.

    Pass 1: Enlarged backface extrusion for outline silhouette.
    Pass 2: Normal forward rendering of the object.

    Args:
        outline_color: RGBA color for the outline.
        outline_width: Thickness of the outline in world units.

    Returns:
        Complete ShaderLab source string.
    """
    r, g, b, a = outline_color

    return f'''Shader "VeilBreakers/Outline"
{{
    Properties
    {{
        _MainTex ("Base Texture", 2D) = "white" {{}}
        _OutlineColor ("Outline Color", Color) = ({r}, {g}, {b}, {a})
        _OutlineWidth ("Outline Width", Float) = {outline_width}
        _Color ("Tint", Color) = (1, 1, 1, 1)
    }}

    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        LOD 200

        // Pass 1: Outline -- enlarged backface extrusion
        Pass
        {{
            Name "Outline"
            Cull Front
            ZWrite On

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile_fog

            {_URP_CORE_INCLUDE}

            struct Attributes
            {{
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
            }};

            struct Varyings
            {{
                float4 positionCS : SV_POSITION;
            }};

            CBUFFER_START(UnityPerMaterial)
                float4 _OutlineColor;
                float _OutlineWidth;
                float4 _MainTex_ST;
                float4 _Color;
            CBUFFER_END

            Varyings vert(Attributes input)
            {{
                Varyings output;
                // Extrude vertices along normals for outline
                float3 extruded = input.positionOS.xyz + input.normalOS * _OutlineWidth;
                output.positionCS = TransformObjectToHClip(extruded);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                return _OutlineColor;
            }}
            ENDHLSL
        }}

        // Pass 2: Normal forward rendering with full URP lighting
        Pass
        {{
            Name "ForwardLit"
            Tags {{ "LightMode"="UniversalForward" }}
            Cull Back

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT

            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Attributes
            {{
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
                float3 normalOS : NORMAL;
            }};

            struct Varyings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 positionWS : TEXCOORD2;
                float3 viewDirWS : TEXCOORD3;
                float4 shadowCoord : TEXCOORD4;
            }};

            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _OutlineColor;
                float _OutlineWidth;
                float4 _MainTex_ST;
                float4 _Color;
            CBUFFER_END

            Varyings vert(Attributes input)
            {{
                Varyings output;
                VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);
                output.positionCS = vertexInput.positionCS;
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.positionWS = vertexInput.positionWS;
                output.viewDirWS = GetWorldSpaceNormalizeViewDir(vertexInput.positionWS);
                output.shadowCoord = GetShadowCoord(vertexInput);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                half4 baseColor = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv) * _Color;
                float3 normalWS = normalize(input.normalWS);

                // URP main light with shadows
                Light mainLight = GetMainLight(input.shadowCoord);
                float NdotL = saturate(dot(normalWS, mainLight.direction));
                half3 diffuse = mainLight.color * NdotL * mainLight.shadowAttenuation * mainLight.distanceAttenuation;
                half3 ambient = SampleSH(normalWS);

                // Specular
                float3 halfDir = normalize(mainLight.direction + normalize(input.viewDirWS));
                float spec = pow(saturate(dot(normalWS, halfDir)), 64.0) * mainLight.shadowAttenuation;
                half3 specular = mainLight.color * spec * 0.3;

                // Additional lights
                uint additionalLightCount = GetAdditionalLightsCount();
                for (uint li = 0u; li < additionalLightCount; li++)
                {{
                    Light addLight = GetAdditionalLight(li, input.positionWS);
                    float addNdotL = saturate(dot(normalWS, addLight.direction));
                    diffuse += addLight.color * addNdotL * addLight.shadowAttenuation * addLight.distanceAttenuation;
                }}

                half3 finalColor = baseColor.rgb * (diffuse + ambient) + specular;
                return half4(finalColor, baseColor.a);
            }}
            ENDHLSL
        }}

        // ShadowCaster pass
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
                #if UNITY_REVERSED_Z
                output.positionCS.z = min(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #else
                output.positionCS.z = max(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                return output;
            }}

            half4 ShadowFrag(ShadowVaryings input) : SV_TARGET
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
# VFX-07: Damage overlay shader
# ---------------------------------------------------------------------------


def generate_damage_overlay_shader(
    overlay_color: tuple[float, float, float, float] = (0.5, 0.0, 0.0, 0.6),
) -> str:
    """Generate HLSL fullscreen damage overlay shader.

    Renders a fullscreen pass with blood/damage texture overlay. Alpha is
    controlled by _Intensity property for fade-in/out.

    Args:
        overlay_color: RGBA base overlay color.

    Returns:
        Complete ShaderLab source string.
    """
    r, g, b, a = overlay_color

    return f'''Shader "VeilBreakers/DamageOverlay"
{{
    Properties
    {{
        _MainTex ("Overlay Texture", 2D) = "white" {{}}
        _Intensity ("Intensity", Range(0, 1)) = 0
        _OverlayColor ("Overlay Color", Color) = ({r}, {g}, {b}, {a})
        _VignetteStrength ("Vignette Strength", Float) = 1.5
    }}

    SubShader
    {{
        Tags {{ "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Overlay" }}
        LOD 100
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        ZTest Always
        Cull Off

        Pass
        {{
            Name "DamageOverlay"

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile_fog

            {_URP_CORE_INCLUDE}

            struct Attributes
            {{
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
            }};

            struct Varyings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
            }};

            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float _Intensity;
                float4 _OverlayColor;
                float _VignetteStrength;
            CBUFFER_END

            Varyings vert(Attributes input)
            {{
                Varyings output;
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                // Sample overlay texture
                half4 overlayTex = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv);

                // Vignette effect -- darken edges for blood splatter look
                float2 centeredUV = input.uv * 2.0 - 1.0;
                float vignette = 1.0 - dot(centeredUV, centeredUV) * 0.5;
                vignette = saturate(pow(vignette, _VignetteStrength));
                float edgeDarken = 1.0 - vignette;

                // Blend overlay color with texture
                half4 finalColor = _OverlayColor * overlayTex;
                finalColor.a *= _Intensity * (edgeDarken + 0.2);

                return finalColor;
            }}
            ENDHLSL
        }}
    }}

    FallBack Off
}}
'''


# ---------------------------------------------------------------------------
# SHDR-01: Arbitrary shader builder
# ---------------------------------------------------------------------------


def _sanitize_shader_name(name: str) -> str:
    """Remove characters that are invalid in a Shader path string."""
    return re.sub(r'[^A-Za-z0-9_ /]', '', name).strip()


def _sanitize_shader_identifier(name: str) -> str:
    """Sanitize a string into a valid HLSL identifier."""
    sanitized = re.sub(r'[^A-Za-z0-9_]', '', name)
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
    return sanitized or '_Unnamed'


_RENDER_TYPE_DEFAULTS: dict[str, dict[str, str]] = {
    'Opaque': {'queue': 'Geometry', 'zwrite': 'On', 'blend': ''},
    'Transparent': {'queue': 'Transparent', 'zwrite': 'Off', 'blend': 'SrcAlpha OneMinusSrcAlpha'},
    'TransparentCutout': {'queue': 'AlphaTest', 'zwrite': 'On', 'blend': ''},
}

_VALID_CULL_VALUES = frozenset({'Off', 'Front', 'Back'})
_VALID_ZWRITE_VALUES = frozenset({'On', 'Off'})
_VALID_BLEND_TOKENS = frozenset({
    'One', 'Zero', 'SrcColor', 'SrcAlpha', 'DstColor', 'DstAlpha',
    'OneMinusSrcColor', 'OneMinusSrcAlpha', 'OneMinusDstColor', 'OneMinusDstAlpha',
})


def _sanitize_display_name(name: str) -> str:
    """Escape a display name for safe embedding inside ShaderLab quoted strings."""
    return name.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', '')


def _validate_cull(value: str) -> str:
    """Validate a cull value against known ShaderLab cull modes."""
    if value in _VALID_CULL_VALUES:
        return value
    return 'Back'


def _validate_zwrite(value: str) -> str:
    """Validate a zwrite value against known ShaderLab modes."""
    if value in _VALID_ZWRITE_VALUES:
        return value
    return 'On'


def _validate_blend(value: str) -> str:
    """Validate a blend string against known ShaderLab blend factor tokens."""
    if not value:
        return ''
    tokens = value.split()
    for token in tokens:
        if token not in _VALID_BLEND_TOKENS:
            return ''
    return value


def _build_property_line(prop: dict) -> str:
    """Build a single ShaderLab Properties line from a property dict."""
    name = _sanitize_shader_identifier(prop.get('name', '_Unnamed'))
    display = _sanitize_display_name(prop.get('display_name', name.lstrip('_')))
    ptype = prop.get('type', 'Float')
    default = prop.get('default', '')

    if ptype == 'Color':
        default = default or '(1,1,1,1)'
        return f'        {name} ("{display}", Color) = {default}'
    elif ptype == 'Vector':
        default = default or '(0,0,0,0)'
        return f'        {name} ("{display}", Vector) = {default}'
    elif ptype == '2D':
        default = default or '"white" {}'
        return f'        {name} ("{display}", 2D) = {default}'
    elif ptype == '3D':
        default = default or '"" {}'
        return f'        {name} ("{display}", 3D) = {default}'
    elif ptype == 'Cube':
        default = default or '"" {}'
        return f'        {name} ("{display}", Cube) = {default}'
    elif ptype.startswith('Range'):
        default = default or '0'
        return f'        {name} ("{display}", {ptype}) = {default}'
    else:
        # Float or any other type
        default = default or '0'
        return f'        {name} ("{display}", Float) = {default}'


_TEXTURE_TYPE_MAP: dict[str, str] = {
    '2D': 'TEXTURE2D',
    '3D': 'TEXTURE3D',
    'Cube': 'TEXTURECUBE',
}


def _hlsl_type_for_property(prop: dict) -> str | None:
    """Return the HLSL variable type for a shader property."""
    ptype = prop.get('type', 'Float')
    if ptype == 'Color':
        return 'float4'
    elif ptype == 'Vector':
        return 'float4'
    elif ptype in _TEXTURE_TYPE_MAP:
        return None  # textures handled separately
    else:
        return 'float'


def generate_arbitrary_shader(
    shader_name: str,
    shader_path: str = "VeilBreakers/Custom",
    render_type: str = "Opaque",
    queue: str = "",
    properties: list[dict] | None = None,
    vertex_code: str = "",
    fragment_code: str = "",
    tags: dict | None = None,
    pragma_directives: list[str] | None = None,
    include_paths: list[str] | None = None,
    cull: str = "Back",
    zwrite: str = "",
    blend: str = "",
    two_passes: bool = False,
    second_pass_vertex: str = "",
    second_pass_fragment: str = "",
) -> str:
    """Generate a complete, configurable HLSL/ShaderLab shader for URP.

    Produces a full .shader file with ShaderLab wrapper, Properties block,
    SubShader tags, and one or two HLSL passes with configurable vertex/fragment
    programs.

    Args:
        shader_name: Display name for the shader (sanitized for path safety).
        shader_path: Shader menu path prefix (e.g. ``"VeilBreakers/Custom"``).
        render_type: ``"Opaque"`` | ``"Transparent"`` | ``"TransparentCutout"``.
        queue: Render queue override; auto-derived from *render_type* if empty.
        properties: List of property dicts, each with ``name``, ``display_name``,
            ``type`` (``"Float"`` | ``"Range(min,max)"`` | ``"Color"`` | ``"Vector"``
            | ``"2D"`` | ``"3D"`` | ``"Cube"``), and ``default``.
        vertex_code: Custom vertex shader body. If empty, a standard transform is
            generated.
        fragment_code: Custom fragment shader body. If empty, returns white.
        tags: Extra SubShader tags merged with the auto-generated ones.
        pragma_directives: Extra ``#pragma`` lines (e.g. ``"#pragma multi_compile_fog"``).
        include_paths: Extra ``#include`` paths beyond the default URP Core include.
        cull: ``"Back"`` | ``"Front"`` | ``"Off"``.
        zwrite: ``"On"`` | ``"Off"``; auto-derived from *render_type* if empty.
        blend: Blend mode string (e.g. ``"SrcAlpha OneMinusSrcAlpha"``); auto-derived
            from *render_type* if empty.
        two_passes: If ``True``, a second Pass block is appended.
        second_pass_vertex: Vertex code for the second pass.
        second_pass_fragment: Fragment code for the second pass.

    Returns:
        Complete ShaderLab source string targeting URP.
    """
    # Sanitize
    safe_name = _sanitize_shader_name(shader_name) or 'CustomShader'
    safe_path = _sanitize_shader_name(shader_path) or 'VeilBreakers/Custom'

    # Defaults from render type
    rt_defaults = _RENDER_TYPE_DEFAULTS.get(render_type, _RENDER_TYPE_DEFAULTS['Opaque'])
    effective_queue = queue or rt_defaults['queue']
    effective_zwrite = _validate_zwrite(zwrite or rt_defaults['zwrite'])
    effective_blend = _validate_blend(blend or rt_defaults['blend'])

    # Validate cull
    cull = _validate_cull(cull)

    props = properties or []

    # --- Properties block ---
    prop_lines = []
    for p in props:
        prop_lines.append(_build_property_line(p))
    properties_block = '\n'.join(prop_lines)

    # --- SubShader tags ---
    merged_tags = {
        'RenderType': render_type,
        'RenderPipeline': 'UniversalPipeline',
        'Queue': effective_queue,
    }
    if tags:
        merged_tags.update(tags)
    tags_str = ' '.join(f'"{sanitize_cs_string(k)}"="{sanitize_cs_string(v)}"' for k, v in merged_tags.items())

    # --- Render state lines ---
    render_state_lines = []
    if effective_blend:
        render_state_lines.append(f'        Blend {effective_blend}')
    render_state_lines.append(f'        ZWrite {effective_zwrite}')
    if cull != 'Back':
        render_state_lines.append(f'        Cull {cull}')
    render_state = '\n'.join(render_state_lines)

    # --- CBUFFER variable declarations ---
    cbuffer_vars = []
    texture_decls = []
    for p in props:
        hlsl_type = _hlsl_type_for_property(p)
        pname = _sanitize_shader_identifier(p.get('name', '_Unnamed'))
        if hlsl_type is None:
            # Texture declaration
            tex_macro = _TEXTURE_TYPE_MAP.get(p.get('type', '2D'), 'TEXTURE2D')
            texture_decls.append(f'            {tex_macro}({pname});')
            texture_decls.append(f'            SAMPLER(sampler{pname});')
            cbuffer_vars.append(f'                float4 {pname}_ST;')
        else:
            cbuffer_vars.append(f'                {hlsl_type} {pname};')

    texture_block = '\n'.join(texture_decls)
    cbuffer_content = '\n'.join(cbuffer_vars)

    cbuffer_block = ''
    if cbuffer_vars:
        cbuffer_block = f'''
            CBUFFER_START(UnityPerMaterial)
{cbuffer_content}
            CBUFFER_END'''

    # --- Pragma directives ---
    extra_pragmas = ''
    if pragma_directives:
        extra_pragmas = '\n'.join(f'            {d}' for d in pragma_directives)
        extra_pragmas = '\n' + extra_pragmas

    # --- Include paths ---
    extra_includes = ''
    if include_paths:
        extra_includes = '\n'.join(f'            #include "{p}"' for p in include_paths)
        extra_includes = '\n' + extra_includes

    # --- Vertex function ---
    if vertex_code:
        vert_body = vertex_code
    else:
        vert_body = '''Varyings output;
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.uv = input.uv;
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.positionWS = TransformObjectToWorld(input.positionOS.xyz);
                return output;'''

    # --- Fragment function ---
    if fragment_code:
        frag_body = fragment_code
    else:
        frag_body = 'return half4(1, 1, 1, 1);'

    # --- Build pass ---
    def _build_pass(v_body: str, f_body: str, pass_name: str = 'ForwardLit') -> str:
        return f'''        Pass
        {{
            Name "{pass_name}"
            Tags {{ "LightMode"="UniversalForward" }}

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile_fog{extra_pragmas}

            {_URP_CORE_INCLUDE}{extra_includes}

            struct Attributes
            {{
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
                float3 normalOS : NORMAL;
            }};

            struct Varyings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 positionWS : TEXCOORD2;
            }};

{texture_block}
{cbuffer_block}

            Varyings vert(Attributes input)
            {{
                {v_body}
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                {f_body}
            }}
            ENDHLSL
        }}'''

    pass1 = _build_pass(vert_body, frag_body, 'ForwardLit')

    pass2 = ''
    if two_passes:
        second_v = second_pass_vertex or vert_body
        second_f = second_pass_fragment or frag_body
        pass2 = '\n\n' + _build_pass(second_v, second_f, 'SecondPass')

    return f'''Shader "{safe_path}/{safe_name}"
{{
    Properties
    {{
{properties_block}
    }}

    SubShader
    {{
        Tags {{ {tags_str} }}
        LOD 200
{render_state}

{pass1}{pass2}
    }}

    FallBack "Hidden/InternalErrorShader"
}}
'''


# ---------------------------------------------------------------------------
# SHDR-02: URP ScriptableRendererFeature + RenderGraph pass
# ---------------------------------------------------------------------------


def _sanitize_cs_attribute(attr: str) -> str:
    """Sanitize a C# attribute expression (e.g. ``Range(0f, 1f)``).

    Allows alphanumerics, underscores, parentheses, commas, dots, spaces,
    and quotes -- the characters valid inside a C# attribute declaration.
    Strips everything else to prevent code injection while preserving
    typical attribute syntax.
    """
    sanitized = re.sub(r'[^A-Za-z0-9_().,\s"\']', '', attr)
    return sanitized


_VALID_RENDER_PASS_EVENTS = frozenset({
    'BeforeRendering', 'BeforeRenderingShadows', 'AfterRenderingShadows',
    'BeforeRenderingPrePasses', 'AfterRenderingPrePasses',
    'BeforeRenderingGbuffer', 'AfterRenderingGbuffer',
    'BeforeRenderingDeferredLights', 'AfterRenderingDeferredLights',
    'BeforeRenderingOpaques', 'AfterRenderingOpaques',
    'BeforeRenderingSkybox', 'AfterRenderingSkybox',
    'BeforeRenderingTransparents', 'AfterRenderingTransparents',
    'BeforeRenderingPostProcessing', 'AfterRenderingPostProcessing',
    'AfterRendering',
})


def generate_renderer_feature(
    feature_name: str,
    namespace: str = "",
    settings_fields: list[dict] | None = None,
    render_pass_event: str = "BeforeRenderingPostProcessing",
    shader_property_name: str = "_shader",
    material_properties: list[dict] | None = None,
    pass_code: str = "",
) -> str:
    """Generate a URP ScriptableRendererFeature with RenderGraph render pass.

    Produces TWO C# classes in a single file:

    1. ``{feature_name}Feature`` -- extends ``ScriptableRendererFeature`` with
       shader/material lifecycle, settings serialization, and pass enqueueing.
    2. ``{feature_name}Pass`` -- extends ``ScriptableRenderPass`` using the
       modern ``RecordRenderGraph`` API (URP 17 / Unity 6). Does **not**
       implement the legacy ``Execute()`` method.

    Args:
        feature_name: Base name (e.g. ``"CustomBloom"``). ``Feature`` / ``Pass``
            suffixes are appended automatically.
        namespace: Optional C# namespace wrapper.
        settings_fields: List of settings field dicts, each with ``type``,
            ``name``, ``default``, and optional ``attribute``.
        render_pass_event: URP ``RenderPassEvent`` enum value for pass
            scheduling.
        shader_property_name: Name of the ``Shader`` serialized field on the
            feature class.
        material_properties: List of material property dicts (``name``, ``type``,
            ``value``) set on the material each frame in ``RecordRenderGraph``.
        pass_code: Custom body for ``RecordRenderGraph``. If empty, a default
            blit-and-copy-back pass is generated.

    Returns:
        Complete C# source string with required ``using`` directives.
    """
    safe_name = sanitize_cs_identifier(feature_name)

    # Sanitize shader_property_name to prevent C# injection
    shader_property_name = sanitize_cs_identifier(shader_property_name) or '_shader'

    # Validate render_pass_event against known enum values
    if render_pass_event not in _VALID_RENDER_PASS_EVENTS:
        render_pass_event = 'BeforeRenderingPostProcessing'
    feature_cls = f'{safe_name}Feature'
    pass_cls = f'{safe_name}Pass'
    settings_cls = f'{safe_name}Settings'

    fields = settings_fields or []

    # --- Settings class body ---
    settings_body_lines = []
    for f in fields:
        attr = _sanitize_cs_attribute(f.get('attribute', '')) if f.get('attribute', '') else ''
        ftype = _safe_type(f.get('type', 'float'))
        fname = sanitize_cs_identifier(f.get('name', 'value')) or 'value'
        fdefault = sanitize_cs_string(str(f.get('default', ''))) if f.get('default', '') else ''
        attr_line = f'        [{attr}] ' if attr else '        '
        default_part = f' = {fdefault};' if fdefault else ';'
        settings_body_lines.append(f'{attr_line}public {ftype} {fname}{default_part}')

    settings_body = '\n'.join(settings_body_lines) if settings_body_lines else '        // No settings fields'

    # --- Material property set calls ---
    mat_prop_calls = []
    for mp in (material_properties or []):
        mp_name = sanitize_cs_string(mp.get('name', '_Value'))
        mp_type = mp.get('type', 'float')
        mp_value = sanitize_cs_string(mp.get('value', '0f'))
        setter = 'SetFloat'
        if mp_type == 'int':
            setter = 'SetInt'
        elif mp_type == 'Color':
            setter = 'SetColor'
        elif mp_type == 'Vector':
            setter = 'SetVector'
        elif mp_type == 'Texture':
            setter = 'SetTexture'
        mat_prop_calls.append(f'            _material.{setter}("{mp_name}", {mp_value});')

    mat_prop_block = '\n'.join(mat_prop_calls)

    # --- RecordRenderGraph body ---
    if pass_code:
        record_body = pass_code
    else:
        record_body = f'''var resourceData = frameData.Get<UniversalResourceData>();
            if (resourceData.isActiveTargetBackBuffer) return;

            var src = resourceData.activeColorTexture;
            var desc = renderGraph.GetTextureDesc(src);
            desc.depthBufferBits = 0;
            var dst = renderGraph.CreateTexture(desc);

{mat_prop_block}

            var blitParams = new RenderGraphUtils.BlitMaterialParameters(src, dst, _material, 0);
            renderGraph.AddBlitPass(blitParams, "{safe_name}");

            var copyBack = new RenderGraphUtils.BlitMaterialParameters(dst, src, _material, 0);
            renderGraph.AddBlitPass(copyBack, "{safe_name}CopyBack");'''

    # --- Namespace handling ---
    indent = ''
    ns_open = ''
    ns_close = ''
    if namespace:
        indent = '    '
        ns_open = f'namespace {_safe_namespace(namespace)}\n{{\n'
        ns_close = '\n}'

    source = f'''using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.Rendering.RenderGraphModule;

{ns_open}{indent}public class {feature_cls} : ScriptableRendererFeature
{indent}{{
{indent}    [SerializeField] private Shader {shader_property_name};
{indent}    [SerializeField] private {settings_cls} _settings;
{indent}    private Material _material;
{indent}    private {pass_cls} _pass;

{indent}    public override void Create()
{indent}    {{
{indent}        if ({shader_property_name} != null)
{indent}            _material = CoreUtils.CreateEngineMaterial({shader_property_name});
{indent}        _pass = new {pass_cls}(_material, _settings);
{indent}        _pass.renderPassEvent = RenderPassEvent.{render_pass_event};
{indent}    }}

{indent}    public override void AddRenderPasses(ScriptableRenderer renderer, ref RenderingData renderingData)
{indent}    {{
{indent}        if (_material != null && renderingData.cameraData.cameraType == CameraType.Game)
{indent}            renderer.EnqueuePass(_pass);
{indent}    }}

{indent}    protected override void Dispose(bool disposing)
{indent}    {{
{indent}        CoreUtils.Destroy(_material);
{indent}    }}

{indent}    [System.Serializable]
{indent}    public class {settings_cls}
{indent}    {{
{indent}{settings_body}
{indent}    }}
{indent}}}

{indent}public class {pass_cls} : ScriptableRenderPass
{indent}{{
{indent}    private Material _material;
{indent}    private {feature_cls}.{settings_cls} _settings;

{indent}    public {pass_cls}(Material material, {feature_cls}.{settings_cls} settings)
{indent}    {{
{indent}        _material = material;
{indent}        _settings = settings;
{indent}    }}

{indent}    public override void RecordRenderGraph(RenderGraph renderGraph, ContextContainer frameData)
{indent}    {{
{indent}        {record_body}
{indent}    }}
{indent}}}{ns_close}
'''

    return source


# ---------------------------------------------------------------------------
# AAA: Anisotropic hair shader (Kajiya-Kay)
# ---------------------------------------------------------------------------


def generate_anisotropic_hair_shader(
    hair_color: tuple[float, float, float, float] = (0.15, 0.1, 0.07, 1.0),
    specular_shift1: float = 0.1,
    specular_shift2: float = -0.1,
) -> str:
    """Generate Kajiya-Kay anisotropic hair shader for URP.

    Dual-specular model with tangent-based highlights, alpha-to-coverage
    transparency, backface rendering, and subsurface scattering
    approximation through thin strands.  Targets FFXVI / God of War quality.

    Args:
        hair_color: RGBA base hair color.
        specular_shift1: Tangent shift for primary (narrow, bright) specular.
        specular_shift2: Tangent shift for secondary (wide, colored) specular.

    Returns:
        Complete ShaderLab source string.
    """
    r, g, b, a = hair_color

    return f'''Shader "VeilBreakers/AnisotropicHair"
{{
    Properties
    {{
        _MainTex ("Hair Texture", 2D) = "white" {{}}
        _HairColor ("Hair Color", Color) = ({r}, {g}, {b}, {a})
        _SpecularColor1 ("Primary Specular Color", Color) = (1, 1, 1, 1)
        _SpecularColor2 ("Secondary Specular Color", Color) = (0.8, 0.6, 0.4, 1)
        _SpecularShift1 ("Primary Specular Shift", Float) = {specular_shift1}
        _SpecularShift2 ("Secondary Specular Shift", Float) = {specular_shift2}
        _SpecularWidth1 ("Primary Specular Width", Range(1, 256)) = 64
        _SpecularWidth2 ("Secondary Specular Width", Range(1, 256)) = 16
        _AlphaCutoff ("Alpha Cutoff", Range(0, 1)) = 0.5
        _FlowMap ("Flow / Tangent Map", 2D) = "bump" {{}}
        _SSSStrength ("SSS Strength", Range(0, 1)) = 0.3
        _SSSColor ("SSS Color", Color) = (0.6, 0.3, 0.15, 1)
    }}

    SubShader
    {{
        Tags {{ "RenderType"="TransparentCutout" "RenderPipeline"="UniversalPipeline" "Queue"="AlphaTest" }}
        LOD 300
        Cull Off
        AlphaToMask On

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
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

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
                float3 viewDirWS : TEXCOORD5;
                float4 shadowCoord : TEXCOORD6;
            }};

            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);
            TEXTURE2D(_FlowMap);
            SAMPLER(sampler_FlowMap);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float4 _HairColor;
                float4 _SpecularColor1;
                float4 _SpecularColor2;
                float _SpecularShift1;
                float _SpecularShift2;
                float _SpecularWidth1;
                float _SpecularWidth2;
                float _AlphaCutoff;
                float4 _FlowMap_ST;
                float _SSSStrength;
                float4 _SSSColor;
            CBUFFER_END

            // Kajiya-Kay specular term along tangent direction
            float KajiyaKaySpecular(float3 T, float3 H, float exponent)
            {{
                float TdotH = dot(T, H);
                float sinTH = sqrt(1.0 - TdotH * TdotH);
                return pow(saturate(sinTH), exponent);
            }}

            Varyings vert(Attributes input)
            {{
                Varyings output;
                VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);
                output.positionCS = vertexInput.positionCS;
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                output.positionWS = vertexInput.positionWS;
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                float3 tangentWS = TransformObjectToWorldDir(input.tangentOS.xyz);
                output.tangentWS = normalize(tangentWS);
                output.bitangentWS = normalize(cross(output.normalWS, tangentWS) * input.tangentOS.w);
                output.viewDirWS = GetWorldSpaceNormalizeViewDir(vertexInput.positionWS);
                output.shadowCoord = GetShadowCoord(vertexInput);
                return output;
            }}

            half4 frag(Varyings input, half facing : VFACE) : SV_Target
            {{
                // Sample hair texture
                half4 hairTex = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv);
                half4 baseColor = hairTex * _HairColor;

                // Alpha-to-coverage clip
                clip(hairTex.a - _AlphaCutoff);

                // Flip normal for backface rendering
                float3 normalWS = normalize(input.normalWS) * (facing > 0 ? 1.0 : -1.0);

                // Sample flow map to modulate tangent direction
                half3 flowSample = SAMPLE_TEXTURE2D(_FlowMap, sampler_FlowMap, input.uv).xyz * 2.0 - 1.0;
                float3 T = normalize(input.tangentWS + flowSample.x * input.bitangentWS * 0.5);

                // URP main light
                Light mainLight = GetMainLight(input.shadowCoord);
                float3 L = mainLight.direction;
                float3 V = normalize(input.viewDirWS);
                float3 H = normalize(L + V);
                float NdotL = saturate(dot(normalWS, L));

                // Dual Kajiya-Kay specular highlights
                float3 T1 = normalize(T + normalWS * _SpecularShift1);
                float3 T2 = normalize(T + normalWS * _SpecularShift2);

                float spec1 = KajiyaKaySpecular(T1, H, _SpecularWidth1);
                float spec2 = KajiyaKaySpecular(T2, H, _SpecularWidth2);

                half3 specular1 = _SpecularColor1.rgb * spec1;
                half3 specular2 = _SpecularColor2.rgb * spec2;

                // Diffuse lighting
                half3 diffuse = mainLight.color * NdotL * mainLight.shadowAttenuation * mainLight.distanceAttenuation;
                half3 ambient = SampleSH(normalWS);

                // Subsurface scattering approximation through thin strands
                float sssNdotL = saturate(-dot(normalWS, L) * 0.5 + 0.5);
                half3 sss = _SSSColor.rgb * sssNdotL * _SSSStrength * mainLight.color * mainLight.shadowAttenuation;

                // Additional lights
                uint additionalLightCount = GetAdditionalLightsCount();
                for (uint li = 0u; li < additionalLightCount; li++)
                {{
                    Light addLight = GetAdditionalLight(li, input.positionWS);
                    float addNdotL = saturate(dot(normalWS, addLight.direction));
                    diffuse += addLight.color * addNdotL * addLight.shadowAttenuation * addLight.distanceAttenuation;

                    // Additional light specular
                    float3 addH = normalize(addLight.direction + V);
                    float addSpec1 = KajiyaKaySpecular(T1, addH, _SpecularWidth1);
                    specular1 += _SpecularColor1.rgb * addSpec1 * addLight.color * addLight.shadowAttenuation * addLight.distanceAttenuation;
                }}

                half3 totalSpecular = (specular1 + specular2) * mainLight.shadowAttenuation;
                half3 finalColor = baseColor.rgb * (diffuse + ambient) + totalSpecular + sss;
                return half4(finalColor, hairTex.a);
            }}
            ENDHLSL
        }}

        // ShadowCaster pass with alpha clip for hair strands
        Pass
        {{
            Name "ShadowCaster"
            Tags {{ "LightMode"="ShadowCaster" }}
            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull Off

            HLSLPROGRAM
            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag

            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float4 _HairColor;
                float4 _SpecularColor1;
                float4 _SpecularColor2;
                float _SpecularShift1;
                float _SpecularShift2;
                float _SpecularWidth1;
                float _SpecularWidth2;
                float _AlphaCutoff;
                float4 _FlowMap_ST;
                float _SSSStrength;
                float4 _SSSColor;
            CBUFFER_END

            struct ShadowAttributes
            {{
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float2 uv : TEXCOORD0;
            }};

            struct ShadowVaryings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
            }};

            float3 _LightDirection;

            ShadowVaryings ShadowVert(ShadowAttributes input)
            {{
                ShadowVaryings output;
                float3 posWS = TransformObjectToWorld(input.positionOS.xyz);
                float3 normWS = TransformObjectToWorldNormal(input.normalOS);
                output.positionCS = TransformWorldToHClip(ApplyShadowBias(posWS, normWS, _LightDirection));
                #if UNITY_REVERSED_Z
                output.positionCS.z = min(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #else
                output.positionCS.z = max(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                output.uv = input.uv * _MainTex_ST.xy + _MainTex_ST.zw;
                return output;
            }}

            half4 ShadowFrag(ShadowVaryings input) : SV_TARGET
            {{
                half alpha = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv).a;
                clip(alpha - _AlphaCutoff);
                return 0;
            }}
            ENDHLSL
        }}

        // DepthOnly pass for depth prepass
        Pass
        {{
            Name "DepthOnly"
            Tags {{ "LightMode"="DepthOnly" }}
            ZWrite On
            ColorMask R
            Cull Off

            HLSLPROGRAM
            #pragma vertex DepthVert
            #pragma fragment DepthFrag

            {_URP_CORE_INCLUDE}

            TEXTURE2D(_MainTex);
            SAMPLER(sampler_MainTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST;
                float4 _HairColor;
                float4 _SpecularColor1;
                float4 _SpecularColor2;
                float _SpecularShift1;
                float _SpecularShift2;
                float _SpecularWidth1;
                float _SpecularWidth2;
                float _AlphaCutoff;
                float4 _FlowMap_ST;
                float _SSSStrength;
                float4 _SSSColor;
            CBUFFER_END

            struct DepthAttributes
            {{
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
            }};

            struct DepthVaryings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
            }};

            DepthVaryings DepthVert(DepthAttributes input)
            {{
                DepthVaryings output;
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.uv = input.uv * _MainTex_ST.xy + _MainTex_ST.zw;
                return output;
            }}

            half4 DepthFrag(DepthVaryings input) : SV_TARGET
            {{
                half alpha = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv).a;
                clip(alpha - _AlphaCutoff);
                return 0;
            }}
            ENDHLSL
        }}
    }}

    FallBack "Universal Render Pipeline/Lit"
}}
'''


# ---------------------------------------------------------------------------
# AAA: Terrain blend shader (height-based multi-material)
# ---------------------------------------------------------------------------


def generate_terrain_blend_shader(
    blend_sharpness: float = 8.0,
    triplanar_enabled: bool = False,
) -> str:
    """Generate height-based terrain material blending shader for URP.

    Supports 4 terrain layers controlled by an RGBA splat map, with
    height-map-based transitions for realistic material blending (rocks
    peek through snow, grass fills dirt cracks).  Optional triplanar
    projection for cliff faces.  Targets Horizon / Elden Ring quality.

    Args:
        blend_sharpness: Controls how sharp transitions are between materials.
        triplanar_enabled: Enable triplanar projection for cliff faces.

    Returns:
        Complete ShaderLab source string.
    """
    triplanar_flag = "1" if triplanar_enabled else "0"

    return f'''Shader "VeilBreakers/TerrainBlend"
{{
    Properties
    {{
        _SplatMap ("Splat Map (RGBA)", 2D) = "white" {{}}

        _Layer0Tex ("Layer 0 Albedo", 2D) = "white" {{}}
        _Layer0Normal ("Layer 0 Normal", 2D) = "bump" {{}}
        _Layer0Height ("Layer 0 Height", 2D) = "gray" {{}}
        _Layer0Tiling ("Layer 0 Tiling", Float) = 10
        _Layer0Metallic ("Layer 0 Metallic", Range(0, 1)) = 0
        _Layer0Roughness ("Layer 0 Roughness", Range(0, 1)) = 0.8

        _Layer1Tex ("Layer 1 Albedo", 2D) = "white" {{}}
        _Layer1Normal ("Layer 1 Normal", 2D) = "bump" {{}}
        _Layer1Height ("Layer 1 Height", 2D) = "gray" {{}}
        _Layer1Tiling ("Layer 1 Tiling", Float) = 10
        _Layer1Metallic ("Layer 1 Metallic", Range(0, 1)) = 0
        _Layer1Roughness ("Layer 1 Roughness", Range(0, 1)) = 0.8

        _Layer2Tex ("Layer 2 Albedo", 2D) = "white" {{}}
        _Layer2Normal ("Layer 2 Normal", 2D) = "bump" {{}}
        _Layer2Height ("Layer 2 Height", 2D) = "gray" {{}}
        _Layer2Tiling ("Layer 2 Tiling", Float) = 10
        _Layer2Metallic ("Layer 2 Metallic", Range(0, 1)) = 0
        _Layer2Roughness ("Layer 2 Roughness", Range(0, 1)) = 0.8

        _Layer3Tex ("Layer 3 Albedo", 2D) = "white" {{}}
        _Layer3Normal ("Layer 3 Normal", 2D) = "bump" {{}}
        _Layer3Height ("Layer 3 Height", 2D) = "gray" {{}}
        _Layer3Tiling ("Layer 3 Tiling", Float) = 10
        _Layer3Metallic ("Layer 3 Metallic", Range(0, 1)) = 0
        _Layer3Roughness ("Layer 3 Roughness", Range(0, 1)) = 0.8

        _BlendSharpness ("Blend Sharpness", Range(1, 32)) = {blend_sharpness}
        _TriplanarEnabled ("Triplanar Enabled", Float) = {triplanar_flag}
        _TriplanarSharpness ("Triplanar Sharpness", Float) = 4.0
    }}

    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry-100" }}
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
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

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
                float3 viewDirWS : TEXCOORD5;
                float4 shadowCoord : TEXCOORD6;
            }};

            // Splat map
            TEXTURE2D(_SplatMap);
            SAMPLER(sampler_SplatMap);

            // Layer textures
            TEXTURE2D(_Layer0Tex); SAMPLER(sampler_Layer0Tex);
            TEXTURE2D(_Layer0Normal); SAMPLER(sampler_Layer0Normal);
            TEXTURE2D(_Layer0Height); SAMPLER(sampler_Layer0Height);

            TEXTURE2D(_Layer1Tex); SAMPLER(sampler_Layer1Tex);
            TEXTURE2D(_Layer1Normal); SAMPLER(sampler_Layer1Normal);
            TEXTURE2D(_Layer1Height); SAMPLER(sampler_Layer1Height);

            TEXTURE2D(_Layer2Tex); SAMPLER(sampler_Layer2Tex);
            TEXTURE2D(_Layer2Normal); SAMPLER(sampler_Layer2Normal);
            TEXTURE2D(_Layer2Height); SAMPLER(sampler_Layer2Height);

            TEXTURE2D(_Layer3Tex); SAMPLER(sampler_Layer3Tex);
            TEXTURE2D(_Layer3Normal); SAMPLER(sampler_Layer3Normal);
            TEXTURE2D(_Layer3Height); SAMPLER(sampler_Layer3Height);

            CBUFFER_START(UnityPerMaterial)
                float4 _SplatMap_ST;
                float _Layer0Tiling; float _Layer0Metallic; float _Layer0Roughness;
                float _Layer1Tiling; float _Layer1Metallic; float _Layer1Roughness;
                float _Layer2Tiling; float _Layer2Metallic; float _Layer2Roughness;
                float _Layer3Tiling; float _Layer3Metallic; float _Layer3Roughness;
                float _BlendSharpness;
                float _TriplanarEnabled;
                float _TriplanarSharpness;
            CBUFFER_END

            // Height-based blending: weights biased by height for realistic transitions
            float4 HeightBlend(float4 splatWeights, float h0, float h1, float h2, float h3, float sharpness)
            {{
                float4 heights = float4(h0, h1, h2, h3) * splatWeights;
                float maxHeight = max(max(heights.x, heights.y), max(heights.z, heights.w));
                float4 diff = heights - (maxHeight - 1.0 / sharpness);
                float4 blended = max(diff, 0.0) * splatWeights;
                float total = dot(blended, float4(1, 1, 1, 1));
                return total > 0.001 ? blended / total : splatWeights;
            }}

            // UDN normal blending for multi-layer normal combination
            float3 BlendNormalsUDN(float3 n1, float3 n2)
            {{
                return normalize(float3(n1.xy + n2.xy, n1.z));
            }}

            // Triplanar sampling helper
            half4 TriplanarSample(TEXTURE2D_PARAM(tex, samp), float3 posWS, float3 blendAxes, float tiling)
            {{
                half4 xProj = SAMPLE_TEXTURE2D(tex, samp, posWS.yz * tiling);
                half4 yProj = SAMPLE_TEXTURE2D(tex, samp, posWS.xz * tiling);
                half4 zProj = SAMPLE_TEXTURE2D(tex, samp, posWS.xy * tiling);
                return xProj * blendAxes.x + yProj * blendAxes.y + zProj * blendAxes.z;
            }}

            Varyings vert(Attributes input)
            {{
                Varyings output;
                VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);
                output.positionCS = vertexInput.positionCS;
                output.uv = TRANSFORM_TEX(input.uv, _SplatMap);
                output.positionWS = vertexInput.positionWS;
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                float3 tangentWS = TransformObjectToWorldDir(input.tangentOS.xyz);
                output.tangentWS = normalize(tangentWS);
                output.bitangentWS = normalize(cross(output.normalWS, tangentWS) * input.tangentOS.w);
                output.viewDirWS = GetWorldSpaceNormalizeViewDir(vertexInput.positionWS);
                output.shadowCoord = GetShadowCoord(vertexInput);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                // Sample splat map weights
                float4 splat = SAMPLE_TEXTURE2D(_SplatMap, sampler_SplatMap, input.uv);

                float3 normalWS = normalize(input.normalWS);
                float3 absNormal = abs(normalWS);

                // Triplanar blend axes (for cliff faces)
                float3 triBlend = pow(absNormal, _TriplanarSharpness);
                triBlend /= dot(triBlend, float3(1, 1, 1));

                // Sample each layer -- use triplanar on steep surfaces if enabled
                float steepness = 1.0 - absNormal.y;
                bool useTriplanar = _TriplanarEnabled > 0.5 && steepness > 0.5;

                // Layer 0
                float2 uv0 = input.uv * _Layer0Tiling;
                half4 albedo0 = useTriplanar ? TriplanarSample(TEXTURE2D_ARGS(_Layer0Tex, sampler_Layer0Tex), input.positionWS, triBlend, _Layer0Tiling) : SAMPLE_TEXTURE2D(_Layer0Tex, sampler_Layer0Tex, uv0);
                half3 normal0 = UnpackNormal(SAMPLE_TEXTURE2D(_Layer0Normal, sampler_Layer0Normal, uv0));
                float height0 = SAMPLE_TEXTURE2D(_Layer0Height, sampler_Layer0Height, uv0).r;

                // Layer 1
                float2 uv1 = input.uv * _Layer1Tiling;
                half4 albedo1 = useTriplanar ? TriplanarSample(TEXTURE2D_ARGS(_Layer1Tex, sampler_Layer1Tex), input.positionWS, triBlend, _Layer1Tiling) : SAMPLE_TEXTURE2D(_Layer1Tex, sampler_Layer1Tex, uv1);
                half3 normal1 = UnpackNormal(SAMPLE_TEXTURE2D(_Layer1Normal, sampler_Layer1Normal, uv1));
                float height1 = SAMPLE_TEXTURE2D(_Layer1Height, sampler_Layer1Height, uv1).r;

                // Layer 2
                float2 uv2 = input.uv * _Layer2Tiling;
                half4 albedo2 = useTriplanar ? TriplanarSample(TEXTURE2D_ARGS(_Layer2Tex, sampler_Layer2Tex), input.positionWS, triBlend, _Layer2Tiling) : SAMPLE_TEXTURE2D(_Layer2Tex, sampler_Layer2Tex, uv2);
                half3 normal2 = UnpackNormal(SAMPLE_TEXTURE2D(_Layer2Normal, sampler_Layer2Normal, uv2));
                float height2 = SAMPLE_TEXTURE2D(_Layer2Height, sampler_Layer2Height, uv2).r;

                // Layer 3
                float2 uv3 = input.uv * _Layer3Tiling;
                half4 albedo3 = useTriplanar ? TriplanarSample(TEXTURE2D_ARGS(_Layer3Tex, sampler_Layer3Tex), input.positionWS, triBlend, _Layer3Tiling) : SAMPLE_TEXTURE2D(_Layer3Tex, sampler_Layer3Tex, uv3);
                half3 normal3 = UnpackNormal(SAMPLE_TEXTURE2D(_Layer3Normal, sampler_Layer3Normal, uv3));
                float height3 = SAMPLE_TEXTURE2D(_Layer3Height, sampler_Layer3Height, uv3).r;

                // Height-based blend weights
                float4 blendWeights = HeightBlend(splat, height0, height1, height2, height3, _BlendSharpness);

                // Blend albedo
                half3 finalAlbedo = albedo0.rgb * blendWeights.x + albedo1.rgb * blendWeights.y
                                  + albedo2.rgb * blendWeights.z + albedo3.rgb * blendWeights.w;

                // Blend normals using UDN method
                half3 blendedNormal = normalize(
                    normal0 * blendWeights.x + normal1 * blendWeights.y
                  + normal2 * blendWeights.z + normal3 * blendWeights.w
                );

                // Transform blended normal from tangent to world space
                float3x3 TBN = float3x3(normalize(input.tangentWS), normalize(input.bitangentWS), normalWS);
                float3 finalNormalWS = normalize(mul(blendedNormal, TBN));

                // Blend metallic and roughness
                float finalMetallic = _Layer0Metallic * blendWeights.x + _Layer1Metallic * blendWeights.y
                                    + _Layer2Metallic * blendWeights.z + _Layer3Metallic * blendWeights.w;
                float finalRoughness = _Layer0Roughness * blendWeights.x + _Layer1Roughness * blendWeights.y
                                     + _Layer2Roughness * blendWeights.z + _Layer3Roughness * blendWeights.w;

                // URP Lighting
                Light mainLight = GetMainLight(input.shadowCoord);
                float NdotL = saturate(dot(finalNormalWS, mainLight.direction));
                half3 diffuse = mainLight.color * NdotL * mainLight.shadowAttenuation * mainLight.distanceAttenuation;
                half3 ambient = SampleSH(finalNormalWS);

                // GGX-style specular
                float3 V = normalize(input.viewDirWS);
                float3 H = normalize(mainLight.direction + V);
                float NdotH = saturate(dot(finalNormalWS, H));
                float roughness2 = finalRoughness * finalRoughness;
                float d = NdotH * NdotH * (roughness2 - 1.0) + 1.0;
                float ggx = roughness2 / (3.14159 * d * d + 0.0001);
                half3 specular = mainLight.color * ggx * finalMetallic * mainLight.shadowAttenuation;

                // Additional lights
                uint additionalLightCount = GetAdditionalLightsCount();
                for (uint li = 0u; li < additionalLightCount; li++)
                {{
                    Light addLight = GetAdditionalLight(li, input.positionWS);
                    float addNdotL = saturate(dot(finalNormalWS, addLight.direction));
                    diffuse += addLight.color * addNdotL * addLight.shadowAttenuation * addLight.distanceAttenuation;
                }}

                half3 finalColor = finalAlbedo * (diffuse + ambient) + specular;
                return half4(finalColor, 1.0);
            }}
            ENDHLSL
        }}

        // ShadowCaster pass
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
                #if UNITY_REVERSED_Z
                output.positionCS.z = min(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #else
                output.positionCS.z = max(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                return output;
            }}

            half4 ShadowFrag(ShadowVaryings input) : SV_TARGET
            {{
                return 0;
            }}
            ENDHLSL
        }}

        // DepthOnly pass for depth prepass
        Pass
        {{
            Name "DepthOnly"
            Tags {{ "LightMode"="DepthOnly" }}
            ZWrite On
            ColorMask R

            HLSLPROGRAM
            #pragma vertex DepthVert
            #pragma fragment DepthFrag

            {_URP_CORE_INCLUDE}

            struct DepthAttributes
            {{
                float4 positionOS : POSITION;
            }};

            struct DepthVaryings
            {{
                float4 positionCS : SV_POSITION;
            }};

            DepthVaryings DepthVert(DepthAttributes input)
            {{
                DepthVaryings output;
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                return output;
            }}

            half4 DepthFrag(DepthVaryings input) : SV_TARGET
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
# AAA: Ice / crystal shader (SURGE / GRACE brands)
# ---------------------------------------------------------------------------


def generate_ice_crystal_shader(
    ice_color: tuple[float, float, float, float] = (0.6, 0.85, 1.0, 0.8),
    crystal_tint: tuple[float, float, float, float] = (0.3, 0.5, 0.9, 1.0),
    refraction_strength: float = 0.05,
) -> str:
    """Generate stylized ice/crystal shader for dark fantasy URP.

    Features fresnel edge highlights, fake interior refraction via
    screen-space UV offset, animated internal noise patterns, sub-surface
    scattering through ice thickness, depth-based color absorption, and
    sparkle highlights.  Designed for SURGE / GRACE brand visuals.

    Args:
        ice_color: RGBA base ice color.
        crystal_tint: RGBA deep crystal tint for absorption.
        refraction_strength: Intensity of screen-space refraction offset.

    Returns:
        Complete ShaderLab source string.
    """
    ir, ig, ib, ia = ice_color
    cr, cg, cb, ca = crystal_tint

    return f'''Shader "VeilBreakers/IceCrystal"
{{
    Properties
    {{
        _IceColor ("Ice Color", Color) = ({ir}, {ig}, {ib}, {ia})
        _CrystalColor ("Crystal Tint", Color) = ({cr}, {cg}, {cb}, {ca})
        _Refraction ("Refraction Strength", Range(0, 0.2)) = {refraction_strength}
        _Thickness ("Thickness", Range(0, 2)) = 0.5
        _InternalNoiseTex ("Internal Noise", 2D) = "white" {{}}
        _FresnelPower ("Fresnel Power", Float) = 3.0
        _FresnelColor ("Fresnel Color", Color) = (0.8, 0.95, 1.0, 1.0)
        _NoiseSpeed ("Internal Noise Speed", Float) = 0.3
        _NoiseScale ("Internal Noise Scale", Float) = 2.0
        _SparkleThreshold ("Sparkle Threshold", Range(0.9, 1.0)) = 0.97
        _SparkleIntensity ("Sparkle Intensity", Float) = 3.0
        _AbsorptionDensity ("Absorption Density", Float) = 1.5
        _SSSStrength ("SSS Strength", Range(0, 1)) = 0.4
        _SSSColor ("SSS Color", Color) = (0.4, 0.7, 1.0, 1)
    }}

    SubShader
    {{
        Tags {{ "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" }}
        LOD 300
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Back

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
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"

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
                float3 viewDirWS : TEXCOORD3;
                float4 shadowCoord : TEXCOORD4;
                float4 screenPos : TEXCOORD5;
            }};

            TEXTURE2D(_InternalNoiseTex);
            SAMPLER(sampler_InternalNoiseTex);

            CBUFFER_START(UnityPerMaterial)
                float4 _IceColor;
                float4 _CrystalColor;
                float _Refraction;
                float _Thickness;
                float4 _InternalNoiseTex_ST;
                float _FresnelPower;
                float4 _FresnelColor;
                float _NoiseSpeed;
                float _NoiseScale;
                float _SparkleThreshold;
                float _SparkleIntensity;
                float _AbsorptionDensity;
                float _SSSStrength;
                float4 _SSSColor;
            CBUFFER_END

            // Simple hash for sparkle
            float hash21(float2 p)
            {{
                return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453);
            }}

            Varyings vert(Attributes input)
            {{
                Varyings output;
                VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);
                output.positionCS = vertexInput.positionCS;
                output.uv = TRANSFORM_TEX(input.uv, _InternalNoiseTex);
                output.positionWS = vertexInput.positionWS;
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.viewDirWS = GetWorldSpaceNormalizeViewDir(vertexInput.positionWS);
                output.shadowCoord = GetShadowCoord(vertexInput);
                output.screenPos = ComputeScreenPos(output.positionCS);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                float3 normalWS = normalize(input.normalWS);
                float3 V = normalize(input.viewDirWS);

                // Fresnel edge highlight (bright rim like real ice)
                float fresnel = pow(1.0 - saturate(dot(normalWS, V)), _FresnelPower);
                half3 fresnelColor = _FresnelColor.rgb * fresnel;

                // Screen-space UV for fake interior refraction
                float2 screenUV = input.screenPos.xy / input.screenPos.w;
                float2 refractionOffset = normalWS.xy * _Refraction;
                float2 refractedUV = screenUV + refractionOffset;

                // Depth-based color absorption (deeper = darker blue)
                float sceneDepth = LinearEyeDepth(SampleSceneDepth(screenUV), _ZBufferParams);
                float fragDepth = input.screenPos.w;
                float depthDiff = max(sceneDepth - fragDepth, 0.0);
                float absorption = 1.0 - exp(-depthDiff * _AbsorptionDensity);
                half3 absorbedColor = lerp(_IceColor.rgb, _CrystalColor.rgb, absorption);

                // Animated internal noise pattern
                float2 noiseUV1 = input.uv * _NoiseScale + _Time.y * _NoiseSpeed * float2(0.3, 0.7);
                float2 noiseUV2 = input.uv * _NoiseScale * 1.3 - _Time.y * _NoiseSpeed * float2(0.5, 0.2);
                float noise1 = SAMPLE_TEXTURE2D(_InternalNoiseTex, sampler_InternalNoiseTex, noiseUV1).r;
                float noise2 = SAMPLE_TEXTURE2D(_InternalNoiseTex, sampler_InternalNoiseTex, noiseUV2).r;
                float internalPattern = (noise1 + noise2) * 0.5;
                half3 internalColor = lerp(absorbedColor, _CrystalColor.rgb * 1.2, internalPattern * 0.3);

                // Sub-surface scattering through ice thickness
                Light mainLight = GetMainLight(input.shadowCoord);
                float3 L = mainLight.direction;
                float sssNdotL = saturate(-dot(normalWS, L) * 0.5 + 0.5);
                float sssFactor = sssNdotL * _SSSStrength * _Thickness;
                half3 sss = _SSSColor.rgb * sssFactor * mainLight.color;

                // Sparkle highlights (screen-space noise threshold)
                float2 sparkleUV = screenUV * 500.0 + _Time.y * 2.0;
                float sparkle = hash21(floor(sparkleUV));
                float sparkleActive = step(_SparkleThreshold, sparkle) * _SparkleIntensity;
                // Only sparkle on surfaces facing the light
                float NdotL = saturate(dot(normalWS, L));
                sparkleActive *= NdotL;

                // URP Diffuse lighting
                half3 diffuse = mainLight.color * NdotL * mainLight.shadowAttenuation * mainLight.distanceAttenuation;
                half3 ambient = SampleSH(normalWS);

                // Specular (sharp reflections for ice)
                float3 H = normalize(L + V);
                float spec = pow(saturate(dot(normalWS, H)), 128.0) * mainLight.shadowAttenuation;
                half3 specular = mainLight.color * spec * 0.8;

                // Additional lights
                uint additionalLightCount = GetAdditionalLightsCount();
                for (uint li = 0u; li < additionalLightCount; li++)
                {{
                    Light addLight = GetAdditionalLight(li, input.positionWS);
                    float addNdotL = saturate(dot(normalWS, addLight.direction));
                    diffuse += addLight.color * addNdotL * addLight.shadowAttenuation * addLight.distanceAttenuation;
                }}

                // Compose final color
                half3 finalColor = internalColor * (diffuse + ambient) + fresnelColor + specular + sss;
                finalColor += sparkleActive * mainLight.color;  // sparkle flashes

                // Alpha: base ice alpha + fresnel rim
                float finalAlpha = lerp(_IceColor.a, 1.0, fresnel * 0.6);

                return half4(finalColor, finalAlpha);
            }}
            ENDHLSL
        }}

        // ShadowCaster pass for ice casting shadows
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
                #if UNITY_REVERSED_Z
                output.positionCS.z = min(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #else
                output.positionCS.z = max(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                return output;
            }}

            half4 ShadowFrag(ShadowVaryings input) : SV_TARGET
            {{
                return 0;
            }}
            ENDHLSL
        }}
    }}

    FallBack "Universal Render Pipeline/Lit"
}}
'''
