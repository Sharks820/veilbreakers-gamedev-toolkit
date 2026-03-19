"""SQLite asset catalog with CRUD and query operations.

Stores and queries game assets by name, type, tags, poly count, texture
resolution, LOD count, status, and arbitrary JSON metadata.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


# Columns that may be referenced in dynamic SQL.  Every key used in
# update_asset **kwargs or query_assets filters is validated against this
# frozenset so that arbitrary user strings can never become column names.
_ALLOWED_COLUMNS: frozenset[str] = frozenset({
    "name", "asset_type", "path", "tags", "poly_count", "texture_res",
    "lod_count", "status", "metadata", "updated_at",
})


class AssetCatalog:
    """SQLite-backed asset catalog for tracking game assets.

    Usage::

        catalog = AssetCatalog("assets.db")
        asset_id = catalog.add_asset("Barrel", "prop", "/barrel.glb", tags=["wood"])
        results = catalog.query_assets(tags=["wood"])
        catalog.close()
    """

    def __init__(self, db_path: str = "assets.db"):
        """Initialize catalog and create tables if needed.

        Args:
            db_path: Path to SQLite database file, or ":memory:" for in-memory.
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Create the assets table if it does not exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                path TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                poly_count INTEGER,
                texture_res TEXT,
                lod_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'imported',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_name ON assets(name)
        """)
        self.conn.commit()

    def add_asset(
        self,
        name: str,
        asset_type: str,
        path: str,
        tags: list[str] | None = None,
        poly_count: int | None = None,
        texture_res: str | None = None,
        lod_count: int = 0,
        status: str = "imported",
        metadata: dict | None = None,
    ) -> str:
        """Add an asset to the catalog.

        Args:
            name: Human-readable asset name.
            asset_type: Category (e.g. "prop", "weapon", "environment").
            path: File path to the asset.
            tags: List of string tags for filtering.
            poly_count: Polygon/face count.
            texture_res: Texture resolution string (e.g. "2048x2048").
            lod_count: Number of LOD levels.
            status: Asset status (e.g. "imported", "processed", "exported").
            metadata: Arbitrary JSON metadata dict.

        Returns:
            UUID string for the new asset entry.
        """
        asset_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            INSERT INTO assets
                (id, name, asset_type, path, tags, poly_count, texture_res,
                 lod_count, status, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                name,
                asset_type,
                path,
                json.dumps(tags or []),
                poly_count,
                texture_res,
                lod_count,
                status,
                now,
                now,
                json.dumps(metadata or {}),
            ),
        )
        self.conn.commit()
        return asset_id

    def get_asset(self, asset_id: str) -> dict | None:
        """Get full asset metadata by ID.

        Args:
            asset_id: The UUID of the asset.

        Returns:
            Dict with all asset fields, or None if not found.
        """
        cursor = self.conn.execute(
            "SELECT * FROM assets WHERE id = ?", (asset_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    # Static UPDATE statements keyed by column name.  Each statement is a
    # compile-time literal so no dynamic SQL construction is needed.
    _UPDATE_STMTS: dict[str, str] = {
        "name":        "UPDATE assets SET name = ?, updated_at = ? WHERE id = ?",
        "asset_type":  "UPDATE assets SET asset_type = ?, updated_at = ? WHERE id = ?",
        "path":        "UPDATE assets SET path = ?, updated_at = ? WHERE id = ?",
        "tags":        "UPDATE assets SET tags = ?, updated_at = ? WHERE id = ?",
        "poly_count":  "UPDATE assets SET poly_count = ?, updated_at = ? WHERE id = ?",
        "texture_res": "UPDATE assets SET texture_res = ?, updated_at = ? WHERE id = ?",
        "lod_count":   "UPDATE assets SET lod_count = ?, updated_at = ? WHERE id = ?",
        "status":      "UPDATE assets SET status = ?, updated_at = ? WHERE id = ?",
        "metadata":    "UPDATE assets SET metadata = ?, updated_at = ? WHERE id = ?",
    }

    def update_asset(self, asset_id: str, **kwargs) -> bool:
        """Update fields of an existing asset.

        Args:
            asset_id: The UUID of the asset to update.
            **kwargs: Field names and new values to set.
                Supported: name, asset_type, path, tags, poly_count,
                texture_res, lod_count, status, metadata.

        Returns:
            True if an asset was updated, False if asset_id not found.
        """
        if not kwargs:
            return False

        # Serialize list/dict fields to JSON
        if "tags" in kwargs and isinstance(kwargs["tags"], list):
            kwargs["tags"] = json.dumps(kwargs["tags"])
        if "metadata" in kwargs and isinstance(kwargs["metadata"], dict):
            kwargs["metadata"] = json.dumps(kwargs["metadata"])

        now = datetime.now(timezone.utc).isoformat()
        updated = False

        for col, value in kwargs.items():
            stmt = self._UPDATE_STMTS.get(col)
            if stmt is None:
                continue  # skip unknown columns silently
            cursor = self.conn.execute(stmt, (value, now, asset_id))
            if cursor.rowcount > 0:
                updated = True

        self.conn.commit()
        return updated

    def delete_asset(self, asset_id: str) -> bool:
        """Delete an asset by ID.

        Args:
            asset_id: The UUID of the asset to delete.

        Returns:
            True if an asset was deleted, False if not found.
        """
        cursor = self.conn.execute(
            "DELETE FROM assets WHERE id = ?", (asset_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def query_assets(
        self,
        asset_type: str | None = None,
        tags: list[str] | None = None,
        status: str | None = None,
        name_pattern: str | None = None,
        min_poly: int | None = None,
        max_poly: int | None = None,
    ) -> list[dict]:
        """Query assets with optional filters.

        Fetches all rows via a static prepared statement and applies filters
        in Python to avoid dynamic SQL construction.

        Args:
            asset_type: Filter by asset type.
            tags: Filter by tags (asset must have ALL specified tags).
            status: Filter by status.
            name_pattern: SQL LIKE pattern for name matching (uses fnmatch).
            min_poly: Minimum polygon count (inclusive).
            max_poly: Maximum polygon count (inclusive).

        Returns:
            List of asset dicts matching all specified filters.
        """
        cursor = self.conn.execute(
            "SELECT * FROM assets ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        results = [self._row_to_dict(row) for row in rows]

        # Apply filters in Python -- avoids dynamic SQL entirely
        if asset_type is not None:
            results = [a for a in results if a.get("asset_type") == asset_type]

        if status is not None:
            results = [a for a in results if a.get("status") == status]

        if name_pattern is not None:
            results = self._filter_by_name_pattern(results, name_pattern)

        if min_poly is not None:
            results = [
                a for a in results
                if a.get("poly_count") is not None and a["poly_count"] >= min_poly
            ]

        if max_poly is not None:
            results = [
                a for a in results
                if a.get("poly_count") is not None and a["poly_count"] <= max_poly
            ]

        if tags:
            results = [
                a for a in results
                if all(t in set(a.get("tags", [])) for t in tags)
            ]

        return results

    @staticmethod
    def _filter_by_name_pattern(assets: list[dict], pattern: str) -> list[dict]:
        """Filter assets by SQL LIKE-style name pattern (% and _ wildcards)."""
        import fnmatch
        # Convert SQL LIKE pattern to fnmatch: % -> *, _ -> ?
        glob = pattern.replace("%", "*").replace("_", "?")
        return [a for a in assets if fnmatch.fnmatch(a.get("name", ""), glob)]

    def export_metadata(self, asset_id: str, output_path: str) -> dict:
        """Export asset metadata as a JSON sidecar file.

        Args:
            asset_id: The UUID of the asset.
            output_path: Path for the output JSON file.

        Returns:
            Dict with asset_id, output_path, success status.
        """
        asset = self.get_asset(asset_id)
        if asset is None:
            return {
                "asset_id": asset_id,
                "output_path": output_path,
                "success": False,
                "error": f"Asset {asset_id} not found",
            }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asset, f, indent=2, default=str)

        return {
            "asset_id": asset_id,
            "output_path": output_path,
            "success": True,
        }

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Convert a sqlite3.Row to a plain dict with JSON fields deserialized."""
        d = dict(row)
        # Deserialize JSON fields
        for field in ("tags", "metadata"):
            if field in d and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
