# UI/UX, Accessibility, Analytics & Player-Facing Systems Research

**Researched:** 2026-04-02
**Domain:** HUD, menus, accessibility, analytics, platform integration, onboarding, photo mode
**Confidence:** HIGH (cross-referenced official Unity docs, Xbox Accessibility Guidelines, Steamworks docs, game accessibility guidelines, and existing toolkit audit)

## Summary

VeilBreakers already has substantial UI/UX infrastructure in both the Unity game project (UI Toolkit + PrimeTween, combat HUD, minimap, damage numbers, radial menu, rarity VFX, dark fantasy frames) and the MCP toolkit (12 UX template generators, accessibility system, analytics, loading screens, settings menus). The gap is NOT missing systems -- most systems exist as templates or partial implementations. The gap is the "last mile" polish, integration, and completeness that separates a tech demo from a shippable game.

The three highest-impact areas are: (1) a unified settings/options menu system that actually persists and applies all graphics/audio/accessibility/controls settings, (2) platform integration (Steamworks for achievements, cloud saves, rich presence), and (3) onboarding flow that teaches VeilBreakers' unique mechanics (brands, corruption, The Veil) without walls of text.

**Primary recommendation:** Focus on wiring existing template generators into a cohesive player experience pipeline. The toolkit can already generate individual systems (minimap, damage numbers, accessibility, analytics). What's missing is the orchestration layer that connects these into a complete player-facing package: main menu -> settings -> onboarding -> gameplay HUD -> pause -> photo mode, with platform integration throughout.

---

## 1. HUD and UI Systems

### 1.1 Existing Toolkit Coverage (HIGH confidence -- verified from source)

| System | Toolkit Generator | Template File | Status |
|--------|------------------|---------------|--------|
| Minimap | `unity_ux` action=`create_minimap` | ux_templates.py:106 | EXISTS - render texture, compass, markers |
| Damage Numbers | `unity_ux` action=`create_damage_numbers` | ux_templates.py:376 | EXISTS - pooled, crit scaling |
| Interaction Prompts | `unity_ux` action=`create_interaction_prompts` | ux_templates.py:554 | EXISTS - trigger radius, fade |
| Tutorial System | `unity_ux` action=`create_tutorial_system` | ux_templates.py:1192 | EXISTS - step-based |
| Accessibility | `unity_ux` action=`create_accessibility` | ux_templates.py:1485 | EXISTS - colorblind, subtitles, motor |
| Character Select | `unity_ux` action=`create_character_select` | ux_templates.py:1833 | EXISTS - hero paths |
| World Map | `unity_ux` action=`create_world_map` | ux_templates.py:2185 | EXISTS - fog of war |
| Rarity VFX | `unity_ux` action=`create_rarity_vfx` | ux_templates.py:2465 | EXISTS - 5 tiers with glow |
| Corruption VFX | `unity_ux` action=`create_corruption_vfx` | ux_templates.py:2837 | EXISTS |
| Combat HUD | `unity_ui` | ui_templates.py:568 | EXISTS - health, stamina, abilities |
| Radial Menu | `unity_ui_polish` | ui_polish_templates.py:1499 | EXISTS |
| Tooltip System | `unity_ui_polish` | ui_polish_templates.py:1047 | EXISTS |
| Loading Screen | `unity_ui_polish` | ui_polish_templates.py:2226 | EXISTS |
| Notification System | `unity_ui_polish` | ui_polish_templates.py:1885 | EXISTS |
| Procedural Frames | `unity_ui_polish` | ui_polish_templates.py:55 | EXISTS - dark fantasy ornate frames |
| Cursor System | `unity_ui_polish` | ui_polish_templates.py:852 | EXISTS |
| Inventory System | `unity_content` | content_templates.py:88 | EXISTS |
| Dialogue System | `unity_content` | content_templates.py:603 | EXISTS |
| Quest System | `unity_content` | content_templates.py:947 | EXISTS |
| Crafting System | `unity_content` | content_templates.py:1393 | EXISTS |
| Skill Tree | `unity_content` | content_templates.py:1604 | EXISTS |
| Shop System | `unity_content` | content_templates.py:2216 | EXISTS |
| Journal System | `unity_content` | content_templates.py:2501 | EXISTS |
| Settings Menu | `unity_game` | game_templates.py:1592 | EXISTS |
| Input Config | `unity_game` | game_templates.py:1046 | EXISTS |
| Save System | `unity_game` | game_templates.py:81 | EXISTS |
| Analytics | `unity_qa` action=`setup_analytics` | qa_templates.py:2196 | EXISTS - singleton, JSON file logging |
| Crash Reporting | `unity_qa` | qa_templates.py:1948 | EXISTS |

### 1.2 HUD Design Patterns for Dark Fantasy Action RPGs

**Health/Stamina/Mana Bars:**
- **Standard pattern:** Bottom-left or bottom-center cluster. Health bar is always largest and most prominent.
- **Dark Souls approach:** Bars at top-left, minimal, with delayed damage display (white bar shrinks first, then red follows).
- **VeilBreakers recommendation:** Bottom-left cluster with corruption overlay. Health (red), Stamina (green/yellow), Mana/Brand power (brand-colored). Add corruption visual distortion to bars as corruption increases (0-100%).
- **Technical:** Use Unity UI Toolkit `VisualElement` with USS transitions. Fill bars via `style.width` percentage. PrimeTween for smooth interpolation. Separate static (frame/icons) from dynamic (fill amounts) elements for batching.

