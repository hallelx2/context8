from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass

from ..models import ResolutionRecord

logger = logging.getLogger("context8.ingest.github")

GITHUB_NAMESPACE = uuid.UUID("c0c8c0c8-0000-0000-0000-000000000067")
DEFAULT_USER_AGENT = "context8-importer/1.0"
DEFAULT_PER_PAGE = 50

_ERROR_PATTERN = re.compile(r"\b([A-Z][A-Za-z]*(?:Error|Exception|Warning))\b")
_FENCED_CODE = re.compile(r"```[a-zA-Z0-9_+-]*\n([\s\S]*?)```", re.MULTILINE)


def _slug_to_id(repo: str, issue_number: int) -> str:
    return str(uuid.uuid5(GITHUB_NAMESPACE, f"{repo}#{issue_number}"))


def _strip_html_comments(text: str) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", text or "")


def _extract_error_type(text: str) -> str:
    if not text:
        return ""
    match = _ERROR_PATTERN.search(text)
    return match.group(1) if match else ""


def _extract_first_code_block(text: str) -> str:
    if not text:
        return ""
    match = _FENCED_CODE.search(text)
    return match.group(1).strip() if match else ""


def _detect_language(repo: str, body: str, labels: list[str]) -> str:
    label_blob = " ".join(labels).lower()
    body_blob = (body or "").lower()
    blob = f"{label_blob} {body_blob} {repo.lower()}"
    for marker, lang in [
        ("typescript", "typescript"),
        ("javascript", "javascript"),
        ("python", "python"),
        ("rust", "rust"),
        ("golang", "go"),
        ("kotlin", "kotlin"),
        ("swift", "swift"),
    ]:
        if marker in blob:
            return lang
    return ""


def _detect_framework(repo: str) -> str:
    name = repo.split("/")[-1].lower()
    mapping = {
        "next.js": "nextjs",
        "react": "react",
        "vite": "vite",
        "fastapi": "fastapi",
        "django": "django",
        "transformers": "transformers",
        "pytorch": "pytorch",
        "tensorflow": "tensorflow",
        "vue": "vue",
        "svelte": "svelte",
    }
    return mapping.get(name, "")


def _looks_resolved(comment_body: str) -> bool:
    if not comment_body:
        return False
    blob = comment_body.lower()
    markers = [
        "fixed in",
        "fixed by",
        "resolved in",
        "this is fixed",
        "should be fixed",
        "fix is to",
        "you can fix this",
        "the fix is",
        "workaround:",
        "solution:",
    ]
    return any(m in blob for m in markers)


@dataclass
class FetchResult:
    issues: list[dict]
    comments_by_issue: dict[int, list[dict]]


class GitHubIssueImporter:
    def __init__(
        self,
        token: str | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        request_timeout: float = 15.0,
        sleep_between_requests: float = 0.25,
    ):
        self.token = token or os.environ.get("GITHUB_TOKEN") or ""
        self.user_agent = user_agent
        self.request_timeout = request_timeout
        self.sleep_between_requests = sleep_between_requests

    def fetch(
        self,
        repo: str,
        labels: list[str] | None = None,
        max_issues: int = 50,
        state: str = "closed",
    ) -> FetchResult:
        params = {
            "state": state,
            "per_page": str(min(DEFAULT_PER_PAGE, max_issues)),
            "sort": "updated",
            "direction": "desc",
        }
        if labels:
            params["labels"] = ",".join(labels)

        issues: list[dict] = []
        comments_by_issue: dict[int, list[dict]] = {}
        page = 1
        while len(issues) < max_issues:
            params["page"] = str(page)
            url = f"https://api.github.com/repos/{repo}/issues?{urllib.parse.urlencode(params)}"
            batch = self._get_json(url)
            if not isinstance(batch, list) or not batch:
                break

            for raw in batch:
                if "pull_request" in raw:
                    continue
                issues.append(raw)
                if len(issues) >= max_issues:
                    break

            page += 1
            if len(batch) < int(params["per_page"]):
                break

        for issue in issues:
            number = issue.get("number")
            if number is None:
                continue
            comments_url = (
                f"https://api.github.com/repos/{repo}/issues/{number}/comments?per_page=20"
            )
            try:
                comments = self._get_json(comments_url)
                if isinstance(comments, list):
                    comments_by_issue[number] = comments
            except Exception as e:
                logger.debug(f"comments fetch failed for {repo}#{number}: {e}")
                comments_by_issue[number] = []

        return FetchResult(issues=issues, comments_by_issue=comments_by_issue)

    def to_records(
        self,
        repo: str,
        fetched: FetchResult,
        require_resolution: bool = True,
    ) -> list[ResolutionRecord]:
        records: list[ResolutionRecord] = []
        for issue in fetched.issues:
            number = issue.get("number")
            if number is None:
                continue

            title = issue.get("title", "").strip()
            body = _strip_html_comments(issue.get("body") or "")
            labels = [str(lbl.get("name", "")) for lbl in issue.get("labels") or []]
            comments = fetched.comments_by_issue.get(number, [])

            resolution_comment = self._pick_resolution_comment(
                comments, allow_fallback=not require_resolution
            )
            if require_resolution and resolution_comment is None:
                continue

            solution_text = (
                _strip_html_comments(resolution_comment.get("body") or "")
                if resolution_comment
                else ""
            )

            if require_resolution and not solution_text.strip():
                continue

            problem_text = title if not body else f"{title}\n\n{body}"
            problem_text = _truncate(problem_text, 2000)
            solution_text = _truncate(solution_text, 2000)

            record = ResolutionRecord(
                id=_slug_to_id(repo, number),
                problem_text=problem_text,
                solution_text=solution_text,
                error_type=_extract_error_type(f"{title}\n{body}"),
                code_snippet=_extract_first_code_block(body),
                language=_detect_language(repo, body, labels),
                framework=_detect_framework(repo),
                tags=[lbl.lower() for lbl in labels if lbl],
                confidence=0.75 if resolution_comment else 0.5,
                resolved=resolution_comment is not None,
                source=f"github:{repo}",
                file_path=issue.get("html_url", ""),
                timestamp=issue.get("created_at", "") or "",
                last_seen=issue.get("updated_at", "") or "",
            )
            records.append(record)
        return records

    def _pick_resolution_comment(
        self,
        comments: list[dict],
        allow_fallback: bool = False,
    ) -> dict | None:
        if not comments:
            return None
        for comment in reversed(comments):
            if _looks_resolved(comment.get("body", "")):
                return comment
        if allow_fallback:
            return comments[-1]
        return None

    def _get_json(self, url: str):
        if self.sleep_between_requests:
            time.sleep(self.sleep_between_requests)

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.request_timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise RuntimeError(
                    "GitHub API returned 403 (rate limited). "
                    "Set GITHUB_TOKEN to raise the limit."
                ) from e
            raise


def _truncate(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."
