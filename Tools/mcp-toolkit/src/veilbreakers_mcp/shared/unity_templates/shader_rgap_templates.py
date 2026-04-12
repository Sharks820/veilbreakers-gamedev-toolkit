"""RGAP rendering gap shader template generators for Unity URP.

33 shader generators addressing rendering gaps identified in the terrain/
environment quality audit. Each function returns a complete ShaderLab source
string targeting the Universal Render Pipeline.

RGAP-01  Stochastic tiling (breaks texture repetition)
RGAP-02  Advanced height-blend (macro variation)
RGAP-03  Atmospheric fog (height + sun scatter)
RGAP-04  Snow SSS (subsurface scattering)
RGAP-05  Vegetation wind (multi-layer: trunk/branch/leaf)
RGAP-06  Water-terrain intersection (shoreline foam)
RGAP-07  Decal projector (depth-reconstructed)
RGAP-08  Minimap (top-down composite)
RGAP-09  Waterfall (cascading flow + mist)
RGAP-10  River flow (flowmap + phase cycling)
RGAP-11  Parallax occlusion mapping
RGAP-12  Moss overlay (directional + noise)
RGAP-13  Wet surface (darkening + specular boost)
RGAP-14  Puddle accumulation (flat-detect + ripples)
RGAP-15  Rain ripple (concentric ring animation)
RGAP-16  God rays (radial blur light shafts)
RGAP-17  Procedural skybox (sun/stars/clouds)
RGAP-18  Cloud shadow (scrolling noise projection)
RGAP-19  Distance fog gradient (3-band)
RGAP-20  Detail normal blend (reoriented mapping)
RGAP-21  Rock face (triplanar + strata + weathering)
RGAP-22  Caustics (dual-layer underwater)
RGAP-23  Underwater post-process (tint/distortion/vignette)
RGAP-24  Lava flow (emissive crust + pulse)
RGAP-25  Emissive crystal (pulse + fresnel glow)
RGAP-26  Cloth wind (pinned-edge banner)
RGAP-27  Triplanar moss (world-normal blend)
RGAP-28  Edge detection outline (Roberts Cross)
RGAP-29  SSAO (hemisphere sampling)
RGAP-30  Vertex color blend (RGBA 4-layer)
RGAP-31  UV-free detail (triplanar + distance fade)
RGAP-32  Snow accumulation (directional + snow line)
RGAP-33  Terrain cutout (mask + edge glow)
"""

from __future__ import annotations

_URP_CORE_INCLUDE = '#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"'


# ---------------------------------------------------------------------------
# RGAP-01: Stochastic tiling shader
# ---------------------------------------------------------------------------