**Inventory UI:**
- **Grid inventory** (Diablo/Elden Ring): Best for action RPGs with many unique items. 8x5 or 6x8 grids with category tabs. Icons must be legible at 64x64px minimum.
- **List inventory** (Skyrim): Better for text-heavy RPGs. Faster to scan. Works well with controller navigation.
- **VeilBreakers recommendation:** Grid inventory with category tabs (Weapons, Armor, Consumables, Materials, Key Items). Grid for items, detail panel on right showing stats/lore/brand affinity. Controller support via D-pad navigation between cells.
- **Equipment screen:** Paper doll character model with equipment slots around it. 12 armor slots already defined in the game. Show stat comparison on hover/selection.

**Minimap/Compass:**
- Already has generator with render texture, compass, and markers.
- **Enhancement needed:** Add marker types for quest objectives, merchants, fast travel points, corruption hotspots.
- **Compass alternative:** Some dark fantasy games (Skyrim) use a compass strip at top instead of minimap. Consider offering both options in settings.

**Quest Tracker:**
- Compact side panel (right edge) showing 1-3 active quests with next objective.
- Toggle to expand/collapse. Auto-hide during combat.
- **VeilBreakers:** Quest system template exists. Need a HUD-integrated tracker widget that reads from QuestManager.

**Boss Health Bars:**
- Large bar at top-center or bottom-center of screen. Boss name in ornate dark fantasy font.
- Phase indicators (dots or segments) below the bar.
- **VeilBreakers:** Boss phase controller exists (gameplay_templates.py). Need dedicated boss HP bar UI widget.

**Damage Numbers:**
- Already exists with pool and crit scaling.
- **Enhancement:** Add brand-colored damage numbers. Show damage type icons (physical, fire, void, etc.). Add "absorbed" display for blocked damage.

**Status Effects Display:**
- Row of icons below or near the health bars. Timer indicators (radial fill or countdown).
- Group by positive/negative (buffs left, debuffs right).
- **VeilBreakers:** Status effect system exists (gameplay_templates.py:3590). Need status icon bar HUD widget.

### 1.3 UI Rendering Performance (HIGH confidence)

**Unity UI Toolkit advantages over UGUI:**
- No GameObject overhead per element.
- Retained-mode rendering with automatic batching.
- Shader supports up to 8 textures per batch (fewer draw calls).
- Uses Yoga/Flexbox layout engine.
- Recommended for menus and data-heavy screens.

**Performance best practices:**
- Separate Panel Settings assets for HUD vs menus vs minimap. Each gets its own render pass but avoids cross-contamination of dirty flags.
- Static elements (frames, backgrounds) should not share containers with dynamic elements (fill bars, numbers). When one element changes, the entire container's mesh is regenerated.
- Avoid `VisualElement.style` changes every frame for non-animated elements.
- Use USS transitions instead of per-frame C# property updates where possible.
- Pool damage number elements rather than creating/destroying.
- For the minimap, use a dedicated render texture camera with aggressive culling layers.
- Target: < 5 draw calls for the entire HUD during normal gameplay.

**Hybrid approach:** Use UI Toolkit for all menus, inventory, settings, dialogue. Use UGUI only if needed for world-space 3D UI (health bars above enemies). Both systems can coexist.

---

## 2. Menu Systems

### 2.1 Main Menu

**Standard flow:**
```
Main Menu
  |- New Game -> Character Select -> Difficulty Select -> Intro Cinematic -> Game
  |- Continue -> Load save -> Game
  |- Load Game -> Save slot list -> Game
  |- Settings -> (Graphics | Audio | Controls | Accessibility | Gameplay)
  |- Credits
  |- Quit
```

**Dark fantasy presentation:**
- Animated background: The starter town or a corrupted landscape, slowly rotating camera or parallax layers.
- Dark atmospheric music (already have adaptive music system).
- Logo with subtle corruption VFX animation.
- Menu items: ornate dark fantasy font (Cinzel or similar), with hover effects using PrimeTween.

**VeilBreakers already has:** Character select template, settings menu template, save system template. Need to wire these into an actual main menu scene with transitions.

### 2.2 Pause Menu

- Must pause game time (`Time.timeScale = 0`).
- Quick access: Resume, Settings, Save, Load, Quit to Main Menu.
- Darken/blur background using URP post-processing Volume override.
- Must work with PrimeTween (PrimeTween supports `useUnscaledTime` for paused animations).

### 2.3 Settings Menu

**Required categories:**

| Category | Settings | Implementation |
|----------|----------|----------------|
| Graphics | Resolution, fullscreen mode, quality preset (Low/Med/High/Ultra), V-Sync, shadow quality, anti-aliasing, render scale, ambient occlusion, bloom, depth of field, motion blur | URP Quality Settings + Graphics Settings template exists |
| Audio | Master volume, Music volume, SFX volume, Voice volume, Ambient volume | Audio Mixer groups (template exists) |
| Controls | Key rebinding, controller sensitivity, invert Y, toggle/hold for sprint/block | Input System + Input Config template exists |
| Accessibility | Colorblind mode, subtitle scale, screen reader, toggle vs hold, input timing, camera shake intensity, UI scale, high contrast mode | Accessibility template exists |
| Gameplay | Difficulty, HUD scale, minimap toggle, damage numbers toggle, camera shake intensity, language | Custom |

**Key rebinding (HIGH confidence):**
- Unity New Input System supports runtime rebinding via `InputAction.PerformInteractiveRebinding()`.
- Display bindings using `InputAction.GetBindingDisplayString()` which auto-adapts to active device (keyboard vs controller).
- Store rebindings as JSON via `InputActionAsset.SaveBindingOverridesAsJson()` / `LoadBindingOverridesFromJson()`.
- Must support both keyboard+mouse AND controller rebinding.

**Settings persistence:**
- Use `PlayerPrefs` for simple values (volume, toggles).
- Use JSON file for complex data (key rebindings, graphics profiles).
- Apply settings immediately with real-time preview (the game runs behind the settings menu).
- Save on change, not on menu close.

### 2.4 Loading Screens

**Already exists:** `generate_loading_screen_script` in ui_polish_templates.py.

