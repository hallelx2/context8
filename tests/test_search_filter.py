"""Unit tests for SearchFilter and the per-backend WHERE/FilterBuilder
translations. These exercise pure logic — no DB or SDK required."""

from __future__ import annotations

from context8.storage.backend import SearchFilter
from context8.storage.sqlite_backend import _where_fragments


class TestSearchFilter:
    def test_default_is_empty(self):
        sf = SearchFilter()
        assert sf.is_empty() is True

    def test_any_field_makes_non_empty(self):
        assert SearchFilter(language="python").is_empty() is False
        assert SearchFilter(framework="react").is_empty() is False
        assert SearchFilter(error_type="TypeError").is_empty() is False
        assert SearchFilter(source="github").is_empty() is False
        assert SearchFilter(resolved_only=True).is_empty() is False
        assert SearchFilter(tags_any_of=["docker"]).is_empty() is False


class TestSQLiteWhereFragments:
    def test_empty_filter_yields_no_fragment(self):
        assert _where_fragments(None) == ("", [])
        assert _where_fragments(SearchFilter()) == ("", [])

    def test_language_lowercased(self):
        sql, params = _where_fragments(SearchFilter(language="Python"))
        assert "r.language = ?" in sql
        assert params == ["python"]

    def test_framework_lowercased(self):
        sql, params = _where_fragments(SearchFilter(framework="React"))
        assert "r.framework = ?" in sql
        assert params == ["react"]

    def test_error_type_preserved_as_is(self):
        sql, params = _where_fragments(SearchFilter(error_type="TypeError"))
        assert "r.error_type = ?" in sql
        assert params == ["TypeError"]  # case preserved

    def test_resolved_only_no_param(self):
        sql, params = _where_fragments(SearchFilter(resolved_only=True))
        assert "r.resolved = 1" in sql
        assert params == []

    def test_tags_any_of_uses_json_each(self):
        sql, params = _where_fragments(SearchFilter(tags_any_of=["docker", "wsl"]))
        assert "json_each(r.tags)" in sql
        assert "IN (?,?)" in sql
        assert params == ["docker", "wsl"]

    def test_combined_filter(self):
        sf = SearchFilter(
            language="python",
            framework="fastapi",
            error_type="ImportError",
            source="github",
            resolved_only=True,
            tags_any_of=["import"],
        )
        sql, params = _where_fragments(sf)
        # All clauses present, ANDed.
        assert sql.count(" AND ") >= 5  # leading " AND " + 5 inter-clause ANDs
        assert "r.language = ?" in sql
        assert "r.framework = ?" in sql
        assert "r.error_type = ?" in sql
        assert "r.source = ?" in sql
        assert "r.resolved = 1" in sql
        assert "json_each(r.tags)" in sql
        # Param order matches clause order in builder.
        assert params == ["python", "fastapi", "ImportError", "github", "import"]

    def test_fragment_starts_with_and_for_appending(self):
        # The contract: fragment is appended to a WHERE that already has
        # the MATCH clause, so it must start with " AND " (or be empty).
        sql, _ = _where_fragments(SearchFilter(language="python"))
        assert sql.startswith(" AND ")
