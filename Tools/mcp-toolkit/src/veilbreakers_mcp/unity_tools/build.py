"""unity_build tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template,
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
    namespace: str = "",
) -> str:
    """Unity Build & Deploy Pipeline tools -- multi-platform builds, addressables,
    CI/CD, versioning, platform config, shader stripping, store metadata.

    Build Orchestration:
    - build_multi_platform: 6-platform build orchestrator with IL2CPP/Mono backend selection (BUILD-01)
    - configure_addressables: Addressable Asset Group configurator with BundledAssetGroupSchema (BUILD-02)
    - configure_platform: Android manifest/iOS PostProcessBuild/WebGL PlayerSettings config (BUILD-05)
    - setup_shader_stripping: IPreprocessShaders keyword blacklist for variant reduction (SHDR-03)

    CI/CD & Versioning:
    - generate_ci_pipeline: GitHub Actions or GitLab CI YAML with GameCI integration (BUILD-03)
    - manage_version: SemVer version bump + changelog generation C# editor scripts (BUILD-04)

    Store Publishing:
    - generate_store_metadata: Store description, content ratings, privacy policy markdown (ACC-02)

    Args:
        action: The build action to perform.
        name: Name for generated system (used in file paths).
        platforms: Multi-platform build target definitions (list of dicts with name/target/group/backend/extension).
        development: Enable development build mode with debugging.
        groups: Addressable group definitions (list of dicts with name/packing/local).
        build_remote: Build Addressable content for remote hosting.
        ci_provider: CI/CD provider -- "github" or "gitlab".
        unity_version: Unity editor version for CI Docker images.
        ci_platforms: CI build platforms list (e.g. ["StandaloneWindows64", "Android"]).
        run_tests: Run tests in CI pipeline before building.
        version: SemVer version string (e.g. "1.0.0").
        auto_increment: Version component to auto-increment (major/minor/patch).
        update_android: Update Android bundleVersionCode on version bump.
        update_ios: Update iOS buildNumber on version bump.
        project_name: Project name for changelog generation.
        platform: Target platform for platform-specific config (android/ios/webgl).
        permissions: Android permissions list (e.g. ["android.permission.CAMERA"]).
        features: Android features list.
        plist_entries: iOS Info.plist entries (list of dicts with key/value/type).
        webgl_memory_mb: WebGL initial memory size in MB.
        keywords_to_strip: Shader keywords to strip during builds.
        log_stripping: Log shader stripping results to JSON.
        game_title: Game title for store metadata.
        genre: Game genre for store metadata.
        has_iap: Game includes in-app purchases.
        has_ads: Game includes advertisements.
        collects_data: Game collects user data.
        namespace: C# namespace override (empty = generator default).
    """
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
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/Build/VBMultiPlatformBuild.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "build_multi_platform",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile build script",
                    "Execute menu item: VeilBreakers > Build > Multi-Platform Build",
                    "Read results from Temp/vb_build_results.json",
                ],
            }, indent=2)

        elif action == "configure_addressables":
            script = generate_addressables_config_script(
                groups=groups,
                build_remote=build_remote,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/Build/VBAddressablesConfig.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "configure_addressables",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile addressables config",
                    "Execute menu item: VeilBreakers > Build > Configure Addressables",
                    "Read results from Temp/vb_result.json",
                ],
            }, indent=2)

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

            # CI/CD files go at project root, not under Assets/
            project_root = Path(settings.unity_project_path).resolve()
            target = (project_root / output_path).resolve()
            try:
                target.relative_to(project_root)
            except ValueError:
                return json.dumps({
                    "status": "error",
                    "action": "generate_ci_pipeline",
                    "message": f"Path traversal detected: '{output_path}'",
                })
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

            return json.dumps({
                "status": "success",
                "action": "generate_ci_pipeline",
                "file_path": str(target),
                "ci_provider": ci_provider,
                "next_steps": [
                    f"Review generated {ci_provider.title()} CI YAML at {output_path}",
                    "Set CI secrets: UNITY_LICENSE, UNITY_EMAIL, UNITY_PASSWORD",
                    "Push to trigger pipeline",
                ],
            }, indent=2)

        elif action == "manage_version":
            script = generate_version_management_script(
                version=version,
                auto_increment=auto_increment,
                update_android=update_android,
                update_ios=update_ios,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/Build/VBVersionManager.cs",
            )
            next_steps = [
                "Call unity_editor action='recompile' to compile version manager",
                "Execute menu item: VeilBreakers > Build > Bump Version",
            ]

            # Also generate changelog script
            changelog_script = generate_changelog(
                project_name=project_name,
                version=version,
                **ns_kwargs,
            )
            changelog_path = _write_to_unity(
                changelog_script,
                "Assets/Editor/Generated/Build/VBChangelogGenerator.cs",
            )
            next_steps.append(
                "Execute menu item: VeilBreakers > Build > Generate Changelog"
            )

            return json.dumps({
                "status": "success",
                "action": "manage_version",
                "script_path": abs_path,
                "changelog_path": changelog_path,
                "next_steps": next_steps,
            }, indent=2)

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
            abs_path = _write_to_unity(script, output_path)

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

            return json.dumps({
                "status": "success",
                "action": "configure_platform",
                "platform": platform,
                "script_path": abs_path,
                "next_steps": platform_next_steps[platform],
            }, indent=2)

        elif action == "setup_shader_stripping":
            script = generate_shader_stripping_script(
                keywords_to_strip=keywords_to_strip,
                log_stripping=log_stripping,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/Build/VBShaderStripper.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "setup_shader_stripping",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile shader stripper",
                    "Build project to see shader stripping in action",
                    "Check Temp/vb_shader_strip_results.json for stripping report",
                ],
            }, indent=2)

        elif action == "generate_store_metadata":
            content = generate_store_metadata(
                game_title=game_title,
                genre=genre,
                has_iap=has_iap,
                has_ads=has_ads,
                collects_data=collects_data,
            )

            # Store metadata goes at project root, not under Assets/
            project_root = Path(settings.unity_project_path).resolve()
            target = (project_root / "StoreMetadata" / "STORE_LISTING.md").resolve()
            try:
                target.relative_to(project_root)
            except ValueError:
                return json.dumps({
                    "status": "error",
                    "action": "generate_store_metadata",
                    "message": "Path traversal detected",
                })
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

            return json.dumps({
                "status": "success",
                "action": "generate_store_metadata",
                "file_path": str(target),
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
