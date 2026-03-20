# Phase 17: Build & Deploy Pipeline - Research

**Researched:** 2026-03-20
**Domain:** Unity build automation, CI/CD, Addressable assets, shader variant stripping, platform configuration, store publishing
**Confidence:** HIGH

## Summary

Phase 17 is the final phase of the v2.0 milestone, covering 7 requirements (BUILD-01 through BUILD-05, SHDR-03, ACC-02). The phase generates C# editor scripts for multi-platform build orchestration, Addressable Asset Group configuration, CI/CD pipeline YAML files, version management, platform-specific settings (Android manifest, iOS plist, WebGL template), shader variant stripping via `IPreprocessShaders`, and store publishing metadata.

This phase follows the established compound tool pattern -- a new `build_templates.py` file containing template generators, a new `unity_build` compound tool wired in `unity_server.py`, plus direct-write outputs for CI/CD YAML configs and store metadata files (which don't require Unity compilation). The existing `automate_build` action in `unity_performance` handles single-platform builds; Phase 17 extends this with multi-platform orchestration, per-platform settings, and the full deployment pipeline.

**Primary recommendation:** Create a new `build_templates.py` with 7-8 generators plus a `unity_build` compound tool. CI/CD YAML and store metadata are plain text files written directly (no C# needed). The Addressables configuration generates C# editor scripts since it requires the Unity Editor API. Shader stripping generates an `IPreprocessShaders` implementation.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Multi-Platform Builds (BUILD-01)**: Platform targets are Windows (StandaloneWindows64), Mac (StandaloneOSX), Linux (StandaloneLinux64), Android, iOS, WebGL. Per-platform settings cover scripting backend (IL2CPP vs Mono), architecture, compression, texture format overrides. Generate editor scripts that perform builds with configurable options and post-build reporting.
- **Addressable Assets (BUILD-02)**: Create/configure Addressable groups with local/remote load paths, configure catalog settings, update paths, cache control, configure asset release policies and reference counting options. VeilBreakers already has Addressables 2.8.0 installed -- extend configuration, don't install.
- **CI/CD Pipeline (BUILD-03)**: GitHub Actions primary (.github/workflows/unity-build.yml with matrix builds), GitLab CI secondary (.gitlab-ci.yml). Pipeline stages: Lint -> Test -> Build -> Deploy with per-platform matrix. Include Unity license activation step and artifact upload.
- **Version Management (BUILD-04)**: SemVer Major.Minor.Patch with optional pre-release suffix. Automated version bumping in PlayerSettings.bundleVersion. Generate CHANGELOG.md from git log between tags. Create release/* branches from main.
- **Platform Configuration (BUILD-05)**: Android: Generate/modify AndroidManifest.xml with permissions, features, min/target SDK. iOS: Generate Info.plist entries, capabilities, entitlements. WebGL: Configure WebGL template, memory size, compression.
- **Shader Variant Stripping (SHDR-03)**: IPreprocessShaders implementation that removes unused variants at build time. Keyword management to configure which keywords to strip per build target. Build size analysis reporting variant counts before/after stripping.
- **Store Publishing (ACC-02)**: Generate store description, feature list, screenshots specs. Generate questionnaire answers for ESRB/PEGI/IARC. Generate privacy policy template based on app features.

### Claude's Discretion
- Exact CI/CD pipeline step ordering and parallel job configuration
- Addressable group naming conventions
- Shader stripping aggressiveness defaults
- Privacy policy template legal language specifics

### Deferred Ideas (OUT OF SCOPE)
None -- autonomous mode stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BUILD-01 | Multi-platform builds (Windows, Mac, Linux, Android, iOS, WebGL) with per-platform settings | BuildPipeline.BuildPlayer API with BuildPlayerOptions, per-platform BuildTarget enum, IL2CPP/Mono backend config, PlayerSettings per-platform overrides |
| BUILD-02 | Addressable Asset Groups configuration (remote/local paths, content catalogs, memory management) | AddressableAssetSettings.CreateGroup API, BundledAssetGroupSchema, ContentUpdateGroupSchema, profile variables, Addressables 2.8.0 already installed |
| BUILD-03 | CI/CD pipeline configs (GitHub Actions, GitLab CI) for automated builds and tests | GameCI actions (game-ci/unity-test-runner@v4, game-ci/unity-builder@v4), YAML generation, license activation, matrix builds |
| BUILD-04 | Version management (version numbers, release branches, changelogs) | PlayerSettings.bundleVersion, Application.version, SemVer parsing, git log changelog generation |
| BUILD-05 | Platform-specific settings (Android manifest, iOS plist, WebGL template) | AndroidManifest.xml XML generation, PlistDocument API for iOS, PlayerSettings.WebGL properties |
| SHDR-03 | Shader variant stripping and keyword set management | IPreprocessShaders.OnProcessShader(Shader, ShaderSnippetData, IList\<ShaderCompilerData\>), ShaderKeyword, callbackOrder |
| ACC-02 | Store publishing metadata (screenshots, descriptions, content ratings, privacy policy) | Plain text/JSON/markdown output -- no Unity API needed, direct file write |

</phase_requirements>

## Standard Stack

### Core
| Library/API | Version | Purpose | Why Standard |
|-------------|---------|---------|--------------|
| UnityEditor.Build.Reporting (BuildPipeline) | Unity 6+ | Multi-platform build execution with BuildReport | Official Unity API for programmatic builds |
| UnityEditor.AddressableAssets | 2.8.0 (installed) | Addressable group/entry/profile management | Already in VeilBreakers manifest, industry standard for asset management |
| UnityEditor.Build.IPreprocessShaders | Unity 6+ | Shader variant stripping at build time | Only official API for build-time shader stripping |
| UnityEditor.iOS.Xcode (PlistDocument, PBXProject) | Unity 6+ | iOS Info.plist and Xcode project modification | Official Unity API for iOS build post-processing |
| game-ci/unity-builder@v4 | v4 | GitHub Actions Unity build action | De facto standard, most widely used Unity CI/CD tool |
| game-ci/unity-test-runner@v4 | v4 | GitHub Actions Unity test runner | Companion to unity-builder for CI testing |
| unityci/editor | v3 (IMAGE_VERSION) | GitLab CI Docker image | GameCI official Docker images for CI builds |

### Supporting
| Library/API | Version | Purpose | When to Use |
|-------------|---------|---------|-------------|
| System.Xml.Linq | .NET | Android manifest XML generation/modification | When generating AndroidManifest.xml |
| PlayerSettings.WebGL | Unity 6+ | WebGL build configuration | Template selection, memory size, compression |
| EditorUserBuildSettings | Unity 6+ | Per-platform scripting backend, architecture | Build configuration before BuildPipeline.BuildPlayer |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| game-ci/unity-builder | Unity Build Automation (cloud) | GameCI is free/open-source, cloud requires license; generate YAML for both |
| Custom manifest XML generation | IPostGenerateGradleAndroidProject | Post-process works for existing builds; generation is more flexible for template creation |
| Direct file I/O for iOS plist | PlistDocument API | PlistDocument is cleaner and type-safe; use it when available (Editor context) |

## Architecture Patterns

### Recommended Project Structure
```
Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/
├── build_templates.py       # NEW: all build/deploy template generators
├── performance_templates.py # EXISTING: has generate_build_automation_script (PERF-05)

Tools/mcp-toolkit/tests/
├── test_build_templates.py  # NEW: unit tests for build template generators
├── test_csharp_syntax_deep.py # EXISTING: extend with Phase 17 generators
```

### Pattern 1: C# Editor Script Generation (BUILD-01, BUILD-02, BUILD-05, SHDR-03)
**What:** Python functions that return complete C# source strings as editor scripts with `[MenuItem]` attributes
**When to use:** Any operation that requires the Unity Editor API (BuildPipeline, AddressableAssetSettings, PlayerSettings)
**Example:**
```python
# Source: Existing pattern from performance_templates.py, qa_templates.py
def generate_multi_platform_build_script(
    platforms: list[dict] | None = None,
    development: bool = False,
) -> str:
    """Generate C# editor script for multi-platform build orchestration.

    Each platform dict: {"target": "StandaloneWindows64", "backend": "IL2CPP", ...}
    """
    # Returns C# with BuildPipeline.BuildPlayer calls per platform
    # Writes JSON result to Temp/vb_result.json
    ...
```

### Pattern 2: Direct File Write (BUILD-03, BUILD-04, ACC-02)
**What:** Python functions that return plain text (YAML, markdown, JSON) written directly to disk
**When to use:** CI/CD configs, changelogs, store metadata -- no Unity compilation needed
**Example:**
```python
def generate_github_actions_workflow(
    unity_version: str = "6000.0.0f1",
    platforms: list[str] | None = None,
) -> str:
    """Generate .github/workflows/unity-build.yml content."""
    # Returns YAML string -- no C# involved
    ...
```

### Pattern 3: Compound Tool Wiring (unity_build)
**What:** New `unity_build` compound tool in unity_server.py following the established Literal action pattern
**When to use:** All Phase 17 actions dispatched through a single tool
**Example:**
```python
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
    ...
) -> str:
```

### Anti-Patterns to Avoid
- **Do NOT modify existing `automate_build` in unity_performance:** That action serves PERF-05 with single-platform builds. Phase 17 creates a separate multi-platform orchestrator in `unity_build`.
- **Do NOT generate CI/CD YAML as C# editor scripts:** YAML files are plain text; writing them through C# is unnecessary indirection.
- **Do NOT hardcode Unity version in CI configs:** Accept it as a parameter; projects use different Unity versions.
- **Do NOT strip ALL shader variants by default:** Conservative defaults (strip DEBUG, _EDITOR only) prevent runtime black screens.
- **Do NOT generate AndroidManifest.xml via C# that runs in Editor:** Generate the XML file directly from Python using string templates. The manifest is placed at `Assets/Plugins/Android/AndroidManifest.xml` and Unity picks it up automatically.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-platform build matrix | Custom build loop with manual settings | BuildPipeline.BuildPlayer with BuildPlayerOptions per platform | BuildReport provides size breakdown, error info, packed assets |
| Addressable group configuration | Manual ScriptableObject manipulation | AddressableAssetSettings.CreateGroup + BundledAssetGroupSchema | Official API handles schema dependencies, profile variable resolution |
| CI/CD pipeline | Custom shell scripts | GameCI actions (v4) for GitHub Actions, GameCI Docker images for GitLab | Handles Unity license activation, platform-specific runners, caching |
| iOS plist modification | Raw XML manipulation | PlistDocument + PBXProject.AddCapability | Type-safe API, handles capability entitlements correctly |
| Shader keyword enumeration | Manual keyword list | ShaderKeyword constructor + ShaderCompilerData.shaderKeywordSet | Handles local vs global keywords correctly per Unity version |
| SemVer parsing | Regex parsing | System.Version or simple split('.') | Edge cases with pre-release suffixes handled consistently |

**Key insight:** Build pipeline operations have many platform-specific edge cases (IL2CPP requirements, signing certificates, architecture constraints). Using official APIs ensures correctness across Unity versions.

## Common Pitfalls

### Pitfall 1: BuildResult Not Checked Before Accessing PackedAssets
**What goes wrong:** Accessing `BuildReport.packedAssets` when `BuildResult != Succeeded` throws exceptions or returns garbage data.
**Why it happens:** BuildReport object exists even for failed builds.
**How to avoid:** Always check `report.summary.result == BuildResult.Succeeded` before accessing any report details. The existing `generate_build_automation_script` already does this correctly.
**Warning signs:** NullReferenceException when reading build sizes.

### Pitfall 2: IL2CPP Backend Requires Platform-Specific Setup
**What goes wrong:** Build fails with cryptic errors when IL2CPP backend is selected without proper toolchain.
**Why it happens:** IL2CPP needs NDK for Android, Xcode for iOS, C++ compiler for desktop.
**How to avoid:** Document prerequisites per platform in the generated build script output. Check `PlayerSettings.GetScriptingBackend()` before building.
**Warning signs:** "Unable to find C++ compiler" or "NDK not found" errors.

### Pitfall 3: Addressables Content Catalog Not Updated After Group Changes
**What goes wrong:** Asset groups are configured but runtime loading fails because the catalog wasn't rebuilt.
**Why it happens:** Creating groups is an editor-time operation; the catalog is only built when you explicitly build Addressables content.
**How to avoid:** Include `AddressableAssetSettings.BuildPlayerContent()` call or document it as a next_step.
**Warning signs:** "Unknown address" errors at runtime.

### Pitfall 4: Shader Stripping Too Aggressive -- Black Materials at Runtime
**What goes wrong:** Stripping shader keywords that are actually used causes black/pink materials.
**Why it happens:** IPreprocessShaders strips ALL matching variants; no safety net.
**How to avoid:** Conservative defaults (strip only DEBUG, _EDITOR, _SHADOWS_SOFT when not needed). Provide a keyword whitelist/blacklist configuration. Log stripped variant counts.
**Warning signs:** Visual glitches only appearing in builds, not in editor.

### Pitfall 5: GitHub Actions Unity License Not Activated
**What goes wrong:** CI builds fail with "No valid Unity Editor license found."
**Why it happens:** Unity requires activation even for Plus/Pro licenses in CI. Personal licenses use manual .ulf activation.
**How to avoid:** Generate the license activation step in the workflow. Document the manual .ulf creation process for Personal licenses. Require UNITY_LICENSE, UNITY_EMAIL, UNITY_PASSWORD secrets.
**Warning signs:** Build job fails before reaching the actual build step.

### Pitfall 6: Android Manifest Permission Conflicts
**What goes wrong:** Custom AndroidManifest.xml conflicts with Unity's auto-generated permissions.
**Why it happens:** Unity automatically adds permissions based on API usage; custom manifest may duplicate or contradict.
**How to avoid:** Use `tools:node="merge"` attributes. Don't manually add permissions Unity adds automatically (e.g., INTERNET is auto-added if you use UnityWebRequest).
**Warning signs:** Duplicate permission warnings during build, app crashes on launch.

### Pitfall 7: WebGL Memory Size Too Low
**What goes wrong:** WebGL build crashes with "out of memory" on load or during gameplay.
**Why it happens:** Default WebGL memory is often insufficient for complex games.
**How to avoid:** Set `PlayerSettings.WebGL.memorySize` based on project complexity. 256MB minimum for most games, 512MB for complex ones.
**Warning signs:** "Cannot enlarge memory arrays" error in browser console.

## Code Examples

Verified patterns from official sources and project conventions:

### Multi-Platform Build Orchestration (BUILD-01)
```csharp
// Source: Unity BuildPipeline API + existing generate_build_automation_script pattern
// Key difference from PERF-05: iterates multiple platforms with per-platform settings
foreach (var platform in platforms)
{
    EditorUserBuildSettings.SwitchActiveBuildTarget(
        BuildTargetGroup.Standalone, BuildTarget.StandaloneWindows64);
    PlayerSettings.SetScriptingBackend(
        BuildTargetGroup.Standalone, ScriptingBackend.IL2CPP);

    var options = new BuildPlayerOptions
    {
        scenes = buildScenes,
        locationPathName = "Builds/" + platform.name + "/Game",
        target = platform.target,
        options = BuildOptions.None,
    };
    BuildReport report = BuildPipeline.BuildPlayer(options);
    // Check report.summary.result before accessing packed assets
}
```

### Addressable Group Configuration (BUILD-02)
```csharp
// Source: Addressables 2.0 API docs - CreateGroup method
// Namespace: UnityEditor.AddressableAssets, UnityEditor.AddressableAssets.Settings
var settings = AddressableAssetSettingsDefaultObject.Settings;
if (settings == null)
{
    settings = AddressableAssetSettings.Create(
        AddressableAssetSettings.kDefaultConfigFolder,
        AddressableAssetSettings.kDefaultConfigAssetName, true, true);
}

// Create a group with BundledAssetGroupSchema
var group = settings.CreateGroup(
    groupName, false, false, true, null,
    typeof(BundledAssetGroupSchema), typeof(ContentUpdateGroupSchema));

// Configure schema
var schema = group.GetSchema<BundledAssetGroupSchema>();
schema.BuildPath.SetVariableByName(settings, AddressableAssetSettings.kLocalBuildPath);
schema.LoadPath.SetVariableByName(settings, AddressableAssetSettings.kLocalLoadPath);
schema.BundleMode = BundledAssetGroupSchema.BundlePackingMode.PackSeparately;
```

### IPreprocessShaders Implementation (SHDR-03)
```csharp
// Source: Unity IPreprocessShaders API docs
using UnityEditor.Build;
using UnityEditor.Rendering;
using UnityEngine;
using UnityEngine.Rendering;
using System.Collections.Generic;

class VeilBreakers_ShaderStripper : IPreprocessShaders
{
    static readonly ShaderKeyword[] _keywordsToStrip = new ShaderKeyword[]
    {
        new ShaderKeyword("DEBUG"),
        new ShaderKeyword("_EDITOR"),
    };

    public int callbackOrder { get { return 0; } }

    public void OnProcessShader(
        Shader shader, ShaderSnippetData snippet, IList<ShaderCompilerData> data)
    {
        int beforeCount = data.Count;
        for (int i = data.Count - 1; i >= 0; i--)
        {
            foreach (var keyword in _keywordsToStrip)
            {
                if (data[i].shaderKeywordSet.IsEnabled(keyword))
                {
                    data.RemoveAt(i);
                    break;
                }
            }
        }
        int stripped = beforeCount - data.Count;
        if (stripped > 0)
            Debug.Log($"[VeilBreakers] Stripped {stripped}/{beforeCount} variants from {shader.name}");
    }
}
```

### GitHub Actions Workflow Structure (BUILD-03)
```yaml
# Source: GameCI docs (game.ci/docs/github/getting-started)
name: Unity Build Pipeline
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch: {}

env:
  UNITY_LICENSE: ${{ secrets.UNITY_LICENSE }}
  UNITY_EMAIL: ${{ secrets.UNITY_EMAIL }}
  UNITY_PASSWORD: ${{ secrets.UNITY_PASSWORD }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { lfs: true }
      - uses: actions/cache@v3
        with:
          path: Library
          key: Library-${{ hashFiles('Assets/**', 'Packages/**', 'ProjectSettings/**') }}
      - uses: game-ci/unity-test-runner@v4
        with:
          testMode: all
          githubToken: ${{ secrets.GITHUB_TOKEN }}

  build:
    needs: test
    runs-on: ubuntu-latest
    strategy:
      matrix:
        targetPlatform:
          - StandaloneWindows64
          - StandaloneOSX
          - StandaloneLinux64
          - Android
          - iOS
          - WebGL
    steps:
      - uses: actions/checkout@v4
        with: { lfs: true }
      - uses: game-ci/unity-builder@v4
        with:
          targetPlatform: ${{ matrix.targetPlatform }}
      - uses: actions/upload-artifact@v4
        with:
          name: Build-${{ matrix.targetPlatform }}
          path: build/${{ matrix.targetPlatform }}
```

### Android Manifest Generation (BUILD-05)
```xml
<!-- Source: Unity Android manifest docs -->
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools"
    package="com.company.product">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.VIBRATE" />
    <uses-feature android:glEsVersion="0x00030000" android:required="true" />

    <application android:label="@string/app_name"
                 android:icon="@mipmap/app_icon">
        <activity android:name="com.unity3d.player.UnityPlayerActivity"
                  android:configChanges="fontScale|keyboard|keyboardHidden|locale|..."
                  android:screenOrientation="landscape">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

### iOS Plist Modification (BUILD-05)
```csharp
// Source: Unity PlistDocument API docs
// Used in [PostProcessBuild] callback
using UnityEditor;
using UnityEditor.Callbacks;
using UnityEditor.iOS.Xcode;
using System.IO;

public class VeilBreakers_iOSPostProcess
{
    [PostProcessBuild]
    public static void OnPostProcessBuild(BuildTarget target, string path)
    {
        if (target != BuildTarget.iOS) return;

        string plistPath = Path.Combine(path, "Info.plist");
        PlistDocument plist = new PlistDocument();
        plist.ReadFromFile(plistPath);

        PlistElementDict root = plist.root;
        root.SetString("NSCameraUsageDescription", "Camera access for AR features");
        root.SetBoolean("UIRequiresFullScreen", true);
        root.SetString("ITSAppUsesNonExemptEncryption", "false");

        plist.WriteToFile(plistPath);

        // Add capabilities via PBXProject
        string projPath = PBXProject.GetPBXProjectPath(path);
        var proj = new PBXProject();
        proj.ReadFromFile(projPath);
        string targetGuid = proj.GetUnityMainTargetGuid();
        proj.AddCapability(targetGuid, PBXCapabilityType.GameCenter);
        proj.WriteToFile(projPath);
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| BuildPipeline.BuildPlayer with string path | BuildPlayerOptions struct | Unity 2019+ | Cleaner API, explicit scene lists, build options |
| AssetBundles manual management | Addressables package | Unity 2019+ | Simplified async loading, content catalogs, remote delivery |
| Custom CI bash scripts | GameCI GitHub Actions v4 | 2023-2024 | Standardized Unity license activation, matrix builds, caching |
| Manual shader variant management | IPreprocessShaders + Shader Variant Collection | Unity 2018+ | Build-time stripping reduces size by 50-80% |
| Custom build scripts per platform | EditorUserBuildSettings + PlayerSettings per-platform | Unity 2021+ | Unified API for switching targets and setting backends |
| AndroidManifest direct editing | IPostGenerateGradleAndroidProject or XML template | Unity 2019+ | Build system handles merging; templates avoid conflicts |

**Deprecated/outdated:**
- `BuildPipeline.BuildAssetBundles()` -- replaced by Addressables for new projects
- `game-ci/unity-builder@v2/v3` -- use v4 for Unity 6 compatibility
- `EditorUserBuildSettings.development` for all build config -- use `BuildOptions` flags instead
- Direct `.ulf` license activation in CI without GameCI -- GameCI handles this automatically

## Open Questions

1. **Addressables 2.8.0 vs 2.0.8 API compatibility**
   - What we know: CONTEXT.md says 2.8.0 is in VeilBreakers manifest. The latest docs found are for 2.4.6 and 2.0.8. The CreateGroup API signature is stable across versions.
   - What's unclear: Whether 2.8.0 has any new APIs or breaking changes from 2.0.8
   - Recommendation: Use the documented CreateGroup/CreateOrMoveEntry pattern -- it's stable across all 2.x versions. If 2.8.0 has extras, they're additive.

2. **GameCI runner compatibility with Unity 6**
   - What we know: GameCI v4 supports Unity 2019-2023. Unity 6 uses the 6000.x version numbering scheme.
   - What's unclear: Whether game-ci/unity-builder@v4 handles the Unity 6 version string correctly
   - Recommendation: Generate the workflow with a configurable `unityVersion` parameter. Document that users may need to update GameCI actions when new versions are released.

3. **Store metadata accuracy for ESRB/PEGI content ratings**
   - What we know: Content rating questionnaires are complex and jurisdiction-specific.
   - What's unclear: Whether generated questionnaire answers should be legally binding recommendations
   - Recommendation: Generate templates with clear "REVIEW BEFORE SUBMISSION" disclaimers. Provide common dark fantasy/action RPG default answers but mark them as suggestions.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio |
| Config file | `Tools/mcp-toolkit/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_build_templates.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUILD-01 | Multi-platform build script generation | unit | `pytest tests/test_build_templates.py::TestMultiPlatformBuild -x` | Wave 0 |
| BUILD-02 | Addressable group config script generation | unit | `pytest tests/test_build_templates.py::TestAddressablesConfig -x` | Wave 0 |
| BUILD-03 | CI/CD YAML generation (GitHub Actions + GitLab CI) | unit | `pytest tests/test_build_templates.py::TestCICDGeneration -x` | Wave 0 |
| BUILD-04 | Version management script + changelog generation | unit | `pytest tests/test_build_templates.py::TestVersionManagement -x` | Wave 0 |
| BUILD-05 | Platform config scripts (Android/iOS/WebGL) | unit | `pytest tests/test_build_templates.py::TestPlatformConfig -x` | Wave 0 |
| SHDR-03 | Shader variant stripping script generation | unit | `pytest tests/test_build_templates.py::TestShaderStripping -x` | Wave 0 |
| ACC-02 | Store metadata text generation | unit | `pytest tests/test_build_templates.py::TestStoreMetadata -x` | Wave 0 |
| ALL | Deep C# syntax verification for all generators | unit | `pytest tests/test_csharp_syntax_deep.py::TestCSharpTemplateSyntax -x` | Extend existing |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_build_templates.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_build_templates.py` -- covers BUILD-01 through BUILD-05, SHDR-03, ACC-02
- [ ] Extend `tests/test_csharp_syntax_deep.py` -- add Phase 17 generators to deep syntax checks

## Sources

### Primary (HIGH confidence)
- [Unity BuildPipeline API](https://docs.unity3d.com/ScriptReference/BuildPipeline.html) -- BuildPlayer method, BuildPlayerOptions, BuildReport
- [Unity IPreprocessShaders.OnProcessShader](https://docs.unity3d.com/ScriptReference/Build.IPreprocessShaders.OnProcessShader.html) -- Method signature, ShaderCompilerData, code example
- [Unity Shader Variant Stripping Manual](https://docs.unity3d.com/6000.3/Documentation/Manual/shader-variant-stripping.html) -- Stripping approach, IPreprocessShaders usage
- [Addressables 2.0 CreateGroup](https://docs.unity3d.com/Packages/com.unity.addressables@2.0/api/UnityEditor.AddressableAssets.Settings.AddressableAssetSettings.CreateGroup.html) -- CreateGroup(string, bool, bool, bool, List, params Type[])
- [Addressables CreateOrMoveEntry](https://docs.unity3d.com/Packages/com.unity.addressables@1.20/api/UnityEditor.AddressableAssets.Settings.AddressableAssetSettings.CreateOrMoveEntry.html) -- CreateOrMoveEntry(string, AddressableAssetGroup, bool, bool)
- [Unity iOS PlistDocument API](https://docs.unity3d.com/ScriptReference/iOS.Xcode.PlistDocument.html) -- iOS plist modification
- [Unity PBXProject.AddCapability](https://docs.unity3d.com/ScriptReference/iOS.Xcode.PBXProject.AddCapability.html) -- Xcode capability management
- [GameCI GitHub Actions Getting Started](https://game.ci/docs/github/getting-started/) -- Workflow structure, actions, secrets
- [GameCI GitLab CI Example](https://github.com/game-ci/unity3d-gitlab-ci-example-mirror/blob/main/.gitlab-ci.yml) -- Complete GitLab CI YAML
- [Unity Android Manifest Manual](https://docs.unity3d.com/Manual/android-manifest.html) -- Manifest structure, auto-permissions
- [Unity WebGL Player Settings](https://docs.unity3d.com/Manual/class-PlayerSettingsWebGL.html) -- WebGL configuration options
- [Unity IL2CPP Manual](https://docs.unity3d.com/6000.2/Documentation/Manual/scripting-backends-il2cpp.html) -- IL2CPP backend configuration

### Secondary (MEDIUM confidence)
- [Unity Shader Variant Optimization Blog](https://blog.unity.com/engine-platform/shader-variants-optimization-troubleshooting-tips) -- Practical stripping strategies
- [GameCI GitLab CI Full Example](https://gitlab.com/game-ci/unity3d-gitlab-ci-example/-/blob/main/.gitlab-ci.yml) -- Complete CI pipeline reference
- [UnityAndroidManifestCallback GitHub](https://github.com/Over17/UnityAndroidManifestCallback) -- IPostGenerateGradleAndroidProject pattern

### Tertiary (LOW confidence)
- Store metadata templates for ESRB/PEGI -- based on general industry knowledge; specific questionnaire formats may vary by submission year

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All APIs verified through official Unity documentation
- Architecture: HIGH -- Follows established project patterns (compound tool, template generators, deep syntax tests)
- Pitfalls: HIGH -- Build pipeline pitfalls well-documented across Unity community; verified against official docs
- CI/CD: MEDIUM -- GameCI v4 confirmed stable for Unity 2023; Unity 6 compatibility not explicitly verified
- Store metadata: MEDIUM -- Template formats are best-effort; actual store requirements change periodically

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days -- APIs are stable; CI tooling evolves slowly)
