"""unity_audio tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template,
)

from veilbreakers_mcp.shared.unity_templates.audio_templates import (
    generate_footstep_manager_script,
    generate_adaptive_music_script,
    generate_audio_zone_script,
    generate_audio_mixer_setup_script,
    generate_audio_pool_manager_script,
    generate_animation_event_sfx_script,
)
from veilbreakers_mcp.shared.unity_templates.audio_middleware_templates import (
    generate_spatial_audio_script,
    generate_audio_lod_script,
    generate_layered_sound_script,
    generate_audio_event_chain_script,
    generate_procedural_foley_script,
    generate_dynamic_music_script,
    generate_portal_audio_script,
    generate_vo_pipeline_script,
)
from veilbreakers_mcp.shared.unity_templates.code_templates import _sanitize_cs_identifier
from veilbreakers_mcp.shared.elevenlabs_client import ElevenLabsAudioClient




@mcp.tool()
async def unity_audio(
    action: Literal[
        "generate_sfx",             # AUD-01: AI SFX from text
        "generate_music_loop",      # AUD-02: combat/exploration/boss/town loops
        "generate_voice_line",      # AUD-03: NPC/monster voice synthesis
        "generate_ambient",         # AUD-04: biome ambient soundscape
        "setup_footstep_system",    # AUD-05: surface-material footstep mapping
        "setup_adaptive_music",     # AUD-06: layered music responding to game state
        "setup_audio_zones",        # AUD-07: reverb zones for caves/outdoor/indoor
        "setup_audio_mixer",        # AUD-08: Unity Audio Mixer with groups
        "setup_audio_pool_manager", # AUD-09: audio pooling, priority, ducking
        "assign_animation_sfx",     # AUD-10: SFX at animation event keyframes
        "setup_spatial_audio",      # AUDM-01: 3D spatial audio with occlusion
        "setup_layered_sound",      # AUDM-02: composite layered sound design
        "setup_audio_event_chain",  # AUDM-03: sequenced audio event chains
        "setup_dynamic_music",      # AUDM-04: horizontal re-sequencing + vertical layering
        "setup_portal_audio",       # AUDM-05: room-based sound propagation via portals
        "setup_audio_lod",          # AUDM-06: distance-based audio quality tiers
        "setup_vo_pipeline",        # AUDM-07: dialogue/VO playback pipeline
        "setup_procedural_foley",   # AUDM-08: movement-based procedural foley
    ],
    # Common
    name: str = "default",
    # SFX/Music/Voice params
    description: str = "",
    duration_seconds: float = 2.0,
    theme: str = "combat",
    text: str = "",
    voice_id: str = "default",
    # Ambient params
    biome: str = "forest",
    layers: list[str] | None = None,
    # Footstep params
    surfaces: list[str] | None = None,
    # Adaptive music params
    music_layers: list[str] | None = None,
    # Audio zone params
    zone_type: str = "cave",
    # Pool manager params
    pool_size: int = 16,
    max_sources: int = 32,
    # Mixer params
    groups: list[str] | None = None,
    # Animation event params
    events: list[dict] | None = None,
    anim_clip_path: str = "",
    # Spatial audio params (AUDM-01)
    min_distance: float = 1.0,
    max_distance: float = 50.0,
    occlusion_enabled: bool = True,
    occlusion_layers: str = "Default",
    rolloff_mode: str = "Logarithmic",
    doppler_level: float = 0.5,
    spread_angle: float = 60.0,
    # Layered sound params (AUDM-02)
    sound_layers: list[dict] | None = None,
    # Audio event chain params (AUDM-03)
    chain_events: list[dict] | None = None,
    # Dynamic music params (AUDM-04)
    sections: list[str] | None = None,
    stems: list[str] | None = None,
    stingers: list[str] | None = None,
    crossfade_duration: float = 2.0,
    # Portal audio params (AUDM-05)
    room_a: str = "RoomA",
    room_b: str = "RoomB",
    attenuation_closed: float = 0.9,
    attenuation_open: float = 0.1,
    # Audio LOD params (AUDM-06)
    lod_distances: list[float] | None = None,
    channel_reduction: bool = True,
    priority_scaling: bool = True,
    # VO pipeline params (AUDM-07)
    vo_entries: list[dict] | None = None,
    # Procedural foley params (AUDM-08)
    armor_type: str = "plate",
    surface_materials: list[str] | None = None,
) -> str:
    """Unity Audio system -- AI audio generation, C# audio infrastructure, and
    middleware-level audio architecture.

    This compound tool covers all audio functionality: AI-generated sound
    effects, music loops, voice lines, and ambient soundscapes via ElevenLabs,
    Unity audio infrastructure setup (mixer, pool manager, footstep system,
    adaptive music, audio zones, animation event SFX), and advanced audio
    middleware features (spatial audio, layered sound, event chains, dynamic
    music, portal propagation, audio LOD, VO pipeline, procedural foley).

    Actions:
    - generate_sfx: Generate AI sound effect from text description (AUD-01)
    - generate_music_loop: Generate loopable music track (AUD-02)
    - generate_voice_line: Synthesise NPC/monster voice line (AUD-03)
    - generate_ambient: Generate layered ambient soundscape (AUD-04)
    - setup_footstep_system: Generate footstep manager C# scripts (AUD-05)
    - setup_adaptive_music: Generate adaptive music manager C# script (AUD-06)
    - setup_audio_zones: Generate audio reverb zone C# script (AUD-07)
    - setup_audio_mixer: Generate audio mixer setup C# script (AUD-08)
    - setup_audio_pool_manager: Generate audio pool manager C# script (AUD-09)
    - assign_animation_sfx: Generate animation event SFX binding C# script (AUD-10)
    - setup_spatial_audio: 3D spatial audio with occlusion/rolloff (AUDM-01)
    - setup_layered_sound: Composite layered sound design (AUDM-02)
    - setup_audio_event_chain: Sequenced audio event chains (AUDM-03)
    - setup_dynamic_music: Horizontal re-sequencing + vertical layering + stingers (AUDM-04)
    - setup_portal_audio: Room-based sound propagation via portals (AUDM-05)
    - setup_audio_lod: Distance-based audio quality tiers (AUDM-06)
    - setup_vo_pipeline: Dialogue/VO playback with subtitles and lip sync (AUDM-07)
    - setup_procedural_foley: Movement-based procedural foley (AUDM-08)

    Args:
        action: The audio action to perform.
        name: Name for the generated asset or script.
        description: Text description for SFX generation.
        duration_seconds: Duration for generated audio (seconds).
        theme: Music theme for loop generation.
        text: Dialogue text for voice line synthesis.
        voice_id: ElevenLabs voice ID for voice synthesis.
        biome: Biome type for ambient soundscape generation.
        layers: Layer descriptions for ambient generation.
        surfaces: Surface types for footstep system.
        music_layers: Layer/state names for adaptive music.
        zone_type: Environment type for audio zones.
        pool_size: Initial pool size for audio pool manager.
        max_sources: Maximum audio sources for pool manager.
        groups: Mixer group names for audio mixer setup.
        events: Animation event definitions for SFX binding.
        anim_clip_path: Path to animation clip for event binding.
    """
    try:
        if action == "generate_sfx":
            return await _handle_audio_generate_sfx(name, description, duration_seconds)
        elif action == "generate_music_loop":
            return await _handle_audio_generate_music_loop(name, theme, duration_seconds)
        elif action == "generate_voice_line":
            return await _handle_audio_generate_voice_line(name, text, voice_id)
        elif action == "generate_ambient":
            return await _handle_audio_generate_ambient(name, biome, layers)
        elif action == "setup_footstep_system":
            return await _handle_audio_setup_footstep(name, surfaces)
        elif action == "setup_adaptive_music":
            return await _handle_audio_setup_adaptive_music(name, music_layers)
        elif action == "setup_audio_zones":
            return await _handle_audio_setup_zones(name, zone_type)
        elif action == "setup_audio_mixer":
            return await _handle_audio_setup_mixer(groups)
        elif action == "setup_audio_pool_manager":
            return await _handle_audio_setup_pool_manager(name, pool_size, max_sources)
        elif action == "assign_animation_sfx":
            return await _handle_audio_assign_animation_sfx(name, events)
        elif action == "setup_spatial_audio":
            return await _handle_dict_template(
                "setup_spatial_audio",
                generate_spatial_audio_script(
                    source_name=name, min_distance=min_distance, max_distance=max_distance,
                    occlusion_enabled=occlusion_enabled, occlusion_layers=occlusion_layers,
                    rolloff_mode=rolloff_mode, doppler_level=doppler_level, spread_angle=spread_angle,
                ),
            )
        elif action == "setup_layered_sound":
            return await _handle_dict_template(
                "setup_layered_sound",
                generate_layered_sound_script(sound_name=name, layers=sound_layers),
            )
        elif action == "setup_audio_event_chain":
            return await _handle_dict_template(
                "setup_audio_event_chain",
                generate_audio_event_chain_script(chain_name=name, events=chain_events),
            )
        elif action == "setup_dynamic_music":
            return await _handle_dict_template(
                "setup_dynamic_music",
                generate_dynamic_music_script(
                    music_name=name, sections=sections, stems=stems,
                    stingers=stingers, crossfade_duration=crossfade_duration,
                ),
            )
        elif action == "setup_portal_audio":
            return await _handle_dict_template(
                "setup_portal_audio",
                generate_portal_audio_script(
                    portal_name=name, room_a=room_a, room_b=room_b,
                    attenuation_closed=attenuation_closed, attenuation_open=attenuation_open,
                ),
            )
        elif action == "setup_audio_lod":
            return await _handle_dict_template(
                "setup_audio_lod",
                generate_audio_lod_script(
                    lod_distances=lod_distances, channel_reduction=channel_reduction,
                    priority_scaling=priority_scaling,
                ),
            )
        elif action == "setup_vo_pipeline":
            return await _handle_dict_template(
                "setup_vo_pipeline",
                generate_vo_pipeline_script(database_name=name, entries=vo_entries),
            )
        elif action == "setup_procedural_foley":
            return await _handle_dict_template(
                "setup_procedural_foley",
                generate_procedural_foley_script(
                    character_name=name, armor_type=armor_type,
                    surface_materials=surface_materials,
                ),
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_audio action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})



_audio_client: ElevenLabsAudioClient | None = None


def _get_audio_client() -> ElevenLabsAudioClient:
    """Lazily initialise the ElevenLabs audio client."""
    global _audio_client
    if _audio_client is None:
        _audio_client = ElevenLabsAudioClient(
            api_key=settings.elevenlabs_api_key or None,
            unity_project_path=settings.unity_project_path,
        )
    return _audio_client

# ---------------------------------------------------------------------------
# Audio action handlers
# ---------------------------------------------------------------------------


async def _handle_audio_generate_sfx(
    name: str, description: str, duration_seconds: float
) -> str:
    """Generate AI SFX from text description (AUD-01)."""
    client = _get_audio_client()
    safe_name = _sanitize_cs_identifier(name) or "sfx"
    output_rel = f"Assets/Resources/Audio/SFX/{safe_name}.mp3"

    if settings.unity_project_path:
        output_path = str(Path(settings.unity_project_path) / output_rel)
    else:
        output_path = output_rel

    result = client.generate_sfx(
        description=description,
        duration_seconds=duration_seconds,
        output_path=output_path,
    )

    return json.dumps(
        {
            "status": "success",
            "action": "generate_sfx",
            "audio_path": result["path"],
            "relative_path": output_rel,
            "duration": result["duration"],
            "stub": result["stub"],
            "description": description,
            "next_steps": [
                "Audio file written. Import into Unity via AssetDatabase.Refresh.",
                "Call unity_editor action='recompile' to pick up new assets.",
            ],
        },
        indent=2,
    )


async def _handle_audio_generate_music_loop(
    name: str, theme: str, duration_seconds: float
) -> str:
    """Generate loopable music track (AUD-02)."""
    client = _get_audio_client()
    safe_name = _sanitize_cs_identifier(name) or "music"
    safe_theme = _sanitize_cs_identifier(theme) or "theme"
    output_rel = f"Assets/Resources/Audio/Music/{safe_name}_{safe_theme}.mp3"

    if settings.unity_project_path:
        output_path = str(Path(settings.unity_project_path) / output_rel)
    else:
        output_path = output_rel

    result = client.generate_music_loop(
        theme=theme,
        duration_seconds=duration_seconds,
        output_path=output_path,
    )

    return json.dumps(
        {
            "status": "success",
            "action": "generate_music_loop",
            "audio_path": result["path"],
            "relative_path": output_rel,
            "duration": result["duration"],
            "stub": result["stub"],
            "theme": theme,
            "next_steps": [
                "Music loop written. Import into Unity via AssetDatabase.Refresh.",
                "Assign to AdaptiveMusicManager via inspector or script.",
            ],
        },
        indent=2,
    )


async def _handle_audio_generate_voice_line(
    name: str, text: str, voice_id: str
) -> str:
    """Synthesise NPC/monster voice line (AUD-03)."""
    client = _get_audio_client()
    safe_name = _sanitize_cs_identifier(name) or "voice"
    output_rel = f"Assets/Resources/Audio/Voice/{safe_name}.mp3"

    if settings.unity_project_path:
        output_path = str(Path(settings.unity_project_path) / output_rel)
    else:
        output_path = output_rel

    result = client.generate_voice_line(
        text=text,
        voice_id=voice_id,
        output_path=output_path,
    )

    return json.dumps(
        {
            "status": "success",
            "action": "generate_voice_line",
            "audio_path": result["path"],
            "relative_path": output_rel,
            "stub": result["stub"],
            "text": text,
            "voice_id": voice_id,
            "next_steps": [
                "Voice line written. Import into Unity via AssetDatabase.Refresh.",
                "Assign to dialogue system or NPC AudioSource.",
            ],
        },
        indent=2,
    )


async def _handle_audio_generate_ambient(
    name: str, biome: str, layers: list[str] | None
) -> str:
    """Generate layered ambient soundscape (AUD-04)."""
    client = _get_audio_client()
    safe_biome = _sanitize_cs_identifier(biome) or "ambient"
    output_rel = f"Assets/Resources/Audio/Ambient/{safe_biome}"

    if settings.unity_project_path:
        output_dir = str(Path(settings.unity_project_path) / output_rel)
    else:
        output_dir = output_rel

    result = client.generate_ambient_layers(
        biome=biome,
        layers=layers,
        output_dir=output_dir,
    )

    return json.dumps(
        {
            "status": "success",
            "action": "generate_ambient",
            "layer_paths": result["layer_paths"],
            "biome": biome,
            "layer_count": len(result["layer_paths"]),
            "stub": result["stub"],
            "next_steps": [
                f"Generated {len(result['layer_paths'])} ambient layers for {biome} biome.",
                "Import into Unity via AssetDatabase.Refresh.",
                "Layer these AudioClips in an AudioSource group for rich ambient sound.",
            ],
        },
        indent=2,
    )


async def _handle_audio_setup_footstep(
    name: str, surfaces: list[str] | None
) -> str:
    """Generate footstep manager C# scripts (AUD-05)."""
    script = generate_footstep_manager_script(surfaces=surfaces)
    script_path = f"Assets/Scripts/Runtime/Audio/VeilBreakers_FootstepManager.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_footstep_system", "message": str(exc)}
        )

    effective_surfaces = surfaces or ["stone", "wood", "grass", "metal", "water"]

    return json.dumps(
        {
            "status": "success",
            "action": "setup_footstep_system",
            "script_path": abs_path,
            "surfaces": effective_surfaces,
            "next_steps": [
                "Run unity_editor action=recompile to compile the new scripts",
                "Attach VeilBreakers_FootstepManager to the player character",
                "Create a FootstepSoundBank via Assets > Create > VeilBreakers > Audio > Footstep Sound Bank",
                f"Assign AudioClips for surfaces: {', '.join(effective_surfaces)}",
            ],
        },
        indent=2,
    )