**Enhancement for dark fantasy:**
- Background art: concept art or in-game screenshots of areas the player is entering.
- Lore tips: random lore snippets from the journal system. Brand descriptions, corruption lore, NPC backstory.
- Progress bar: ornate dark fantasy styling. Use `AsyncOperation.progress` (0 to 0.9, divide by 0.9f for display).
- Set `allowSceneActivation = false` to hold on the loading screen until a minimum display time has passed (avoid flash-loading for small scenes).
- Minimum 2-second display time for readability.

---

## 3. Accessibility (HIGH confidence)

### 3.1 Existing Toolkit Coverage

The `create_accessibility` action generates:
- `AccessibilitySettings.cs` MonoBehaviour with PlayerPrefs persistence
- Colorblind simulation shader (HLSL, 3 LMS matrices for protanopia, deuteranopia, tritanopia)
- URP Renderer Feature for fullscreen colorblind blit
- Subtitle scaling (1.0x to 3.0x)
- Screen reader toggle
- Motor accessibility: toggle vs hold, input timing multiplier (0.5x to 2.0x)

### 3.2 Game Accessibility Guidelines -- Required Features

Sourced from gameaccessibilityguidelines.com and Xbox Accessibility Guidelines (XAG v3.2).

**BASIC (must-have for any shipped game):**

| Feature | Status | Gap |
|---------|--------|-----|
| Remappable controls | Template exists (Input Config) | Needs actual UI wiring |
| Subtitles for all speech | Template exists (VO pipeline has subtitle support) | Needs in-game subtitle display widget |
| Colorblind mode | EXISTS in accessibility template | DONE - 3 modes |
| High contrast text/UI vs background | Partially in accessibility template | Need explicit high-contrast toggle |
| No essential info by color alone | Design guideline | Audit all UI elements |
| Adjustable game speed / difficulty | Difficulty template exists | Need difficulty options in settings |
| Large, well-spaced interactive elements | Design guideline | UI layout review |
| Consistent input methods | Design guideline | Input audit |
| Separate volume controls | Audio Mixer template exists | Wire to settings menu |
| Allow text progression at own pace | Dialogue system supports this | Verify implementation |
| Interactive tutorials | Tutorial system template exists | Wire to game |
| Avoid flickering images | Design guideline | VFX audit needed |

**INTERMEDIATE (expected for indie RPGs):**

| Feature | Status | Gap |
|---------|--------|-----|
| Subtitle customization (size, background, speaker ID) | Subtitle scale exists, need background opacity and speaker colors | MEDIUM gap |
| Contextual help/objective reminders | Quest tracker concept | Need implementation |
| Toggle/hold alternatives | EXISTS in accessibility template | DONE |
| Multiple simultaneous input devices | Unity Input System supports this | Verify |
| Adjustable camera sensitivity | Need in settings | SMALL gap |
| Field of view adjustment | URP supports this | Need settings slider |
| Screen reader support | Toggle exists | Need TTS integration |
| Input timing adjustments | EXISTS in accessibility template (0.5x-2.0x multiplier) | DONE |
| Assist modes (auto-aim, generous dodge windows) | Not implemented | MEDIUM gap |
| Adjustable difficulty during gameplay | Not in templates | SMALL gap |

**ADVANCED (differentiator, exceeds expectations):**

| Feature | Status | Gap |
|---------|--------|-----|
| One-handed play support | Not implemented | Need alternative control scheme |
| Full screen reader with menu navigation | Toggle exists, no TTS engine | LARGE gap -- need Windows SAPI or plugin |
| Symbol-based communication | N/A (single player) | SKIP |
| Pre-recorded voiceover for all text | ElevenLabs integration exists | LARGE content gap |

### 3.3 CVAA Compliance

The CVAA (21st Century Communications and Video Accessibility Act) requires accessibility of advanced communications features (voice chat, text chat, video chat). For a single-player game with no online communications, CVAA has minimal direct impact. However, if multiplayer is added later, text-to-speech and speech-to-text for in-game chat becomes legally required.

### 3.4 Platform Accessibility Badges

Xbox and PlayStation offer accessibility review programs that can award visibility-boosting badges. Key criteria:
- Text-to-speech for UI navigation
- Customizable subtitles (size, opacity, speaker colors)
- Remappable controls
- Colorblind options
- Difficulty options

### 3.5 Specific Implementation Recommendations

**Colorblind modes:**
- Already have protanopia, deuteranopia, tritanopia shader simulation.
- Additionally: ensure all UI uses shape AND color to convey meaning (not color alone). E.g., item rarity uses both color AND icon border style. Brand affinity uses both color AND icon symbol.
- Test with Color Oracle simulator tool.

**Subtitle system:**
- Background: semi-transparent black box behind text (adjustable opacity 0-100%).
- Speaker identification: colored name prefix (with colorblind-safe colors + icon).
- Font size: minimum 28pt at 1080p, scalable to 200%.
- Letterboxing: 32-42 characters per line maximum.
- Position: bottom-center, adjustable to top/middle/bottom.

**Camera/motion sickness options:**
- Camera shake intensity slider (0-100%, default 100%).
- Motion blur toggle (off by default in settings).
- Field of view slider (60-120 degrees).
- Head bob toggle for first-person segments (if any).
- Screen flash intensity slider.

**UI scale:**
- Global UI scale slider (80% to 200%).
- Separate HUD scale option.
- Minimum text size: 16pt at 1080p (24pt recommended for body text, 28pt for subtitles).

---

## 4. Analytics and Telemetry (HIGH confidence)

### 4.1 Existing Toolkit Coverage

`setup_analytics` action generates `VBAnalytics.cs`:
- Singleton MonoBehaviour
- Buffers events in memory, flushes to JSON file on disk
- Configurable flush interval (default 30s) and max buffer size (default 100)
- Typed convenience methods for standard event names
- Session tracking with GUID

