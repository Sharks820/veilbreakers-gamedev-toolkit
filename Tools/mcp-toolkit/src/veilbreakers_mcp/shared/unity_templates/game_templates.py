"""Core game system C# template generators for Unity.

Each function returns a complete C# source string (or tuple of strings for
multi-file generators) for runtime MonoBehaviours and utility classes. These
are placed in the Unity project's Assets/Scripts/Runtime/ directory -- they
are NOT editor scripts and must NEVER reference the UnityEditor namespace.

Exports:
    generate_save_system_script           -- GAME-01: Save/Load with JSON, AES-CBC, migration
    generate_health_system_script         -- GAME-05: HP component with DamageCalculator
    generate_character_controller_script  -- GAME-06: Third-person CharacterController + Cinemachine 3.x
    generate_input_config_script          -- GAME-07: .inputactions JSON + C# wrapper with rebinding
    generate_settings_menu_script         -- GAME-08: Settings C# + UXML + USS
    generate_http_client_script           -- MEDIA-02: UnityWebRequest wrapper with retry
    generate_interactable_script          -- RPG-03: Interactable state machine + InteractionManager
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


# ---------------------------------------------------------------------------
# C# reserved words
# ---------------------------------------------------------------------------

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
    Strips everything else. Segments starting with a digit get a ``_``
    prefix, and segments that are C# reserved words get an ``@`` prefix.

    Args:
        ns: Raw namespace string.

    Returns:
        Sanitized namespace string safe for C# ``namespace`` declarations.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_.]", "", ns)
    # Strip leading/trailing dots and collapse consecutive dots
    sanitized = re.sub(r"\.{2,}", ".", sanitized).strip(".")
    if not sanitized:
        return "Generated"
    # Validate each segment: fix leading-digit and reserved-word segments
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
# GAME-01: Save system (JSON + AES-CBC + migration)
# ---------------------------------------------------------------------------


def generate_save_system_script(
    slot_count: int = 3,
    use_encryption: bool = True,
    use_compression: bool = True,
    auto_save: bool = True,
    namespace: str = "VeilBreakers.GameSystems",
) -> str:
    """Generate C# runtime MonoBehaviour for a save/load system.

    Produces VB_SaveSystem singleton with JSON serialization, optional
    AES-CBC encryption, optional GZip compression, auto-save slot,
    data migration framework, and atomic writes.

    Args:
        slot_count: Number of manual save slots.
        use_encryption: Whether to include AES-CBC encryption.
        use_compression: Whether to include GZip compression.
        auto_save: Whether to include auto-save slot.
        namespace: C# namespace for generated code.

    Returns:
        Complete C# source string.
    """
    lines = []

    # Using directives
    lines.append("using System;")
    lines.append("using System.Collections.Generic;")
    lines.append("using System.IO;")
    if use_compression:
        lines.append("using System.IO.Compression;")
    if use_encryption:
        lines.append("using System.Security.Cryptography;")
    lines.append("using System.Text;")
    lines.append("using UnityEngine;")
    lines.append("")
    lines.append("namespace " + _safe_namespace(namespace))
    lines.append("{")

    # SaveSlot class
    lines.append("    /// <summary>")
    lines.append("    /// Represents a save slot with metadata for display.")
    lines.append("    /// </summary>")
    lines.append("    [System.Serializable]")
    lines.append("    public class SaveSlot")
    lines.append("    {")
    lines.append("        public int slotIndex;")
    lines.append("        public string displayName;")
    lines.append("        public string timestamp;")
    lines.append("        public string previewData;")
    lines.append("        public bool isEmpty = true;")
    lines.append("    }")
    lines.append("")

    # GameSystemsSaveData class
    lines.append("    /// <summary>")
    lines.append("    /// Serializable save data container with version for migration.")
    lines.append("    /// </summary>")
    lines.append("    [System.Serializable]")
    lines.append("    public class GameSystemsSaveData")
    lines.append("    {")
    lines.append("        public int version = 1;")
    lines.append("        public string saveDate;")
    lines.append("        public float playtimeSeconds;")
    lines.append("        public int currency;")
    lines.append("        public int experiencePoints;")
    lines.append("        public string currentLocation;")
    lines.append("        public List<string> interactableStates = new List<string>();")
    lines.append("        public List<string> discoveredLocations = new List<string>();")
    lines.append("        public string customData;")
    lines.append("    }")
    lines.append("")

    # VB_SaveSystem class
    lines.append("    /// <summary>")
    lines.append("    /// Save system with JSON serialization, optional encryption/compression,")
    lines.append("    /// atomic writes, backup rotation, and data migration.")
    lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    lines.append("    /// </summary>")
    lines.append("    public class VB_SaveSystem : MonoBehaviour")
    lines.append("    {")
    lines.append("        private static VB_SaveSystem _instance;")
    lines.append("        public static VB_SaveSystem Instance => _instance;")
    lines.append("")
    lines.append("        [Header(\"Save Configuration\")]")
    lines.append("        public int slotCount = " + str(slot_count) + ";")
    if auto_save:
        lines.append("        public bool autoSaveEnabled = true;")
        lines.append("        public float autoSaveInterval = 300f;")
    lines.append("")
    lines.append("        private GameSystemsSaveData _currentData;")
    lines.append("        private int _activeSlot = -1;")
    lines.append("        private SaveSlot[] _slots;")
    if auto_save:
        lines.append("        private float _autoSaveTimer;")
    lines.append("")

    # Migration delegate
    lines.append("        /// <summary>")
    lines.append("        /// Migration delegate: takes save data and upgrades it one version.")
    lines.append("        /// </summary>")
    lines.append("        public delegate GameSystemsSaveData MigrationStep(GameSystemsSaveData data);")
    lines.append("        private readonly List<MigrationStep> _migrations = new List<MigrationStep>();")
    lines.append("")

    # Awake
    lines.append("        private void Awake()")
    lines.append("        {")
    lines.append("            if (_instance != null && _instance != this)")
    lines.append("            {")
    lines.append("                Destroy(gameObject);")
    lines.append("                return;")
    lines.append("            }")
    lines.append("            _instance = this;")
    lines.append("            DontDestroyOnLoad(gameObject);")
    total_slots = str(slot_count) + " + 1" if auto_save else str(slot_count)
    lines.append("            _slots = new SaveSlot[" + total_slots + "];")
    lines.append("            for (int i = 0; i < _slots.Length; i++)")
    lines.append("            {")
    lines.append("                _slots[i] = new SaveSlot { slotIndex = i };")
    lines.append("            }")
    lines.append("            RegisterMigrations();")
    lines.append("        }")
    lines.append("")

    # Update (auto-save)
    if auto_save:
        lines.append("        private void Update()")
        lines.append("        {")
        lines.append("            if (autoSaveEnabled && _currentData != null)")
        lines.append("            {")
        lines.append("                _autoSaveTimer += Time.unscaledDeltaTime;")
        lines.append("                if (_autoSaveTimer >= autoSaveInterval)")
        lines.append("                {")
        lines.append("                    _autoSaveTimer = 0f;")
        lines.append("                    Save(slotCount); // Auto-save uses last slot")
        lines.append("                    Debug.Log(\"[VB_SaveSystem] Auto-save completed.\");")
        lines.append("                }")
        lines.append("            }")
        lines.append("        }")
        lines.append("")

    # RegisterMigrations
    lines.append("        /// <summary>")
    lines.append("        /// Register version migration steps. Override to add custom migrations.")
    lines.append("        /// </summary>")
    lines.append("        protected virtual void RegisterMigrations()")
    lines.append("        {")
    lines.append("            // Example: _migrations.Add(MigrateV1ToV2);")
    lines.append("        }")
    lines.append("")

    # ApplyMigrations
    lines.append("        private GameSystemsSaveData ApplyMigrations(GameSystemsSaveData data)")
    lines.append("        {")
    lines.append("            int currentVersion = data.version;")
    lines.append("            while (currentVersion - 1 < _migrations.Count)")
    lines.append("            {")
    lines.append("                data = _migrations[currentVersion - 1](data);")
    lines.append("                currentVersion++;")
    lines.append("                data.version = currentVersion;")
    lines.append("            }")
    lines.append("            return data;")
    lines.append("        }")
    lines.append("")

    # Save method
    lines.append("        /// <summary>")
    lines.append("        /// Save current data to the specified slot.")
    lines.append("        /// Uses atomic write (temp file + rename) with backup rotation.")
    lines.append("        /// </summary>")
    lines.append("        public bool Save(int slot)")
    lines.append("        {")
    lines.append("            if (_currentData == null)")
    lines.append("            {")
    lines.append("                Debug.LogError(\"[VB_SaveSystem] No data to save.\");")
    lines.append("                return false;")
    lines.append("            }")
    lines.append("")
    lines.append("            try")
    lines.append("            {")
    lines.append("                _currentData.saveDate = DateTime.UtcNow.ToString(\"o\");")
    lines.append("                string json = JsonUtility.ToJson(_currentData, true);")
    lines.append("                byte[] data = Encoding.UTF8.GetBytes(json);")
    lines.append("")
    if use_compression:
        lines.append("                // GZip compression")
        lines.append("                data = Compress(data);")
        lines.append("")
    if use_encryption:
        lines.append("                // AES-CBC encryption")
        lines.append("                data = Encrypt(data);")
        lines.append("")
    lines.append("                string dir = GetSaveDirectory();")
    lines.append("                if (!Directory.Exists(dir))")
    lines.append("                    Directory.CreateDirectory(dir);")
    lines.append("")
    lines.append("                string filePath = GetSlotPath(slot);")
    lines.append("                string tempPath = filePath + \".tmp\";")
    lines.append("                string bakPath = filePath + \".bak\";")
    lines.append("")
    lines.append("                // Backup rotation: current -> .bak")
    lines.append("                if (File.Exists(filePath))")
    lines.append("                    File.Copy(filePath, bakPath, true);")
    lines.append("")
    lines.append("                // Atomic write: write temp, then rename")
    lines.append("                File.WriteAllBytes(tempPath, data);")
    lines.append("                if (File.Exists(filePath))")
    lines.append("                    File.Delete(filePath);")
    lines.append("                File.Move(tempPath, filePath);")
    lines.append("")
    lines.append("                // Update slot metadata")
    lines.append("                if (slot < _slots.Length)")
    lines.append("                {")
    lines.append("                    _slots[slot].isEmpty = false;")
    lines.append("                    _slots[slot].timestamp = _currentData.saveDate;")
    lines.append("                    _slots[slot].displayName = \"Slot \" + slot;")
    lines.append("                }")
    lines.append("")
    lines.append("                _activeSlot = slot;")
    lines.append("                Debug.Log(\"[VB_SaveSystem] Saved to slot \" + slot);")
    lines.append("                return true;")
    lines.append("            }")
    lines.append("            catch (Exception ex)")
    lines.append("            {")
    lines.append("                Debug.LogError(\"[VB_SaveSystem] Save failed: \" + ex.Message);")
    lines.append("                return false;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # Load method
    lines.append("        /// <summary>")
    lines.append("        /// Load data from the specified slot.")
    lines.append("        /// Applies migrations if version mismatch detected.")
    lines.append("        /// </summary>")
    lines.append("        public bool Load(int slot)")
    lines.append("        {")
    lines.append("            try")
    lines.append("            {")
    lines.append("                string filePath = GetSlotPath(slot);")
    lines.append("                if (!File.Exists(filePath))")
    lines.append("                {")
    lines.append("                    Debug.LogWarning(\"[VB_SaveSystem] No save file at slot \" + slot);")
    lines.append("                    return false;")
    lines.append("                }")
    lines.append("")
    lines.append("                byte[] data = File.ReadAllBytes(filePath);")
    lines.append("")
    if use_encryption:
        lines.append("                // AES-CBC decryption")
        lines.append("                data = Decrypt(data);")
        lines.append("")
    if use_compression:
        lines.append("                // GZip decompression")
        lines.append("                data = Decompress(data);")
        lines.append("")
    lines.append("                string json = Encoding.UTF8.GetString(data);")
    lines.append("                _currentData = JsonUtility.FromJson<GameSystemsSaveData>(json);")
    lines.append("")
    lines.append("                // Apply migrations if needed")
    lines.append("                if (_currentData.version < _migrations.Count + 1)")
    lines.append("                    _currentData = ApplyMigrations(_currentData);")
    lines.append("")
    lines.append("                _activeSlot = slot;")
    lines.append("                Debug.Log(\"[VB_SaveSystem] Loaded slot \" + slot);")
    lines.append("                return true;")
    lines.append("            }")
    lines.append("            catch (Exception ex)")
    lines.append("            {")
    lines.append("                Debug.LogError(\"[VB_SaveSystem] Load failed: \" + ex.Message);")
    lines.append("                return false;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # Delete method
    lines.append("        /// <summary>")
    lines.append("        /// Delete save data at the specified slot.")
    lines.append("        /// </summary>")
    lines.append("        public bool Delete(int slot)")
    lines.append("        {")
    lines.append("            try")
    lines.append("            {")
    lines.append("                string filePath = GetSlotPath(slot);")
    lines.append("                if (File.Exists(filePath))")
    lines.append("                    File.Delete(filePath);")
    lines.append("")
    lines.append("                string bakPath = filePath + \".bak\";")
    lines.append("                if (File.Exists(bakPath))")
    lines.append("                    File.Delete(bakPath);")
    lines.append("")
    lines.append("                if (slot < _slots.Length)")
    lines.append("                    _slots[slot].isEmpty = true;")
    lines.append("")
    lines.append("                if (_activeSlot == slot)")
    lines.append("                {")
    lines.append("                    _currentData = null;")
    lines.append("                    _activeSlot = -1;")
    lines.append("                }")
    lines.append("")
    lines.append("                Debug.Log(\"[VB_SaveSystem] Deleted slot \" + slot);")
    lines.append("                return true;")
    lines.append("            }")
    lines.append("            catch (Exception ex)")
    lines.append("            {")
    lines.append("                Debug.LogError(\"[VB_SaveSystem] Delete failed: \" + ex.Message);")
    lines.append("                return false;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # CreateNewSave
    lines.append("        /// <summary>")
    lines.append("        /// Create a new empty save data instance.")
    lines.append("        /// </summary>")
    lines.append("        public void CreateNewSave()")
    lines.append("        {")
    lines.append("            _currentData = new GameSystemsSaveData();")
    lines.append("            _currentData.saveDate = DateTime.UtcNow.ToString(\"o\");")
    lines.append("        }")
    lines.append("")

    # GetCurrentData
    lines.append("        /// <summary>")
    lines.append("        /// Returns the current save data, or null if none loaded.")
    lines.append("        /// </summary>")
    lines.append("        public GameSystemsSaveData GetCurrentData() => _currentData;")
    lines.append("")

    # GetSlot
    lines.append("        /// <summary>")
    lines.append("        /// Returns slot metadata for the given index.")
    lines.append("        /// </summary>")
    lines.append("        public SaveSlot GetSlot(int index)")
    lines.append("        {")
    lines.append("            if (index >= 0 && index < _slots.Length)")
    lines.append("                return _slots[index];")
    lines.append("            return null;")
    lines.append("        }")
    lines.append("")

    # Helper methods
    lines.append("        private string GetSaveDirectory()")
    lines.append("        {")
    lines.append("            return Path.Combine(Application.persistentDataPath, \"saves\");")
    lines.append("        }")
    lines.append("")
    lines.append("        private string GetSlotPath(int slot)")
    lines.append("        {")
    lines.append("            return Path.Combine(GetSaveDirectory(), \"slot_\" + slot + \".sav\");")
    lines.append("        }")
    lines.append("")

    # Encryption helpers
    if use_encryption:
        lines.append("        // ---------------------------------------------------------------")
        lines.append("        // AES-CBC Encryption (key derived from Application.identifier)")
        lines.append("        // ---------------------------------------------------------------")
        lines.append("")
        lines.append("        private byte[] GetEncryptionKey()")
        lines.append("        {")
        lines.append("            string seed = Application.identifier + \"_VB_SaveKey\";")
        lines.append("            using (var sha = System.Security.Cryptography.SHA256.Create())")
        lines.append("            {")
        lines.append("                return sha.ComputeHash(Encoding.UTF8.GetBytes(seed));")
        lines.append("            }")
        lines.append("        }")
        lines.append("")
        lines.append("        private byte[] Encrypt(byte[] plainData)")
        lines.append("        {")
        lines.append("            using (var aes = Aes.Create())")
        lines.append("            {")
        lines.append("                aes.Mode = CipherMode.CBC;")
        lines.append("                aes.Key = GetEncryptionKey();")
        lines.append("                aes.GenerateIV();")
        lines.append("")
        lines.append("                using (var encryptor = aes.CreateEncryptor())")
        lines.append("                {")
        lines.append("                    byte[] encrypted = encryptor.TransformFinalBlock(plainData, 0, plainData.Length);")
        lines.append("                    // Prepend IV to encrypted data")
        lines.append("                    byte[] result = new byte[aes.IV.Length + encrypted.Length];")
        lines.append("                    Array.Copy(aes.IV, 0, result, 0, aes.IV.Length);")
        lines.append("                    Array.Copy(encrypted, 0, result, aes.IV.Length, encrypted.Length);")
        lines.append("                    return result;")
        lines.append("                }")
        lines.append("            }")
        lines.append("        }")
        lines.append("")
        lines.append("        private byte[] Decrypt(byte[] encryptedData)")
        lines.append("        {")
        lines.append("            using (var aes = Aes.Create())")
        lines.append("            {")
        lines.append("                aes.Mode = CipherMode.CBC;")
        lines.append("                aes.Key = GetEncryptionKey();")
        lines.append("")
        lines.append("                // Extract IV from first 16 bytes")
        lines.append("                byte[] iv = new byte[16];")
        lines.append("                Array.Copy(encryptedData, 0, iv, 0, 16);")
        lines.append("                aes.IV = iv;")
        lines.append("")
        lines.append("                byte[] cipherText = new byte[encryptedData.Length - 16];")
        lines.append("                Array.Copy(encryptedData, 16, cipherText, 0, cipherText.Length);")
        lines.append("")
        lines.append("                using (var decryptor = aes.CreateDecryptor())")
        lines.append("                {")
        lines.append("                    return decryptor.TransformFinalBlock(cipherText, 0, cipherText.Length);")
        lines.append("                }")
        lines.append("            }")
        lines.append("        }")
        lines.append("")

    # Compression helpers
    if use_compression:
        lines.append("        // ---------------------------------------------------------------")
        lines.append("        // GZip Compression")
        lines.append("        // ---------------------------------------------------------------")
        lines.append("")
        lines.append("        private byte[] Compress(byte[] data)")
        lines.append("        {")
        lines.append("            using (var output = new MemoryStream())")
        lines.append("            {")
        lines.append("                using (var gzip = new GZipStream(output, CompressionMode.Compress))")
        lines.append("                {")
        lines.append("                    gzip.Write(data, 0, data.Length);")
        lines.append("                }")
        lines.append("                return output.ToArray();")
        lines.append("            }")
        lines.append("        }")
        lines.append("")
        lines.append("        private byte[] Decompress(byte[] data)")
        lines.append("        {")
        lines.append("            using (var input = new MemoryStream(data))")
        lines.append("            using (var gzip = new GZipStream(input, CompressionMode.Decompress))")
        lines.append("            using (var output = new MemoryStream())")
        lines.append("            {")
        lines.append("                gzip.CopyTo(output);")
        lines.append("                return output.ToArray();")
        lines.append("            }")
        lines.append("        }")
        lines.append("")

    lines.append("    }")  # end VB_SaveSystem
    lines.append("}")  # end namespace

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GAME-05: Health system (HP + DamageCalculator integration)
# ---------------------------------------------------------------------------


def generate_health_system_script(
    max_hp: int = 100,
    use_damage_numbers: bool = True,
    use_respawn: bool = True,
    respawn_delay: float = 3.0,
    namespace: str = "VeilBreakers.GameSystems",
) -> str:
    """Generate C# runtime MonoBehaviour for a health/damage component.

    Produces VB_HealthComponent with HP tracking, DamageCalculator integration,
    death handling, optional floating damage numbers, optional respawn, and
    invincibility frames.

    Args:
        max_hp: Default maximum hit points.
        use_damage_numbers: Whether to include floating damage number support.
        use_respawn: Whether to include respawn logic.
        respawn_delay: Delay in seconds before respawn.
        namespace: C# namespace for generated code.

    Returns:
        Complete C# source string.
    """
    lines = []

    lines.append("using System;")
    lines.append("using System.Collections;")
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.Events;")
    if use_damage_numbers:
        lines.append("using TMPro;")
    lines.append("")
    lines.append("namespace " + _safe_namespace(namespace))
    lines.append("{")

    lines.append("    /// <summary>")
    lines.append("    /// Health component compatible with VeilBreakers Combatant + DamageCalculator.")
    lines.append("    /// Supports damage, healing, death, invincibility frames, and events.")
    lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    lines.append("    /// </summary>")
    lines.append("    public class VB_HealthComponent : MonoBehaviour")
    lines.append("    {")
    lines.append("        [Header(\"Health\")]")
    lines.append("        [SerializeField] private float _maxHP = " + str(max_hp) + "f;")
    lines.append("        [SerializeField] private float _currentHP;")
    lines.append("")
    lines.append("        [Header(\"Invincibility\")]")
    lines.append("        [SerializeField] private float _iFrameDuration = 0.5f;")
    lines.append("        private float _iFrameTimer;")
    lines.append("        private bool _isInvincible;")
    lines.append("")

    if use_respawn:
        lines.append("        [Header(\"Respawn\")]")
        lines.append("        [SerializeField] private bool _respawnEnabled = true;")
        lines.append("        [SerializeField] private float _respawnDelay = " + str(respawn_delay) + "f;")
        lines.append("        private Vector3 _respawnPosition;")
        lines.append("")

    if use_damage_numbers:
        lines.append("        [Header(\"Damage Numbers\")]")
        lines.append("        [SerializeField] private GameObject _damageNumberPrefab;")
        lines.append("        [SerializeField] private float _damageNumberOffset = 2f;")
        lines.append("")

    lines.append("        [Header(\"Events\")]")
    lines.append("        public UnityEvent OnDeath;")
    lines.append("        public UnityEvent OnRespawn;")
    lines.append("        public UnityEvent<float, float> OnHealthChanged;")
    lines.append("")
    lines.append("        /// <summary>Current hit points.</summary>")
    lines.append("        public float CurrentHP => _currentHP;")
    lines.append("        /// <summary>Maximum hit points.</summary>")
    lines.append("        public float MaxHP => _maxHP;")
    lines.append("        /// <summary>Whether entity is alive.</summary>")
    lines.append("        public bool IsAlive => _currentHP > 0f;")
    lines.append("        /// <summary>Health as 0-1 fraction.</summary>")
    lines.append("        public float HealthPercent => _maxHP > 0f ? _currentHP / _maxHP : 0f;")
    lines.append("")

    # Awake
    lines.append("        private void Awake()")
    lines.append("        {")
    lines.append("            _currentHP = _maxHP;")
    if use_respawn:
        lines.append("            _respawnPosition = transform.position;")
    lines.append("        }")
    lines.append("")

    # Update (iframes)
    lines.append("        private void Update()")
    lines.append("        {")
    lines.append("            if (_isInvincible)")
    lines.append("            {")
    lines.append("                _iFrameTimer -= Time.deltaTime;")
    lines.append("                if (_iFrameTimer <= 0f)")
    lines.append("                    _isInvincible = false;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # TakeDamage (raw)
    lines.append("        /// <summary>")
    lines.append("        /// Apply raw damage amount. Respects invincibility frames.")
    lines.append("        /// </summary>")
    lines.append("        public void TakeDamage(float amount)")
    lines.append("        {")
    lines.append("            if (!IsAlive || _isInvincible) return;")
    lines.append("")
    lines.append("            amount = ApplyShieldReduction(amount);")
    lines.append("            _currentHP = Mathf.Max(0f, _currentHP - amount);")
    lines.append("            OnHealthChanged?.Invoke(_currentHP, _maxHP);")
    lines.append("")
    if use_damage_numbers:
        lines.append("            SpawnDamageNumber(amount, false);")
        lines.append("")
    lines.append("            // Activate invincibility frames")
    lines.append("            _isInvincible = true;")
    lines.append("            _iFrameTimer = _iFrameDuration;")
    lines.append("")
    lines.append("            if (_currentHP <= 0f)")
    lines.append("                Die();")
    lines.append("        }")
    lines.append("")

    # TakeDamage (DamageResult overload)
    lines.append("        /// <summary>")
    lines.append("        /// Apply damage from DamageCalculator.Calculate() result.")
    lines.append("        /// Compatible with VeilBreakers.Combat.DamageResult.")
    lines.append("        /// </summary>")
    lines.append("        public void TakeDamageFromResult(int finalDamage, bool isCritical)")
    lines.append("        {")
    lines.append("            if (!IsAlive || _isInvincible) return;")
    lines.append("")
    lines.append("            float amount = ApplyShieldReduction(finalDamage);")
    lines.append("            _currentHP = Mathf.Max(0f, _currentHP - amount);")
    lines.append("            OnHealthChanged?.Invoke(_currentHP, _maxHP);")
    lines.append("")
    if use_damage_numbers:
        lines.append("            SpawnDamageNumber(amount, isCritical);")
        lines.append("")
    lines.append("            _isInvincible = true;")
    lines.append("            _iFrameTimer = _iFrameDuration;")
    lines.append("")
    lines.append("            if (_currentHP <= 0f)")
    lines.append("                Die();")
    lines.append("        }")
    lines.append("")

    # Heal
    lines.append("        /// <summary>")
    lines.append("        /// Heal by the given amount, clamped to max HP.")
    lines.append("        /// </summary>")
    lines.append("        public void Heal(float amount)")
    lines.append("        {")
    lines.append("            if (!IsAlive) return;")
    lines.append("")
    lines.append("            _currentHP = Mathf.Min(_maxHP, _currentHP + amount);")
    lines.append("            OnHealthChanged?.Invoke(_currentHP, _maxHP);")
    lines.append("        }")
    lines.append("")

    # Shield reduction hook
    lines.append("        /// <summary>")
    lines.append("        /// Virtual method for shield/armor damage reduction. Override to customize.")
    lines.append("        /// </summary>")
    lines.append("        protected virtual float ApplyShieldReduction(float rawDamage)")
    lines.append("        {")
    lines.append("            return rawDamage;")
    lines.append("        }")
    lines.append("")

    # Die
    lines.append("        /// <summary>")
    lines.append("        /// Handle entity death.")
    lines.append("        /// </summary>")
    lines.append("        private void Die()")
    lines.append("        {")
    lines.append("            _currentHP = 0f;")
    lines.append("            OnDeath?.Invoke();")
    lines.append("            Debug.Log(\"[VB_HealthComponent] \" + gameObject.name + \" died.\");")
    lines.append("")
    if use_respawn:
        lines.append("            if (_respawnEnabled)")
        lines.append("                StartCoroutine(RespawnCoroutine());")
    lines.append("        }")
    lines.append("")

    # Respawn
    if use_respawn:
        lines.append("        private IEnumerator RespawnCoroutine()")
        lines.append("        {")
        lines.append("            yield return new WaitForSeconds(_respawnDelay);")
        lines.append("            Respawn();")
        lines.append("        }")
        lines.append("")
        lines.append("        /// <summary>")
        lines.append("        /// Respawn the entity at its original position with full HP.")
        lines.append("        /// </summary>")
        lines.append("        public void Respawn()")
        lines.append("        {")
        lines.append("            _currentHP = _maxHP;")
        lines.append("            transform.position = _respawnPosition;")
        lines.append("            _isInvincible = false;")
        lines.append("            OnRespawn?.Invoke();")
        lines.append("            OnHealthChanged?.Invoke(_currentHP, _maxHP);")
        lines.append("            Debug.Log(\"[VB_HealthComponent] \" + gameObject.name + \" respawned.\");")
        lines.append("        }")
        lines.append("")

    # Damage numbers
    if use_damage_numbers:
        lines.append("        private void SpawnDamageNumber(float amount, bool isCritical)")
        lines.append("        {")
        lines.append("            if (_damageNumberPrefab == null) return;")
        lines.append("")
        lines.append("            Vector3 spawnPos = transform.position + Vector3.up * _damageNumberOffset;")
        lines.append("            GameObject go = Instantiate(_damageNumberPrefab, spawnPos, Quaternion.identity);")
        lines.append("            TextMeshPro tmp = go.GetComponent<TextMeshPro>();")
        lines.append("            if (tmp != null)")
        lines.append("            {")
        lines.append("                tmp.text = Mathf.RoundToInt(amount).ToString();")
        lines.append("                tmp.color = isCritical ? Color.yellow : Color.white;")
        lines.append("                tmp.fontSize = isCritical ? 8f : 6f;")
        lines.append("            }")
        lines.append("            Destroy(go, 1.5f);")
        lines.append("        }")
        lines.append("")

    # SetMaxHP
    lines.append("        /// <summary>")
    lines.append("        /// Set max HP and optionally heal to full.")
    lines.append("        /// </summary>")
    lines.append("        public void SetMaxHP(float newMax, bool healToFull = false)")
    lines.append("        {")
    lines.append("            _maxHP = newMax;")
    lines.append("            if (healToFull)")
    lines.append("                _currentHP = _maxHP;")
    lines.append("            else")
    lines.append("                _currentHP = Mathf.Min(_currentHP, _maxHP);")
    lines.append("            OnHealthChanged?.Invoke(_currentHP, _maxHP);")
    lines.append("        }")

    lines.append("    }")  # end VB_HealthComponent
    lines.append("}")  # end namespace

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GAME-06: Character controller (third-person + Cinemachine 3.x)
# ---------------------------------------------------------------------------


def generate_character_controller_script(
    mode: str = "third_person",
    move_speed: float = 5.0,
    sprint_multiplier: float = 1.5,
    jump_height: float = 1.5,
    gravity: float = -20.0,
    rotation_speed: float = 10.0,
    namespace: str = "VeilBreakers.GameSystems",
) -> str:
    """Generate C# runtime MonoBehaviour for a character controller.

    Produces VB_CharacterController with CharacterController-based movement,
    camera-relative direction, jump, sprint, slope handling, and a
    VB_CameraSetup utility for Cinemachine 3.x (CinemachineCamera +
    CinemachineOrbitalFollow).

    Args:
        mode: Movement mode ('third_person' or 'first_person').
        move_speed: Base movement speed.
        sprint_multiplier: Speed multiplier when sprinting.
        jump_height: Jump height in units.
        gravity: Gravity acceleration.
        rotation_speed: Character rotation speed.
        namespace: C# namespace for generated code.

    Returns:
        Complete C# source string.
    """
    safe_mode = sanitize_cs_identifier(mode)
    lines = []

    lines.append("using UnityEngine;")
    lines.append("using Unity.Cinemachine;")
    lines.append("")
    lines.append("namespace " + _safe_namespace(namespace))
    lines.append("{")

    # VB_CharacterController
    lines.append("    /// <summary>")
    if mode == "third_person":
        lines.append("    /// Third-person character controller with camera-relative movement.")
    else:
        lines.append("    /// First-person character controller with camera-relative movement.")
    lines.append("    /// Uses CharacterController.Move() for physics-free movement.")
    lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    lines.append("    /// </summary>")
    lines.append("    [RequireComponent(typeof(CharacterController))]")
    lines.append("    public class VB_CharacterController : MonoBehaviour")
    lines.append("    {")
    lines.append("        [Header(\"Movement\")]")
    lines.append("        [SerializeField] private float _moveSpeed = " + str(move_speed) + "f;")
    lines.append("        [SerializeField] private float _sprintMultiplier = " + str(sprint_multiplier) + "f;")
    lines.append("        [SerializeField] private float _rotationSpeed = " + str(rotation_speed) + "f;")
    lines.append("")
    lines.append("        [Header(\"Jump & Gravity\")]")
    lines.append("        [SerializeField] private float _jumpHeight = " + str(jump_height) + "f;")
    lines.append("        [SerializeField] private float _gravity = " + str(gravity) + "f;")
    lines.append("")
    lines.append("        [Header(\"Ground Check\")]")
    lines.append("        [SerializeField] private float _groundCheckDistance = 0.2f;")
    lines.append("        [SerializeField] private LayerMask _groundLayer = ~0;")
    lines.append("")
    lines.append("        [Header(\"Slope\")]")
    lines.append("        [SerializeField] private float _maxSlopeAngle = 45f;")
    lines.append("        [SerializeField] private float _slideSpeed = 5f;")
    lines.append("")
    lines.append("        [Header(\"Camera\")]")
    lines.append("        [SerializeField] private Transform _cameraTransform;")
    lines.append("")
    lines.append("        private CharacterController _controller;")
    lines.append("        private Vector3 _velocity;")
    lines.append("        private bool _isGrounded;")
    lines.append("        private bool _isSprinting;")
    lines.append("")
    lines.append("        /// <summary>Whether the character is currently grounded.</summary>")
    lines.append("        public bool IsGrounded => _isGrounded;")
    lines.append("        /// <summary>Whether the character is sprinting.</summary>")
    lines.append("        public bool IsSprinting => _isSprinting;")
    lines.append("")

    # Awake
    lines.append("        private void Awake()")
    lines.append("        {")
    lines.append("            _controller = GetComponent<CharacterController>();")
    lines.append("            if (_cameraTransform == null && Camera.main != null)")
    lines.append("                _cameraTransform = Camera.main.transform;")
    lines.append("        }")
    lines.append("")

    # Update
    lines.append("        private void Update()")
    lines.append("        {")
    lines.append("            GroundCheck();")
    lines.append("            HandleMovement();")
    lines.append("            HandleJump();")
    lines.append("            ApplyGravity();")
    lines.append("            HandleSlopeSliding();")
    lines.append("")
    lines.append("            _controller.Move(_velocity * Time.deltaTime);")
    lines.append("        }")
    lines.append("")

    # GroundCheck
    lines.append("        private void GroundCheck()")
    lines.append("        {")
    lines.append("            _isGrounded = _controller.isGrounded;")
    lines.append("            if (_isGrounded && _velocity.y < 0f)")
    lines.append("                _velocity.y = -2f;")
    lines.append("        }")
    lines.append("")

    # HandleMovement
    lines.append("        private void HandleMovement()")
    lines.append("        {")
    lines.append("            Vector2 input = GetMovementInput();")
    lines.append("            if (input.sqrMagnitude < 0.01f) return;")
    lines.append("")
    lines.append("            // Camera-relative direction")
    lines.append("            Vector3 forward = _cameraTransform != null ? _cameraTransform.forward : transform.forward;")
    lines.append("            Vector3 right = _cameraTransform != null ? _cameraTransform.right : transform.right;")
    lines.append("            forward.y = 0f;")
    lines.append("            right.y = 0f;")
    lines.append("            forward.Normalize();")
    lines.append("            right.Normalize();")
    lines.append("")
    lines.append("            Vector3 moveDir = forward * input.y + right * input.x;")
    lines.append("            moveDir.Normalize();")
    lines.append("")
    lines.append("            float speed = _moveSpeed * (_isSprinting ? _sprintMultiplier : 1f);")
    lines.append("            _velocity = new Vector3(moveDir.x * speed, _velocity.y, moveDir.z * speed);")
    lines.append("")
    if mode == "third_person":
        lines.append("            // Rotate character to face movement direction (third-person)")
        lines.append("            if (moveDir.sqrMagnitude > 0.01f)")
        lines.append("            {")
        lines.append("                Quaternion targetRotation = Quaternion.LookRotation(moveDir);")
        lines.append("                transform.rotation = Quaternion.Slerp(")
        lines.append("                    transform.rotation, targetRotation, _rotationSpeed * Time.deltaTime);")
        lines.append("            }")
    else:
        lines.append("            // First-person: no character rotation from movement input")
    lines.append("        }")
    lines.append("")

    # HandleJump
    lines.append("        private void HandleJump()")
    lines.append("        {")
    lines.append("            if (_isGrounded && GetJumpInput())")
    lines.append("            {")
    lines.append("                // v = sqrt(-2 * gravity * jumpHeight)")
    lines.append("                _velocity.y = Mathf.Sqrt(_jumpHeight * -2f * _gravity);")
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # ApplyGravity
    lines.append("        private void ApplyGravity()")
    lines.append("        {")
    lines.append("            _velocity.y += _gravity * Time.deltaTime;")
    lines.append("        }")
    lines.append("")

    # HandleSlopeSliding
    lines.append("        private void HandleSlopeSliding()")
    lines.append("        {")
    lines.append("            if (!_isGrounded) return;")
    lines.append("")
    lines.append("            if (Physics.Raycast(transform.position, Vector3.down, out RaycastHit hit,")
    lines.append("                _controller.height * 0.5f + _groundCheckDistance, _groundLayer))")
    lines.append("            {")
    lines.append("                float slopeAngle = Vector3.Angle(hit.normal, Vector3.up);")
    lines.append("                if (slopeAngle > _maxSlopeAngle)")
    lines.append("                {")
    lines.append("                    Vector3 slideDir = Vector3.ProjectOnPlane(Vector3.down, hit.normal).normalized;")
    lines.append("                    _velocity = new Vector3(slideDir.x * _slideSpeed, _velocity.y, slideDir.z * _slideSpeed);")
    lines.append("                }")
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # Virtual input methods
    lines.append("        /// <summary>")
    lines.append("        /// Override to provide movement input from InputManager.")
    lines.append("        /// Returns Vector2 (x=horizontal, y=forward).")
    lines.append("        /// </summary>")
    lines.append("        protected virtual Vector2 GetMovementInput()")
    lines.append("        {")
    lines.append("            return new Vector2(Input.GetAxis(\"Horizontal\"), Input.GetAxis(\"Vertical\"));")
    lines.append("        }")
    lines.append("")
    lines.append("        /// <summary>")
    lines.append("        /// Override to provide jump input from InputManager.")
    lines.append("        /// </summary>")
    lines.append("        protected virtual bool GetJumpInput()")
    lines.append("        {")
    lines.append("            return Input.GetButtonDown(\"Jump\");")
    lines.append("        }")
    lines.append("")
    lines.append("        /// <summary>")
    lines.append("        /// Set sprint state externally (e.g. from input handler).")
    lines.append("        /// </summary>")
    lines.append("        public void SetSprinting(bool sprinting)")
    lines.append("        {")
    lines.append("            _isSprinting = sprinting;")
    lines.append("        }")

    lines.append("    }")  # end VB_CharacterController
    lines.append("")

    # VB_CameraSetup utility
    lines.append("    /// <summary>")
    lines.append("    /// Static utility to set up Cinemachine 3.x camera for the character controller.")
    lines.append("    /// Uses CinemachineCamera + CinemachineOrbitalFollow + CinemachineRotationComposer.")
    lines.append("    /// </summary>")
    lines.append("    public static class VB_CameraSetup")
    lines.append("    {")
    lines.append("        /// <summary>")
    lines.append("        /// Create and configure a Cinemachine 3.x orbital camera targeting the player.")
    lines.append("        /// </summary>")
    lines.append("        public static CinemachineCamera CreateOrbitalCamera(Transform followTarget, Transform lookAtTarget)")
    lines.append("        {")
    lines.append("            GameObject camGo = new GameObject(\"VB_CinemachineCamera\");")
    lines.append("")
    lines.append("            // CinemachineCamera component (Cinemachine 3.x)")
    lines.append("            CinemachineCamera cm = camGo.AddComponent<CinemachineCamera>();")
    lines.append("            cm.Follow = followTarget;")
    lines.append("            cm.LookAt = lookAtTarget;")
    lines.append("")
    lines.append("            // CinemachineOrbitalFollow for third-person orbit (Cinemachine 3.x API)")
    lines.append("            CinemachineOrbitalFollow orbital = camGo.AddComponent<CinemachineOrbitalFollow>();")
    lines.append("            orbital.Radius = 5f;")
    lines.append("")
    lines.append("            // CinemachineRotationComposer for look-at tracking")
    lines.append("            CinemachineRotationComposer composer = camGo.AddComponent<CinemachineRotationComposer>();")
    lines.append("            composer.Damping = new Vector3(1f, 0.5f, 0f);")
    lines.append("")
    lines.append("            return cm;")
    lines.append("        }")
    lines.append("    }")

    lines.append("}")  # end namespace

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GAME-07: Input config (.inputactions JSON + C# wrapper)
# ---------------------------------------------------------------------------


def generate_input_config_script(
    action_maps: list[dict] | None = None,
    include_gamepad: bool = True,
    include_rebinding: bool = True,
    namespace: str = "VeilBreakers.GameSystems",
) -> tuple[str, str]:
    """Generate .inputactions JSON and C# wrapper for Unity Input System.

    Produces a tuple of (input_actions_json, input_config_cs) with Gameplay,
    UI, and Menu action maps, WASD+Gamepad bindings, control schemes, and
    optional runtime rebinding persistence.

    Args:
        action_maps: Optional custom action map definitions.
        include_gamepad: Whether to include gamepad bindings.
        include_rebinding: Whether to include runtime rebinding support.
        namespace: C# namespace for generated code.

    Returns:
        Tuple of (input_actions_json: str, input_config_cs: str).
    """
    import json as json_mod

    # action_maps is accepted for API compatibility; built-in maps are always generated
    _ = action_maps

    # ---------------------------------------------------------------
    # Build .inputactions JSON
    # ---------------------------------------------------------------
    def _guid() -> str:
        return str(uuid.uuid4())

    # Gameplay actions
    gameplay_actions = []
    gameplay_bindings = []

    # Helper to add a simple button action with KB + optional gamepad
    def add_button_action(name: str, kb_path: str, gp_path: str = ""):
        action_id = _guid()
        gameplay_actions.append({
            "name": name,
            "type": "Button",
            "id": action_id,
            "expectedControlType": "Button",
            "processors": "",
            "interactions": "",
            "initialStateCheck": False,
        })
        gameplay_bindings.append({
            "name": "",
            "id": _guid(),
            "path": kb_path,
            "interactions": "",
            "processors": "",
            "groups": "Keyboard",
            "action": name,
            "isComposite": False,
            "isPartOfComposite": False,
        })
        if include_gamepad and gp_path:
            gameplay_bindings.append({
                "name": "",
                "id": _guid(),
                "path": gp_path,
                "interactions": "",
                "processors": "",
                "groups": "Gamepad",
                "action": name,
                "isComposite": False,
                "isPartOfComposite": False,
            })
        return action_id

    # Move (Vector2 with WASD composite + Left Stick)
    move_action_id = _guid()
    gameplay_actions.append({
        "name": "Move",
        "type": "Value",
        "id": move_action_id,
        "expectedControlType": "Vector2",
        "processors": "",
        "interactions": "",
        "initialStateCheck": True,
    })
    # WASD composite
    wasd_composite_id = _guid()
    gameplay_bindings.append({
        "name": "WASD",
        "id": wasd_composite_id,
        "path": "2DVector",
        "interactions": "",
        "processors": "",
        "groups": "",
        "action": "Move",
        "isComposite": True,
        "isPartOfComposite": False,
    })
    for part_name, part_path in [("up", "<Keyboard>/w"), ("down", "<Keyboard>/s"),
                                  ("left", "<Keyboard>/a"), ("right", "<Keyboard>/d")]:
        gameplay_bindings.append({
            "name": part_name,
            "id": _guid(),
            "path": part_path,
            "interactions": "",
            "processors": "",
            "groups": "Keyboard",
            "action": "Move",
            "isComposite": False,
            "isPartOfComposite": True,
        })
    if include_gamepad:
        gameplay_bindings.append({
            "name": "",
            "id": _guid(),
            "path": "<Gamepad>/leftStick",
            "interactions": "",
            "processors": "",
            "groups": "Gamepad",
            "action": "Move",
            "isComposite": False,
            "isPartOfComposite": False,
        })

    # Look (Vector2 with Mouse Delta + Right Stick)
    look_action_id = _guid()
    gameplay_actions.append({
        "name": "Look",
        "type": "Value",
        "id": look_action_id,
        "expectedControlType": "Vector2",
        "processors": "",
        "interactions": "",
        "initialStateCheck": True,
    })
    gameplay_bindings.append({
        "name": "",
        "id": _guid(),
        "path": "<Mouse>/delta",
        "interactions": "",
        "processors": "",
        "groups": "Keyboard",
        "action": "Look",
        "isComposite": False,
        "isPartOfComposite": False,
    })
    if include_gamepad:
        gameplay_bindings.append({
            "name": "",
            "id": _guid(),
            "path": "<Gamepad>/rightStick",
            "interactions": "",
            "processors": "",
            "groups": "Gamepad",
            "action": "Look",
            "isComposite": False,
            "isPartOfComposite": False,
        })

    # Button actions
    add_button_action("LightAttack", "<Mouse>/leftButton", "<Gamepad>/buttonWest")
    add_button_action("HeavyAttack", "<Mouse>/rightButton", "<Gamepad>/buttonEast")
    add_button_action("Dodge", "<Keyboard>/space", "<Gamepad>/buttonSouth")
    add_button_action("Block", "<Keyboard>/leftShift", "<Gamepad>/leftTrigger")
    add_button_action("Interact", "<Keyboard>/e", "<Gamepad>/buttonNorth")
    add_button_action("Sprint", "<Keyboard>/leftCtrl", "<Gamepad>/leftStickPress")
    add_button_action("Jump", "<Keyboard>/space", "<Gamepad>/buttonSouth")
    add_button_action("UseAbility", "<Keyboard>/q", "<Gamepad>/rightShoulder")
    add_button_action("Pause", "<Keyboard>/escape", "<Gamepad>/start")

    # UI actions
    ui_actions = []
    ui_bindings = []

    ui_navigate_id = _guid()
    ui_actions.append({
        "name": "Navigate",
        "type": "Value",
        "id": ui_navigate_id,
        "expectedControlType": "Vector2",
        "processors": "",
        "interactions": "",
        "initialStateCheck": False,
    })

    ui_submit_id = _guid()
    ui_actions.append({
        "name": "Submit",
        "type": "Button",
        "id": ui_submit_id,
        "expectedControlType": "Button",
        "processors": "",
        "interactions": "",
        "initialStateCheck": False,
    })
    ui_bindings.append({
        "name": "",
        "id": _guid(),
        "path": "<Keyboard>/enter",
        "interactions": "",
        "processors": "",
        "groups": "Keyboard",
        "action": "Submit",
        "isComposite": False,
        "isPartOfComposite": False,
    })

    ui_cancel_id = _guid()
    ui_actions.append({
        "name": "Cancel",
        "type": "Button",
        "id": ui_cancel_id,
        "expectedControlType": "Button",
        "processors": "",
        "interactions": "",
        "initialStateCheck": False,
    })
    ui_bindings.append({
        "name": "",
        "id": _guid(),
        "path": "<Keyboard>/escape",
        "interactions": "",
        "processors": "",
        "groups": "Keyboard",
        "action": "Cancel",
        "isComposite": False,
        "isPartOfComposite": False,
    })

    ui_point_id = _guid()
    ui_actions.append({
        "name": "Point",
        "type": "PassThrough",
        "id": ui_point_id,
        "expectedControlType": "Vector2",
        "processors": "",
        "interactions": "",
        "initialStateCheck": True,
    })
    ui_bindings.append({
        "name": "",
        "id": _guid(),
        "path": "<Mouse>/position",
        "interactions": "",
        "processors": "",
        "groups": "Keyboard",
        "action": "Point",
        "isComposite": False,
        "isPartOfComposite": False,
    })

    ui_click_id = _guid()
    ui_actions.append({
        "name": "Click",
        "type": "Button",
        "id": ui_click_id,
        "expectedControlType": "Button",
        "processors": "",
        "interactions": "",
        "initialStateCheck": False,
    })
    ui_bindings.append({
        "name": "",
        "id": _guid(),
        "path": "<Mouse>/leftButton",
        "interactions": "",
        "processors": "",
        "groups": "Keyboard",
        "action": "Click",
        "isComposite": False,
        "isPartOfComposite": False,
    })

    # Menu actions
    menu_actions = []
    menu_bindings = []

    menu_pause_id = _guid()
    menu_actions.append({
        "name": "Pause",
        "type": "Button",
        "id": menu_pause_id,
        "expectedControlType": "Button",
        "processors": "",
        "interactions": "",
        "initialStateCheck": False,
    })
    menu_bindings.append({
        "name": "",
        "id": _guid(),
        "path": "<Keyboard>/escape",
        "interactions": "",
        "processors": "",
        "groups": "Keyboard",
        "action": "Pause",
        "isComposite": False,
        "isPartOfComposite": False,
    })
    if include_gamepad:
        menu_bindings.append({
            "name": "",
            "id": _guid(),
            "path": "<Gamepad>/start",
            "interactions": "",
            "processors": "",
            "groups": "Gamepad",
            "action": "Pause",
            "isComposite": False,
            "isPartOfComposite": False,
        })

    # Control schemes
    control_schemes = [
        {
            "name": "Keyboard",
            "bindingGroup": "Keyboard",
            "devices": [
                {"devicePath": "<Keyboard>", "isOptional": False, "isOR": False},
                {"devicePath": "<Mouse>", "isOptional": False, "isOR": False},
            ],
        },
    ]
    if include_gamepad:
        control_schemes.append({
            "name": "Gamepad",
            "bindingGroup": "Gamepad",
            "devices": [
                {"devicePath": "<Gamepad>", "isOptional": False, "isOR": False},
            ],
        })

    input_asset = {
        "name": "VB_InputActions",
        "maps": [
            {
                "name": "Gameplay",
                "id": _guid(),
                "actions": gameplay_actions,
                "bindings": gameplay_bindings,
            },
            {
                "name": "UI",
                "id": _guid(),
                "actions": ui_actions,
                "bindings": ui_bindings,
            },
            {
                "name": "Menu",
                "id": _guid(),
                "actions": menu_actions,
                "bindings": menu_bindings,
            },
        ],
        "controlSchemes": control_schemes,
    }

    input_json = json_mod.dumps(input_asset, indent=4)

    # ---------------------------------------------------------------
    # Build C# VB_InputConfig wrapper
    # ---------------------------------------------------------------
    cs_lines = []
    cs_lines.append("using System;")
    cs_lines.append("using UnityEngine;")
    cs_lines.append("using UnityEngine.InputSystem;")
    cs_lines.append("")
    cs_lines.append("namespace " + _safe_namespace(namespace))
    cs_lines.append("{")
    cs_lines.append("    /// <summary>")
    cs_lines.append("    /// Input configuration wrapper for Unity Input System.")
    cs_lines.append("    /// Manages action maps, event callbacks, and runtime rebinding.")
    cs_lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    cs_lines.append("    /// </summary>")
    cs_lines.append("    public class VB_InputConfig : MonoBehaviour")
    cs_lines.append("    {")
    cs_lines.append("        [Header(\"Input Asset\")]")
    cs_lines.append("        [SerializeField] private InputActionAsset _inputActions;")
    cs_lines.append("")
    cs_lines.append("        private InputActionMap _gameplayMap;")
    cs_lines.append("        private InputActionMap _uiMap;")
    cs_lines.append("        private InputActionMap _menuMap;")
    cs_lines.append("")

    # Events
    cs_lines.append("        // Action events")
    cs_lines.append("        public event Action<Vector2> OnMove;")
    cs_lines.append("        public event Action<Vector2> OnLook;")
    cs_lines.append("        public event Action OnLightAttack;")
    cs_lines.append("        public event Action OnHeavyAttack;")
    cs_lines.append("        public event Action OnDodge;")
    cs_lines.append("        public event Action OnBlock;")
    cs_lines.append("        public event Action OnInteract;")
    cs_lines.append("        public event Action OnSprint;")
    cs_lines.append("        public event Action OnJump;")
    cs_lines.append("        public event Action OnUseAbility;")
    cs_lines.append("        public event Action OnPause;")
    cs_lines.append("")

    # Constants for rebinding
    if include_rebinding:
        cs_lines.append("        private const string REBIND_KEY = \"VB_InputBindings\";")
        cs_lines.append("")

    # Awake
    cs_lines.append("        private void Awake()")
    cs_lines.append("        {")
    cs_lines.append("            if (_inputActions == null)")
    cs_lines.append("            {")
    cs_lines.append("                Debug.LogError(\"[VB_InputConfig] InputActionAsset not assigned.\");")
    cs_lines.append("                return;")
    cs_lines.append("            }")
    cs_lines.append("")
    cs_lines.append("            _gameplayMap = _inputActions.FindActionMap(\"Gameplay\");")
    cs_lines.append("            _uiMap = _inputActions.FindActionMap(\"UI\");")
    cs_lines.append("            _menuMap = _inputActions.FindActionMap(\"Menu\");")
    cs_lines.append("")
    if include_rebinding:
        cs_lines.append("            LoadBindingOverrides();")
    cs_lines.append("            RegisterCallbacks();")
    cs_lines.append("        }")
    cs_lines.append("")

    # OnEnable / OnDisable
    cs_lines.append("        private void OnEnable()")
    cs_lines.append("        {")
    cs_lines.append("            _inputActions?.Enable();")
    cs_lines.append("        }")
    cs_lines.append("")
    cs_lines.append("        private void OnDisable()")
    cs_lines.append("        {")
    cs_lines.append("            _inputActions?.Disable();")
    cs_lines.append("        }")
    cs_lines.append("")

    # EnableActionMap / DisableActionMap
    cs_lines.append("        /// <summary>")
    cs_lines.append("        /// Enable a specific action map by name.")
    cs_lines.append("        /// </summary>")
    cs_lines.append("        public void EnableActionMap(string mapName)")
    cs_lines.append("        {")
    cs_lines.append("            _inputActions?.FindActionMap(mapName)?.Enable();")
    cs_lines.append("        }")
    cs_lines.append("")
    cs_lines.append("        /// <summary>")
    cs_lines.append("        /// Disable a specific action map by name.")
    cs_lines.append("        /// </summary>")
    cs_lines.append("        public void DisableActionMap(string mapName)")
    cs_lines.append("        {")
    cs_lines.append("            _inputActions?.FindActionMap(mapName)?.Disable();")
    cs_lines.append("        }")
    cs_lines.append("")

    # RegisterCallbacks
    cs_lines.append("        private void RegisterCallbacks()")
    cs_lines.append("        {")
    cs_lines.append("            if (_gameplayMap == null) return;")
    cs_lines.append("")
    cs_lines.append("            _gameplayMap[\"Move\"].performed += ctx => OnMove?.Invoke(ctx.ReadValue<Vector2>());")
    cs_lines.append("            _gameplayMap[\"Move\"].canceled += ctx => OnMove?.Invoke(Vector2.zero);")
    cs_lines.append("            _gameplayMap[\"Look\"].performed += ctx => OnLook?.Invoke(ctx.ReadValue<Vector2>());")
    cs_lines.append("            _gameplayMap[\"LightAttack\"].performed += ctx => OnLightAttack?.Invoke();")
    cs_lines.append("            _gameplayMap[\"HeavyAttack\"].performed += ctx => OnHeavyAttack?.Invoke();")
    cs_lines.append("            _gameplayMap[\"Dodge\"].performed += ctx => OnDodge?.Invoke();")
    cs_lines.append("            _gameplayMap[\"Block\"].performed += ctx => OnBlock?.Invoke();")
    cs_lines.append("            _gameplayMap[\"Interact\"].performed += ctx => OnInteract?.Invoke();")
    cs_lines.append("            _gameplayMap[\"Sprint\"].performed += ctx => OnSprint?.Invoke();")
    cs_lines.append("            _gameplayMap[\"Jump\"].performed += ctx => OnJump?.Invoke();")
    cs_lines.append("            _gameplayMap[\"UseAbility\"].performed += ctx => OnUseAbility?.Invoke();")
    cs_lines.append("            _gameplayMap[\"Pause\"].performed += ctx => OnPause?.Invoke();")
    cs_lines.append("        }")
    cs_lines.append("")

    # Rebinding support
    if include_rebinding:
        cs_lines.append("        // ---------------------------------------------------------------")
        cs_lines.append("        // Runtime Rebinding")
        cs_lines.append("        // ---------------------------------------------------------------")
        cs_lines.append("")
        cs_lines.append("        /// <summary>")
        cs_lines.append("        /// Start interactive rebind for a specific action.")
        cs_lines.append("        /// </summary>")
        cs_lines.append("        public InputActionRebindingExtensions.RebindingOperation StartRebind(")
        cs_lines.append("            string actionName, int bindingIndex = 0, Action onComplete = null)")
        cs_lines.append("        {")
        cs_lines.append("            InputAction action = _inputActions.FindAction(actionName);")
        cs_lines.append("            if (action == null) return null;")
        cs_lines.append("")
        cs_lines.append("            action.Disable();")
        cs_lines.append("            var rebind = action.PerformInteractiveRebinding(bindingIndex)")
        cs_lines.append("                .OnComplete(op =>")
        cs_lines.append("                {")
        cs_lines.append("                    op.Dispose();")
        cs_lines.append("                    action.Enable();")
        cs_lines.append("                    SaveBindingOverrides();")
        cs_lines.append("                    onComplete?.Invoke();")
        cs_lines.append("                })")
        cs_lines.append("                .OnCancel(op =>")
        cs_lines.append("                {")
        cs_lines.append("                    op.Dispose();")
        cs_lines.append("                    action.Enable();")
        cs_lines.append("                })")
        cs_lines.append("                .Start();")
        cs_lines.append("")
        cs_lines.append("            return rebind;")
        cs_lines.append("        }")
        cs_lines.append("")
        cs_lines.append("        /// <summary>")
        cs_lines.append("        /// Save all binding overrides to PlayerPrefs as JSON.")
        cs_lines.append("        /// </summary>")
        cs_lines.append("        public void SaveBindingOverrides()")
        cs_lines.append("        {")
        cs_lines.append("            string json = _inputActions.SaveBindingOverridesAsJson();")
        cs_lines.append("            PlayerPrefs.SetString(REBIND_KEY, json);")
        cs_lines.append("            PlayerPrefs.Save();")
        cs_lines.append("        }")
        cs_lines.append("")
        cs_lines.append("        /// <summary>")
        cs_lines.append("        /// Load binding overrides from PlayerPrefs.")
        cs_lines.append("        /// </summary>")
        cs_lines.append("        public void LoadBindingOverrides()")
        cs_lines.append("        {")
        cs_lines.append("            string json = PlayerPrefs.GetString(REBIND_KEY, \"\");")
        cs_lines.append("            if (!string.IsNullOrEmpty(json))")
        cs_lines.append("                _inputActions.LoadBindingOverridesFromJson(json);")
        cs_lines.append("        }")
        cs_lines.append("")
        cs_lines.append("        /// <summary>")
        cs_lines.append("        /// Reset all bindings to defaults.")
        cs_lines.append("        /// </summary>")
        cs_lines.append("        public void ResetBindings()")
        cs_lines.append("        {")
        cs_lines.append("            _inputActions.RemoveAllBindingOverrides();")
        cs_lines.append("            PlayerPrefs.DeleteKey(REBIND_KEY);")
        cs_lines.append("        }")
        cs_lines.append("")

    cs_lines.append("    }")  # end VB_InputConfig
    cs_lines.append("}")  # end namespace

    return (input_json, "\n".join(cs_lines))


# ---------------------------------------------------------------------------
# GAME-08: Settings menu (C# + UXML + USS)
# ---------------------------------------------------------------------------


def generate_settings_menu_script(
    categories: list[str] | None = None,
    theme: str = "dark_fantasy",
    namespace: str = "VeilBreakers.GameSystems",
) -> tuple[str, str, str]:
    """Generate settings menu C#, UXML, and USS files.

    Produces a tuple of (settings_cs, settings_uxml, settings_uss) for a
    complete settings menu with graphics, audio, controls, and accessibility
    sections.

    Args:
        categories: Optional list of setting categories to include.
        theme: Visual theme name.
        namespace: C# namespace for generated code.

    Returns:
        Tuple of (settings_cs: str, settings_uxml: str, settings_uss: str).
    """
    if categories is None:
        categories = ["Graphics", "Audio", "Controls", "Accessibility"]

    # theme is accepted for API compatibility but USS is currently always dark_fantasy
    _ = theme

    # ---------------------------------------------------------------
    # C# SettingsMenu
    # ---------------------------------------------------------------
    cs = []
    cs.append("using System;")
    cs.append("using UnityEngine;")
    cs.append("using UnityEngine.Audio;")
    cs.append("using UnityEngine.UIElements;")
    cs.append("")
    cs.append("namespace " + _safe_namespace(namespace))
    cs.append("{")

    # SettingsData class
    cs.append("    /// <summary>")
    cs.append("    /// Serializable container for all user settings.")
    cs.append("    /// </summary>")
    cs.append("    [System.Serializable]")
    cs.append("    public class SettingsData")
    cs.append("    {")
    cs.append("        // Graphics")
    cs.append("        public int qualityLevel = 2;")
    cs.append("        public int resolutionIndex = -1;")
    cs.append("        public bool fullscreen = true;")
    cs.append("        public bool vsync = true;")
    cs.append("        public int shadowQuality = 2;")
    cs.append("")
    cs.append("        // Audio")
    cs.append("        public int masterVolume = 80;")
    cs.append("        public int sfxVolume = 80;")
    cs.append("        public int musicVolume = 70;")
    cs.append("        public int voiceVolume = 80;")
    cs.append("        public bool masterMute = false;")
    cs.append("")
    cs.append("        // Accessibility")
    cs.append("        public int subtitleSize = 16;")
    cs.append("        public int colorblindMode = 0;")
    cs.append("        public bool highContrast = false;")
    cs.append("    }")
    cs.append("")

    # VB_SettingsMenu class
    cs.append("    /// <summary>")
    cs.append("    /// Settings menu with graphics, audio, controls, and accessibility options.")
    cs.append("    /// Persists settings via PlayerPrefs JSON serialization.")
    cs.append("    /// Generated by VeilBreakers MCP toolkit.")
    cs.append("    /// </summary>")
    cs.append("    [RequireComponent(typeof(UIDocument))]")
    cs.append("    public class VB_SettingsMenu : MonoBehaviour")
    cs.append("    {")
    cs.append("        [Header(\"Audio\")]")
    cs.append("        [SerializeField] private AudioMixer _audioMixer;")
    cs.append("")
    cs.append("        private UIDocument _document;")
    cs.append("        private VisualElement _root;")
    cs.append("        private SettingsData _settings;")
    cs.append("        private SettingsData _pendingSettings;")
    cs.append("")
    cs.append("        private const string SETTINGS_KEY = \"VB_Settings\";")
    cs.append("")

    # Start
    cs.append("        private void Start()")
    cs.append("        {")
    cs.append("            _document = GetComponent<UIDocument>();")
    cs.append("            _root = _document.rootVisualElement;")
    cs.append("            _settings = LoadSettings();")
    cs.append("            _pendingSettings = JsonUtility.FromJson<SettingsData>(JsonUtility.ToJson(_settings));")
    cs.append("            BindUI();")
    cs.append("            ApplySettings(_settings);")
    cs.append("        }")
    cs.append("")

    # BindUI
    cs.append("        private void BindUI()")
    cs.append("        {")
    cs.append("            if (_root == null) return;")
    cs.append("")
    cs.append("            // Unregister all existing callbacks to prevent stacking on rebind")
    cs.append("            UnregisterAllCallbacks();")
    cs.append("")
    if "Graphics" in categories:
        cs.append("            // Graphics")
        cs.append("            var qualityDropdown = _root.Q<DropdownField>(\"quality-dropdown\");")
        cs.append("            if (qualityDropdown != null)")
        cs.append("            {")
        cs.append("                qualityDropdown.index = _settings.qualityLevel;")
        cs.append("                qualityDropdown.RegisterValueChangedCallback(_onQualityChanged);")
        cs.append("            }")
        cs.append("")
        cs.append("            var resolutionDropdown = _root.Q<DropdownField>(\"resolution-dropdown\");")
        cs.append("            if (resolutionDropdown != null)")
        cs.append("            {")
        cs.append("                resolutionDropdown.index = Mathf.Max(0, _settings.resolutionIndex);")
        cs.append("                resolutionDropdown.RegisterValueChangedCallback(_onResolutionChanged);")
        cs.append("            }")
        cs.append("")
        cs.append("            var fullscreenToggle = _root.Q<Toggle>(\"fullscreen-toggle\");")
        cs.append("            if (fullscreenToggle != null)")
        cs.append("            {")
        cs.append("                fullscreenToggle.value = _settings.fullscreen;")
        cs.append("                fullscreenToggle.RegisterValueChangedCallback(_onFullscreenChanged);")
        cs.append("            }")
        cs.append("")
        cs.append("            var vsyncToggle = _root.Q<Toggle>(\"vsync-toggle\");")
        cs.append("            if (vsyncToggle != null)")
        cs.append("            {")
        cs.append("                vsyncToggle.value = _settings.vsync;")
        cs.append("                vsyncToggle.RegisterValueChangedCallback(_onVsyncChanged);")
        cs.append("            }")
        cs.append("")
        cs.append("            var shadowDropdown = _root.Q<DropdownField>(\"shadow-quality-dropdown\");")
        cs.append("            if (shadowDropdown != null)")
        cs.append("            {")
        cs.append("                shadowDropdown.index = _settings.shadowQuality;")
        cs.append("                shadowDropdown.RegisterValueChangedCallback(_onShadowChanged);")
        cs.append("            }")
        cs.append("")

    if "Audio" in categories:
        cs.append("            // Audio")
        cs.append("            BindSlider(\"master-volume-slider\", _settings.masterVolume, v => _pendingSettings.masterVolume = v);")
        cs.append("            BindSlider(\"sfx-volume-slider\", _settings.sfxVolume, v => _pendingSettings.sfxVolume = v);")
        cs.append("            BindSlider(\"music-volume-slider\", _settings.musicVolume, v => _pendingSettings.musicVolume = v);")
        cs.append("            BindSlider(\"voice-volume-slider\", _settings.voiceVolume, v => _pendingSettings.voiceVolume = v);")
        cs.append("")

    if "Accessibility" in categories:
        cs.append("            // Accessibility")
        cs.append("            BindSlider(\"subtitle-size-slider\", _settings.subtitleSize, v => _pendingSettings.subtitleSize = v);")
        cs.append("")
        cs.append("            var colorblindDropdown = _root.Q<DropdownField>(\"colorblind-dropdown\");")
        cs.append("            if (colorblindDropdown != null)")
        cs.append("            {")
        cs.append("                colorblindDropdown.index = _settings.colorblindMode;")
        cs.append("                colorblindDropdown.RegisterValueChangedCallback(_onColorblindChanged);")
        cs.append("            }")
        cs.append("")
        cs.append("            var highContrastToggle = _root.Q<Toggle>(\"high-contrast-toggle\");")
        cs.append("            if (highContrastToggle != null)")
        cs.append("            {")
        cs.append("                highContrastToggle.value = _settings.highContrast;")
        cs.append("                highContrastToggle.RegisterValueChangedCallback(_onHighContrastChanged);")
        cs.append("            }")
        cs.append("")

    # Buttons
    cs.append("            // Buttons")
    cs.append("            _root.Q<Button>(\"apply-button\")?.RegisterCallback<ClickEvent>(evt => ApplyPending());")
    cs.append("            _root.Q<Button>(\"revert-button\")?.RegisterCallback<ClickEvent>(evt => RevertPending());")
    cs.append("            _root.Q<Button>(\"defaults-button\")?.RegisterCallback<ClickEvent>(evt => ResetToDefaults());")
    cs.append("        }")
    cs.append("")

    # Named callback methods (so they can be unregistered)
    cs.append("        // Named callback delegates for unregistration")
    cs.append("        private void _onQualityChanged(ChangeEvent<string> evt)")
    cs.append("        {")
    cs.append("            var dd = _root.Q<DropdownField>(\"quality-dropdown\");")
    cs.append("            if (dd != null) _pendingSettings.qualityLevel = dd.index;")
    cs.append("        }")
    cs.append("")
    cs.append("        private void _onResolutionChanged(ChangeEvent<string> evt)")
    cs.append("        {")
    cs.append("            var dd = _root.Q<DropdownField>(\"resolution-dropdown\");")
    cs.append("            if (dd != null) _pendingSettings.resolutionIndex = dd.index;")
    cs.append("        }")
    cs.append("")
    cs.append("        private void _onFullscreenChanged(ChangeEvent<bool> evt)")
    cs.append("        { _pendingSettings.fullscreen = evt.newValue; }")
    cs.append("")
    cs.append("        private void _onVsyncChanged(ChangeEvent<bool> evt)")
    cs.append("        { _pendingSettings.vsync = evt.newValue; }")
    cs.append("")
    cs.append("        private void _onShadowChanged(ChangeEvent<string> evt)")
    cs.append("        {")
    cs.append("            var dd = _root.Q<DropdownField>(\"shadow-quality-dropdown\");")
    cs.append("            if (dd != null) _pendingSettings.shadowQuality = dd.index;")
    cs.append("        }")
    cs.append("")
    cs.append("        private void _onColorblindChanged(ChangeEvent<string> evt)")
    cs.append("        {")
    cs.append("            var dd = _root.Q<DropdownField>(\"colorblind-dropdown\");")
    cs.append("            if (dd != null) _pendingSettings.colorblindMode = dd.index;")
    cs.append("        }")
    cs.append("")
    cs.append("        private void _onHighContrastChanged(ChangeEvent<bool> evt)")
    cs.append("        { _pendingSettings.highContrast = evt.newValue; }")
    cs.append("")
    cs.append("        private void UnregisterAllCallbacks()")
    cs.append("        {")
    cs.append("            _root.Q<DropdownField>(\"quality-dropdown\")?.UnregisterValueChangedCallback(_onQualityChanged);")
    cs.append("            _root.Q<DropdownField>(\"resolution-dropdown\")?.UnregisterValueChangedCallback(_onResolutionChanged);")
    cs.append("            _root.Q<Toggle>(\"fullscreen-toggle\")?.UnregisterValueChangedCallback(_onFullscreenChanged);")
    cs.append("            _root.Q<Toggle>(\"vsync-toggle\")?.UnregisterValueChangedCallback(_onVsyncChanged);")
    cs.append("            _root.Q<DropdownField>(\"shadow-quality-dropdown\")?.UnregisterValueChangedCallback(_onShadowChanged);")
    cs.append("            _root.Q<DropdownField>(\"colorblind-dropdown\")?.UnregisterValueChangedCallback(_onColorblindChanged);")
    cs.append("            _root.Q<Toggle>(\"high-contrast-toggle\")?.UnregisterValueChangedCallback(_onHighContrastChanged);")
    cs.append("        }")
    cs.append("")

    # BindSlider helper
    cs.append("        private void BindSlider(string name, int initialValue, Action<int> onChange)")
    cs.append("        {")
    cs.append("            var slider = _root.Q<SliderInt>(name);")
    cs.append("            if (slider != null)")
    cs.append("            {")
    cs.append("                slider.value = initialValue;")
    cs.append("                slider.RegisterValueChangedCallback(evt => onChange?.Invoke(evt.newValue));")
    cs.append("            }")
    cs.append("        }")
    cs.append("")

    # ApplySettings
    cs.append("        /// <summary>")
    cs.append("        /// Apply settings to Unity systems.")
    cs.append("        /// </summary>")
    cs.append("        public void ApplySettings(SettingsData data)")
    cs.append("        {")
    cs.append("            // Graphics")
    cs.append("            QualitySettings.SetQualityLevel(data.qualityLevel);")
    cs.append("            Screen.fullScreen = data.fullscreen;")
    cs.append("            QualitySettings.vSyncCount = data.vsync ? 1 : 0;")
    cs.append("")
    cs.append("            // Resolution")
    cs.append("            if (data.resolutionIndex >= 0 && data.resolutionIndex < Screen.resolutions.Length)")
    cs.append("            {")
    cs.append("                Resolution res = Screen.resolutions[data.resolutionIndex];")
    cs.append("                Screen.SetResolution(res.width, res.height, Screen.fullScreen);")
    cs.append("            }")
    cs.append("")
    cs.append("            // Shadow quality (0=Disable, 1=HardOnly, 2=All)")
    cs.append("            QualitySettings.shadows = (ShadowQuality)Mathf.Clamp(data.shadowQuality, 0, 2);")
    cs.append("")
    cs.append("            // Audio (AudioMixer exposed parameters)")
    cs.append("            if (_audioMixer != null)")
    cs.append("            {")
    cs.append("                _audioMixer.SetFloat(\"MasterVolume\", VolumeToDecibels(data.masterVolume));")
    cs.append("                _audioMixer.SetFloat(\"SFXVolume\", VolumeToDecibels(data.sfxVolume));")
    cs.append("                _audioMixer.SetFloat(\"MusicVolume\", VolumeToDecibels(data.musicVolume));")
    cs.append("                _audioMixer.SetFloat(\"VoiceVolume\", VolumeToDecibels(data.voiceVolume));")
    cs.append("            }")
    cs.append("        }")
    cs.append("")

    # Volume helper
    cs.append("        private float VolumeToDecibels(int volume)")
    cs.append("        {")
    cs.append("            float normalized = volume / 100f;")
    cs.append("            return normalized > 0f ? Mathf.Log10(normalized) * 20f : -80f;")
    cs.append("        }")
    cs.append("")

    # ApplyPending / RevertPending / ResetToDefaults
    cs.append("        private void ApplyPending()")
    cs.append("        {")
    cs.append("            _settings = JsonUtility.FromJson<SettingsData>(JsonUtility.ToJson(_pendingSettings));")
    cs.append("            ApplySettings(_settings);")
    cs.append("            SaveSettings(_settings);")
    cs.append("        }")
    cs.append("")
    cs.append("        private void RevertPending()")
    cs.append("        {")
    cs.append("            _pendingSettings = JsonUtility.FromJson<SettingsData>(JsonUtility.ToJson(_settings));")
    cs.append("            BindUI();")
    cs.append("        }")
    cs.append("")
    cs.append("        private void ResetToDefaults()")
    cs.append("        {")
    cs.append("            _settings = new SettingsData();")
    cs.append("            _pendingSettings = new SettingsData();")
    cs.append("            ApplySettings(_settings);")
    cs.append("            SaveSettings(_settings);")
    cs.append("            BindUI();")
    cs.append("        }")
    cs.append("")

    # Persistence
    cs.append("        // ---------------------------------------------------------------")
    cs.append("        // PlayerPrefs JSON Persistence")
    cs.append("        // ---------------------------------------------------------------")
    cs.append("")
    cs.append("        private SettingsData LoadSettings()")
    cs.append("        {")
    cs.append("            string json = PlayerPrefs.GetString(SETTINGS_KEY, \"\");")
    cs.append("            if (!string.IsNullOrEmpty(json))")
    cs.append("                return JsonUtility.FromJson<SettingsData>(json);")
    cs.append("            return new SettingsData();")
    cs.append("        }")
    cs.append("")
    cs.append("        private void SaveSettings(SettingsData data)")
    cs.append("        {")
    cs.append("            string json = JsonUtility.ToJson(data);")
    cs.append("            PlayerPrefs.SetString(SETTINGS_KEY, json);")
    cs.append("            PlayerPrefs.Save();")
    cs.append("        }")

    cs.append("    }")  # end VB_SettingsMenu
    cs.append("}")  # end namespace

    settings_cs = "\n".join(cs)

    # ---------------------------------------------------------------
    # UXML
    # ---------------------------------------------------------------
    uxml = []
    uxml.append('<ui:UXML xmlns:ui="UnityEngine.UIElements">')
    uxml.append('    <ui:VisualElement name="settings-root" class="settings-panel">')
    uxml.append('        <ui:Label text="Settings" class="settings-title" />')
    uxml.append('        <ui:ScrollView>')

    if "Graphics" in categories:
        uxml.append('            <ui:Foldout text="Graphics" value="true">')
        uxml.append('                <ui:DropdownField name="quality-dropdown" label="Quality" />')
        uxml.append('                <ui:DropdownField name="resolution-dropdown" label="Resolution" />')
        uxml.append('                <ui:Toggle name="fullscreen-toggle" label="Fullscreen" />')
        uxml.append('                <ui:Toggle name="vsync-toggle" label="VSync" />')
        uxml.append('                <ui:DropdownField name="shadow-quality-dropdown" label="Shadow Quality" />')
        uxml.append('            </ui:Foldout>')

    if "Audio" in categories:
        uxml.append('            <ui:Foldout text="Audio" value="true">')
        uxml.append('                <ui:SliderInt name="master-volume-slider" label="Master Volume" low-value="0" high-value="100" />')
        uxml.append('                <ui:SliderInt name="sfx-volume-slider" label="SFX Volume" low-value="0" high-value="100" />')
        uxml.append('                <ui:SliderInt name="music-volume-slider" label="Music Volume" low-value="0" high-value="100" />')
        uxml.append('                <ui:SliderInt name="voice-volume-slider" label="Voice Volume" low-value="0" high-value="100" />')
        uxml.append('            </ui:Foldout>')

    if "Controls" in categories:
        uxml.append('            <ui:Foldout text="Controls" value="true">')
        uxml.append('                <ui:VisualElement name="keybinding-list" />')
        uxml.append('            </ui:Foldout>')

    if "Accessibility" in categories:
        uxml.append('            <ui:Foldout text="Accessibility" value="true">')
        uxml.append('                <ui:SliderInt name="subtitle-size-slider" label="Subtitle Size" low-value="12" high-value="32" />')
        uxml.append('                <ui:DropdownField name="colorblind-dropdown" label="Colorblind Mode" />')
        uxml.append('                <ui:Toggle name="high-contrast-toggle" label="High Contrast" />')
        uxml.append('            </ui:Foldout>')

    uxml.append('        </ui:ScrollView>')
    uxml.append('        <ui:VisualElement class="button-row">')
    uxml.append('            <ui:Button name="apply-button" text="Apply" class="settings-button" />')
    uxml.append('            <ui:Button name="revert-button" text="Revert" class="settings-button" />')
    uxml.append('            <ui:Button name="defaults-button" text="Defaults" class="settings-button" />')
    uxml.append('        </ui:VisualElement>')
    uxml.append('    </ui:VisualElement>')
    uxml.append('</ui:UXML>')

    settings_uxml = "\n".join(uxml)

    # ---------------------------------------------------------------
    # USS (dark fantasy theme)
    # ---------------------------------------------------------------
    uss = []
    uss.append("/* VeilBreakers Settings Menu - Dark Fantasy Theme */")
    uss.append("")
    uss.append(".settings-panel {")
    uss.append("    background-color: #1a1a2e;")
    uss.append("    padding: 20px;")
    uss.append("    border-radius: 8px;")
    uss.append("    border-width: 2px;")
    uss.append("    border-color: #d4a634;")
    uss.append("    min-width: 600px;")
    uss.append("    min-height: 400px;")
    uss.append("}")
    uss.append("")
    uss.append(".settings-title {")
    uss.append("    font-size: 28px;")
    uss.append("    color: #d4a634;")
    uss.append("    -unity-font-style: bold;")
    uss.append("    margin-bottom: 16px;")
    uss.append("    -unity-text-align: middle-center;")
    uss.append("}")
    uss.append("")
    uss.append("Foldout {")
    uss.append("    margin-bottom: 8px;")
    uss.append("}")
    uss.append("")
    uss.append("Foldout > Toggle > VisualElement > Label {")
    uss.append("    color: #d4a634;")
    uss.append("    font-size: 18px;")
    uss.append("    -unity-font-style: bold;")
    uss.append("}")
    uss.append("")
    uss.append("Label {")
    uss.append("    color: #e0d6c8;")
    uss.append("    font-size: 14px;")
    uss.append("}")
    uss.append("")
    uss.append("SliderInt {")
    uss.append("    margin: 4px 0;")
    uss.append("}")
    uss.append("")
    uss.append("Toggle {")
    uss.append("    margin: 4px 0;")
    uss.append("}")
    uss.append("")
    uss.append("DropdownField {")
    uss.append("    margin: 4px 0;")
    uss.append("}")
    uss.append("")
    uss.append(".button-row {")
    uss.append("    flex-direction: row;")
    uss.append("    justify-content: flex-end;")
    uss.append("    margin-top: 16px;")
    uss.append("    padding-top: 8px;")
    uss.append("    border-top-width: 1px;")
    uss.append("    border-top-color: #333355;")
    uss.append("}")
    uss.append("")
    uss.append(".settings-button {")
    uss.append("    background-color: #2a2a4e;")
    uss.append("    color: #d4a634;")
    uss.append("    border-width: 1px;")
    uss.append("    border-color: #d4a634;")
    uss.append("    border-radius: 4px;")
    uss.append("    padding: 8px 24px;")
    uss.append("    margin-left: 8px;")
    uss.append("    font-size: 14px;")
    uss.append("    -unity-font-style: bold;")
    uss.append("}")
    uss.append("")
    uss.append(".settings-button:hover {")
    uss.append("    background-color: #3a3a6e;")
    uss.append("}")

    settings_uss = "\n".join(uss)

    return (settings_cs, settings_uxml, settings_uss)


# ---------------------------------------------------------------------------
# MEDIA-02: HTTP client (UnityWebRequest + retry)
# ---------------------------------------------------------------------------


def generate_http_client_script(
    base_url: str = "",
    max_retries: int = 3,
    timeout_seconds: int = 30,
    namespace: str = "VeilBreakers.GameSystems",
) -> str:
    """Generate C# static HTTP client utility using UnityWebRequest.

    Produces VB_HttpClient with typed GET/POST/PUT/DELETE methods,
    exponential backoff retry, configurable timeout, and header management.

    Args:
        base_url: Default base URL for requests.
        max_retries: Maximum retry attempts.
        timeout_seconds: Request timeout in seconds.
        namespace: C# namespace for generated code.

    Returns:
        Complete C# source string.
    """
    safe_base_url = sanitize_cs_string(base_url)
    lines = []

    lines.append("using System;")
    lines.append("using System.Collections;")
    lines.append("using System.Collections.Generic;")
    lines.append("using System.Text;")
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.Networking;")
    lines.append("")
    lines.append("namespace " + _safe_namespace(namespace))
    lines.append("{")

    # HttpResponse<T>
    lines.append("    /// <summary>")
    lines.append("    /// Typed HTTP response wrapper.")
    lines.append("    /// </summary>")
    lines.append("    [System.Serializable]")
    lines.append("    public class HttpResponse<T>")
    lines.append("    {")
    lines.append("        public bool success;")
    lines.append("        public string error;")
    lines.append("        public long statusCode;")
    lines.append("        public T data;")
    lines.append("        public string rawBody;")
    lines.append("    }")
    lines.append("")

    # VB_HttpClient class
    lines.append("    /// <summary>")
    lines.append("    /// Static HTTP client with typed methods, retry with exponential backoff,")
    lines.append("    /// and configurable timeout. Uses UnityWebRequest internally.")
    lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    lines.append("    /// </summary>")
    lines.append("    public static class VB_HttpClient")
    lines.append("    {")
    lines.append("        private static string _baseUrl = \"" + safe_base_url + "\";")
    lines.append("        private static int _maxRetries = " + str(max_retries) + ";")
    lines.append("        private static int _timeoutSeconds = " + str(timeout_seconds) + ";")
    lines.append("        private static Dictionary<string, string> _defaultHeaders = new Dictionary<string, string>();")
    lines.append("")

    # SetBaseUrl / SetAuth / AddHeader
    lines.append("        /// <summary>Set the base URL for all requests.</summary>")
    lines.append("        public static void SetBaseUrl(string url) => _baseUrl = url;")
    lines.append("")
    lines.append("        /// <summary>Set bearer token for Authorization header.</summary>")
    lines.append("        public static void SetAuthToken(string token)")
    lines.append("        {")
    lines.append("            _defaultHeaders[\"Authorization\"] = \"Bearer \" + token;")
    lines.append("        }")
    lines.append("")
    lines.append("        /// <summary>Add a default header to all requests.</summary>")
    lines.append("        public static void AddHeader(string key, string value)")
    lines.append("        {")
    lines.append("            _defaultHeaders[key] = value;")
    lines.append("        }")
    lines.append("")

    # Unity 6 async with fallback
    lines.append("#if UNITY_6000_0_OR_NEWER")
    lines.append("        // ---------------------------------------------------------------")
    lines.append("        // Unity 6+ async/await API using Awaitable")
    lines.append("        // ---------------------------------------------------------------")
    lines.append("")

    # Get<T> async
    lines.append("        /// <summary>Typed GET request with retry.</summary>")
    lines.append("        public static async Awaitable<HttpResponse<T>> Get<T>(string url)")
    lines.append("        {")
    lines.append("            return await SendWithRetry<T>(BuildUrl(url), \"GET\", null);")
    lines.append("        }")
    lines.append("")

    # Post<T> async
    lines.append("        /// <summary>Typed POST request with retry.</summary>")
    lines.append("        public static async Awaitable<HttpResponse<T>> Post<T>(string url, object body)")
    lines.append("        {")
    lines.append("            string json = JsonUtility.ToJson(body);")
    lines.append("            return await SendWithRetry<T>(BuildUrl(url), \"POST\", json);")
    lines.append("        }")
    lines.append("")

    # Put<T> async
    lines.append("        /// <summary>Typed PUT request with retry.</summary>")
    lines.append("        public static async Awaitable<HttpResponse<T>> Put<T>(string url, object body)")
    lines.append("        {")
    lines.append("            string json = JsonUtility.ToJson(body);")
    lines.append("            return await SendWithRetry<T>(BuildUrl(url), \"PUT\", json);")
    lines.append("        }")
    lines.append("")

    # Delete<T> async
    lines.append("        /// <summary>Typed DELETE request with retry.</summary>")
    lines.append("        public static async Awaitable<HttpResponse<T>> Delete<T>(string url)")
    lines.append("        {")
    lines.append("            return await SendWithRetry<T>(BuildUrl(url), \"DELETE\", null);")
    lines.append("        }")
    lines.append("")

    # SendWithRetry async
    lines.append("        private static async Awaitable<HttpResponse<T>> SendWithRetry<T>(")
    lines.append("            string url, string method, string jsonBody)")
    lines.append("        {")
    lines.append("            HttpResponse<T> lastResponse = null;")
    lines.append("            float baseDelay = 1f;")
    lines.append("            float maxDelay = 30f;")
    lines.append("")
    lines.append("            for (int attempt = 0; attempt <= _maxRetries; attempt++)")
    lines.append("            {")
    lines.append("                if (attempt > 0)")
    lines.append("                {")
    lines.append("                    // Exponential backoff with jitter")
    lines.append("                    float delay = Mathf.Min(baseDelay * Mathf.Pow(2f, attempt - 1), maxDelay);")
    lines.append("                    delay += UnityEngine.Random.Range(0f, delay * 0.1f);")
    lines.append("                    await Awaitable.WaitForSecondsAsync(delay);")
    lines.append("                    Debug.Log($\"[VB_HttpClient] Retry {attempt}/{_maxRetries} for {method} {url}\");")
    lines.append("                }")
    lines.append("")
    lines.append("                lastResponse = await SendRequest<T>(url, method, jsonBody);")
    lines.append("                if (lastResponse.success || lastResponse.statusCode < 500)")
    lines.append("                    return lastResponse;")
    lines.append("            }")
    lines.append("")
    lines.append("            return lastResponse;")
    lines.append("        }")
    lines.append("")

    # SendRequest async
    lines.append("        private static async Awaitable<HttpResponse<T>> SendRequest<T>(")
    lines.append("            string url, string method, string jsonBody)")
    lines.append("        {")
    lines.append("            var response = new HttpResponse<T>();")
    lines.append("")
    lines.append("            using (UnityWebRequest request = new UnityWebRequest(url, method))")
    lines.append("            {")
    lines.append("                request.timeout = _timeoutSeconds;")
    lines.append("                request.downloadHandler = new DownloadHandlerBuffer();")
    lines.append("")
    lines.append("                if (jsonBody != null)")
    lines.append("                {")
    lines.append("                    byte[] bodyData = Encoding.UTF8.GetBytes(jsonBody);")
    lines.append("                    request.uploadHandler = new UploadHandlerRaw(bodyData);")
    lines.append("                    request.SetRequestHeader(\"Content-Type\", \"application/json\");")
    lines.append("                }")
    lines.append("")
    lines.append("                foreach (var header in _defaultHeaders)")
    lines.append("                    request.SetRequestHeader(header.Key, header.Value);")
    lines.append("")
    lines.append("                await request.SendWebRequest();")
    lines.append("")
    lines.append("                response.statusCode = request.responseCode;")
    lines.append("                response.rawBody = request.downloadHandler?.text;")
    lines.append("")
    lines.append("                if (request.result == UnityWebRequest.Result.Success)")
    lines.append("                {")
    lines.append("                    response.success = true;")
    lines.append("                    if (!string.IsNullOrEmpty(response.rawBody))")
    lines.append("                        response.data = JsonUtility.FromJson<T>(response.rawBody);")
    lines.append("                }")
    lines.append("                else")
    lines.append("                {")
    lines.append("                    response.success = false;")
    lines.append("                    response.error = request.error;")
    lines.append("                    Debug.LogWarning($\"[VB_HttpClient] {method} {url} failed: {request.error}\");")
    lines.append("                }")
    lines.append("            }")
    lines.append("")
    lines.append("            return response;")
    lines.append("        }")
    lines.append("")
    lines.append("#else")
    lines.append("        // ---------------------------------------------------------------")
    lines.append("        // Pre-Unity 6 coroutine fallback")
    lines.append("        // ---------------------------------------------------------------")
    lines.append("")

    # Coroutine-based Get
    lines.append("        /// <summary>Coroutine-based GET request. Use with StartCoroutine.</summary>")
    lines.append("        public static IEnumerator Get<T>(string url, Action<HttpResponse<T>> callback)")
    lines.append("        {")
    lines.append("            yield return SendWithRetryCoroutine<T>(BuildUrl(url), \"GET\", null, callback);")
    lines.append("        }")
    lines.append("")
    lines.append("        /// <summary>Coroutine-based POST request. Use with StartCoroutine.</summary>")
    lines.append("        public static IEnumerator Post<T>(string url, object body, Action<HttpResponse<T>> callback)")
    lines.append("        {")
    lines.append("            string json = JsonUtility.ToJson(body);")
    lines.append("            yield return SendWithRetryCoroutine<T>(BuildUrl(url), \"POST\", json, callback);")
    lines.append("        }")
    lines.append("")
    lines.append("        /// <summary>Coroutine-based PUT request. Use with StartCoroutine.</summary>")
    lines.append("        public static IEnumerator Put<T>(string url, object body, Action<HttpResponse<T>> callback)")
    lines.append("        {")
    lines.append("            string json = JsonUtility.ToJson(body);")
    lines.append("            yield return SendWithRetryCoroutine<T>(BuildUrl(url), \"PUT\", json, callback);")
    lines.append("        }")
    lines.append("")
    lines.append("        /// <summary>Coroutine-based DELETE request. Use with StartCoroutine.</summary>")
    lines.append("        public static IEnumerator Delete<T>(string url, Action<HttpResponse<T>> callback)")
    lines.append("        {")
    lines.append("            yield return SendWithRetryCoroutine<T>(BuildUrl(url), \"DELETE\", null, callback);")
    lines.append("        }")
    lines.append("")

    # SendWithRetryCoroutine
    lines.append("        private static IEnumerator SendWithRetryCoroutine<T>(")
    lines.append("            string url, string method, string jsonBody, Action<HttpResponse<T>> callback)")
    lines.append("        {")
    lines.append("            HttpResponse<T> lastResponse = null;")
    lines.append("            float baseDelay = 1f;")
    lines.append("            float maxDelay = 30f;")
    lines.append("")
    lines.append("            for (int attempt = 0; attempt <= _maxRetries; attempt++)")
    lines.append("            {")
    lines.append("                if (attempt > 0)")
    lines.append("                {")
    lines.append("                    float delay = Mathf.Min(baseDelay * Mathf.Pow(2f, attempt - 1), maxDelay);")
    lines.append("                    delay += UnityEngine.Random.Range(0f, delay * 0.1f);")
    lines.append("                    yield return new WaitForSeconds(delay);")
    lines.append("                    Debug.Log($\"[VB_HttpClient] Retry {attempt}/{_maxRetries} for {method} {url}\");")
    lines.append("                }")
    lines.append("")
    lines.append("                lastResponse = new HttpResponse<T>();")
    lines.append("                using (UnityWebRequest request = new UnityWebRequest(url, method))")
    lines.append("                {")
    lines.append("                    request.timeout = _timeoutSeconds;")
    lines.append("                    request.downloadHandler = new DownloadHandlerBuffer();")
    lines.append("")
    lines.append("                    if (jsonBody != null)")
    lines.append("                    {")
    lines.append("                        byte[] bodyData = Encoding.UTF8.GetBytes(jsonBody);")
    lines.append("                        request.uploadHandler = new UploadHandlerRaw(bodyData);")
    lines.append("                        request.SetRequestHeader(\"Content-Type\", \"application/json\");")
    lines.append("                    }")
    lines.append("")
    lines.append("                    foreach (var header in _defaultHeaders)")
    lines.append("                        request.SetRequestHeader(header.Key, header.Value);")
    lines.append("")
    lines.append("                    yield return request.SendWebRequest();")
    lines.append("")
    lines.append("                    lastResponse.statusCode = request.responseCode;")
    lines.append("                    lastResponse.rawBody = request.downloadHandler?.text;")
    lines.append("")
    lines.append("                    if (request.result == UnityWebRequest.Result.Success)")
    lines.append("                    {")
    lines.append("                        lastResponse.success = true;")
    lines.append("                        if (!string.IsNullOrEmpty(lastResponse.rawBody))")
    lines.append("                            lastResponse.data = JsonUtility.FromJson<T>(lastResponse.rawBody);")
    lines.append("                        callback?.Invoke(lastResponse);")
    lines.append("                        yield break;")
    lines.append("                    }")
    lines.append("                    else")
    lines.append("                    {")
    lines.append("                        lastResponse.success = false;")
    lines.append("                        lastResponse.error = request.error;")
    lines.append("                        Debug.LogWarning($\"[VB_HttpClient] {method} {url} failed: {request.error}\");")
    lines.append("                        if (request.responseCode < 500)")
    lines.append("                        {")
    lines.append("                            callback?.Invoke(lastResponse);")
    lines.append("                            yield break;")
    lines.append("                        }")
    lines.append("                    }")
    lines.append("                }")
    lines.append("            }")
    lines.append("")
    lines.append("            callback?.Invoke(lastResponse);")
    lines.append("        }")
    lines.append("")
    lines.append("#endif")
    lines.append("")

    # BuildUrl helper
    lines.append("        private static string BuildUrl(string path)")
    lines.append("        {")
    lines.append("            if (string.IsNullOrEmpty(_baseUrl) || path.StartsWith(\"http\"))")
    lines.append("                return path;")
    lines.append("            return _baseUrl.TrimEnd('/') + \"/\" + path.TrimStart('/');")
    lines.append("        }")
    lines.append("    }")  # end VB_HttpClient

    lines.append("}")  # end namespace

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# RPG-03: Interactable system (state machine + interaction manager)
# ---------------------------------------------------------------------------


def generate_interactable_script(
    interactable_types: list[str] | None = None,
    interaction_radius: float = 2.0,
    use_animation: bool = True,
    use_sound: bool = True,
    namespace: str = "VeilBreakers.GameSystems",
) -> str:
    """Generate C# for interactable objects and interaction manager.

    Produces VB_Interactable with state machine (Door/Chest/Lever/Switch),
    proximity detection, lock/unlock, save/load state, and VB_InteractionManager
    singleton for tracking closest interactable.

    Args:
        interactable_types: Optional list of interactable type names.
        interaction_radius: Default interaction radius.
        use_animation: Whether to include Animator hooks.
        use_sound: Whether to include AudioSource hooks.
        namespace: C# namespace for generated code.

    Returns:
        Complete C# source string.
    """
    # interactable_types is accepted for API compatibility; built-in types always generated
    _ = interactable_types

    lines = []

    lines.append("using System;")
    lines.append("using System.Collections.Generic;")
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.Events;")
    lines.append("")
    lines.append("namespace " + _safe_namespace(namespace))
    lines.append("{")

    # InteractableType enum
    lines.append("    /// <summary>")
    lines.append("    /// Types of interactable objects in the world.")
    lines.append("    /// </summary>")
    lines.append("    public enum InteractableType")
    lines.append("    {")
    lines.append("        Door,")
    lines.append("        Chest,")
    lines.append("        Lever,")
    lines.append("        Switch,")
    lines.append("        Custom")
    lines.append("    }")
    lines.append("")

    # InteractState enum
    lines.append("    /// <summary>")
    lines.append("    /// Possible states for an interactable object.")
    lines.append("    /// </summary>")
    lines.append("    public enum InteractState")
    lines.append("    {")
    lines.append("        Idle,")
    lines.append("        Interacting,")
    lines.append("        Open,")
    lines.append("        Closed,")
    lines.append("        Locked,")
    lines.append("        Disabled")
    lines.append("    }")
    lines.append("")

    # VB_Interactable
    lines.append("    /// <summary>")
    lines.append("    /// Interactable object with state machine, proximity trigger,")
    lines.append("    /// lock/unlock, and save/load support.")
    lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    lines.append("    /// </summary>")
    lines.append("    [RequireComponent(typeof(SphereCollider))]")
    lines.append("    public class VB_Interactable : MonoBehaviour")
    lines.append("    {")
    lines.append("        [Header(\"Configuration\")]")
    lines.append("        [SerializeField] private string _interactableId;")
    lines.append("        [SerializeField] private InteractableType _type = InteractableType.Door;")
    lines.append("        [SerializeField] private InteractState _currentState = InteractState.Closed;")
    lines.append("        [SerializeField] private float _interactionRadius = " + str(interaction_radius) + "f;")
    lines.append("")
    lines.append("        [Header(\"Lock\")]")
    lines.append("        [SerializeField] private bool _isLocked = false;")
    lines.append("        [SerializeField] private string _requiredKeyId = \"\";")
    lines.append("")

    if use_animation:
        lines.append("        [Header(\"Animation\")]")
        lines.append("        [SerializeField] private Animator _animator;")
        lines.append("")

    if use_sound:
        lines.append("        [Header(\"Sound\")]")
        lines.append("        [SerializeField] private AudioSource _audioSource;")
        lines.append("        [SerializeField] private AudioClip _interactSound;")
        lines.append("")

    lines.append("        [Header(\"Events\")]")
    lines.append("        public UnityEvent OnInteract;")
    lines.append("        public UnityEvent<InteractState> OnStateChanged;")
    lines.append("        public UnityEvent OnLocked;")
    lines.append("")
    lines.append("        /// <summary>Unique identifier for save/load.</summary>")
    lines.append("        public string InteractableId => _interactableId;")
    lines.append("        /// <summary>Current interaction state.</summary>")
    lines.append("        public InteractState CurrentState => _currentState;")
    lines.append("        /// <summary>The type of interactable.</summary>")
    lines.append("        public InteractableType Type => _type;")
    lines.append("        /// <summary>Whether this interactable is locked.</summary>")
    lines.append("        public bool IsLocked => _isLocked;")
    lines.append("")

    # Reset (editor-only: auto-generate ID when component is first added)
    lines.append("        /// <summary>Called in Editor when component is first added or reset.</summary>")
    lines.append("        private void Reset()")
    lines.append("        {")
    lines.append("            if (string.IsNullOrEmpty(_interactableId))")
    lines.append("                _interactableId = Guid.NewGuid().ToString();")
    lines.append("        }")
    lines.append("")

    # Awake
    lines.append("        private void Awake()")
    lines.append("        {")
    lines.append("            if (string.IsNullOrEmpty(_interactableId))")
    lines.append("                Debug.LogWarning(\"[VB_Interactable] \" + gameObject.name + \" has no interactableId. Assign one in the Inspector for save/load.\");")
    lines.append("")
    lines.append("            // Setup trigger collider for proximity detection")
    lines.append("            SphereCollider trigger = GetComponent<SphereCollider>();")
    lines.append("            trigger.isTrigger = true;")
    lines.append("            trigger.radius = _interactionRadius;")
    lines.append("        }")
    lines.append("")

    # Interact
    lines.append("        /// <summary>")
    lines.append("        /// Attempt to interact with this object.")
    lines.append("        /// </summary>")
    lines.append("        public bool Interact(string keyId = null)")
    lines.append("        {")
    lines.append("            if (_currentState == InteractState.Disabled)")
    lines.append("                return false;")
    lines.append("")
    lines.append("            if (_isLocked)")
    lines.append("            {")
    lines.append("                if (string.IsNullOrEmpty(keyId) || keyId != _requiredKeyId)")
    lines.append("                {")
    lines.append("                    OnLocked?.Invoke();")
    lines.append("                    Debug.Log(\"[VB_Interactable] \" + gameObject.name + \" is locked.\");")
    lines.append("                    return false;")
    lines.append("                }")
    lines.append("                Unlock();")
    lines.append("            }")
    lines.append("")
    lines.append("            // State transition based on type")
    lines.append("            InteractState newState = GetNextState();")
    lines.append("            SetState(newState);")
    lines.append("")
    if use_sound:
        lines.append("            // Play interaction sound")
        lines.append("            if (_audioSource != null && _interactSound != null)")
        lines.append("                _audioSource.PlayOneShot(_interactSound);")
        lines.append("")
    if use_animation:
        lines.append("            // Trigger animation")
        lines.append("            PlayAnimation(newState);")
        lines.append("")
    lines.append("            OnInteract?.Invoke();")
    lines.append("            return true;")
    lines.append("        }")
    lines.append("")

    # GetNextState
    lines.append("        private InteractState GetNextState()")
    lines.append("        {")
    lines.append("            switch (_type)")
    lines.append("            {")
    lines.append("                case InteractableType.Door:")
    lines.append("                    return _currentState == InteractState.Closed ? InteractState.Open : InteractState.Closed;")
    lines.append("")
    lines.append("                case InteractableType.Chest:")
    lines.append("                    return InteractState.Open; // Chests only open")
    lines.append("")
    lines.append("                case InteractableType.Lever:")
    lines.append("                    return _currentState == InteractState.Idle ? InteractState.Interacting : InteractState.Idle;")
    lines.append("")
    lines.append("                case InteractableType.Switch:")
    lines.append("                    return _currentState == InteractState.Idle ? InteractState.Interacting : InteractState.Idle;")
    lines.append("")
    lines.append("                default:")
    lines.append("                    return InteractState.Interacting;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # SetState
    lines.append("        private void SetState(InteractState newState)")
    lines.append("        {")
    lines.append("            _currentState = newState;")
    lines.append("            OnStateChanged?.Invoke(newState);")
    lines.append("        }")
    lines.append("")

    # PlayAnimation
    if use_animation:
        lines.append("        private void PlayAnimation(InteractState state)")
        lines.append("        {")
        lines.append("            if (_animator == null) return;")
        lines.append("")
        lines.append("            switch (state)")
        lines.append("            {")
        lines.append("                case InteractState.Open:")
        lines.append("                    _animator.SetTrigger(\"Open\");")
        lines.append("                    break;")
        lines.append("                case InteractState.Closed:")
        lines.append("                    _animator.SetTrigger(\"Close\");")
        lines.append("                    break;")
        lines.append("                case InteractState.Interacting:")
        lines.append("                    _animator.SetTrigger(\"Activate\");")
        lines.append("                    break;")
        lines.append("            }")
        lines.append("        }")
        lines.append("")

    # Lock/Unlock
    lines.append("        /// <summary>Lock this interactable with a key requirement.</summary>")
    lines.append("        public void Lock(string keyId)")
    lines.append("        {")
    lines.append("            _isLocked = true;")
    lines.append("            _requiredKeyId = keyId;")
    lines.append("            SetState(InteractState.Locked);")
    lines.append("        }")
    lines.append("")
    lines.append("        /// <summary>Unlock this interactable.</summary>")
    lines.append("        public void Unlock()")
    lines.append("        {")
    lines.append("            _isLocked = false;")
    lines.append("            SetState(InteractState.Closed);")
    lines.append("        }")
    lines.append("")

    # Save/Load state
    lines.append("        /// <summary>Get serializable state string for save system.</summary>")
    lines.append("        public string GetSaveState()")
    lines.append("        {")
    lines.append("            return _interactableId + \"|\" + (int)_currentState + \"|\" + (_isLocked ? 1 : 0);")
    lines.append("        }")
    lines.append("")
    lines.append("        /// <summary>Restore state from save string.</summary>")
    lines.append("        public void LoadSaveState(string state)")
    lines.append("        {")
    lines.append("            if (string.IsNullOrEmpty(state)) return;")
    lines.append("")
    lines.append("            string[] parts = state.Split('|');")
    lines.append("            if (parts.Length >= 3 && parts[0] == _interactableId)")
    lines.append("            {")
    lines.append("                if (int.TryParse(parts[1], out int stateInt))")
    lines.append("                    SetState((InteractState)stateInt);")
    lines.append("                if (int.TryParse(parts[2], out int lockedInt))")
    lines.append("                    _isLocked = lockedInt == 1;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")

    # OnTriggerEnter/Exit
    lines.append("        private void OnTriggerEnter(Collider other)")
    lines.append("        {")
    lines.append("            if (other.CompareTag(\"Player\"))")
    lines.append("            {")
    lines.append("                VB_InteractionManager.Instance?.RegisterInRange(this);")
    lines.append("            }")
    lines.append("        }")
    lines.append("")
    lines.append("        private void OnTriggerExit(Collider other)")
    lines.append("        {")
    lines.append("            if (other.CompareTag(\"Player\"))")
    lines.append("            {")
    lines.append("                VB_InteractionManager.Instance?.UnregisterInRange(this);")
    lines.append("            }")
    lines.append("        }")

    lines.append("    }")  # end VB_Interactable
    lines.append("")

    # VB_InteractionManager singleton
    lines.append("    /// <summary>")
    lines.append("    /// Singleton that tracks all interactables in range of the player.")
    lines.append("    /// Provides GetClosestInteractable() for UI prompt system.")
    lines.append("    /// Generated by VeilBreakers MCP toolkit.")
    lines.append("    /// </summary>")
    lines.append("    public class VB_InteractionManager : MonoBehaviour")
    lines.append("    {")
    lines.append("        private static VB_InteractionManager _instance;")
    lines.append("        public static VB_InteractionManager Instance => _instance;")
    lines.append("")
    lines.append("        private readonly List<VB_Interactable> _inRange = new List<VB_Interactable>();")
    lines.append("        private Transform _playerTransform;")
    lines.append("")
    lines.append("        private void Awake()")
    lines.append("        {")
    lines.append("            if (_instance != null && _instance != this)")
    lines.append("            {")
    lines.append("                Destroy(gameObject);")
    lines.append("                return;")
    lines.append("            }")
    lines.append("            _instance = this;")
    lines.append("        }")
    lines.append("")
    lines.append("        private void Start()")
    lines.append("        {")
    lines.append("            var player = GameObject.FindGameObjectWithTag(\"Player\");")
    lines.append("            if (player != null)")
    lines.append("                _playerTransform = player.transform;")
    lines.append("        }")
    lines.append("")

    # RegisterInRange / UnregisterInRange
    lines.append("        /// <summary>Register an interactable as in range.</summary>")
    lines.append("        public void RegisterInRange(VB_Interactable interactable)")
    lines.append("        {")
    lines.append("            if (!_inRange.Contains(interactable))")
    lines.append("                _inRange.Add(interactable);")
    lines.append("        }")
    lines.append("")
    lines.append("        /// <summary>Unregister an interactable as out of range.</summary>")
    lines.append("        public void UnregisterInRange(VB_Interactable interactable)")
    lines.append("        {")
    lines.append("            _inRange.Remove(interactable);")
    lines.append("        }")
    lines.append("")

    # GetClosestInteractable
    lines.append("        /// <summary>")
    lines.append("        /// Returns the closest interactable in range, or null if none.")
    lines.append("        /// </summary>")
    lines.append("        public VB_Interactable GetClosestInteractable()")
    lines.append("        {")
    lines.append("            if (_playerTransform == null || _inRange.Count == 0)")
    lines.append("                return null;")
    lines.append("")
    lines.append("            // Clean up destroyed objects")
    lines.append("            _inRange.RemoveAll(i => i == null);")
    lines.append("")
    lines.append("            VB_Interactable closest = null;")
    lines.append("            float closestDist = float.MaxValue;")
    lines.append("")
    lines.append("            foreach (var interactable in _inRange)")
    lines.append("            {")
    lines.append("                float dist = Vector3.Distance(_playerTransform.position, interactable.transform.position);")
    lines.append("                if (dist < closestDist)")
    lines.append("                {")
    lines.append("                    closestDist = dist;")
    lines.append("                    closest = interactable;")
    lines.append("                }")
    lines.append("            }")
    lines.append("")
    lines.append("            return closest;")
    lines.append("        }")
    lines.append("")

    # HasInteractablesInRange
    lines.append("        /// <summary>Whether any interactables are in range.</summary>")
    lines.append("        public bool HasInteractablesInRange => _inRange.Count > 0;")

    lines.append("    }")  # end VB_InteractionManager
    lines.append("}")  # end namespace

    return "\n".join(lines)