async def _handle_audio_setup_adaptive_music(
    name: str, music_layers: list[str] | None
) -> str:
    """Generate adaptive music manager C# script (AUD-06)."""
    script = generate_adaptive_music_script(layers=music_layers)
    script_path = f"Assets/Scripts/Runtime/Audio/VeilBreakers_AdaptiveMusicManager.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_adaptive_music", "message": str(exc)}
        )

    effective_layers = music_layers or ["Exploration", "Combat", "Boss", "Town", "Stealth"]

    return json.dumps(
        {
            "status": "success",
            "action": "setup_adaptive_music",
            "script_path": abs_path,
            "layers": effective_layers,
            "next_steps": [
                "Run unity_editor action=recompile to compile the new script",
                "Add VeilBreakers_AdaptiveMusicManager to a persistent GameObject",
                f"Assign AudioClips for states: {', '.join(effective_layers)}",
                "Call SetGameState(GameState.Combat) etc. from game logic",
            ],
        },
        indent=2,
    )


async def _handle_audio_setup_zones(name: str, zone_type: str) -> str:
    """Generate audio reverb zone C# script (AUD-07)."""
    script = generate_audio_zone_script(zone_type=zone_type)
    zone_label = zone_type.capitalize()
    script_path = f"Assets/Editor/Generated/Audio/VeilBreakers_AudioZone_{zone_label}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_audio_zones", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_audio_zones",
            "script_path": abs_path,
            "zone_type": zone_type,
            "next_steps": [
                "Run unity_editor action=recompile to compile the new script",
                f'Open Unity Editor and run VeilBreakers > Audio > Create {zone_label} Reverb Zone from the menu bar',
                "Position the reverb zone in the scene as needed",
            ],
        },
        indent=2,
    )