### 4.2 What to Track

**Essential game events:**

| Category | Events | Why |
|----------|--------|-----|
| Session | session_start, session_end, session_duration | Engagement metrics |
| Progression | area_discovered, quest_started, quest_completed, level_up | Funnel analysis |
| Combat | death (with location, enemy, brand), boss_attempt (boss ID, phase reached, duration, result), damage_dealt (by type), skill_used | Balance tuning |
| Economy | item_acquired (source, rarity), item_crafted, gold_earned, gold_spent, shop_purchase | Economy balance |
| Exploration | fast_travel_used, map_fog_revealed_percentage, secret_found | Content discovery |
| Brand System | brand_equipped, brand_synergy_triggered, corruption_level_changed | Unique mechanic validation |
| Performance | fps_average (per 30s), frame_drops (below 30fps), load_time_scene | Technical health |
| UI/UX | menu_opened (which menu), settings_changed (which setting, old/new value), tutorial_step_completed | UX optimization |

**Heatmap data:**
- Player position every 5 seconds (sampled, not continuous) -> location heatmap.
- Death location + cause -> death heatmap for difficulty tuning.
- Enemy encounter location + outcome -> balance heatmap.
- Store as: `{x, y, z, timestamp, session_id, event_type}`.
- Visualization: offline tool that renders heatmap overlay on level geometry. Can use Python + matplotlib or custom Unity editor window.

### 4.3 Privacy and GDPR Compliance

**Unity Analytics SDK 5.0+ (HIGH confidence):**
- SDK initializes in dormant state by default -- collects NO personal data until activated.
- Developer is responsible for determining applicable privacy legislation and obtaining consent.
- Anonymized user IDs generated unless external IDs are explicitly provided.
- "Request Data Deletion" function deletes all data for a player within 30 days.

**VeilBreakers recommendation:**
- For initial release: local-only analytics (JSON file on disk). No data leaves the player's machine.
- Add opt-in telemetry later: "Help improve VeilBreakers by sharing anonymous gameplay data" toggle in settings.
- If using Unity Gaming Services Analytics: implement consent flow per GDPR.
- Never collect: IP addresses, hardware IDs, personally identifiable information.
- Always collect locally: crash logs, performance metrics (these stay on machine for player bug reports).

### 4.4 Crash Reporting

**Unity Cloud Diagnostics is DEPRECATED** as of 2025. For Unity 6.2+, use the new built-in diagnostics experience.

**VeilBreakers already has:** `generate_crash_reporting_script` in qa_templates.py.

**Recommended approach:**
- Local crash log capture (Application.logMessageReceived for exceptions).
- Stack trace writing to `Application.persistentDataPath/CrashLogs/`.
- Player-facing: "The game encountered an error. Would you like to send a report?" dialog.
- Include: stack trace, Unity version, graphics API, system specs (RAM, GPU), last 5 analytics events before crash.
- Steam has built-in crash dump collection for shipped games.

---

## 5. Platform Integration

### 5.1 Steamworks (HIGH confidence)

