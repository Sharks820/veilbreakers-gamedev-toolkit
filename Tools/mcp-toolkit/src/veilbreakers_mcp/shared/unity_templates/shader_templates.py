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
"""

from __future__ import annotations

_URP_CORE_INCLUDE = '#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"'


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
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                output.positionWS = TransformObjectToWorld(input.positionOS.xyz);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
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

                return corruptedColor;
            }}
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
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
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

                half4 finalColor = baseColor;
                finalColor.rgb += edgeGlow;

                return finalColor;
            }}
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

                // Fresnel for edge transparency / refraction approximation
                float fresnel = pow(1.0 - saturate(dot(input.normalWS, input.viewDirWS)), 4.0);

                // Final water color with Alpha transparency
                half4 col = _WaterColor;
                col.rgb += fresnel * 0.3;
                col.a = lerp(_Transparency, 1.0, fresnel);

                return col;
            }}
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

                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.positionWS = TransformObjectToWorld(input.positionOS.xyz);
                output.viewDirWS = GetWorldSpaceNormalizeViewDir(output.positionWS);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                half4 baseColor = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv);
                clip(baseColor.a - _Cutoff);

                // Simple subsurface scattering approximation
                Light mainLight = GetMainLight();
                float NdotL = dot(input.normalWS, mainLight.direction);
                float subsurface = saturate(-NdotL) * _SubsurfaceStrength;
                half3 sssColor = _SubsurfaceColor.rgb * subsurface * mainLight.color;

                half3 finalColor = baseColor.rgb + sssColor;
                return half4(finalColor, baseColor.a);
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

        // Pass 2: Normal forward rendering
        Pass
        {{
            Name "ForwardLit"
            Tags {{ "LightMode"="UniversalForward" }}
            Cull Back

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag

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
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.uv = TRANSFORM_TEX(input.uv, _MainTex);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                return output;
            }}

            half4 frag(Varyings input) : SV_Target
            {{
                half4 baseColor = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv);
                return baseColor * _Color;
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