async def _handle_audio_setup_mixer(groups: list[str] | None) -> str:
    """Generate audio mixer setup C# script (AUD-08)."""
    script = generate_audio_mixer_setup_script(groups=groups)
    script_path = "Assets/Editor/Generated/Audio/VeilBreakers_AudioMixerSetup.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_audio_mixer", "message": str(exc)}
        )

    effective_groups = groups or ["Master", "SFX", "Music", "Voice", "Ambient", "UI"]

    return json.dumps(
        {
            "status": "success",
            "action": "setup_audio_mixer",
            "script_path": abs_path,
            "groups": effective_groups,
            "next_steps": [
                "First, create an AudioMixer at Assets/Audio/VeilBreakersMixer.mixer in Unity",
                f"Add these groups to the mixer: {', '.join(effective_groups)}",
                "Run unity_editor action=recompile to compile the setup script",
                'Open Unity Editor and run VeilBreakers > Audio > Setup Audio Mixer from the menu bar',
            ],
        },
        indent=2,
    )


async def _handle_audio_setup_pool_manager(
    name: str, pool_size: int, max_sources: int
) -> str:
    """Generate audio pool manager C# script (AUD-09)."""
    script = generate_audio_pool_manager_script(
        pool_size=pool_size, max_sources=max_sources
    )
    script_path = "Assets/Scripts/Runtime/Audio/VeilBreakers_AudioPoolManager.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_audio_pool_manager", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_audio_pool_manager",
            "script_path": abs_path,
            "pool_size": pool_size,
            "max_sources": max_sources,
            "next_steps": [
                "Run unity_editor action=recompile to compile the new script",
                "Add VeilBreakers_AudioPoolManager to a persistent GameObject",
                f"Pool starts with {pool_size} AudioSources, grows up to {max_sources}",
                "Call VeilBreakers_AudioPoolManager.Instance.Play(clip, position, priority)",
            ],
        },
        indent=2,
    )


async def _handle_audio_assign_animation_sfx(
    name: str, events: list[dict] | None
) -> str:
    """Generate animation event SFX binding C# script (AUD-10)."""
    script = generate_animation_event_sfx_script(events=events)
    script_path = "Assets/Editor/Generated/Audio/VeilBreakers_AnimationEventSFX.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "assign_animation_sfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "assign_animation_sfx",
            "script_path": abs_path,
            "next_steps": [
                "Run unity_editor action=recompile to compile the new script",
                "Select an AnimationClip in the Unity Project window",
                'Open Unity Editor and run VeilBreakers > Audio > Assign Animation SFX Events from the menu bar',
                "The script will bind SFX function calls to the specified animation keyframes",
            ],
        },
        indent=2,
    )