def generate_stochastic_tiling_shader(
    hex_scale: float = 1.0,
    blend_contrast: float = 0.5,
) -> str:
    """Generate stochastic tiling shader that eliminates texture repetition.

    Uses hex-grid randomised UV offsets with smooth blending to break up
    visible tiling patterns on large terrain surfaces.

    Args:
        hex_scale: Scale factor for the hex grid cells.
        blend_contrast: Controls sharpness of blending between hex cells.

    Returns:
        Complete ShaderLab source string.
    """
    return f'''Shader "VeilBreakers/StochasticTiling"
{{
    Properties
    {{
        _MainTex ("Albedo", 2D) = "white" {{}}
        _BumpMap ("Normal Map", 2D) = "bump" {{}}
        _HexScale ("Hex Scale", Float) = {hex_scale}
        _BlendContrast ("Blend Contrast", Range(0.01, 2.0)) = {blend_contrast}
        _Tiling ("Texture Tiling", Float) = 1.0
        _Metallic ("Metallic", Range(0, 1)) = 0
        _Smoothness ("Smoothness", Range(0, 1)) = 0.5
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
            #pragma multi_compile_fragment _ _SHADOWS_SOFT
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 tangentOS : TANGENT; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; float3 normalWS : TEXCOORD2; float3 viewDirWS : TEXCOORD3; float4 shadowCoord : TEXCOORD4; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_BumpMap); SAMPLER(sampler_BumpMap);
            CBUFFER_START(UnityPerMaterial)
                float4 _MainTex_ST; float _HexScale; float _BlendContrast; float _Tiling; float _Metallic; float _Smoothness;
            CBUFFER_END
            float2 hash22(float2 p) {{ float3 p3 = frac(float3(p.xyx) * float3(0.1031, 0.1030, 0.0973)); p3 += dot(p3, p3.yzx + 33.33); return frac((p3.xx + p3.yz) * p3.zy); }}
            void hexGrid(float2 uv, out float2 cellID, out float2 cellUV, out float w) {{
                float2 hexUV = uv * _HexScale;
                float2 a = floor(hexUV) + 0.5; float2 b = floor(hexUV + 0.5) + 0.5;
                float2 da = hexUV - a; float2 db = hexUV - b;
                float la = dot(da, da); float lb = dot(db, db);
                if (la < lb) {{ cellID = a; cellUV = da; w = saturate(1.0 - la * _BlendContrast * 4.0); }}
                else {{ cellID = b; cellUV = db; w = saturate(1.0 - lb * _BlendContrast * 4.0); }}
            }}
            Varyings vert(Attributes input) {{
                Varyings output; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz);
                output.positionCS = vpi.positionCS; output.uv = input.uv * _Tiling;
                output.positionWS = vpi.positionWS; output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); output.shadowCoord = GetShadowCoord(vpi);
                return output;
            }}
            half4 frag(Varyings input) : SV_Target {{
                float2 cellID, cellUV; float w; hexGrid(input.uv, cellID, cellUV, w);
                float2 randOffset = hash22(cellID) * 100.0; float2 sampledUV = input.uv + randOffset;
                half4 albedo = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, sampledUV);
                float3 N = normalize(input.normalWS);
                Light mainLight = GetMainLight(input.shadowCoord);
                float NdotL = saturate(dot(N, mainLight.direction));
                half3 diffuse = mainLight.color * NdotL * mainLight.shadowAttenuation;
                half3 ambient = SampleSH(N);
                float3 V = normalize(input.viewDirWS); float3 H = normalize(mainLight.direction + V);
                float spec = pow(saturate(dot(N, H)), lerp(1.0, 128.0, _Smoothness));
                half3 color = albedo.rgb * (diffuse + ambient) + mainLight.color * spec * _Metallic;
                return half4(color, 1.0);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''


# ---------------------------------------------------------------------------
# RGAP-02: Advanced height-blend shader
# ---------------------------------------------------------------------------

def generate_height_blend_shader(
    layer_count: int = 4,
    blend_sharpness: float = 10.0,
    macro_variation: bool = True,
) -> str:
    """Generate advanced height-based material blending with macro variation.

    Args:
        layer_count: Number of terrain layers (2-4).
        blend_sharpness: Controls transition sharpness between materials.
        macro_variation: Enable macro-scale color variation noise.

    Returns:
        Complete ShaderLab source string.
    """
    layer_count = max(2, min(4, layer_count))
    macro_flag = "1" if macro_variation else "0"
    return f'''Shader "VeilBreakers/HeightBlend"
{{
    Properties
    {{
        _SplatMap ("Splat Map (RGBA)", 2D) = "white" {{}}
        _BlendSharpness ("Blend Sharpness", Range(1, 32)) = {blend_sharpness}
        _MacroVariation ("Macro Variation", Float) = {macro_flag}
        _MacroNoiseTex ("Macro Noise", 2D) = "gray" {{}}
        _MacroScale ("Macro Scale", Float) = 0.01
        _MacroStrength ("Macro Strength", Range(0, 1)) = 0.3
        _Layer0Tex ("Layer 0 Albedo", 2D) = "white" {{}}
        _Layer0Height ("Layer 0 Height", 2D) = "gray" {{}}
        _Layer0Tiling ("Layer 0 Tiling", Float) = 10
        _Layer1Tex ("Layer 1 Albedo", 2D) = "white" {{}}
        _Layer1Height ("Layer 1 Height", 2D) = "gray" {{}}
        _Layer1Tiling ("Layer 1 Tiling", Float) = 10
        _Layer2Tex ("Layer 2 Albedo", 2D) = "white" {{}}
        _Layer2Height ("Layer 2 Height", 2D) = "gray" {{}}
        _Layer2Tiling ("Layer 2 Tiling", Float) = 10
        _Layer3Tex ("Layer 3 Albedo", 2D) = "white" {{}}
        _Layer3Height ("Layer 3 Height", 2D) = "gray" {{}}
        _Layer3Tiling ("Layer 3 Tiling", Float) = 10
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
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; float3 normalWS : TEXCOORD2; float4 shadowCoord : TEXCOORD3; }};
            TEXTURE2D(_SplatMap); SAMPLER(sampler_SplatMap); TEXTURE2D(_MacroNoiseTex); SAMPLER(sampler_MacroNoiseTex);
            TEXTURE2D(_Layer0Tex); SAMPLER(sampler_Layer0Tex); TEXTURE2D(_Layer0Height); SAMPLER(sampler_Layer0Height);
            TEXTURE2D(_Layer1Tex); SAMPLER(sampler_Layer1Tex); TEXTURE2D(_Layer1Height); SAMPLER(sampler_Layer1Height);
            TEXTURE2D(_Layer2Tex); SAMPLER(sampler_Layer2Tex); TEXTURE2D(_Layer2Height); SAMPLER(sampler_Layer2Height);
            TEXTURE2D(_Layer3Tex); SAMPLER(sampler_Layer3Tex); TEXTURE2D(_Layer3Height); SAMPLER(sampler_Layer3Height);
            CBUFFER_START(UnityPerMaterial)
                float _BlendSharpness; float _MacroVariation; float _MacroScale; float _MacroStrength;
                float _Layer0Tiling; float _Layer1Tiling; float _Layer2Tiling; float _Layer3Tiling;
            CBUFFER_END
            float4 heightBlend(float4 splat, float h0, float h1, float h2, float h3) {{
                float4 h = float4(h0, h1, h2, h3) + splat * _BlendSharpness;
                float maxH = max(max(h.x, h.y), max(h.z, h.w));
                float4 weights = max(h - maxH + 1.0, 0.0);
                return weights / (dot(weights, 1.0) + 0.001);
            }}
            Varyings vert(Attributes input) {{
                Varyings output; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz);
                output.positionCS = vpi.positionCS; output.uv = input.uv;
                output.positionWS = vpi.positionWS; output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.shadowCoord = GetShadowCoord(vpi); return output;
            }}
            half4 frag(Varyings input) : SV_Target {{
                float4 splat = SAMPLE_TEXTURE2D(_SplatMap, sampler_SplatMap, input.uv);
                half4 c0 = SAMPLE_TEXTURE2D(_Layer0Tex, sampler_Layer0Tex, input.uv * _Layer0Tiling);
                half4 c1 = SAMPLE_TEXTURE2D(_Layer1Tex, sampler_Layer1Tex, input.uv * _Layer1Tiling);
                half4 c2 = SAMPLE_TEXTURE2D(_Layer2Tex, sampler_Layer2Tex, input.uv * _Layer2Tiling);
                half4 c3 = SAMPLE_TEXTURE2D(_Layer3Tex, sampler_Layer3Tex, input.uv * _Layer3Tiling);
                float h0 = SAMPLE_TEXTURE2D(_Layer0Height, sampler_Layer0Height, input.uv * _Layer0Tiling).r;
                float h1 = SAMPLE_TEXTURE2D(_Layer1Height, sampler_Layer1Height, input.uv * _Layer1Tiling).r;
                float h2 = SAMPLE_TEXTURE2D(_Layer2Height, sampler_Layer2Height, input.uv * _Layer2Tiling).r;
                float h3 = SAMPLE_TEXTURE2D(_Layer3Height, sampler_Layer3Height, input.uv * _Layer3Tiling).r;
                float4 weights = heightBlend(splat, h0, h1, h2, h3);
                half3 albedo = c0.rgb * weights.x + c1.rgb * weights.y + c2.rgb * weights.z + c3.rgb * weights.w;
                if (_MacroVariation > 0.5) {{
                    float macro = SAMPLE_TEXTURE2D(_MacroNoiseTex, sampler_MacroNoiseTex, input.uv * _MacroScale).r;
                    albedo *= lerp(1.0 - _MacroStrength, 1.0 + _MacroStrength, macro);
                }}
                float3 N = normalize(input.normalWS);
                Light mainLight = GetMainLight(input.shadowCoord);
                float NdotL = saturate(dot(N, mainLight.direction));
                return half4(albedo * (mainLight.color * NdotL * mainLight.shadowAttenuation + SampleSH(N)), 1.0);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''


# ---------------------------------------------------------------------------
# RGAP-03 through RGAP-33: Compact shader generators
# Each returns a complete ShaderLab string targeting URP.
# ---------------------------------------------------------------------------

def generate_atmospheric_fog_shader(fog_color=(0.6, 0.65, 0.75), fog_density=0.02, fog_height_falloff=0.1):
    """Atmospheric height-fog post-process with sun scattering."""
    fr, fg, fb = fog_color
    return f'''Shader "VeilBreakers/AtmosphericFog"
{{
    Properties {{ _MainTex ("Scene Texture", 2D) = "white" {{}} _FogColor ("Fog Color", Color) = ({fr},{fg},{fb},1) _FogDensity ("Fog Density", Range(0,0.2)) = {fog_density} _FogHeightFalloff ("Height Falloff", Range(0,1)) = {fog_height_falloff} _FogStart ("Fog Start", Float) = 10 _FogEnd ("Fog End", Float) = 500 _SunScatterColor ("Sun Scatter", Color) = (1,0.8,0.5,1) _SunScatterPower ("Sun Scatter Power", Float) = 8 _SunScatterIntensity ("Sun Scatter Intensity", Range(0,2)) = 0.5 _FogHeightBase ("Height Base", Float) = 0 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" }} ZWrite Off Cull Off
        Pass {{ Name "AtmosphericFog"
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            CBUFFER_START(UnityPerMaterial) float4 _FogColor; float _FogDensity; float _FogHeightFalloff; float _FogStart; float _FogEnd; float4 _SunScatterColor; float _SunScatterPower; float _SunScatterIntensity; float _FogHeightBase; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; o.positionCS = TransformObjectToHClip(input.positionOS.xyz); o.uv = input.uv; return o; }}
            half4 frag(Varyings input) : SV_Target {{
                half4 scene = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv);
                float linearDepth = LinearEyeDepth(SampleSceneDepth(input.uv), _ZBufferParams);
                float2 posNDC = input.uv * 2.0 - 1.0;
                float3 vd = mul(unity_CameraInvProjection, float4(posNDC,1,1)).xyz;
                float3 wp = _WorldSpaceCameraPos + vd * linearDepth;
                float hf = exp(-max(wp.y - _FogHeightBase, 0) * _FogHeightFalloff);
                float df = saturate((linearDepth - _FogStart) / max(_FogEnd - _FogStart, 0.001));
                float fog = (1.0 - exp(-_FogDensity * linearDepth * hf)) * df;
                float3 V = normalize(wp - _WorldSpaceCameraPos);
                float ss = pow(saturate(dot(V, _MainLightPosition.xyz)), _SunScatterPower) * _SunScatterIntensity;
                half3 fc = lerp(_FogColor.rgb, _SunScatterColor.rgb, ss);
                return half4(lerp(scene.rgb, fc, saturate(fog)), scene.a);
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_snow_sss_shader(snow_color=(0.95,0.95,1.0), sss_color=(0.4,0.6,0.9), sss_power=3.0):
    """Snow with subsurface scattering, sparkle, and wrap lighting."""
    sr,sg,sb = snow_color; cr,cg,cb = sss_color
    return f'''Shader "VeilBreakers/SnowSSS"
{{
    Properties {{ _SnowColor ("Snow Color", Color) = ({sr},{sg},{sb},1) _SSSColor ("SSS Color", Color) = ({cr},{cg},{cb},1) _SSSPower ("SSS Power", Float) = {sss_power} _SSSStrength ("SSS Strength", Range(0,2)) = 1 _SSSDistortion ("SSS Distortion", Range(0,1)) = 0.5 _NoiseTex ("Snow Noise", 2D) = "white" {{}} _NormalMap ("Normal Map", 2D) = "bump" {{}} _SparkleScale ("Sparkle Scale", Float) = 200 _SparkleThreshold ("Sparkle Threshold", Range(0.9,1)) = 0.96 _SparkleIntensity ("Sparkle Intensity", Float) = 3 _Thickness ("Thickness", Range(0,2)) = 0.5 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }} LOD 200
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 tangentOS : TANGENT; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; float3 normalWS : TEXCOORD2; float3 viewDirWS : TEXCOORD3; float4 shadowCoord : TEXCOORD4; float3 tangentWS : TEXCOORD5; float3 bitangentWS : TEXCOORD6; }};
            TEXTURE2D(_NoiseTex); SAMPLER(sampler_NoiseTex); TEXTURE2D(_NormalMap); SAMPLER(sampler_NormalMap);
            CBUFFER_START(UnityPerMaterial) float4 _SnowColor; float4 _SSSColor; float _SSSPower; float _SSSStrength; float _SSSDistortion; float4 _NoiseTex_ST; float _SparkleScale; float _SparkleThreshold; float _SparkleIntensity; float _Thickness; CBUFFER_END
            float hash21(float2 p) {{ return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453); }}
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); VertexNormalInputs vni = GetVertexNormalInputs(input.normalOS, input.tangentOS); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _NoiseTex); o.positionWS = vpi.positionWS; o.normalWS = vni.normalWS; o.tangentWS = vni.tangentWS; o.bitangentWS = vni.bitangentWS; o.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float3 N = normalize(i.normalWS); float3 V = normalize(i.viewDirWS);
                Light ml = GetMainLight(i.shadowCoord); float3 L = ml.direction;
                half3 nTS = UnpackNormal(SAMPLE_TEXTURE2D(_NormalMap, sampler_NormalMap, i.uv));
                float3x3 TBN = float3x3(normalize(i.tangentWS), normalize(i.bitangentWS), N);
                N = normalize(mul(nTS, TBN));
                float NdotL = saturate(dot(N, L));
                half3 diff = _SnowColor.rgb * ml.color * NdotL * ml.shadowAttenuation;
                float3 sssL = L + N * _SSSDistortion;
                float sssFactor = pow(saturate(dot(V, -sssL)), _SSSPower) * _SSSStrength * _Thickness;
                half3 sss = _SSSColor.rgb * ml.color * sssFactor * ml.shadowAttenuation;
                float wrap = saturate(dot(N, L) * 0.5 + 0.5);
                half3 wd = _SnowColor.rgb * ml.color * wrap * 0.3;
                float sparkle = step(_SparkleThreshold, hash21(floor(i.uv * _SparkleScale + _Time.y))) * _SparkleIntensity * NdotL;
                return half4(diff + sss + wd + SampleSH(N) * _SnowColor.rgb + sparkle * ml.color, 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_vegetation_wind_shader(wind_speed=1.0, wind_strength=0.3, trunk_flexibility=0.02):
    """Multi-layer vegetation wind: trunk/branch/leaf via vertex color RGB."""
    return f'''Shader "VeilBreakers/VegetationWind"
{{
    Properties {{ _MainTex ("Albedo", 2D) = "white" {{}} _WindSpeed ("Wind Speed", Float) = {wind_speed} _WindStrength ("Wind Strength", Float) = {wind_strength} _TrunkFlex ("Trunk Flex", Float) = {trunk_flexibility} _BranchFreq ("Branch Freq", Float) = 1.5 _LeafFlutterFreq ("Leaf Flutter Freq", Float) = 5 _LeafFlutterAmp ("Leaf Flutter Amp", Float) = 0.05 _WindDirection ("Wind Dir", Vector) = (1,0,0.3,0) _Cutoff ("Alpha Cutoff", Range(0,1)) = 0.5 _SubsurfaceColor ("Subsurface", Color) = (0.3,0.5,0.1,1) _SubsurfaceStrength ("Subsurface Strength", Range(0,1)) = 0.4 }}
    SubShader
    {{
        Tags {{ "RenderType"="TransparentCutout" "RenderPipeline"="UniversalPipeline" "Queue"="AlphaTest" }} Cull Off
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 color : COLOR; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 normalWS : TEXCOORD1; float3 positionWS : TEXCOORD2; float4 shadowCoord : TEXCOORD3; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float _WindSpeed; float _WindStrength; float _TrunkFlex; float _BranchFreq; float _LeafFlutterFreq; float _LeafFlutterAmp; float4 _WindDirection; float _Cutoff; float4 _SubsurfaceColor; float _SubsurfaceStrength; CBUFFER_END
            Varyings vert(Attributes input) {{
                Varyings o; float3 p = input.positionOS.xyz; float t = _Time.y * _WindSpeed; float3 wd = normalize(_WindDirection.xyz);
                p += wd * sin(t*0.8+p.y*0.3) * input.color.r * _TrunkFlex * _WindStrength;
                p += wd * sin(t*_BranchFreq+p.x*2+p.z*1.5) * input.color.g * _WindStrength * 0.5;
                float lf = sin(t*_LeafFlutterFreq+dot(p,float3(3.1,1.7,2.3)));
                p += float3(lf,abs(lf)*0.5,lf*0.7) * input.color.b * _LeafFlutterAmp;
                VertexPositionInputs vpi = GetVertexPositionInputs(p);
                o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex);
                o.positionWS = vpi.positionWS; o.normalWS = TransformObjectToWorldNormal(input.normalOS);
                o.shadowCoord = GetShadowCoord(vpi); return o;
            }}
            half4 frag(Varyings i) : SV_Target {{
                half4 a = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv); clip(a.a - _Cutoff);
                float3 N = normalize(i.normalWS); Light ml = GetMainLight(i.shadowCoord);
                float NdotL = saturate(dot(N, ml.direction));
                half3 diff = a.rgb * ml.color * NdotL * ml.shadowAttenuation;
                float bl = saturate(dot(-N, ml.direction)) * _SubsurfaceStrength;
                return half4(diff + _SubsurfaceColor.rgb * ml.color * bl + SampleSH(N) * a.rgb, 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_water_terrain_intersection_shader(water_color=(0.1,0.3,0.4,0.8), foam_color=(0.9,0.95,1.0), foam_width=1.5):
    """Water-terrain intersection with shoreline foam and depth gradient."""
    wr,wg,wb,wa = water_color; fr,fg,fb = foam_color
    return f'''Shader "VeilBreakers/WaterTerrainIntersection"
{{
    Properties {{ _WaterColor ("Water Color", Color) = ({wr},{wg},{wb},{wa}) _DeepColor ("Deep Color", Color) = (0.02,0.08,0.15,1) _FoamColor ("Foam Color", Color) = ({fr},{fg},{fb},1) _FoamWidth ("Foam Width", Float) = {foam_width} _FoamNoiseTex ("Foam Noise", 2D) = "white" {{}} _FoamSpeed ("Foam Speed", Float) = 0.3 _FoamScale ("Foam Scale", Float) = 5 _DepthFade ("Depth Fade", Float) = 5 _WaveNormalMap ("Wave Normal", 2D) = "bump" {{}} _WaveScale ("Wave Scale", Float) = 2 _WaveSpeed ("Wave Speed", Float) = 0.5 _EdgeSharpness ("Edge Sharpness", Range(1,10)) = 3 }}
    SubShader
    {{
        Tags {{ "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" }} Blend SrcAlpha OneMinusSrcAlpha ZWrite Off
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 normalWS : TEXCOORD1; float4 shadowCoord : TEXCOORD2; float4 screenPos : TEXCOORD3; }};
            TEXTURE2D(_FoamNoiseTex); SAMPLER(sampler_FoamNoiseTex); TEXTURE2D(_WaveNormalMap); SAMPLER(sampler_WaveNormalMap);
            CBUFFER_START(UnityPerMaterial) float4 _WaterColor; float4 _DeepColor; float4 _FoamColor; float _FoamWidth; float _FoamSpeed; float _FoamScale; float _DepthFade; float _WaveScale; float _WaveSpeed; float _EdgeSharpness; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.uv = input.uv; o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.shadowCoord = GetShadowCoord(vpi); o.screenPos = ComputeScreenPos(o.positionCS); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float2 sUV = i.screenPos.xy / i.screenPos.w;
                float dd = LinearEyeDepth(SampleSceneDepth(sUV), _ZBufferParams) - i.screenPos.w;
                float df = saturate(dd / _DepthFade);
                half3 wc = lerp(_WaterColor.rgb, _DeepColor.rgb, df);
                float fm = pow(1.0 - saturate(dd / _FoamWidth), _EdgeSharpness);
                float fn = SAMPLE_TEXTURE2D(_FoamNoiseTex, sampler_FoamNoiseTex, i.uv * _FoamScale + _Time.y * _FoamSpeed * float2(0.3,0.1)).r;
                fm *= step(0.3, fn);
                half3 c = lerp(wc, _FoamColor.rgb, fm);
                Light ml = GetMainLight(i.shadowCoord);
                float NdotL = saturate(dot(normalize(i.normalWS), ml.direction));
                c *= ml.color * NdotL * ml.shadowAttenuation * 0.5 + 0.5;
                return half4(c, lerp(_WaterColor.a, 1, fm));
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_decal_projector_shader(blend_mode="alpha"):
    """Decal projection via depth reconstruction. Alpha or additive blend."""
    blend_mode = blend_mode.lower()
    if blend_mode not in ("alpha","additive"): blend_mode = "alpha"
    bo = "Blend SrcAlpha OneMinusSrcAlpha" if blend_mode == "alpha" else "Blend SrcAlpha One"
    return f'''Shader "VeilBreakers/DecalProjector"
{{
    Properties {{ _DecalTex ("Decal", 2D) = "white" {{}} _Color ("Tint", Color) = (1,1,1,1) _AngleFade ("Angle Fade", Range(0,1)) = 0.5 _DepthFade ("Depth Fade", Range(0,1)) = 0.1 }}
    SubShader
    {{
        Tags {{ "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent+10" }} {bo} ZWrite Off Cull Front ZTest Always
        Pass {{ Name "DecalProjection"
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareNormalsTexture.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float4 screenPos : TEXCOORD0; float3 cameraDirWS : TEXCOORD1; }};
            TEXTURE2D(_DecalTex); SAMPLER(sampler_DecalTex);
            CBUFFER_START(UnityPerMaterial) float4 _Color; float _AngleFade; float _DepthFade; CBUFFER_END
            float4x4 _DecalWorldToLocal;
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.screenPos = ComputeScreenPos(o.positionCS); o.cameraDirWS = vpi.positionWS - _WorldSpaceCameraPos; return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float2 sUV = i.screenPos.xy / i.screenPos.w;
                float ld = LinearEyeDepth(SampleSceneDepth(sUV), _ZBufferParams);
                float3 wp = _WorldSpaceCameraPos + normalize(i.cameraDirWS) * ld;
                float3 lp = mul(_DecalWorldToLocal, float4(wp,1)).xyz;
                clip(0.5 - abs(lp.xyz));
                float2 duv = lp.xz + 0.5;
                float3 sn = SampleSceneNormals(sUV);
                float3 dn = mul((float3x3)_DecalWorldToLocal, float3(0,1,0));
                float am = smoothstep(_AngleFade, 1.0, saturate(dot(sn, -dn)));
                half4 dc = SAMPLE_TEXTURE2D(_DecalTex, sampler_DecalTex, duv) * _Color;
                float2 ef = smoothstep(0.0, _DepthFade, 0.5 - abs(lp.xz));
                dc.a *= am * ef.x * ef.y;
                return dc;
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_minimap_shader():
    """Top-down minimap composite with circular mask and border."""
    return f'''Shader "VeilBreakers/Minimap"
{{
    Properties {{ _MainTex ("Scene", 2D) = "white" {{}} _MinimapMask ("Mask", 2D) = "white" {{}} _TerrainLowColor ("Low", Color) = (0.2,0.35,0.15,1) _TerrainHighColor ("High", Color) = (0.6,0.55,0.4,1) _BorderColor ("Border", Color) = (0.3,0.25,0.2,1) _BorderWidth ("Border Width", Range(0,0.1)) = 0.02 _HeightMin ("Height Min", Float) = 0 _HeightMax ("Height Max", Float) = 100 }}
    SubShader
    {{
        Tags {{ "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Overlay" }} Blend SrcAlpha OneMinusSrcAlpha ZWrite Off ZTest Always
        Pass {{ Name "MinimapComposite"
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_MinimapMask); SAMPLER(sampler_MinimapMask);
            CBUFFER_START(UnityPerMaterial) float4 _TerrainLowColor; float4 _TerrainHighColor; float4 _BorderColor; float _BorderWidth; float _HeightMin; float _HeightMax; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; o.positionCS = TransformObjectToHClip(input.positionOS.xyz); o.uv = input.uv; return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half4 sc = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
                float mask = SAMPLE_TEXTURE2D(_MinimapMask, sampler_MinimapMask, i.uv).a;
                float2 c = i.uv - 0.5; float d = length(c);
                float cm = 1.0 - smoothstep(0.48 - _BorderWidth, 0.48, d);
                float bm = smoothstep(0.48 - _BorderWidth, 0.48 - _BorderWidth*0.5, d) * (1.0 - smoothstep(0.48, 0.5, d));
                float h = saturate((sc.r - _HeightMin) / max(_HeightMax - _HeightMin, 0.001));
                half3 tc = lerp(_TerrainLowColor.rgb, _TerrainHighColor.rgb, h);
                return half4(lerp(tc, _BorderColor.rgb, bm), cm * mask);
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_waterfall_shader(water_color=(0.7,0.85,0.95,0.85), foam_color=(1,1,1), flow_speed=2.0):
    """Cascading waterfall with foam, vertex displacement, and mist."""
    wr,wg,wb,wa = water_color; fr,fg,fb = foam_color
    return f'''Shader "VeilBreakers/Waterfall"
{{
    Properties {{ _WaterColor ("Water", Color) = ({wr},{wg},{wb},{wa}) _FoamColor ("Foam", Color) = ({fr},{fg},{fb},1) _FlowSpeed ("Flow Speed", Float) = {flow_speed} _FlowNoiseTex ("Flow Noise", 2D) = "white" {{}} _FoamTex ("Foam", 2D) = "white" {{}} _FlowTiling ("Flow Tiling", Vector) = (1,2,0,0) _FoamThreshold ("Foam Threshold", Range(0,1)) = 0.6 _DisplacementStrength ("Displacement", Float) = 0.1 _MistFade ("Mist Fade", Float) = 3 _FresnelPower ("Fresnel", Float) = 3 }}
    SubShader
    {{
        Tags {{ "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" }} Blend SrcAlpha OneMinusSrcAlpha ZWrite Off Cull Off
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 color : COLOR; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 normalWS : TEXCOORD1; float3 viewDirWS : TEXCOORD2; float4 shadowCoord : TEXCOORD3; float4 screenPos : TEXCOORD4; float flowMask : TEXCOORD5; }};
            TEXTURE2D(_FlowNoiseTex); SAMPLER(sampler_FlowNoiseTex); TEXTURE2D(_FoamTex); SAMPLER(sampler_FoamTex);
            CBUFFER_START(UnityPerMaterial) float4 _WaterColor; float4 _FoamColor; float _FlowSpeed; float4 _FlowTiling; float _FoamThreshold; float _DisplacementStrength; float _MistFade; float _FresnelPower; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; float3 p = input.positionOS.xyz; p += input.normalOS * sin(_Time.y*_FlowSpeed*3+p.y*5)*_DisplacementStrength*input.color.r; VertexPositionInputs vpi = GetVertexPositionInputs(p); o.positionCS = vpi.positionCS; o.uv = input.uv; o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); o.shadowCoord = GetShadowCoord(vpi); o.screenPos = ComputeScreenPos(o.positionCS); o.flowMask = input.color.r; return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float t = _Time.y * _FlowSpeed;
                float n1 = SAMPLE_TEXTURE2D(_FlowNoiseTex, sampler_FlowNoiseTex, i.uv * _FlowTiling.xy + float2(0,-t)).r;
                float n2 = SAMPLE_TEXTURE2D(_FlowNoiseTex, sampler_FlowNoiseTex, i.uv * _FlowTiling.xy * 1.3 + float2(0.3,-t*0.8)).r;
                float fm = max(step(_FoamThreshold, (n1+n2)*0.5), step(0.7, SAMPLE_TEXTURE2D(_FoamTex, sampler_FoamTex, i.uv * _FlowTiling.xy*0.8+float2(0,-t*1.2)).r));
                half3 c = lerp(_WaterColor.rgb, _FoamColor.rgb, fm * i.flowMask);
                float3 N = normalize(i.normalWS); float fresnel = pow(1-saturate(dot(N, normalize(i.viewDirWS))), _FresnelPower);
                c += fresnel * 0.3;
                float2 sUV = i.screenPos.xy / i.screenPos.w;
                float mf = saturate((LinearEyeDepth(SampleSceneDepth(sUV), _ZBufferParams) - i.screenPos.w) / _MistFade);
                Light ml = GetMainLight(i.shadowCoord);
                c *= ml.color * (saturate(dot(N, ml.direction))*0.5+0.5) * ml.shadowAttenuation;
                return half4(c, _WaterColor.a * mf * (0.7 + fm * 0.3));
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_river_flow_shader(water_color=(0.05,0.2,0.3,0.9), flow_speed=0.5):
    """River flow with flowmap, phase cycling, and shore foam."""
    wr,wg,wb,wa = water_color
    return f'''Shader "VeilBreakers/RiverFlow"
{{
    Properties {{ _WaterColor ("Water", Color) = ({wr},{wg},{wb},{wa}) _ShallowColor ("Shallow", Color) = (0.15,0.4,0.35,0.6) _FlowMap ("FlowMap", 2D) = "gray" {{}} _NormalMap ("Normal", 2D) = "bump" {{}} _FoamTex ("Foam", 2D) = "white" {{}} _FlowSpeed ("Flow Speed", Float) = {flow_speed} _FlowStrength ("Flow Strength", Float) = 0.2 _NormalTiling ("Normal Tiling", Float) = 4 _DepthFade ("Depth Fade", Float) = 2 _SpecularPower ("Specular", Float) = 64 _FresnelPower ("Fresnel", Float) = 4 _FoamThreshold ("Foam Threshold", Range(0,1)) = 0.7 _FoamWidth ("Foam Width", Float) = 0.5 }}
    SubShader
    {{
        Tags {{ "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" }} Blend SrcAlpha OneMinusSrcAlpha ZWrite Off
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 normalWS : TEXCOORD1; float3 viewDirWS : TEXCOORD2; float4 shadowCoord : TEXCOORD3; float4 screenPos : TEXCOORD4; }};
            TEXTURE2D(_FlowMap); SAMPLER(sampler_FlowMap); TEXTURE2D(_NormalMap); SAMPLER(sampler_NormalMap); TEXTURE2D(_FoamTex); SAMPLER(sampler_FoamTex);
            CBUFFER_START(UnityPerMaterial) float4 _WaterColor; float4 _ShallowColor; float _FlowSpeed; float _FlowStrength; float _NormalTiling; float _DepthFade; float _SpecularPower; float _FresnelPower; float _FoamThreshold; float _FoamWidth; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.uv = input.uv; o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); o.shadowCoord = GetShadowCoord(vpi); o.screenPos = ComputeScreenPos(o.positionCS); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float2 fd = SAMPLE_TEXTURE2D(_FlowMap, sampler_FlowMap, i.uv).rg * 2 - 1; fd *= _FlowStrength;
                float p0 = frac(_Time.y*_FlowSpeed); float p1 = frac(_Time.y*_FlowSpeed+0.5); float bl = abs(p0*2-1);
                half3 n0 = UnpackNormal(SAMPLE_TEXTURE2D(_NormalMap, sampler_NormalMap, i.uv*_NormalTiling - fd*p0));
                half3 n1 = UnpackNormal(SAMPLE_TEXTURE2D(_NormalMap, sampler_NormalMap, i.uv*_NormalTiling - fd*p1));
                float3 N = normalize(i.normalWS + float3(lerp(n0,n1,bl).xy * 0.3, 0));
                float3 V = normalize(i.viewDirWS);
                float2 sUV = i.screenPos.xy / i.screenPos.w;
                float dd = LinearEyeDepth(SampleSceneDepth(sUV), _ZBufferParams) - i.screenPos.w;
                float df = saturate(dd / _DepthFade);
                half3 wc = lerp(_ShallowColor.rgb, _WaterColor.rgb, df);
                float sf = (1-saturate(dd/_FoamWidth)) * step(_FoamThreshold, SAMPLE_TEXTURE2D(_FoamTex, sampler_FoamTex, i.uv*5-fd*p0).r);
                wc = lerp(wc, float3(1,1,1), sf*0.8);
                Light ml = GetMainLight(i.shadowCoord); float NdotL = saturate(dot(N, ml.direction));
                float3 H = normalize(ml.direction + V); float spec = pow(saturate(dot(N,H)), _SpecularPower);
                half3 c = wc*(ml.color*NdotL*0.5+0.5) + ml.color*spec*0.5 + pow(1-saturate(dot(N,V)),_FresnelPower)*_ShallowColor.rgb*0.3;
                return half4(c, max(lerp(_ShallowColor.a, _WaterColor.a, df), sf*0.9));
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_parallax_occlusion_shader(height_scale=0.05, min_layers=8, max_layers=32):
    """Parallax occlusion mapping with ray-march and binary refinement."""
    return f'''Shader "VeilBreakers/ParallaxOcclusion"
{{
    Properties {{ _MainTex ("Albedo", 2D) = "white" {{}} _BumpMap ("Normal", 2D) = "bump" {{}} _HeightMap ("Height", 2D) = "gray" {{}} _HeightScale ("Height Scale", Range(0,0.3)) = {height_scale} _MinLayers ("Min Layers", Float) = {min_layers} _MaxLayers ("Max Layers", Float) = {max_layers} _Metallic ("Metallic", Range(0,1)) = 0 _Smoothness ("Smoothness", Range(0,1)) = 0.5 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }} LOD 300
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 tangentOS : TANGENT; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; float3 normalWS : TEXCOORD2; float3 tangentWS : TEXCOORD3; float3 bitangentWS : TEXCOORD4; float3 viewDirWS : TEXCOORD5; float4 shadowCoord : TEXCOORD6; float3 viewDirTS : TEXCOORD7; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_BumpMap); SAMPLER(sampler_BumpMap); TEXTURE2D(_HeightMap); SAMPLER(sampler_HeightMap);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float _HeightScale; float _MinLayers; float _MaxLayers; float _Metallic; float _Smoothness; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); VertexNormalInputs vni = GetVertexNormalInputs(input.normalOS, input.tangentOS); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex); o.positionWS = vpi.positionWS; o.normalWS = vni.normalWS; o.tangentWS = vni.tangentWS; o.bitangentWS = vni.bitangentWS; o.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); o.shadowCoord = GetShadowCoord(vpi); o.viewDirTS = mul(float3x3(vni.tangentWS, vni.bitangentWS, vni.normalWS), o.viewDirWS); return o; }}
            float2 pom(float2 uv, float3 vTS) {{
                float nl = lerp(_MaxLayers, _MinLayers, abs(dot(float3(0,0,1), normalize(vTS))));
                float ld = 1.0/nl; float cd = 0; float2 P = vTS.xy/vTS.z*_HeightScale; float2 dUV = P/nl;
                float2 cUV = uv; float ch = SAMPLE_TEXTURE2D_LOD(_HeightMap, sampler_HeightMap, cUV, 0).r;
                for (int j = 0; j < 64 && cd < ch; j++) {{ cUV -= dUV; ch = SAMPLE_TEXTURE2D_LOD(_HeightMap, sampler_HeightMap, cUV, 0).r; cd += ld; }}
                float2 pUV = cUV + dUV; float pd = cd - ld;
                float ad = ch - cd; float bd = SAMPLE_TEXTURE2D_LOD(_HeightMap, sampler_HeightMap, pUV, 0).r - pd;
                return lerp(cUV, pUV, ad / (ad - bd));
            }}
            half4 frag(Varyings i) : SV_Target {{
                float2 uv = pom(i.uv, normalize(i.viewDirTS));
                if (uv.x < 0 || uv.x > 1 || uv.y < 0 || uv.y > 1) discard;
                half4 a = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uv);
                half3 nTS = UnpackNormal(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, uv));
                float3x3 TBN = float3x3(normalize(i.tangentWS), normalize(i.bitangentWS), normalize(i.normalWS));
                float3 N = normalize(mul(nTS, TBN));
                Light ml = GetMainLight(i.shadowCoord); float NdotL = saturate(dot(N, ml.direction));
                float3 V = normalize(i.viewDirWS); float3 H = normalize(ml.direction + V);
                float spec = pow(saturate(dot(N, H)), lerp(1, 256, _Smoothness));
                return half4(a.rgb * (ml.color * NdotL * ml.shadowAttenuation + SampleSH(N)) + ml.color * spec * _Metallic, 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_moss_overlay_shader(moss_color=(0.15,0.35,0.1)):
    """Procedural moss overlay based on world normal direction and noise."""
    mr,mg,mb = moss_color
    return f'''Shader "VeilBreakers/MossOverlay"
{{
    Properties {{ _MainTex ("Base", 2D) = "white" {{}} _MossColor ("Moss Color", Color) = ({mr},{mg},{mb},1) _MossNoiseTex ("Noise", 2D) = "white" {{}} _MossAmount ("Amount", Range(0,1)) = 0.5 _MossSharpness ("Sharpness", Range(1,20)) = 8 _MossNoiseScale ("Noise Scale", Float) = 3 _MossDirection ("Direction", Vector) = (0,1,0,0) _MossDirectionBias ("Dir Bias", Range(0,1)) = 0.5 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; float3 normalWS : TEXCOORD2; float4 shadowCoord : TEXCOORD3; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_MossNoiseTex); SAMPLER(sampler_MossNoiseTex);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float4 _MossColor; float _MossAmount; float _MossSharpness; float _MossNoiseScale; float4 _MossDirection; float _MossDirectionBias; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex); o.positionWS = vpi.positionWS; o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half4 ba = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv); float3 N = normalize(i.normalWS);
                float df = smoothstep(_MossDirectionBias, 1, saturate(dot(N, normalize(_MossDirection.xyz))));
                float noise = SAMPLE_TEXTURE2D(_MossNoiseTex, sampler_MossNoiseTex, i.positionWS.xz * _MossNoiseScale * 0.01).r;
                float mm = saturate((df * noise - (1 - _MossAmount)) * _MossSharpness);
                half3 albedo = lerp(ba.rgb, _MossColor.rgb, mm);
                Light ml = GetMainLight(i.shadowCoord); float NdotL = saturate(dot(N, ml.direction));
                return half4(albedo * (ml.color * NdotL * ml.shadowAttenuation + SampleSH(N)), 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_wet_surface_shader(wetness=0.7):
    """Wet surface: darkened albedo, boosted specular, flattened normals."""
    return f'''Shader "VeilBreakers/WetSurface"
{{
    Properties {{ _MainTex ("Albedo", 2D) = "white" {{}} _BumpMap ("Normal", 2D) = "bump" {{}} _Wetness ("Wetness", Range(0,1)) = {wetness} _WetDarkening ("Darkening", Range(0,0.8)) = 0.4 _WetSmoothness ("Wet Smoothness", Range(0,1)) = 0.8 _Porosity ("Porosity", Range(0,1)) = 0.5 _Metallic ("Metallic", Range(0,1)) = 0 _Smoothness ("Smoothness", Range(0,1)) = 0.3 _NormalFlatten ("Normal Flatten", Range(0,1)) = 0.5 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 tangentOS : TANGENT; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 normalWS : TEXCOORD1; float3 tangentWS : TEXCOORD2; float3 bitangentWS : TEXCOORD3; float3 viewDirWS : TEXCOORD4; float4 shadowCoord : TEXCOORD5; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_BumpMap); SAMPLER(sampler_BumpMap);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float _Wetness; float _WetDarkening; float _WetSmoothness; float _Porosity; float _Metallic; float _Smoothness; float _NormalFlatten; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); VertexNormalInputs vni = GetVertexNormalInputs(input.normalOS, input.tangentOS); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex); o.normalWS = vni.normalWS; o.tangentWS = vni.tangentWS; o.bitangentWS = vni.bitangentWS; o.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half4 a = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
                half3 nTS = lerp(UnpackNormal(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, i.uv)), half3(0,0,1), _Wetness * _NormalFlatten);
                float3 N = normalize(mul(nTS, float3x3(normalize(i.tangentWS), normalize(i.bitangentWS), normalize(i.normalWS))));
                half3 wa = a.rgb * (1 - _WetDarkening * _Porosity * _Wetness);
                float sm = lerp(_Smoothness, max(_Smoothness, _WetSmoothness), _Wetness);
                Light ml = GetMainLight(i.shadowCoord); float NdotL = saturate(dot(N, ml.direction));
                float3 V = normalize(i.viewDirWS); float3 H = normalize(ml.direction + V);
                float spec = pow(saturate(dot(N, H)), lerp(1, 256, sm));
                return half4(wa * (ml.color * NdotL * ml.shadowAttenuation + SampleSH(N)) + ml.color * spec * lerp(_Metallic, _Metallic+0.3, _Wetness), 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_puddle_shader(puddle_color=(0.1,0.12,0.15)):
    """Puddle accumulation on flat surfaces with ripples and reflection."""
    pr,pg,pb = puddle_color
    return f'''Shader "VeilBreakers/PuddleAccumulation"
{{
    Properties {{ _MainTex ("Base", 2D) = "white" {{}} _BumpMap ("Normal", 2D) = "bump" {{}} _PuddleColor ("Puddle Color", Color) = ({pr},{pg},{pb},1) _PuddleAmount ("Amount", Range(0,1)) = 0.5 _PuddleNoiseTex ("Noise", 2D) = "white" {{}} _PuddleNoiseScale ("Noise Scale", Float) = 2 _PuddleSmoothness ("Smoothness", Range(0,1)) = 0.95 _PuddleRippleTex ("Ripple", 2D) = "bump" {{}} _RippleSpeed ("Ripple Speed", Float) = 1 _RippleScale ("Ripple Scale", Float) = 5 _Smoothness ("Base Smoothness", Range(0,1)) = 0.3 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 tangentOS : TANGENT; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; float3 normalWS : TEXCOORD2; float3 viewDirWS : TEXCOORD3; float4 shadowCoord : TEXCOORD4; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_BumpMap); SAMPLER(sampler_BumpMap); TEXTURE2D(_PuddleNoiseTex); SAMPLER(sampler_PuddleNoiseTex); TEXTURE2D(_PuddleRippleTex); SAMPLER(sampler_PuddleRippleTex);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float4 _PuddleColor; float _PuddleAmount; float _PuddleNoiseScale; float _PuddleSmoothness; float _RippleSpeed; float _RippleScale; float _Smoothness; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex); o.positionWS = vpi.positionWS; o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half4 ba = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv); float3 N = normalize(i.normalWS);
                float flat = smoothstep(0.8, 1, saturate(dot(N, float3(0,1,0))));
                float noise = SAMPLE_TEXTURE2D(_PuddleNoiseTex, sampler_PuddleNoiseTex, i.positionWS.xz * _PuddleNoiseScale * 0.01).r;
                float pm = flat * saturate((noise - (1 - _PuddleAmount)) * 5);
                half3 albedo = lerp(ba.rgb, _PuddleColor.rgb, pm * 0.7);
                float sm = lerp(_Smoothness, _PuddleSmoothness, pm);
                Light ml = GetMainLight(i.shadowCoord); float NdotL = saturate(dot(N, ml.direction));
                float3 V = normalize(i.viewDirWS); float3 H = normalize(ml.direction + V);
                float spec = pow(saturate(dot(N, H)), lerp(1, 256, sm));
                float fresnel = pow(1 - saturate(dot(N, V)), 5) * pm;
                return half4(albedo * (ml.color * NdotL * ml.shadowAttenuation + SampleSH(N)) + ml.color * spec * 0.5 + SampleSH(reflect(-V, N)) * fresnel, 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_rain_ripple_shader():
    """Rain ripple concentric rings on upward-facing surfaces."""
    return f'''Shader "VeilBreakers/RainRipple"
{{
    Properties {{ _MainTex ("Base", 2D) = "white" {{}} _RippleIntensity ("Intensity", Range(0,1)) = 0.5 _RippleScale ("Scale", Float) = 10 _RippleSpeed ("Speed", Float) = 3 _RippleDensity ("Density", Float) = 4 _Wetness ("Wetness", Range(0,1)) = 0.5 _Smoothness ("Smoothness", Range(0,1)) = 0.3 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; float3 normalWS : TEXCOORD2; float3 viewDirWS : TEXCOORD3; float4 shadowCoord : TEXCOORD4; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float _RippleIntensity; float _RippleScale; float _RippleSpeed; float _RippleDensity; float _Wetness; float _Smoothness; CBUFFER_END
            float2 hash22(float2 p) {{ float3 p3 = frac(float3(p.xyx)*float3(0.1031,0.1030,0.0973)); p3 += dot(p3,p3.yzx+33.33); return frac((p3.xx+p3.yz)*p3.zy); }}
            float ripple(float2 uv, float t) {{ float2 cell = floor(uv*_RippleDensity); float2 rnd = hash22(cell); float tt = frac(t+rnd.x); float dist = length(frac(uv*_RippleDensity)-0.5-(rnd-0.5)*0.5); return sin(dist*40-tt*_RippleSpeed*20)*smoothstep(0.4,0,dist)*(1-tt)*(1-tt); }}
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex); o.positionWS = vpi.positionWS; o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half4 a = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
                float2 rUV = i.positionWS.xz * _RippleScale * 0.01;
                float r = (ripple(rUV, _Time.y*0.3) + ripple(rUV+0.5, _Time.y*0.3+0.33) + ripple(rUV+0.25, _Time.y*0.3+0.66)) * _RippleIntensity / 3;
                r *= smoothstep(0.7, 1, saturate(dot(normalize(i.normalWS), float3(0,1,0))));
                float3 N = normalize(i.normalWS);
                Light ml = GetMainLight(i.shadowCoord); float NdotL = saturate(dot(N, ml.direction));
                half3 wa = a.rgb * (1 - _Wetness * 0.3);
                float sm = lerp(_Smoothness, max(_Smoothness, 0.9), _Wetness);
                float3 V = normalize(i.viewDirWS); float spec = pow(saturate(dot(N, normalize(ml.direction+V))), lerp(1,256,sm));
                return half4(wa * (ml.color * NdotL * ml.shadowAttenuation + SampleSH(N)) + ml.color * spec * 0.3, 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_god_rays_shader(ray_color=(1,0.9,0.7), ray_density=0.5):
    """Screen-space radial blur god rays from light source."""
    rr,rg,rb = ray_color
    return f'''Shader "VeilBreakers/GodRays"
{{
    Properties {{ _MainTex ("Scene", 2D) = "white" {{}} _RayColor ("Ray Color", Color) = ({rr},{rg},{rb},1) _RayDensity ("Density", Range(0,2)) = {ray_density} _RaySamples ("Samples", Float) = 32 _RayDecay ("Decay", Range(0.9,1)) = 0.96 _RayWeight ("Weight", Range(0,1)) = 0.3 _RayExposure ("Exposure", Range(0,2)) = 1 _LightScreenPos ("Light Pos", Vector) = (0.5,0.7,0,0) }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" }} ZWrite Off Cull Off
        Pass {{ Name "GodRays"
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            CBUFFER_START(UnityPerMaterial) float4 _RayColor; float _RayDensity; float _RaySamples; float _RayDecay; float _RayWeight; float _RayExposure; float4 _LightScreenPos; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; o.positionCS = TransformObjectToHClip(input.positionOS.xyz); o.uv = input.uv; return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half4 sc = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
                float2 dUV = (i.uv - _LightScreenPos.xy) * _RayDensity / _RaySamples;
                float2 sUV = i.uv; half3 rays = 0; float decay = 1;
                for (int j = 0; j < (int)_RaySamples; j++) {{ sUV -= dUV; half3 s = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, sUV).rgb; s *= step(0.5, dot(s, float3(0.299,0.587,0.114))); s *= decay * _RayWeight; rays += s; decay *= _RayDecay; }}
                return half4(sc.rgb + rays * _RayExposure * _RayColor.rgb, sc.a);
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_procedural_skybox_shader(horizon_color=(0.7,0.5,0.3), zenith_color=(0.1,0.15,0.35)):
    """Procedural skybox with sun disk, clouds, stars, and horizon haze."""
    hr,hg,hb = horizon_color; zr,zg,zb = zenith_color
    return f'''Shader "VeilBreakers/ProceduralSkybox"
{{
    Properties {{ _HorizonColor ("Horizon", Color) = ({hr},{hg},{hb},1) _ZenithColor ("Zenith", Color) = ({zr},{zg},{zb},1) _SunColor ("Sun", Color) = (1,0.95,0.8,1) _SunSize ("Sun Size", Range(0.01,0.2)) = 0.05 _SunBloom ("Bloom", Range(1,20)) = 8 _CloudTex ("Cloud", 2D) = "gray" {{}} _CloudColor ("Cloud Color", Color) = (0.9,0.85,0.8,1) _CloudSpeed ("Cloud Speed", Float) = 0.01 _CloudDensity ("Cloud Density", Range(0,1)) = 0.5 _CloudScale ("Cloud Scale", Float) = 2 _HazeStrength ("Haze", Range(0,1)) = 0.3 _StarDensity ("Stars", Range(0,1)) = 0.5 _NightThreshold ("Night Threshold", Range(-0.5,0.5)) = -0.1 }}
    SubShader
    {{
        Tags {{ "Queue"="Background" "RenderType"="Background" "RenderPipeline"="UniversalPipeline" "PreviewType"="Skybox" }} Cull Off ZWrite Off
        Pass {{
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            struct Attributes {{ float4 positionOS : POSITION; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float3 viewDirWS : TEXCOORD0; }};
            TEXTURE2D(_CloudTex); SAMPLER(sampler_CloudTex);
            CBUFFER_START(UnityPerMaterial) float4 _HorizonColor; float4 _ZenithColor; float4 _SunColor; float _SunSize; float _SunBloom; float4 _CloudColor; float _CloudSpeed; float _CloudDensity; float _CloudScale; float _HazeStrength; float _StarDensity; float _NightThreshold; CBUFFER_END
            float hash21(float2 p) {{ return frac(sin(dot(p, float2(127.1,311.7)))*43758.5453); }}
            Varyings vert(Attributes input) {{ Varyings o; o.positionCS = TransformObjectToHClip(input.positionOS.xyz); o.viewDirWS = TransformObjectToWorld(input.positionOS.xyz); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float3 V = normalize(i.viewDirWS);
                half3 sky = lerp(_HorizonColor.rgb, _ZenithColor.rgb, pow(saturate(V.y), 0.8));
                float sd = dot(V, _MainLightPosition.xyz);
                sky += _SunColor.rgb * (smoothstep(1-_SunSize, 1, sd) * 5 + pow(saturate(sd), _SunBloom) * 0.5);
                sky = lerp(sky, _HorizonColor.rgb, exp(-abs(V.y)*8) * _HazeStrength);
                float2 cUV = V.xz / (V.y+0.1) * _CloudScale + _Time.y * _CloudSpeed;
                sky = lerp(sky, _CloudColor.rgb, smoothstep(1-_CloudDensity, 1, SAMPLE_TEXTURE2D(_CloudTex, sampler_CloudTex, cUV).r) * step(0,V.y));
                float nf = saturate(-_MainLightPosition.y - _NightThreshold);
                sky += step(1-_StarDensity*0.01, hash21(floor(V.xz/(abs(V.y)+0.01)*50))) * nf * step(0.1, V.y) * 2;
                return half4(sky, 1);
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_cloud_shadow_shader(shadow_strength=0.4, cloud_speed=0.01):
    """Animated cloud shadow projection via multiplicative blending."""
    return f'''Shader "VeilBreakers/CloudShadow"
{{
    Properties {{ _CloudNoiseTex ("Noise", 2D) = "gray" {{}} _ShadowStrength ("Strength", Range(0,1)) = {shadow_strength} _CloudSpeed ("Speed", Float) = {cloud_speed} _CloudScale ("Scale", Float) = 0.002 _CloudThreshold ("Threshold", Range(0,1)) = 0.5 _CloudSoftness ("Softness", Range(0,0.5)) = 0.1 _ShadowColor ("Color", Color) = (0.1,0.1,0.15,1) _WindDirection ("Wind", Vector) = (1,0,0.3,0) }}
    SubShader
    {{
        Tags {{ "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent-50" }} Blend DstColor Zero ZWrite Off
        Pass {{ Name "CloudShadow"
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            struct Attributes {{ float4 positionOS : POSITION; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; }};
            TEXTURE2D(_CloudNoiseTex); SAMPLER(sampler_CloudNoiseTex);
            CBUFFER_START(UnityPerMaterial) float _ShadowStrength; float _CloudSpeed; float _CloudScale; float _CloudThreshold; float _CloudSoftness; float4 _ShadowColor; float4 _WindDirection; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.positionWS = vpi.positionWS; return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float2 cUV = i.positionWS.xz * _CloudScale + _Time.y * _CloudSpeed * normalize(_WindDirection.xz);
                float shadow = smoothstep(_CloudThreshold-_CloudSoftness, _CloudThreshold+_CloudSoftness, SAMPLE_TEXTURE2D(_CloudNoiseTex, sampler_CloudNoiseTex, cUV).r) * _ShadowStrength;
                return half4(lerp(half3(1,1,1), _ShadowColor.rgb, shadow), 1);
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_distance_fog_gradient_shader(near_color=(0.7,0.75,0.8), far_color=(0.4,0.45,0.55)):
    """Three-band distance fog gradient post-process."""
    nr,ng,nb = near_color; fr,fg,fb = far_color
    return f'''Shader "VeilBreakers/DistanceFogGradient"
{{
    Properties {{ _MainTex ("Scene", 2D) = "white" {{}} _NearFogColor ("Near", Color) = ({nr},{ng},{nb},1) _MidFogColor ("Mid", Color) = (0.55,0.6,0.65,1) _FarFogColor ("Far", Color) = ({fr},{fg},{fb},1) _FogStart ("Start", Float) = 20 _FogMid ("Mid", Float) = 100 _FogEnd ("End", Float) = 300 _FogDensity ("Density", Range(0,1)) = 0.8 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" }} ZWrite Off Cull Off
        Pass {{ Name "DistanceFog"
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            CBUFFER_START(UnityPerMaterial) float4 _NearFogColor; float4 _MidFogColor; float4 _FarFogColor; float _FogStart; float _FogMid; float _FogEnd; float _FogDensity; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; o.positionCS = TransformObjectToHClip(input.positionOS.xyz); o.uv = input.uv; return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half4 sc = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
                float d = LinearEyeDepth(SampleSceneDepth(i.uv), _ZBufferParams);
                half3 fc = lerp(lerp(_NearFogColor.rgb, _MidFogColor.rgb, saturate((d-_FogStart)/max(_FogMid-_FogStart,0.001))), _FarFogColor.rgb, saturate((d-_FogMid)/max(_FogEnd-_FogMid,0.001)));
                return half4(lerp(sc.rgb, fc, saturate((d-_FogStart)/max(_FogEnd-_FogStart,0.001))*_FogDensity), sc.a);
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_detail_normal_blend_shader():
    """Detail normal blending with reoriented normal mapping and distance fade."""
    return f'''Shader "VeilBreakers/DetailNormalBlend"
{{
    Properties {{ _MainTex ("Albedo", 2D) = "white" {{}} _BumpMap ("Base Normal", 2D) = "bump" {{}} _DetailNormal ("Detail Normal", 2D) = "bump" {{}} _DetailTiling ("Tiling", Float) = 10 _DetailStrength ("Strength", Range(0,2)) = 1 _DetailFadeStart ("Fade Start", Float) = 10 _DetailFadeEnd ("Fade End", Float) = 50 _Metallic ("Metallic", Range(0,1)) = 0 _Smoothness ("Smoothness", Range(0,1)) = 0.5 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 tangentOS : TANGENT; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; float3 normalWS : TEXCOORD2; float3 tangentWS : TEXCOORD3; float3 bitangentWS : TEXCOORD4; float3 viewDirWS : TEXCOORD5; float4 shadowCoord : TEXCOORD6; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_BumpMap); SAMPLER(sampler_BumpMap); TEXTURE2D(_DetailNormal); SAMPLER(sampler_DetailNormal);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float _DetailTiling; float _DetailStrength; float _DetailFadeStart; float _DetailFadeEnd; float _Metallic; float _Smoothness; CBUFFER_END
            float3 blendNormals(float3 b, float3 d) {{ float3 t = b+float3(0,0,1); float3 u = d*float3(-1,-1,1); return normalize(t*dot(t,u)-u*t.z); }}
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); VertexNormalInputs vni = GetVertexNormalInputs(input.normalOS, input.tangentOS); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex); o.positionWS = vpi.positionWS; o.normalWS = vni.normalWS; o.tangentWS = vni.tangentWS; o.bitangentWS = vni.bitangentWS; o.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half4 a = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
                half3 bn = UnpackNormal(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, i.uv));
                half3 dn = UnpackNormal(SAMPLE_TEXTURE2D(_DetailNormal, sampler_DetailNormal, i.uv * _DetailTiling));
                dn.xy *= _DetailStrength * (1 - saturate((distance(i.positionWS, _WorldSpaceCameraPos) - _DetailFadeStart) / max(_DetailFadeEnd - _DetailFadeStart, 0.001)));
                float3 N = normalize(mul(blendNormals(bn, dn), float3x3(normalize(i.tangentWS), normalize(i.bitangentWS), normalize(i.normalWS))));
                Light ml = GetMainLight(i.shadowCoord); float NdotL = saturate(dot(N, ml.direction));
                float3 V = normalize(i.viewDirWS); float spec = pow(saturate(dot(N, normalize(ml.direction+V))), lerp(1,128,_Smoothness));
                return half4(a.rgb * (ml.color * NdotL * ml.shadowAttenuation + SampleSH(N)) + ml.color * spec * _Metallic, 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_rock_face_shader(rock_color=(0.35,0.3,0.25)):
    """Layered rock face with triplanar, strata, and weathering."""
    rr,rg,rb = rock_color
    return f'''Shader "VeilBreakers/RockFace"
{{
    Properties {{ _RockColor ("Color", Color) = ({rr},{rg},{rb},1) _RockTex ("Albedo", 2D) = "white" {{}} _StrataColor ("Strata", Color) = (0.25,0.22,0.18,1) _StrataScale ("Strata Scale", Float) = 0.5 _StrataSharpness ("Strata Sharp", Range(1,20)) = 8 _WeatheringTex ("Weather", 2D) = "white" {{}} _WeatheringAmount ("Amount", Range(0,1)) = 0.5 _WeatheringColor ("W Color", Color) = (0.4,0.38,0.32,1) _Tiling ("Tiling", Float) = 1 _TriplanarSharpness ("Tri Sharp", Float) = 4 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float3 normalOS : NORMAL; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; float3 normalWS : TEXCOORD1; float4 shadowCoord : TEXCOORD2; }};
            TEXTURE2D(_RockTex); SAMPLER(sampler_RockTex); TEXTURE2D(_WeatheringTex); SAMPLER(sampler_WeatheringTex);
            CBUFFER_START(UnityPerMaterial) float4 _RockColor; float4 _StrataColor; float _StrataScale; float _StrataSharpness; float _WeatheringAmount; float4 _WeatheringColor; float _Tiling; float _TriplanarSharpness; CBUFFER_END
            half4 triSamp(TEXTURE2D_PARAM(tex, samp), float3 p, float3 N) {{ float3 w = pow(abs(N), _TriplanarSharpness); w /= (w.x+w.y+w.z+0.001); return SAMPLE_TEXTURE2D(tex,samp,p.yz*_Tiling)*w.x + SAMPLE_TEXTURE2D(tex,samp,p.xz*_Tiling)*w.y + SAMPLE_TEXTURE2D(tex,samp,p.xy*_Tiling)*w.z; }}
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.positionWS = vpi.positionWS; o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float3 N = normalize(i.normalWS);
                half3 albedo = lerp(triSamp(TEXTURE2D_ARGS(_RockTex, sampler_RockTex), i.positionWS, N).rgb * _RockColor.rgb, _StrataColor.rgb, pow(saturate(sin(i.positionWS.y*_StrataScale*10)*0.5+0.5), _StrataSharpness) * 0.3);
                albedo = lerp(albedo, _WeatheringColor.rgb, (1-saturate(dot(N,float3(0,1,0)))) * triSamp(TEXTURE2D_ARGS(_WeatheringTex, sampler_WeatheringTex), i.positionWS*0.5, N).r * _WeatheringAmount);
                Light ml = GetMainLight(i.shadowCoord);
                return half4(albedo * (ml.color * saturate(dot(N, ml.direction)) * ml.shadowAttenuation + SampleSH(N)), 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_caustics_shader(caustic_color=(0.3,0.5,0.7), caustic_speed=0.5):
    """Dual-layer underwater caustic projection (additive)."""
    cr,cg,cb = caustic_color
    return f'''Shader "VeilBreakers/Caustics"
{{
    Properties {{ _CausticTex ("Caustic", 2D) = "white" {{}} _CausticColor ("Color", Color) = ({cr},{cg},{cb},1) _CausticSpeed ("Speed", Float) = {caustic_speed} _CausticScale ("Scale", Float) = 2 _CausticIntensity ("Intensity", Range(0,3)) = 1.5 _WaterLevel ("Water Y", Float) = 0 _CausticFade ("Fade", Float) = 10 }}
    SubShader
    {{
        Tags {{ "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent-40" }} Blend One One ZWrite Off
        Pass {{ Name "CausticProjection"
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            struct Attributes {{ float4 positionOS : POSITION; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; }};
            TEXTURE2D(_CausticTex); SAMPLER(sampler_CausticTex);
            CBUFFER_START(UnityPerMaterial) float4 _CausticColor; float _CausticSpeed; float _CausticScale; float _CausticIntensity; float _WaterLevel; float _CausticFade; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.positionWS = vpi.positionWS; return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float bw = _WaterLevel - i.positionWS.y; clip(bw);
                float c = min(SAMPLE_TEXTURE2D(_CausticTex, sampler_CausticTex, i.positionWS.xz*_CausticScale + _Time.y*_CausticSpeed*float2(0.3,0.1)).r, SAMPLE_TEXTURE2D(_CausticTex, sampler_CausticTex, i.positionWS.xz*_CausticScale*0.8 - _Time.y*_CausticSpeed*float2(0.1,0.3)).r);
                return half4(_CausticColor.rgb * c * _CausticIntensity * (1 - saturate(bw/_CausticFade)), 0);
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_underwater_post_process_shader(water_tint=(0.1,0.3,0.4)):
    """Underwater post-process: tint, distortion, caustics, vignette."""
    wr,wg,wb = water_tint
    return f'''Shader "VeilBreakers/UnderwaterPostProcess"
{{
    Properties {{ _MainTex ("Scene", 2D) = "white" {{}} _WaterTint ("Tint", Color) = ({wr},{wg},{wb},1) _TintStrength ("Tint Strength", Range(0,1)) = 0.5 _UnderwaterFogDensity ("Fog Density", Range(0,0.1)) = 0.02 _DistortionTex ("Distortion", 2D) = "bump" {{}} _DistortionStrength ("Distortion Str", Range(0,0.1)) = 0.02 _DistortionSpeed ("Distortion Speed", Float) = 0.5 _CausticTex ("Caustic", 2D) = "white" {{}} _CausticIntensity ("Caustic Int", Range(0,1)) = 0.3 _VignetteStrength ("Vignette", Range(0,1)) = 0.3 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" }} ZWrite Off Cull Off
        Pass {{ Name "Underwater"
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_DistortionTex); SAMPLER(sampler_DistortionTex); TEXTURE2D(_CausticTex); SAMPLER(sampler_CausticTex);
            CBUFFER_START(UnityPerMaterial) float4 _WaterTint; float _TintStrength; float _UnderwaterFogDensity; float _DistortionStrength; float _DistortionSpeed; float _CausticIntensity; float _VignetteStrength; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; o.positionCS = TransformObjectToHClip(input.positionOS.xyz); o.uv = input.uv; return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float2 uv = i.uv + UnpackNormal(SAMPLE_TEXTURE2D(_DistortionTex, sampler_DistortionTex, i.uv*3+_Time.y*_DistortionSpeed)).xy * _DistortionStrength;
                half4 sc = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uv);
                float fog = 1 - exp(-LinearEyeDepth(SampleSceneDepth(i.uv), _ZBufferParams) * _UnderwaterFogDensity);
                sc.rgb = lerp(lerp(sc.rgb, _WaterTint.rgb, fog), sc.rgb * _WaterTint.rgb * 2, _TintStrength);
                sc.rgb += SAMPLE_TEXTURE2D(_CausticTex, sampler_CausticTex, i.uv*5+_Time.y*0.5*float2(0.3,0.1)).r * _CausticIntensity * (1-fog);
                float2 c = i.uv - 0.5; sc.rgb *= 1 - dot(c,c) * _VignetteStrength * 4;
                return sc;
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_lava_flow_shader(lava_color=(1,0.3,0.05), crust_color=(0.15,0.08,0.05)):
    """Animated lava with emissive crust, flow noise, and pulse."""
    lr,lg,lb = lava_color; cr,cg,cb = crust_color
    return f'''Shader "VeilBreakers/LavaFlow"
{{
    Properties {{ _LavaColor ("Lava", Color) = ({lr},{lg},{lb},1) _CrustColor ("Crust", Color) = ({cr},{cg},{cb},1) _NoiseTex ("Noise", 2D) = "white" {{}} _FlowSpeed ("Speed", Float) = 0.3 _FlowDirection ("Dir", Vector) = (0.5,0.3,0,0) _CrustThreshold ("Threshold", Range(0,1)) = 0.5 _EmissiveIntensity ("Emissive", Range(0,10)) = 5 _PulseSpeed ("Pulse Speed", Float) = 1 _PulseAmount ("Pulse Amt", Range(0,0.5)) = 0.2 _Tiling ("Tiling", Float) = 2 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 normalWS : TEXCOORD1; }};
            TEXTURE2D(_NoiseTex); SAMPLER(sampler_NoiseTex);
            CBUFFER_START(UnityPerMaterial) float4 _LavaColor; float4 _CrustColor; float _FlowSpeed; float4 _FlowDirection; float _CrustThreshold; float _EmissiveIntensity; float _PulseSpeed; float _PulseAmount; float _Tiling; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; o.positionCS = GetVertexPositionInputs(input.positionOS.xyz).positionCS; o.uv = input.uv; o.normalWS = TransformObjectToWorldNormal(input.normalOS); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float2 fUV = i.uv*_Tiling + _Time.y*_FlowSpeed*_FlowDirection.xy;
                float combined = (SAMPLE_TEXTURE2D(_NoiseTex, sampler_NoiseTex, fUV).r + SAMPLE_TEXTURE2D(_NoiseTex, sampler_NoiseTex, i.uv*_Tiling*1.5 - _Time.y*_FlowSpeed*0.7*_FlowDirection.yx).r) * 0.5;
                float cm = smoothstep(_CrustThreshold-0.1, _CrustThreshold+0.1, combined);
                float em = (1-cm) * _EmissiveIntensity * (sin(_Time.y*_PulseSpeed)*_PulseAmount+1);
                half3 c = lerp(_LavaColor.rgb, _CrustColor.rgb, cm) + _LavaColor.rgb * em;
                c += SampleSH(normalize(i.normalWS)) * _CrustColor.rgb * cm;
                return half4(c, 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_emissive_crystal_shader(crystal_color=(0.3,0.1,0.8), glow_intensity=3.0):
    """Pulsing emissive crystal with fresnel glow and internal noise."""
    cr,cg,cb = crystal_color
    return f'''Shader "VeilBreakers/EmissiveCrystal"
{{
    Properties {{ _CrystalColor ("Color", Color) = ({cr},{cg},{cb},1) _GlowIntensity ("Glow", Float) = {glow_intensity} _PulseSpeed ("Pulse Speed", Float) = 1.5 _PulseMin ("Pulse Min", Range(0,1)) = 0.3 _NoiseTex ("Noise", 2D) = "white" {{}} _NoiseScale ("Noise Scale", Float) = 2 _FresnelPower ("Fresnel", Float) = 3 _FresnelColor ("Fresnel Color", Color) = (0.5,0.3,1,1) }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 normalWS : TEXCOORD1; float3 viewDirWS : TEXCOORD2; float4 shadowCoord : TEXCOORD3; }};
            TEXTURE2D(_NoiseTex); SAMPLER(sampler_NoiseTex);
            CBUFFER_START(UnityPerMaterial) float4 _CrystalColor; float _GlowIntensity; float _PulseSpeed; float _PulseMin; float _NoiseScale; float _FresnelPower; float4 _FresnelColor; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.uv = input.uv; o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float3 N = normalize(i.normalWS); float3 V = normalize(i.viewDirWS);
                float pulse = lerp(_PulseMin, 1, sin(_Time.y*_PulseSpeed)*0.5+0.5);
                float em = _GlowIntensity * pulse * lerp(0.5, 1, SAMPLE_TEXTURE2D(_NoiseTex, sampler_NoiseTex, i.uv*_NoiseScale+_Time.y*0.2).r);
                float fresnel = pow(1-saturate(dot(N,V)), _FresnelPower);
                Light ml = GetMainLight(i.shadowCoord);
                return half4(_CrystalColor.rgb*em + _FresnelColor.rgb*fresnel*em*0.5 + _CrystalColor.rgb*ml.color*saturate(dot(N,ml.direction))*0.2, 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_cloth_wind_shader(wind_speed=1.0, wind_strength=0.3):
    """Cloth/banner wind with pinned-edge vertex color masking."""
    return f'''Shader "VeilBreakers/ClothWind"
{{
    Properties {{ _MainTex ("Cloth", 2D) = "white" {{}} _WindSpeed ("Speed", Float) = {wind_speed} _WindStrength ("Strength", Float) = {wind_strength} _WindDirection ("Dir", Vector) = (1,0,0.2,0) _FlutterFrequency ("Flutter Freq", Float) = 3 _FlutterAmount ("Flutter Amt", Float) = 0.1 _Color ("Tint", Color) = (1,1,1,1) }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }} Cull Off
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 color : COLOR; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 normalWS : TEXCOORD1; float3 viewDirWS : TEXCOORD2; float4 shadowCoord : TEXCOORD3; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float _WindSpeed; float _WindStrength; float4 _WindDirection; float _FlutterFrequency; float _FlutterAmount; float4 _Color; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; float3 p = input.positionOS.xyz; float3 wd = normalize(_WindDirection.xyz); float f = input.color.r; p += wd*(sin(_Time.y*_WindSpeed+p.y*2+p.x)*_WindStrength + sin(_Time.y*_FlutterFrequency*3+p.x*5+p.y*3)*_FlutterAmount)*f; VertexPositionInputs vpi = GetVertexPositionInputs(p); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex); o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half4 a = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv) * _Color;
                float3 N = normalize(i.normalWS) * sign(dot(normalize(i.normalWS), normalize(i.viewDirWS)));
                Light ml = GetMainLight(i.shadowCoord);
                return half4(a.rgb * ml.color * (saturate(dot(N,ml.direction)) + saturate(dot(-N,ml.direction))*0.3) * ml.shadowAttenuation + SampleSH(N)*a.rgb, a.a);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_triplanar_moss_shader(moss_color=(0.12,0.3,0.08)):
    """Triplanar moss blend on world normals for UV-independent coverage."""
    mr,mg,mb = moss_color
    return f'''Shader "VeilBreakers/TriplanarMoss"
{{
    Properties {{ _MainTex ("Base", 2D) = "white" {{}} _MossColor ("Moss", Color) = ({mr},{mg},{mb},1) _MossTex ("Moss Tex", 2D) = "white" {{}} _MossNoiseTex ("Noise", 2D) = "white" {{}} _MossAmount ("Amount", Range(0,1)) = 0.6 _MossSharpness ("Sharp", Range(1,20)) = 8 _MossNoiseScale ("N Scale", Float) = 2 _TriplanarSharpness ("Tri Sharp", Float) = 4 _Tiling ("Tiling", Float) = 1 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; float3 normalWS : TEXCOORD2; float4 shadowCoord : TEXCOORD3; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_MossTex); SAMPLER(sampler_MossTex); TEXTURE2D(_MossNoiseTex); SAMPLER(sampler_MossNoiseTex);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float4 _MossColor; float _MossAmount; float _MossSharpness; float _MossNoiseScale; float _TriplanarSharpness; float _Tiling; CBUFFER_END
            half4 triS(TEXTURE2D_PARAM(t,s), float3 p, float3 N, float ti) {{ float3 w = pow(abs(N),_TriplanarSharpness); w/=(w.x+w.y+w.z+0.001); return SAMPLE_TEXTURE2D(t,s,p.yz*ti)*w.x+SAMPLE_TEXTURE2D(t,s,p.xz*ti)*w.y+SAMPLE_TEXTURE2D(t,s,p.xy*ti)*w.z; }}
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex); o.positionWS = vpi.positionWS; o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float3 N = normalize(i.normalWS);
                half3 ba = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv).rgb;
                half3 ma = triS(TEXTURE2D_ARGS(_MossTex, sampler_MossTex), i.positionWS, N, _Tiling).rgb * _MossColor.rgb;
                float mm = saturate((saturate(dot(N,float3(0,1,0))) * triS(TEXTURE2D_ARGS(_MossNoiseTex, sampler_MossNoiseTex), i.positionWS*_MossNoiseScale, N, 0.1).r - (1-_MossAmount)) * _MossSharpness);
                half3 albedo = lerp(ba, ma, mm);
                Light ml = GetMainLight(i.shadowCoord);
                return half4(albedo * (ml.color * saturate(dot(N, ml.direction)) * ml.shadowAttenuation + SampleSH(N)), 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_edge_detect_outline_shader(outline_color=(0,0,0), outline_thickness=1.0):
    """Screen-space edge detection using Roberts Cross on depth+normals."""
    oc_r,oc_g,oc_b = outline_color
    return f'''Shader "VeilBreakers/EdgeDetectOutline"
{{
    Properties {{ _MainTex ("Scene", 2D) = "white" {{}} _OutlineColor ("Color", Color) = ({oc_r},{oc_g},{oc_b},1) _OutlineThickness ("Thickness", Range(0.1,5)) = {outline_thickness} _DepthThreshold ("Depth Thresh", Range(0,10)) = 1.5 _NormalThreshold ("Normal Thresh", Range(0,2)) = 0.5 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" }} ZWrite Off Cull Off
        Pass {{ Name "EdgeDetection"
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareNormalsTexture.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_TexelSize; float4 _OutlineColor; float _OutlineThickness; float _DepthThreshold; float _NormalThreshold; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; o.positionCS = TransformObjectToHClip(input.positionOS.xyz); o.uv = input.uv; return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half4 sc = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv); float2 ts = _MainTex_TexelSize.xy * _OutlineThickness;
                float d00=LinearEyeDepth(SampleSceneDepth(i.uv+float2(-1,-1)*ts),_ZBufferParams); float d11=LinearEyeDepth(SampleSceneDepth(i.uv+float2(1,1)*ts),_ZBufferParams);
                float d01=LinearEyeDepth(SampleSceneDepth(i.uv+float2(-1,1)*ts),_ZBufferParams); float d10=LinearEyeDepth(SampleSceneDepth(i.uv+float2(1,-1)*ts),_ZBufferParams);
                float de = step(_DepthThreshold, sqrt(pow(d00-d11,2)+pow(d01-d10,2)));
                float3 n00=SampleSceneNormals(i.uv+float2(-1,-1)*ts); float3 n11=SampleSceneNormals(i.uv+float2(1,1)*ts);
                float3 n01=SampleSceneNormals(i.uv+float2(-1,1)*ts); float3 n10=SampleSceneNormals(i.uv+float2(1,-1)*ts);
                float ne = step(_NormalThreshold, sqrt(dot(n00-n11,n00-n11)+dot(n01-n10,n01-n10)));
                return half4(lerp(sc.rgb, _OutlineColor.rgb, max(de,ne)), sc.a);
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_ssao_shader(ao_radius=0.5, ao_intensity=1.0, sample_count=16):
    """Screen-space ambient occlusion with hemisphere sampling."""
    return f'''Shader "VeilBreakers/SSAO"
{{
    Properties {{ _MainTex ("Scene", 2D) = "white" {{}} _NoiseTex ("Noise", 2D) = "white" {{}} _AORadius ("Radius", Range(0.01,3)) = {ao_radius} _AOIntensity ("Intensity", Range(0,3)) = {ao_intensity} _AOBias ("Bias", Range(0,0.2)) = 0.025 _SampleCount ("Samples", Float) = {sample_count} }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" }} ZWrite Off Cull Off
        Pass {{ Name "SSAO"
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareNormalsTexture.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_NoiseTex); SAMPLER(sampler_NoiseTex);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_TexelSize; float _AORadius; float _AOIntensity; float _AOBias; float _SampleCount; CBUFFER_END
            static const float3 kernel[16] = {{ float3(0.04,0.04,0.04),float3(-0.09,0.07,0.03),float3(0.05,-0.12,0.06),float3(-0.13,-0.05,0.10),float3(0.15,0.03,0.08),float3(-0.08,0.16,0.14),float3(0.02,-0.11,0.18),float3(-0.18,0.08,0.06),float3(0.20,-0.09,0.12),float3(-0.06,-0.20,0.15),float3(0.12,0.18,0.20),float3(-0.22,-0.03,0.10),float3(0.08,-0.15,0.24),float3(-0.16,0.20,0.08),float3(0.24,0.06,0.16),float3(-0.10,-0.24,0.20) }};
            Varyings vert(Attributes input) {{ Varyings o; o.positionCS = TransformObjectToHClip(input.positionOS.xyz); o.uv = input.uv; return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half4 sc = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
                float depth = LinearEyeDepth(SampleSceneDepth(i.uv), _ZBufferParams);
                float3 normal = SampleSceneNormals(i.uv);
                float3 rv = SAMPLE_TEXTURE2D(_NoiseTex, sampler_NoiseTex, i.uv*_MainTex_TexelSize.zw/4).xyz*2-1;
                float3 T = normalize(rv - normal*dot(rv,normal)); float3 B = cross(normal,T);
                float3x3 TBN = float3x3(T,B,normal); float ao = 0; int ns = min((int)_SampleCount, 16);
                for (int j = 0; j < ns; j++) {{ float3 sd = mul(kernel[j],TBN)*_AORadius; float sd2 = LinearEyeDepth(SampleSceneDepth(i.uv+sd.xy/depth),_ZBufferParams); ao += step(sd2+_AOBias, depth-sd.z*_AORadius)*smoothstep(0,1,_AORadius/abs(depth-sd2)); }}
                return half4(sc.rgb * (1-(ao/ns)*_AOIntensity), sc.a);
            }}
            ENDHLSL
        }}
    }}
}}
'''

def generate_vertex_color_blend_shader():
    """RGBA vertex color 4-layer material blending."""
    return f'''Shader "VeilBreakers/VertexColorBlend"
{{
    Properties {{ _Layer0Tex ("R", 2D) = "white" {{}} _Layer0Tiling ("R Tiling", Float) = 5 _Layer1Tex ("G", 2D) = "white" {{}} _Layer1Tiling ("G Tiling", Float) = 5 _Layer2Tex ("B", 2D) = "white" {{}} _Layer2Tiling ("B Tiling", Float) = 5 _Layer3Tex ("A", 2D) = "white" {{}} _Layer3Tiling ("A Tiling", Float) = 5 _Smoothness ("Smoothness", Range(0,1)) = 0.5 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 color : COLOR; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 normalWS : TEXCOORD1; float3 viewDirWS : TEXCOORD2; float4 shadowCoord : TEXCOORD3; float4 vc : TEXCOORD4; }};
            TEXTURE2D(_Layer0Tex); SAMPLER(sampler_Layer0Tex); TEXTURE2D(_Layer1Tex); SAMPLER(sampler_Layer1Tex); TEXTURE2D(_Layer2Tex); SAMPLER(sampler_Layer2Tex); TEXTURE2D(_Layer3Tex); SAMPLER(sampler_Layer3Tex);
            CBUFFER_START(UnityPerMaterial) float _Layer0Tiling; float _Layer1Tiling; float _Layer2Tiling; float _Layer3Tiling; float _Smoothness; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.uv = input.uv; o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.viewDirWS = GetWorldSpaceNormalizeViewDir(vpi.positionWS); o.shadowCoord = GetShadowCoord(vpi); o.vc = input.color; return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float4 w = i.vc / max(i.vc.r+i.vc.g+i.vc.b+i.vc.a, 0.001);
                half3 a = SAMPLE_TEXTURE2D(_Layer0Tex,sampler_Layer0Tex,i.uv*_Layer0Tiling).rgb*w.r + SAMPLE_TEXTURE2D(_Layer1Tex,sampler_Layer1Tex,i.uv*_Layer1Tiling).rgb*w.g + SAMPLE_TEXTURE2D(_Layer2Tex,sampler_Layer2Tex,i.uv*_Layer2Tiling).rgb*w.b + SAMPLE_TEXTURE2D(_Layer3Tex,sampler_Layer3Tex,i.uv*_Layer3Tiling).rgb*w.a;
                float3 N = normalize(i.normalWS); Light ml = GetMainLight(i.shadowCoord);
                float spec = pow(saturate(dot(N, normalize(ml.direction+normalize(i.viewDirWS)))), lerp(1,128,_Smoothness));
                return half4(a*(ml.color*saturate(dot(N,ml.direction))*ml.shadowAttenuation+SampleSH(N)) + ml.color*spec*0.2, 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_uv_free_detail_shader():
    """UV-free detail texturing via triplanar projection with distance fade."""
    return f'''Shader "VeilBreakers/UVFreeDetail"
{{
    Properties {{ _MainTex ("Base", 2D) = "white" {{}} _DetailTex ("Detail", 2D) = "gray" {{}} _DetailTiling ("Tiling", Float) = 5 _DetailStrength ("Strength", Range(0,1)) = 0.5 _DetailFadeStart ("Fade Start", Float) = 5 _DetailFadeEnd ("Fade End", Float) = 30 _TriplanarSharpness ("Tri Sharp", Float) = 4 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; float3 normalWS : TEXCOORD2; float4 shadowCoord : TEXCOORD3; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_DetailTex); SAMPLER(sampler_DetailTex);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float _DetailTiling; float _DetailStrength; float _DetailFadeStart; float _DetailFadeEnd; float _TriplanarSharpness; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex); o.positionWS = vpi.positionWS; o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                half3 ba = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv).rgb; float3 N = normalize(i.normalWS);
                float3 w = pow(abs(N), _TriplanarSharpness); w /= (w.x+w.y+w.z+0.001); float3 p = i.positionWS * _DetailTiling;
                half3 d = SAMPLE_TEXTURE2D(_DetailTex,sampler_DetailTex,p.yz).rgb*w.x + SAMPLE_TEXTURE2D(_DetailTex,sampler_DetailTex,p.xz).rgb*w.y + SAMPLE_TEXTURE2D(_DetailTex,sampler_DetailTex,p.xy).rgb*w.z;
                float fade = 1 - saturate((distance(i.positionWS, _WorldSpaceCameraPos) - _DetailFadeStart) / max(_DetailFadeEnd-_DetailFadeStart, 0.001));
                half3 a = lerp(ba, ba*d*2, _DetailStrength*fade);
                Light ml = GetMainLight(i.shadowCoord);
                return half4(a*(ml.color*saturate(dot(N,ml.direction))*ml.shadowAttenuation+SampleSH(N)), 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_snow_accumulation_shader(snow_color=(0.92,0.92,0.97), snow_amount=0.5):
    """Directional snow accumulation with noise breakup and snow line."""
    sr,sg,sb = snow_color
    return f'''Shader "VeilBreakers/SnowAccumulation"
{{
    Properties {{ _MainTex ("Base", 2D) = "white" {{}} _BumpMap ("Normal", 2D) = "bump" {{}} _SnowColor ("Snow", Color) = ({sr},{sg},{sb},1) _SnowAmount ("Amount", Range(0,1)) = {snow_amount} _SnowDirection ("Dir", Vector) = (0,1,0,0) _SnowSharpness ("Sharp", Range(1,20)) = 6 _SnowNoiseTex ("Noise", 2D) = "white" {{}} _SnowNoiseScale ("N Scale", Float) = 3 _SnowLineHeight ("Snow Line", Float) = -1000 _SnowLineFade ("Line Fade", Float) = 50 _Smoothness ("Smoothness", Range(0,1)) = 0.5 }}
    SubShader
    {{
        Tags {{ "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 tangentOS : TANGENT; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; float3 normalWS : TEXCOORD2; float3 tangentWS : TEXCOORD3; float3 bitangentWS : TEXCOORD4; float4 shadowCoord : TEXCOORD5; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_BumpMap); SAMPLER(sampler_BumpMap); TEXTURE2D(_SnowNoiseTex); SAMPLER(sampler_SnowNoiseTex);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float4 _SnowColor; float _SnowAmount; float4 _SnowDirection; float _SnowSharpness; float _SnowNoiseScale; float _SnowLineHeight; float _SnowLineFade; float _Smoothness; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); VertexNormalInputs vni = GetVertexNormalInputs(input.normalOS, input.tangentOS); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex); o.positionWS = vpi.positionWS; o.normalWS = vni.normalWS; o.tangentWS = vni.tangentWS; o.bitangentWS = vni.bitangentWS; o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float3 N = normalize(i.normalWS);
                float dm = saturate(dot(N, normalize(_SnowDirection.xyz)));
                float noise = SAMPLE_TEXTURE2D(_SnowNoiseTex, sampler_SnowNoiseTex, i.positionWS.xz*_SnowNoiseScale*0.01).r;
                float hm = saturate((i.positionWS.y-_SnowLineHeight)/max(_SnowLineFade,0.001));
                float sm = saturate((dm*noise*hm - (1-_SnowAmount))*_SnowSharpness);
                half3 albedo = lerp(SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv).rgb, _SnowColor.rgb, sm);
                half3 bn = lerp(UnpackNormal(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, i.uv)), half3(0,0,1), sm*0.7);
                float3 fN = normalize(mul(bn, float3x3(normalize(i.tangentWS), normalize(i.bitangentWS), N)));
                Light ml = GetMainLight(i.shadowCoord);
                return half4(albedo*(ml.color*saturate(dot(fN,ml.direction))*ml.shadowAttenuation+SampleSH(fN)), 1);
            }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''

def generate_terrain_cutout_shader():
    """Terrain hole/cutout with mask clipping and edge glow."""
    return f'''Shader "VeilBreakers/TerrainCutout"
{{
    Properties {{ _MainTex ("Albedo", 2D) = "white" {{}} _CutoutMask ("Mask (R=vis)", 2D) = "white" {{}} _CutoutThreshold ("Threshold", Range(0,1)) = 0.5 _EdgeColor ("Edge Color", Color) = (0.3,0.15,0.05,1) _EdgeWidth ("Edge Width", Range(0,0.2)) = 0.05 _EdgeEmissive ("Edge Emissive", Range(0,5)) = 2 }}
    SubShader
    {{
        Tags {{ "RenderType"="TransparentCutout" "RenderPipeline"="UniversalPipeline" "Queue"="AlphaTest" }}
        Pass {{ Name "ForwardLit" Tags {{ "LightMode"="UniversalForward" }}
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; }};
            struct Varyings {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; float3 normalWS : TEXCOORD1; float4 shadowCoord : TEXCOORD2; }};
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex); TEXTURE2D(_CutoutMask); SAMPLER(sampler_CutoutMask);
            CBUFFER_START(UnityPerMaterial) float4 _MainTex_ST; float _CutoutThreshold; float4 _EdgeColor; float _EdgeWidth; float _EdgeEmissive; CBUFFER_END
            Varyings vert(Attributes input) {{ Varyings o; VertexPositionInputs vpi = GetVertexPositionInputs(input.positionOS.xyz); o.positionCS = vpi.positionCS; o.uv = TRANSFORM_TEX(input.uv, _MainTex); o.normalWS = TransformObjectToWorldNormal(input.normalOS); o.shadowCoord = GetShadowCoord(vpi); return o; }}
            half4 frag(Varyings i) : SV_Target {{
                float mask = SAMPLE_TEXTURE2D(_CutoutMask, sampler_CutoutMask, i.uv).r; clip(mask - _CutoutThreshold);
                half4 a = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv); float3 N = normalize(i.normalWS);
                half3 edge = _EdgeColor.rgb * (1-saturate((mask-_CutoutThreshold)/_EdgeWidth)) * _EdgeEmissive;
                Light ml = GetMainLight(i.shadowCoord);
                return half4(a.rgb*(ml.color*saturate(dot(N,ml.direction))*ml.shadowAttenuation+SampleSH(N)) + edge, 1);
            }}
            ENDHLSL
        }}
        Pass {{ Name "ShadowCaster" Tags {{ "LightMode"="ShadowCaster" }} ZWrite On ZTest LEqual ColorMask 0
            HLSLPROGRAM
            #pragma vertex sv
            #pragma fragment sf
            {_URP_CORE_INCLUDE}
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"
            struct SA {{ float4 positionOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; }};
            struct SV {{ float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; }};
            TEXTURE2D(_CutoutMask); SAMPLER(sampler_CutoutMask); float _CutoutThreshold; float3 _LightDirection;
            SV sv(SA input) {{ SV o; float3 pw = TransformObjectToWorld(input.positionOS.xyz); float3 nw = TransformObjectToWorldNormal(input.normalOS); o.positionCS = TransformWorldToHClip(ApplyShadowBias(pw,nw,_LightDirection)); o.uv = input.uv;
            #if UNITY_REVERSED_Z
            o.positionCS.z = min(o.positionCS.z, UNITY_NEAR_CLIP_VALUE);
            #else
            o.positionCS.z = max(o.positionCS.z, UNITY_NEAR_CLIP_VALUE);
            #endif
            return o; }}
            half4 sf(SV i) : SV_TARGET {{ clip(SAMPLE_TEXTURE2D(_CutoutMask, sampler_CutoutMask, i.uv).r - _CutoutThreshold); return 0; }}
            ENDHLSL
        }}
    }}
    FallBack "Universal Render Pipeline/Lit"
}}
'''
