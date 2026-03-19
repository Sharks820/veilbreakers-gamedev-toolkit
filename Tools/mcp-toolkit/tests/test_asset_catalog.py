"""Unit tests for SQLite asset catalog.

Uses in-memory SQLite (:memory:) -- no file system needed.
"""

import pytest


# ---------------------------------------------------------------------------
# AssetCatalog tests
# ---------------------------------------------------------------------------


class TestAssetCatalogInit:
    """Test catalog initialization."""

    def test_creates_table_schema_on_init(self):
        """AssetCatalog creates assets table on init with fresh database."""
        from veilbreakers_mcp.shared.asset_catalog import AssetCatalog

        catalog = AssetCatalog(":memory:")
        # Verify table exists by querying sqlite_master
        cursor = catalog.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='assets'"
        )
        assert cursor.fetchone() is not None
        catalog.close()


class TestAssetCatalogCRUD:
    """Test basic CRUD operations."""

    def _make_catalog(self):
        from veilbreakers_mcp.shared.asset_catalog import AssetCatalog
        return AssetCatalog(":memory:")

    def test_add_asset_returns_asset_id(self):
        """add_asset stores an entry and returns a string asset_id."""
        catalog = self._make_catalog()
        asset_id = catalog.add_asset(
            name="Barrel",
            asset_type="prop",
            path="/models/barrel.glb",
            tags=["wood", "container"],
            poly_count=5000,
            texture_res="2048x2048",
        )
        assert isinstance(asset_id, str)
        assert len(asset_id) > 0
        catalog.close()

    def test_get_asset_returns_full_metadata(self):
        """get_asset returns a dict with all fields by asset_id."""
        catalog = self._make_catalog()
        asset_id = catalog.add_asset(
            name="Sword",
            asset_type="weapon",
            path="/models/sword.glb",
            tags=["metal", "weapon"],
            poly_count=8000,
        )
        asset = catalog.get_asset(asset_id)
        assert asset is not None
        assert asset["name"] == "Sword"
        assert asset["asset_type"] == "weapon"
        assert asset["path"] == "/models/sword.glb"
        assert "metal" in asset["tags"]
        assert asset["poly_count"] == 8000
        catalog.close()

    def test_update_asset_modifies_existing(self):
        """update_asset modifies an existing entry's fields."""
        catalog = self._make_catalog()
        asset_id = catalog.add_asset(
            name="Shield",
            asset_type="weapon",
            path="/models/shield.glb",
        )
        result = catalog.update_asset(asset_id, poly_count=3000, status="processed")
        assert result is True
        asset = catalog.get_asset(asset_id)
        assert asset["poly_count"] == 3000
        assert asset["status"] == "processed"
        catalog.close()

    def test_delete_asset_removes_entry(self):
        """delete_asset removes an entry so get_asset returns None."""
        catalog = self._make_catalog()
        asset_id = catalog.add_asset(
            name="Potion",
            asset_type="prop",
            path="/models/potion.glb",
        )
        result = catalog.delete_asset(asset_id)
        assert result is True
        assert catalog.get_asset(asset_id) is None
        catalog.close()


class TestAssetCatalogQuery:
    """Test query/filter operations."""

    def _make_catalog_with_data(self):
        from veilbreakers_mcp.shared.asset_catalog import AssetCatalog
        catalog = AssetCatalog(":memory:")
        catalog.add_asset("Barrel", "prop", "/barrel.glb", tags=["wood", "container"], poly_count=5000)
        catalog.add_asset("Sword", "weapon", "/sword.glb", tags=["metal", "weapon"], poly_count=8000)
        catalog.add_asset("Shield", "weapon", "/shield.glb", tags=["metal", "armor"], poly_count=3000)
        catalog.add_asset("Tree", "environment", "/tree.glb", tags=["wood", "nature"], poly_count=12000)
        return catalog

    def test_query_by_tag_returns_only_matching(self):
        """query_assets with tag filter returns only assets with that tag."""
        catalog = self._make_catalog_with_data()
        results = catalog.query_assets(tags=["metal"])
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"Sword", "Shield"}
        catalog.close()

    def test_query_by_type_returns_only_that_type(self):
        """query_assets with type filter returns only assets of that type."""
        catalog = self._make_catalog_with_data()
        results = catalog.query_assets(asset_type="weapon")
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"Sword", "Shield"}
        catalog.close()

    def test_query_by_name_pattern(self):
        """query_assets with name_pattern uses LIKE matching."""
        catalog = self._make_catalog_with_data()
        results = catalog.query_assets(name_pattern="Sw%")
        assert len(results) == 1
        assert results[0]["name"] == "Sword"
        catalog.close()

    def test_query_by_poly_range(self):
        """query_assets with min_poly/max_poly filters by polygon count."""
        catalog = self._make_catalog_with_data()
        results = catalog.query_assets(min_poly=4000, max_poly=9000)
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"Barrel", "Sword"}
        catalog.close()

    def test_query_no_filters_returns_all(self):
        """query_assets with no filters returns all assets."""
        catalog = self._make_catalog_with_data()
        results = catalog.query_assets()
        assert len(results) == 4
        catalog.close()
