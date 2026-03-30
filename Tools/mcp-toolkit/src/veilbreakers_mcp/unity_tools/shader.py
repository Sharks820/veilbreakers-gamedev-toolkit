"""unity_shader tool handler."""

import json
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, logger,
    _write_to_unity, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.shader_templates import (
    generate_arbitrary_shader,
    generate_renderer_feature,
)
from veilbreakers_mcp.shared.unity_templates.character_templates import (
    generate_sss_skin_shader,
    generate_parallax_eye_shader,
    generate_micro_detail_normal_script,
)
from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier




# ---------------------------------------------------------------------------
# unity_shader compound tool (SHDR-01, SHDR-02)
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_shader(
    action: Literal[
        "create_shader",            # SHDR-01: Generate arbitrary HLSL/ShaderLab shader
        "create_renderer_feature",  # SHDR-02: Generate URP ScriptableRendererFeature
        "sss_skin_shader",          # CHAR-08: Subsurface scattering skin shader
        "parallax_eye_shader",      # CHAR-08: Parallax/refraction eye shader
        "micro_detail_normal",      # CHAR-08: Micro-detail normal compositing script
    ],
    # Shader params (SHDR-01)
    shader_name: str = "",
    shader_path: str = "VeilBreakers/Custom",
    render_type: str = "Opaque",
    shader_properties: list[dict] | None = None,
    vertex_code: str = "",
    fragment_code: str = "",
    shader_tags: dict | None = None,
    pragma_directives: list[str] | None = None,
    include_paths: list[str] | None = None,
    cull: str = "Back",
    zwrite: str = "",
    blend: str = "",
    two_passes: bool = False,
    second_pass_vertex: str = "",
    second_pass_fragment: str = "",
    output_dir: str = "Assets/Shaders/Generated",
    # Renderer feature params (SHDR-02)
    feature_name: str = "",
    namespace: str = "",
    settings_fields: list[dict] | None = None,
    render_pass_event: str = "BeforeRenderingPostProcessing",
    shader_property_name: str = "_shader",
    material_properties: list[dict] | None = None,
    pass_code: str = "",
    # SSS skin shader params (CHAR-08)
    sss_color: list[float] | None = None,
    sss_power: float = 3.0,
    sss_distortion: float = 0.5,
    sss_scale: float = 1.0,
    # Parallax eye shader params (CHAR-08)
    iris_depth: float = 0.3,
    pupil_scale: float = 0.3,
    ior: float = 1.33,
    # Micro-detail normal params (CHAR-08)
    base_normal_property: str = "_BumpMap",
    detail_normal_property: str = "_DetailNormalMap",
    detail_tiling: float = 10.0,
    detail_strength: float = 0.5
) -> str:
    """Shader and renderer feature generation."""
    try:
        if action == "create_shader":
            if not shader_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "shader_name is required"}
                )
            shader_source = generate_arbitrary_shader(
                shader_name=shader_name,
                shader_path=shader_path,
                render_type=render_type,
                properties=shader_properties,
                vertex_code=vertex_code,
                fragment_code=fragment_code,
                tags=shader_tags,
                pragma_directives=pragma_directives,
                include_paths=include_paths,
                cull=cull,
                zwrite=zwrite,
                blend=blend,
                two_passes=two_passes,
                second_pass_vertex=second_pass_vertex,
                second_pass_fragment=second_pass_fragment,
            )
            safe_shader_name = sanitize_cs_identifier(shader_name) or "Shader"
            rel_path = f"{output_dir}/{safe_shader_name}.shader"
            abs_path = _write_to_unity(shader_source, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "shader_path": abs_path,
                "shader_name": shader_name,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "create_renderer_feature":
            if not feature_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "feature_name is required"}
                )
            script = generate_renderer_feature(
                feature_name=feature_name,
                namespace=namespace,
                settings_fields=settings_fields,
                render_pass_event=render_pass_event,
                shader_property_name=shader_property_name,
                material_properties=material_properties,
                pass_code=pass_code,
            )
            safe_feature = sanitize_cs_identifier(feature_name) or "Feature"
            rel_path = f"Assets/Scripts/Rendering/{safe_feature}Feature.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "feature_name": feature_name,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "sss_skin_shader":
            sss_tuple = tuple(sss_color) if sss_color and len(sss_color) == 4 else (0.8, 0.3, 0.2, 1.0)
            shader_source = generate_sss_skin_shader(
                sss_color=sss_tuple,
                sss_power=sss_power,
                sss_distortion=sss_distortion,
                sss_scale=sss_scale,
            )
            rel_path = f"{output_dir}/VB_SSS_Skin.shader"
            abs_path = _write_to_unity(shader_source, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "shader_path": abs_path,
                "shader_name": "VeilBreakers/Character/SSS_Skin",
                "next_steps": STANDARD_NEXT_STEPS,
            }, indent=2)

        elif action == "parallax_eye_shader":
            shader_source = generate_parallax_eye_shader(
                iris_depth=iris_depth,
                pupil_scale=pupil_scale,
                ior=ior,
            )
            rel_path = f"{output_dir}/VB_ParallaxEye.shader"
            abs_path = _write_to_unity(shader_source, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "shader_path": abs_path,
                "shader_name": "VeilBreakers/Character/ParallaxEye",
                "next_steps": STANDARD_NEXT_STEPS,
            }, indent=2)

        elif action == "micro_detail_normal":
            script = generate_micro_detail_normal_script(
                base_normal_property=base_normal_property,
                detail_normal_property=detail_normal_property,
                detail_tiling=detail_tiling,
                detail_strength=detail_strength,
            )
            rel_path = "Assets/Editor/Generated/Character/VeilBreakers_MicroDetailNormal.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": STANDARD_NEXT_STEPS,
            }, indent=2)

        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )

    except Exception as exc:
        logger.exception("unity_shader action '%s' failed", action)
        return json.dumps(
            {"status": "error", "action": action, "message": str(exc)}
        )
