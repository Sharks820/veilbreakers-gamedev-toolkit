"""unity_build tool handler."""

import json
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, logger,
    _write_to_unity, _write_generated_editor_response, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.build_templates import (
    generate_multi_platform_build_script,
    generate_addressables_config_script,
    generate_platform_config_script,
    generate_shader_stripping_script,
    generate_github_actions_workflow,
    generate_gitlab_ci_config,
    generate_version_management_script,
    generate_changelog,
    generate_store_metadata,
)





async def _write_build_editor_response(
    *,
    action_name: str,
    script_content: str,
    rel_path: str,
    menu_path: str = "",
    next_steps: list[str] | None = None,
    result_file: str | None = "Temp/vb_result.json",
    response_fields: dict | None = None,
) -> str:
    """Write a Unity editor script and auto-run it when a menu item exists."""
    return await _write_generated_editor_response(
        action_name=action_name,
        script_content=script_content,
        rel_path=rel_path,
        menu_path=menu_path,
        next_steps=next_steps,
        result_file=result_file,
        response_fields=response_fields,
    )


@mcp.tool()
async def unity_build(
    action: Literal[
        "build_multi_platform",      # BUILD-01
        "configure_addressables",    # BUILD-02
        "generate_ci_pipeline",      # BUILD-03
        "manage_version",            # BUILD-04
        "configure_platform",        # BUILD-05
        "setup_shader_stripping",    # SHDR-03
        "generate_store_metadata",   # ACC-02
    ],
    name: str = "default",
    # multi-platform build params
    platforms: list[dict] | None = None,
    development: bool = False,
    # addressables params
    groups: list[dict] | None = None,
    build_remote: bool = False,
    # CI/CD params
    ci_provider: str = "github",
    unity_version: str = "6000.0.0f1",
    ci_platforms: list[str] | None = None,
    run_tests: bool = True,
    # version params
    version: str = "1.0.0",
    auto_increment: str = "patch",
    update_android: bool = True,
    update_ios: bool = True,
    # changelog params
    project_name: str = "VeilBreakers",
    # platform config params
    platform: str = "android",
    permissions: list[str] | None = None,
    features: list[str] | None = None,
    plist_entries: list[dict] | None = None,
    webgl_memory_mb: int = 256,
    # shader stripping params
    keywords_to_strip: list[str] | None = None,
    log_stripping: bool = True,
    # store metadata params
    game_title: str = "VeilBreakers",
    genre: str = "Action RPG",
    has_iap: bool = False,
    has_ads: bool = False,
    collects_data: bool = False,
    # common
    namespace: str = ""
) -> str:
    """Unity Build & Deploy Pipeline tools -- multi-platform builds, addressables, CI/CD, versioning, platform config, shader stripping, store metadata."""
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "build_multi_platform":
            script = generate_multi_platform_build_script(
                platforms=platforms,
                development=development,
                **ns_kwargs,
            )
            return await _write_build_editor_response(
                action_name="build_multi_platform",
                script_content=script,
                rel_path="Assets/Editor/Generated/Build/VBMultiPlatformBuild.cs",
                menu_path="VeilBreakers/Build/Multi-Platform Build",
                next_steps=STANDARD_NEXT_STEPS,
                result_file="Temp/vb_build_results.json",
                response_fields={
                    "platforms": platforms or [],
                    "development": development,
                },
            )

        elif action == "configure_addressables":
            script = generate_addressables_config_script(
                groups=groups,
                build_remote=build_remote,
                **ns_kwargs,
            )
            return await _write_build_editor_response(
                action_name="configure_addressables",
                script_content=script,
                rel_path="Assets/Editor/Generated/Build/VBAddressablesConfig.cs",
                menu_path="VeilBreakers/Build/Configure Addressables",
                next_steps=STANDARD_NEXT_STEPS,
                response_fields={
                    "build_remote": build_remote,
                    "groups": groups or [],
                },
            )

        elif action == "generate_ci_pipeline":
            # Validate ci_platforms against the allowlist before passing
            # to generators -- prevents YAML injection via crafted names.
            if ci_platforms is not None:
                from veilbreakers_mcp.shared.unity_templates.build_templates import (
                    _validate_ci_platforms,
                )
                try:
                    ci_platforms = _validate_ci_platforms(ci_platforms)
                except ValueError as exc:
                    return json.dumps({
                        "status": "error",
                        "action": "generate_ci_pipeline",
                        "message": str(exc),
                    })

            if ci_provider == "github":
                content = generate_github_actions_workflow(
                    unity_version=unity_version,
                    platforms=ci_platforms,
                    run_tests=run_tests,
                )
                output_path = ".github/workflows/unity-build.yml"
            elif ci_provider == "gitlab":
                content = generate_gitlab_ci_config(
                    unity_version=unity_version,
                    platforms=ci_platforms,
                )
                output_path = ".gitlab-ci.yml"
            else:
                return json.dumps({
                    "status": "error",
                    "action": "generate_ci_pipeline",
                    "message": f"Unknown ci_provider: {ci_provider}. Use 'github' or 'gitlab'.",
                })

            target = _write_to_unity(content, output_path)

            return json.dumps({
                "status": "success",
                "action": "generate_ci_pipeline",
                "file_path": target,
                "ci_provider": ci_provider,
                "next_steps": [
                    f"Review generated {ci_provider.title()} CI YAML at {output_path}",
                    "Set CI secrets: UNITY_LICENSE, UNITY_EMAIL, UNITY_PASSWORD",
                    "Push to trigger pipeline",
                ],
            }, indent=2)

        elif action == "manage_version":
            changelog_script = generate_changelog(
                project_name=project_name,
                version=version,
                **ns_kwargs,
            )
            changelog_path = _write_to_unity(
                changelog_script,
                "Assets/Editor/Generated/Build/VBChangelogGenerator.cs",
            )
            script = generate_version_management_script(
                version=version,
                auto_increment=auto_increment,
                update_android=update_android,
                update_ios=update_ios,
                **ns_kwargs,
            )
            result = json.loads(await _write_build_editor_response(
                action_name="manage_version",
                script_content=script,
                rel_path="Assets/Editor/Generated/Build/VBVersionManager.cs",
                menu_path="VeilBreakers/Build/Bump Version",
                next_steps=[
                    "Call unity_editor action='recompile' to compile version manager",
                    "Execute menu item: VeilBreakers > Build > Bump Version",
                ],
                response_fields={
                    "version": version,
                    "auto_increment": auto_increment,
                    "update_android": update_android,
                    "update_ios": update_ios,
                    "changelog_path": changelog_path,
                    "changelog_menu_path": "VeilBreakers/Build/Generate Changelog",
                },
            ))
            result.setdefault("changelog_path", changelog_path)
            result.setdefault("changelog_menu_path", "VeilBreakers/Build/Generate Changelog")
            if result.get("status") == "success":
                next_steps = result.get("next_steps")
                if not isinstance(next_steps, list):
                    next_steps = []
                next_steps.append(
                    "Execute menu item: VeilBreakers > Build > Generate Changelog"
                )
                result["next_steps"] = next_steps
            return json.dumps(result, indent=2)

        elif action == "configure_platform":
            valid_platforms = ("android", "ios", "webgl")
            if platform not in valid_platforms:
                return json.dumps({
                    "status": "error",
                    "action": "configure_platform",
                    "message": f"Unknown platform: {platform}. Use one of {valid_platforms}.",
                })

            script = generate_platform_config_script(
                platform=platform,
                permissions=permissions,
                features=features,
                plist_entries=plist_entries,
                webgl_memory_mb=webgl_memory_mb,
                **ns_kwargs,
            )

            platform_paths = {
                "android": "Assets/Editor/Generated/Build/VBAndroidConfig.cs",
                "ios": "Assets/Editor/Generated/Build/VBiOSPostProcess.cs",
                "webgl": "Assets/Editor/Generated/Build/VBWebGLConfig.cs",
            }
            output_path = platform_paths[platform]

            platform_next_steps = {
                "android": [
                    "Call unity_editor action='recompile' to compile Android config",
                    "Execute menu item: VeilBreakers > Build > Configure Android",
                    "Review generated AndroidManifest.xml in Assets/Plugins/Android/",
                ],
                "ios": [
                    "Call unity_editor action='recompile' to compile iOS post-process",
                    "Build for iOS to trigger PostProcessBuild callback",
                    "Review Xcode project for applied Info.plist entries",
                ],
                "webgl": [
                    "Call unity_editor action='recompile' to compile WebGL config",
                    "Execute menu item: VeilBreakers > Build > Configure WebGL",
                    "Build for WebGL to apply settings",
                ],
            }
            platform_menu_paths = {
                "android": "VeilBreakers/Build/Configure Android",
                "webgl": "VeilBreakers/Build/Configure WebGL",
            }
            return await _write_build_editor_response(
                action_name="configure_platform",
                script_content=script,
                rel_path=output_path,
                menu_path=platform_menu_paths.get(platform, ""),
                next_steps=platform_next_steps[platform],
                response_fields={"platform": platform},
            )

        elif action == "setup_shader_stripping":
            script = generate_shader_stripping_script(
                keywords_to_strip=keywords_to_strip,
                log_stripping=log_stripping,
                **ns_kwargs,
            )
            return await _write_build_editor_response(
                action_name="setup_shader_stripping",
                script_content=script,
                rel_path="Assets/Editor/Generated/Build/VBShaderStripper.cs",
                next_steps=[
                    "Recompile: unity_editor action=recompile",
                    "Build a player to trigger shader stripping and write Temp/vb_shader_strip_results.json",
                ],
                result_file="Temp/vb_shader_strip_results.json",
                response_fields={
                    "keywords_to_strip": keywords_to_strip or ["DEBUG", "_EDITOR"],
                    "log_stripping": log_stripping,
                },
            )

        elif action == "generate_store_metadata":
            content = generate_store_metadata(
                game_title=game_title,
                genre=genre,
                has_iap=has_iap,
                has_ads=has_ads,
                collects_data=collects_data,
            )

            target = _write_to_unity(content, "StoreMetadata/STORE_LISTING.md")

            return json.dumps({
                "status": "success",
                "action": "generate_store_metadata",
                "file_path": target,
                "next_steps": [
                    "Review generated store metadata at StoreMetadata/STORE_LISTING.md",
                    "Customize placeholder content for your game",
                    "Update screenshot specifications per store requirements",
                ],
            }, indent=2)

        else:
            return json.dumps({
                "status": "error",
                "message": f"Unknown action: {action}",
            })

    except Exception as exc:
        logger.exception("unity_build action '%s' failed", action)
        return json.dumps({
            "status": "error",
            "action": action,
            "message": str(exc),
        })
