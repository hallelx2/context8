from __future__ import annotations

from context8.ingest.github import (
    FetchResult,
    GitHubIssueImporter,
    _detect_framework,
    _detect_language,
    _extract_error_type,
    _extract_first_code_block,
    _looks_resolved,
    _slug_to_id,
)


class TestSlug:
    def test_deterministic(self):
        assert _slug_to_id("vercel/next.js", 1234) == _slug_to_id("vercel/next.js", 1234)

    def test_distinct_per_repo(self):
        assert _slug_to_id("a/b", 1) != _slug_to_id("c/d", 1)

    def test_distinct_per_issue(self):
        assert _slug_to_id("a/b", 1) != _slug_to_id("a/b", 2)


class TestExtractors:
    def test_error_type_present(self):
        assert _extract_error_type("Got TypeError on line 4") == "TypeError"

    def test_error_type_missing(self):
        assert _extract_error_type("things broke") == ""

    def test_code_block(self):
        body = "Here's the code:\n\n```js\nconst x = 1;\n```\nmore text"
        assert _extract_first_code_block(body) == "const x = 1;"

    def test_no_code_block(self):
        assert _extract_first_code_block("plain text") == ""


class TestDetection:
    def test_language_from_label(self):
        assert _detect_language("user/repo", "", ["typescript"]) == "typescript"

    def test_framework_from_repo_name(self):
        assert _detect_framework("vercel/next.js") == "nextjs"

    def test_framework_unknown(self):
        assert _detect_framework("user/random-repo") == ""


class TestResolutionDetection:
    def test_positive_markers(self):
        assert _looks_resolved("This is fixed in v2.0")
        assert _looks_resolved("workaround: use --legacy-peer-deps")
        assert _looks_resolved("the fix is to update tsconfig")

    def test_no_markers(self):
        assert not _looks_resolved("thanks for reporting")


class TestImporterRecordBuilding:
    def test_skips_when_no_resolution(self):
        importer = GitHubIssueImporter()
        fetched = FetchResult(
            issues=[
                {"number": 1, "title": "broken", "body": "help", "html_url": "u", "labels": []}
            ],
            comments_by_issue={1: [{"body": "thanks for reporting"}]},
        )
        records = importer.to_records("user/repo", fetched, require_resolution=True)
        assert records == []

    def test_keeps_when_comment_has_resolution(self):
        importer = GitHubIssueImporter()
        fetched = FetchResult(
            issues=[
                {
                    "number": 42,
                    "title": "TypeError on init",
                    "body": "code: ```js\nx.map()\n```",
                    "html_url": "https://github.com/user/repo/issues/42",
                    "labels": [{"name": "bug"}, {"name": "javascript"}],
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-02-01T00:00:00Z",
                }
            ],
            comments_by_issue={
                42: [{"body": "the fix is to add a null check before .map()"}]
            },
        )
        records = importer.to_records("user/repo", fetched, require_resolution=True)
        assert len(records) == 1
        record = records[0]
        assert record.id == _slug_to_id("user/repo", 42)
        assert record.error_type == "TypeError"
        assert record.language == "javascript"
        assert record.source == "github:user/repo"
        assert record.resolved is True
        assert "bug" in record.tags
