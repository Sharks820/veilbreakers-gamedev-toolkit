# Phase 17: Build & Deploy Pipeline - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning
**Source:** Auto-generated (autonomous mode)

<domain>
## Phase Boundary

Complete build pipeline orchestration: multi-platform builds (Windows, Mac, Linux, Android, iOS, WebGL) with per-platform settings, Addressable Asset Groups configuration (remote/local paths, content catalogs, memory management), CI/CD pipeline generation (GitHub Actions, GitLab CI) for automated builds and tests, version management (version numbers, release branches, changelogs), platform-specific settings (Android manifest, iOS plist, WebGL template), shader variant stripping and keyword set management for build size optimization, and store publishing metadata generation (screenshots, descriptions, content ratings, privacy policy templates).

Requirements: BUILD-01, BUILD-02, BUILD-03, BUILD-04, BUILD-05, SHDR-03, ACC-02.

</domain>

<decisions>
## Implementation Decisions

### Multi-Platform Builds (BUILD-01)
- **Platform targets**: Windows (StandaloneWindows64), Mac (StandaloneOSX), Linux (StandaloneLinux64), Android, iOS, WebGL
- **Per-platform settings**: Scripting backend (IL2CPP vs Mono), architecture, compression, texture format overrides
- **Build automation**: Generate editor scripts that perform builds with configurable options and post-build reporting

### Addressable Assets (BUILD-02)
- **Group configuration**: Create/configure Addressable groups with local/remote load paths
- **Content catalogs**: Configure catalog settings, update paths, cache control
- **Memory management**: Configure asset release policies, reference counting options
- **VeilBreakers already has Addressables 2.8.0 installed** — extend configuration, don't install

### CI/CD Pipeline (BUILD-03)
- **GitHub Actions primary**: Generate .github/workflows/unity-build.yml with matrix builds
- **GitLab CI secondary**: Generate .gitlab-ci.yml as alternative
- **Pipeline stages**: Lint → Test → Build → Deploy with per-platform matrix
- **Unity license activation**: Include license activation step (IL2CPP requires Pro license for some platforms)
- **Artifact upload**: Build output as GitHub Actions artifacts

### Version Management (BUILD-04)
- **SemVer**: Major.Minor.Patch with optional pre-release suffix
- **Automated version bumping**: Increment version in PlayerSettings.bundleVersion
- **Changelog generation**: Generate CHANGELOG.md from git log between tags
- **Release branches**: Create release/* branches from main

### Platform Configuration (BUILD-05)
- **Android**: Generate/modify AndroidManifest.xml with permissions, features, min/target SDK
- **iOS**: Generate Info.plist entries, capabilities, entitlements
- **WebGL**: Configure WebGL template, memory size, compression

### Shader Variant Stripping (SHDR-03)
- **IPreprocessShaders implementation**: Generate shader stripping code that removes unused variants at build time
- **Keyword management**: Configure which shader keywords to strip per build target
- **Build size analysis**: Report shader variant counts before/after stripping

### Store Publishing (ACC-02)
- **Metadata templates**: Generate store description, feature list, screenshots specs
- **Content ratings**: Generate questionnaire answers for ESRB/PEGI/IARC
- **Privacy policy**: Generate privacy policy template based on app features

### Claude's Discretion
- Exact CI/CD pipeline step ordering and parallel job configuration
- Addressable group naming conventions
- Shader stripping aggressiveness defaults
- Privacy policy template legal language specifics

</decisions>

<canonical_refs>
## Canonical References

### VeilBreakers Game Project
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Packages/manifest.json` — Addressables 2.8.0 already installed
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/ProjectSettings/ProjectSettings.asset` — Current build settings

### Toolkit Implementation
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` — Add unity_build compound tool
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/performance_templates.py` — Existing build automation (extend)

### Requirements
- `.planning/REQUIREMENTS.md` — BUILD-01 through BUILD-05, SHDR-03, ACC-02

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 8 `unity_performance` `automate_build` action — existing build automation to extend
- Phase 9 `unity_settings` — Player Settings, Build Settings already configurable
- Phase 10 `unity_code` — Generate C# scripts (IPreprocessShaders)
- Phase 16 `unity_qa` TCP bridge — can trigger builds directly

### Integration Points
- New `unity_build` compound tool or extend `unity_performance`
- CI/CD configs are plain YAML files — write directly, no Unity Editor needed
- Store metadata is markdown/text files — write directly

</code_context>

<specifics>
## Specific Ideas

- VeilBreakers is PC-first but needs Android/iOS prep for future
- GitHub Actions is the primary CI target (repo is on GitHub)
- Addressables groups should follow VeilBreakers asset organization
- Shader variant stripping is critical for mobile — URP generates thousands of variants

</specifics>

<deferred>
## Deferred Ideas

None — autonomous mode stayed within phase scope

</deferred>

---

*Phase: 17-build-deploy-pipeline*
*Context gathered: 2026-03-20 via autonomous mode*