**Standard library:** Steamworks.NET (free, open-source C# wrapper around Steamworks SDK).
- NuGet: `Steamworks.NET` or drop DLLs directly.
- Alternative: Heathen's Toolkit for Steamworks (paid, higher-level API, extensive features).

**Key integrations:**

| Feature | Steamworks API | Complexity | Priority |
|---------|---------------|------------|----------|
| Achievements | `SteamUserStats.SetAchievement()` / `StoreStats()` | LOW | HIGH |
| Cloud Saves | `SteamRemoteStorage.FileWrite()` / `FileRead()` | MEDIUM | HIGH |
| Rich Presence | `SteamFriends.SetRichPresence()` | LOW | MEDIUM |
| Overlay | Automatic with Steamworks init | LOW | HIGH |
| Screenshots | `SteamScreenshots.TriggerScreenshot()` | LOW | MEDIUM |
| Workshop (modding) | `SteamUGC` API | HIGH | LOW (post-launch) |
| Leaderboards | `SteamUserStats.FindLeaderboard()` | MEDIUM | LOW |
| Input (Steam Deck) | Steam Input API | MEDIUM | HIGH for Deck support |

**Achievements design for dark fantasy RPG:**
- Story progression: defeat each main boss (5-12 achievements).
- Exploration: discover all areas, find all secrets.
- Brand mastery: fully level each brand (10 achievements).
- Combat: defeat a boss without taking damage, kill X enemies with each brand.
- Crafting: craft a legendary item.
- Corruption: reach 100% corruption, cure all corruption.
- Meta: complete the game, complete on hard, speedrun under X hours.
- Target: 30-50 achievements total. Mix of progression (guaranteed) and challenge (optional).

**Cloud Saves:**
- Save files stored in `Application.persistentDataPath`.
- Use `SteamRemoteStorage` to sync save files to Steam Cloud.
- Handle conflicts: show "Local save is newer/older than cloud save" dialog.
- Critical: The existing save system has 35 known bugs including data loss (SAVE-02). Fix save system BEFORE wiring to cloud.

**Steam Deck support:**
- Unity New Input System recognizes Steam Deck as a standard gamepad.
- Steam Input API provides additional Steam Deck-specific features (touchpad regions, back grips).
- Valve's Steam Deck compatibility checklist: full controller support, readable text at 1280x800, no anti-cheat conflicts, no launcher/middleware popups.
- All UI must be navigable by controller (D-pad navigation, A/B for confirm/cancel).
- Text size minimum: 9pt at 1280x800 (Valve recommends 12pt+).

### 5.2 Discord Rich Presence

**Official: Discord Social SDK (2025+).**
- Download from Discord Developer Portal.
- Unity integration: drop-in prefabs available.
- Key API: `Activity.SetDetails("Exploring Hearthvale")`, `Activity.SetState("Level 15 Ironbound")`.
- Custom art for game invite banners.
- Features: Rich Presence, voice chat, lobbies (if multiplayer added later).

**Implementation:**
```csharp
// Simplified pattern
var activity = new Activity();
activity.SetType(ActivityTypes.Playing);
activity.SetDetails($"Fighting {bossName}");  // "Escort Mission", "Level 7"
activity.SetState($"Corruption: {corruptionLevel}%");
activity.Assets.SetLargeImage("veilbreakers_logo");
activity.Assets.SetLargeText("VeilBreakers");
activity.Assets.SetSmallImage($"brand_{currentBrand.ToLower()}");
activity.Assets.SetSmallText(currentBrand);
activity.Timestamps.SetStart(sessionStartTime);
```

**VeilBreakers context strings:**
- Exploring: "Wandering {area_name}" with corruption percentage.
- Combat: "Fighting {enemy/boss_name}".
- Menu: "In Menus".
- Dead: "Fallen in {area_name}".
- Brand display: small icon showing current brand.

### 5.3 Controller Support

**Unity New Input System (already referenced in toolkit):**
- Supports Xbox, PlayStation (DualShock 4, DualSense), Steam Deck, generic HID gamepads.
- Device auto-detection: switch UI button prompts (A/B/X/Y vs Cross/Circle/Square/Triangle) based on active controller.
- Use `InputSystem.onDeviceChange` to detect controller connect/disconnect.
- Rumble/haptics: `Gamepad.current.SetMotorSpeeds(lowFreq, highFreq)` -- already have haptics_router template.

**Controller-specific features:**
- DualSense: adaptive triggers (tension on bowstring pull), haptic feedback, touchpad.
- Xbox: standard vibration, impulse triggers.
- Steam Deck: touchpads, back grip buttons, gyroscope.

**UI navigation with controller:**
- All menus must support D-pad navigation with visual focus indicators.
- A = confirm, B = back (Xbox layout). Map to Cross/Circle for PlayStation.
- Bumpers/triggers for tab navigation in menus (inventory categories, settings tabs).
- Hold patterns: must support toggle alternative (accessibility).

**Adaptive button prompts:**
- Detect active input device, swap button prompt sprites.
- Use sprite atlas with Xbox/PlayStation/Keyboard icon sets.
- TextMeshPro inline sprites: `<sprite name="Xbox_A">` / `<sprite name="PS_Cross">` / `<sprite name="Key_E">`.
- Auto-switch when player uses mouse/keyboard vs controller input.

---

## 6. Onboarding and Tutorial

### 6.1 Dark Fantasy RPG Onboarding Philosophy

**Core principle:** "Show, don't tell." Dark fantasy games teach through environment and consequence, not text walls.

**FromSoftware approach:**
- Minimal explicit tutorials.
- First area is a controlled gauntlet that teaches all basic mechanics through spatial design.
- Messages left on the ground provide hints without breaking immersion.
- Early enemies test specific mechanics (one that requires blocking, one that requires dodging).

**VeilBreakers adaptation:**
- The first 30 minutes must showcase 6 things: the Role/Fantasy (brand-wielding warrior), World Stakes (corruption spreading), Goals (stop the Veil), Gameplay Pillars (combat, exploration, brands), Core Systems (health/stamina/brands), and Primary Emotions (dread, discovery, mastery).

### 6.2 Contextual Hints System

**VeilBreakers already has:** Tutorial system template (step-based).

**Enhancement for shipped game:**

| Hint Type | Trigger | Display | Example |
|-----------|---------|---------|---------|
| Movement | First 10 seconds of gameplay | Transparent overlay with control diagram | "WASD to move, Mouse to look" |
| Combat | First enemy encounter | Brief flash at bottom of screen | "LMB to attack, RMB to block" |
| Dodge | First enemy attack animation | Timed prompt | "Space to dodge" |
| Brand | First brand acquisition | Full-screen momentary highlight | "You've awakened the Iron Brand. Hold Q to unleash." |
| Corruption | Corruption first reaches 25% | Narrative warning + UI pulse | Screen edge corruption VFX + "The Veil encroaches..." |
| Inventory | First item pickup | Small popup | "Press I to open inventory" |
| Map | Entering new area | Brief compass flash | New area discovery notification |

**Adaptive input prompts:**
- Detect controller vs keyboard automatically.
- Show Xbox/PlayStation/keyboard icons matching current device.
- Switch in real-time when player changes input method.
- Use TextMeshPro inline sprites for button prompts in all tutorial text.

### 6.3 First 30 Minutes Design

**Recommended structure:**

1. **Minutes 0-2:** Awakening scene. Player in a corrupted ruin. Minimal HUD. Learn movement.
2. **Minutes 2-5:** First combat. Weak enemies teach light attack, heavy attack, dodge. Death is possible but unlikely.
3. **Minutes 5-8:** First brand manifestation. Dramatic VFX moment. Tutorial for brand ability.
4. **Minutes 8-12:** Navigate to the starter town (Hearthvale). Environmental storytelling along the path showing corruption spreading.
5. **Minutes 12-18:** Starter town exploration. Meet NPCs, learn about shops, crafting, quest board. Safe zone.
6. **Minutes 18-25:** First real quest. Combat with brand synergies. Mini-boss or challenging encounter.
7. **Minutes 25-30:** Return to town. Reward. Corruption has visibly advanced. Stakes established.

**The Veil mechanic should NOT be introduced in the first 30 minutes** -- save it for the first major story beat (hour 1-2) for maximum impact.

---

## 7. Photo Mode (MEDIUM confidence)

### 7.1 Unity Photo Mode Demo

Unity provides an official Photo Mode demo showcasing best practices:
- Uses its own virtual camera that orbits/cranes around a target.
- Requires only a Cinemachine Brain in the scene (VeilBreakers already uses Cinemachine).
- Manages post-processing via dedicated global Volume.
- Modular: can change appearance, behaviors, or create custom effect options.
- Input handled by `PhotoModeInputs.cs` -- no Player Input component needed.

### 7.2 Required Features

| Feature | Implementation | Priority |
|---------|---------------|----------|
| Camera orbit/pan/zoom | Cinemachine FreeLook virtual camera | HIGH |
| Camera roll | Transform rotation on Z-axis | MEDIUM |
| FOV adjustment | Cinemachine lens FOV slider | HIGH |
| Depth of field | URP Volume override: focus distance, aperture | HIGH |
| Exposure control | URP Volume override: exposure compensation | HIGH |
| Contrast/Saturation | URP Color Adjustments override | HIGH |
| Vignette | URP Vignette override | MEDIUM |
| Film grain | URP Film Grain override | LOW |
| Filters/LUTs | Swap Color Lookup Table texture | MEDIUM |
| UI hide toggle | Set all Panel Settings to hidden | HIGH |
| Character pose | Animator snapshot + manual pose selection | MEDIUM |
| Time of day | Override directional light rotation + skybox | MEDIUM |
| Particle freeze | Set `ParticleSystem.Simulate(0)` | LOW |
| Screenshot capture | `ScreenCapture.CaptureScreenshot()` | HIGH |
| Resolution scaling | Render at higher res, downsample | LOW |
| Brand VFX toggle | Enable/disable brand particle systems | MEDIUM |
| Corruption VFX intensity | Override corruption shader parameter | MEDIUM |

### 7.3 Implementation Pattern

```csharp
// Photo mode lifecycle
public class PhotoModeController : MonoBehaviour
{
    // 1. Freeze game: Time.timeScale = 0
    // 2. Disable player input actions
    // 3. Enable photo mode input actions
    // 4. Activate photo mode Cinemachine virtual camera (highest priority)
    // 5. Create dedicated URP Volume for photo mode overrides
    // 6. Show photo mode UI (sliders, toggles)
    // On exit: restore all, Time.timeScale = 1
}
```

**VeilBreakers-specific photo mode features:**
- Brand VFX particles frozen but visible.
- Corruption overlay intensity slider.
- Dark fantasy filters: "Veil Vision" (desaturated with purple tint), "Ancient" (sepia + grain), "Blood Moon" (red tint + high contrast).
- Boss arena dramatic lighting presets.
- Toggle individual party member visibility.

---

## 8. Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Steamworks integration | Custom Steam API wrapper | Steamworks.NET (free) or Heathen Toolkit (paid) | API surface is enormous, platform-specific edge cases |
| Discord presence | Custom Discord API client | Discord Social SDK (official, free) | Auth, rate limiting, fallback handled by SDK |
| Colorblind simulation | Custom color transform math | LMS color matrices (already in accessibility template) | Clinically validated matrices exist |
| Key rebinding UI | Custom key capture + storage | Unity Input System `PerformInteractiveRebinding()` | Handles conflicts, device switching, serialization |
| Crash reporting | Custom exception handler only | Unity built-in diagnostics (6.2+) + local log capture | Native crash dumps, ANR detection, symbolication |
| Loading screen progress | Custom multi-step tracking | `AsyncOperation.progress` + Addressables loading events | Engine-level accuracy, handles late-activation |
| Screen reader / TTS | Custom text-to-speech | Windows SAPI via `System.Speech.Synthesis` or Unity Accessibility Plugin (UAP) | Platform TTS engines handle voice selection, rate, locale |
| Controller button prompt sprites | Manual sprite swaps | Input System `GetBindingDisplayString()` + TMP inline sprites | Auto-adapts to active device |
| Analytics backend | Custom server infrastructure | Local JSON (dev) -> Unity Gaming Services Analytics or GameAnalytics (production) | GDPR compliance, dashboards, funnels |

---

## 9. Common Pitfalls

### Pitfall 1: Settings Don't Persist Across Sessions
**What goes wrong:** Player configures graphics/audio/controls, but settings reset on restart.
**Why it happens:** Using `QualitySettings` or `AudioListener.volume` without saving to PlayerPrefs/JSON.
**How to avoid:** Save every setting change immediately to PlayerPrefs. Load all settings in `Awake()` before first frame renders. Use `[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]` for critical settings like resolution.
**Warning signs:** Settings menu shows defaults instead of saved values on restart.

### Pitfall 2: UI Breaks at Non-16:9 Aspect Ratios
**What goes wrong:** HUD elements overlap or disappear on ultrawide (21:9), 16:10, or Steam Deck (16:10).
**Why it happens:** Fixed pixel positions instead of relative/anchored layouts.
**How to avoid:** Use UI Toolkit Flexbox with percentage-based layouts. Test at 1280x800 (Steam Deck), 1920x1080, 2560x1080 (ultrawide), 3840x2160 (4K).
**Warning signs:** Elements outside safe area at non-standard resolutions.

### Pitfall 3: Controller Navigation Doesn't Work in All Menus
**What goes wrong:** Some menus only work with mouse, breaking controller/Steam Deck flow.
**Why it happens:** Menu built mouse-first, focus navigation added as afterthought.
**How to avoid:** Design every menu controller-first. Use UI Toolkit's `focusable` and `tabIndex` properties. Test full menu flow with controller before mouse.
**Warning signs:** Cannot reach certain buttons or fields with D-pad.

### Pitfall 4: Accessibility as an Afterthought
**What goes wrong:** Accessibility features tacked on late, breaking visual design or requiring refactors.
**Why it happens:** Color, contrast, and input assumptions baked into core systems early.
**How to avoid:** Implement accessibility toggle infrastructure at the same time as the base UI. All color choices should have a secondary shape/icon indicator from day one.
**Warning signs:** Information conveyed ONLY by color (red = bad, green = good) with no shape/text backup.

### Pitfall 5: Analytics Collecting Too Much Data
**What goes wrong:** Event flood causes performance dips, file sizes balloon, analysis becomes impossible.
**Why it happens:** Tracking everything "just in case" without sampling.
**How to avoid:** Limit position tracking to 5-second intervals. Cap event buffer at 100. Flush to disk asynchronously. Use sampling for high-frequency events (damage dealt: sample 1 in 10).
**Warning signs:** Analytics JSON file grows to 100MB+ per session.

### Pitfall 6: Photo Mode Breaks Game State
**What goes wrong:** Entering/exiting photo mode causes enemies to teleport, particles to explode, or audio to desync.
**Why it happens:** `Time.timeScale = 0` affects physics, animation, and audio differently.
**How to avoid:** Freeze enemies explicitly (disable NavMeshAgent, Animator, AI state machine). Use `AudioSource.ignoreListenerPause` for ambient sounds that should continue. Cache and restore all modified state on exit.
**Warning signs:** Enemy positions different after exiting photo mode than before entering.

### Pitfall 7: Loading Screen Stuck at 90%
**What goes wrong:** Progress bar reaches 90% and stops.
**Why it happens:** `AsyncOperation.progress` returns 0-0.9, with the last 0.1 happening during scene activation.
**How to avoid:** Divide progress by 0.9f and clamp to 0-1. Or use `allowSceneActivation = false` and manually set to 100% before activating.
**Warning signs:** Progress bar never reaches "full" before scene loads.

### Pitfall 8: Save System Data Loss (CRITICAL -- VeilBreakers Specific)
**What goes wrong:** Cloud saves overwrite local saves or vice versa, causing progress loss.
**Why it happens:** The existing save system has 35 known bugs (from codebase audit). Layering cloud sync on a broken foundation amplifies data loss risk.
**How to avoid:** Fix ALL save system bugs BEFORE implementing Steam Cloud. Implement save file versioning and backup rotation. Test conflict resolution thoroughly.
**Warning signs:** Any save-related test failures.

---

## 10. Architecture Patterns

### 10.1 UI Architecture for Action RPGs

```
Assets/
├── UI/
│   ├── Screens/           # Full-screen UIs (UXML + USS)
│   │   ├── MainMenu/
│   │   ├── PauseMenu/
│   │   ├── Inventory/
│   │   ├── Equipment/
│   │   ├── SkillTree/
│   │   ├── Map/
│   │   ├── Settings/
│   │   ├── Dialogue/
│   │   ├── Shop/
│   │   ├── Crafting/
│   │   └── PhotoMode/
│   ├── HUD/               # Always-visible gameplay UI
│   │   ├── HealthBars/
│   │   ├── Minimap/
│   │   ├── QuestTracker/
│   │   ├── StatusEffects/
│   │   ├── DamageNumbers/
│   │   ├── BossBar/
│   │   ├── InteractionPrompts/
│   │   └── Notifications/
│   ├── Widgets/            # Reusable UI components
│   │   ├── ItemSlot/
│   │   ├── StatBar/
│   │   ├── ButtonPrompt/
│   │   ├── Tooltip/
│   │   └── ConfirmDialog/
│   ├── Styles/             # Shared USS stylesheets
│   │   ├── DarkFantasyTheme.uss
│   │   ├── Typography.uss
│   │   ├── Colors.uss
│   │   └── Accessibility.uss
│   └── Icons/              # Sprite atlases
│       ├── Items/
│       ├── StatusEffects/
│       ├── Brands/
│       ├── InputPrompts/
│       └── MapMarkers/
├── Scripts/
│   ├── UI/
│   │   ├── Screens/       # Screen controllers (C#)
│   │   ├── HUD/           # HUD element controllers
│   │   ├── Widgets/       # Widget logic
│   │   └── UIManager.cs   # Screen stack manager
│   ├── Platform/
│   │   ├── SteamManager.cs
│   │   ├── DiscordManager.cs
│   │   └── PlatformBridge.cs
│   └── Analytics/
│       ├── VBAnalytics.cs
│       └── HeatmapRecorder.cs
```

### 10.2 Screen Stack Pattern

```csharp
// UIManager maintains a stack of active screens
// Push: new screen opens on top (old screen stays but is input-blocked)
// Pop: top screen closes, previous screen regains focus
// Replace: pop + push in one operation

public class UIManager : MonoBehaviour
{
    private Stack<UIScreen> _screenStack;

    public void Push(UIScreen screen) { /* deactivate top, push new */ }
    public void Pop() { /* remove top, reactivate previous */ }
    public bool IsAnyScreenOpen => _screenStack.Count > 0;
    // Pause menu checks IsAnyScreenOpen to prevent double-pause
}
```

### 10.3 Input Device Detection Pattern

```csharp
// Auto-detect controller vs keyboard and swap UI prompts
InputSystem.onActionChange += (obj, change) =>
{
    if (change == InputActionChange.ActionPerformed)
    {
        var action = (InputAction)obj;
        var device = action.activeControl?.device;
        if (device is Gamepad) SetInputMode(InputMode.Controller);
        else if (device is Keyboard || device is Mouse) SetInputMode(InputMode.KeyboardMouse);
    }
};
```

---

## 11. State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| UGUI for everything | UI Toolkit for menus, UGUI for world-space only | Unity 6 (2024) | Fewer draw calls, better batching, CSS-like styling |
| Unity Cloud Diagnostics | Built-in diagnostics (Unity 6.2+) | 2025 | Cloud Diagnostics deprecated |
| Discord Game SDK (deprecated) | Discord Social SDK | 2024-2025 | New API, better Unity support |
| Manual save file sync | Steamworks.NET + Remote Storage | Stable since 2020 | Standard approach unchanged |
| Custom analytics server | Local-first + opt-in cloud (UGS Analytics or GameAnalytics) | 2023+ GDPR evolution | Privacy-by-default, SDK dormant until activated |
| Separate accessibility options | Integrated accessibility system with industry guidelines | XAG v3.2 (2023), ongoing | Platform badges, legal compliance |
| Tutorial text walls | Contextual, adaptive, show-don't-tell | Industry standard since ~2018 | Players skip tutorials, learn by doing |
| Fixed button prompts | Adaptive prompts that detect input device | Unity Input System 1.x | Essential for multi-platform |

---

## 12. VeilBreakers-Specific UI Requirements

### Brand System UI
- 10 brands each need: unique color, icon, VFX style.
- Brand selector: radial menu (already exists) or hotbar.
- Brand synergy display: show FULL/PARTIAL/NEUTRAL/ANTI status when equipping.
- Brand power meter: per-brand charge level near health bars.

### Corruption UI
- Screen-edge corruption VFX that intensifies from 0-100%.
- Corruption meter: dedicated bar or number display.
- At 25/50/75/100% thresholds: dramatic UI pulse + visual change.
- High corruption: UI elements start to "glitch" or "bleed" (dark fantasy aesthetic).

### The Veil UI (when implemented)
- Veil activation indicator: lens/lantern icon that glows when Veil can be pierced.
- Dual-world transition: full-screen shader effect during transition.
- Veil-world HUD: slightly different color palette (purple/blue shift) to reinforce alternate reality.

---

## 13. Priority Ordering for Implementation

### P0: Must Have for Playable Build
1. Main menu (new game, continue, settings, quit)
2. Pause menu with settings access
3. Complete settings menu (graphics, audio, controls, accessibility)
4. HUD: health/stamina/mana bars, brand display, minimap
5. Inventory with equipment screen
6. Quest tracker HUD widget
7. Loading screens with progress bar
8. Basic controller support (all menus navigable)

### P1: Must Have for Steam Release
1. Steamworks integration (achievements, cloud saves, rich presence)
2. Key rebinding UI
3. Full accessibility suite (colorblind, subtitles, motor options, UI scale)
4. Adaptive input prompts (keyboard vs controller icons)
5. Boss health bars
6. Status effect display
7. Damage numbers with brand colors
8. Steam Deck verification (resolution, text size, controller flow)

### P2: Should Have for Quality Release
1. Photo mode
2. Discord Rich Presence
3. Notification system (area discovery, level up, achievement)
4. Contextual tutorial system
5. Shop/merchant UI
6. Crafting UI
7. Skill tree UI
8. Map screen with fog of war

### P3: Nice to Have
1. Analytics/telemetry (opt-in)
2. Heatmap data collection
3. Advanced accessibility (screen reader, one-handed play)
4. Workshop/modding support
5. Photo mode character poses

---

## Sources

### Primary (HIGH confidence)
- Unity UI Toolkit docs: https://docs.unity3d.com/Manual/UIElements.html
- Unity UI performance optimization: https://unity.com/how-to/unity-ui-optimization-tips
- Unity Analytics GDPR: https://docs.unity.com/ugs/en-us/manual/analytics/manual/manage-data-privacy
- Game Accessibility Guidelines: https://gameaccessibilityguidelines.com/full-list/
- Xbox Accessibility Guidelines v3.2: https://learn.microsoft.com/en-us/gaming/accessibility/guidelines
- Steamworks SDK docs: https://partner.steamgames.com/doc/sdk
- Steamworks.NET: https://steamworks.github.io/
- Discord Social SDK: https://discord.com/developers/docs/discord-social-sdk/getting-started/using-unity
- Unity Input System gamepad support: https://docs.unity3d.com/Packages/com.unity.inputsystem@1.0/manual/Gamepad.html
- Steam Deck developer recommendations: https://partner.steamgames.com/doc/steamdeck/recommendations
- Unity Photo Mode demo: https://blog.unity.com/games/exploring-in-game-photography-with-the-new-photo-mode-demo

### Secondary (MEDIUM confidence)
- UI Toolkit vs UGUI 2025 comparison: https://www.angry-shark-studio.com/blog/unity-ui-toolkit-vs-ugui-2025-guide/
- Game analytics guide: https://generalistprogrammer.com/game-analytics
- Heatmap guide for games: https://medium.com/@dariarodionovano/a-heatmap-guide-for-game-level-analysis-68cb6a7bcb2b
- Game onboarding best practices: https://inworld.ai/blog/game-ux-best-practices-for-video-game-onboarding
- Inventory UX design: https://acagamic.com/newsletter/2023/03/21/how-to-unlock-the-secrets-of-video-game-inventory-ux-design/

### Tertiary (LOW confidence)
- Heathen Toolkit for Steamworks feature claims (not verified against source)
- Unity screen reader expansion (September 2025 article -- post training data)

---

## Metadata

**Confidence breakdown:**
- HUD/UI systems: HIGH -- verified against existing toolkit source code and Unity docs
- Menu systems: HIGH -- well-established patterns, templates already exist in toolkit
- Accessibility: HIGH -- cross-referenced gameaccessibilityguidelines.com, Xbox XAGs, and existing toolkit ACC-01 template
- Analytics: HIGH -- verified Unity Analytics SDK 5.0+ behavior, existing toolkit QA-07 template
- Platform integration: HIGH -- Steamworks.NET and Discord Social SDK are well-documented stable APIs
- Onboarding: MEDIUM -- design recommendations based on industry analysis, not project-specific validation
- Photo mode: MEDIUM -- Unity demo exists, implementation pattern clear, but no VeilBreakers-specific prototype

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (30 days -- UI patterns are stable, SDK versions may update)
