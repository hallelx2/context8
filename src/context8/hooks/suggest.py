"""Auto-suggest hook — searches Context8 when an error is detected.

Designed to run as a Claude Code afterError hook. When the agent hits
an error, this script searches Context8 and prints matching solutions
to stdout so the agent sees them in its next context window.

Hook config (.claude/settings.json):
  "hooks": {
    "afterError": [{
      "command": "python -m context8.hooks.suggest"
    }]
  }

Reads the error from stdin (piped by the hook system).
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    # Read hook input from stdin
    try:
        raw = sys.stdin.read()
    except Exception:
        return

    if not raw.strip():
        return

    # Try to parse as JSON (Claude Code hook format)
    error_text = raw.strip()
    try:
        data = json.loads(raw)
        error_text = data.get("error", data.get("message", data.get("output", raw)))
    except (json.JSONDecodeError, TypeError):
        pass

    if not error_text or len(error_text) < 15:
        return

    # Truncate for search
    query = error_text[:500]

    try:
        from context8.embeddings import EmbeddingService
        from context8.search import SearchEngine
        from context8.storage import StorageService

        storage = StorageService()
        embeddings = EmbeddingService()
        engine = SearchEngine(storage, embeddings)

        results = engine.search(query=query, limit=2, score_threshold=0.3)

        if not results:
            return

        # Print suggestion to stdout for the agent to see
        print("\n💡 Context8 found similar problems that were solved before:\n")
        for i, r in enumerate(results, 1):
            rec = r.record
            print(f"  [{i}] {rec.problem_text[:120]}")
            print(f"      Fix: {rec.solution_text[:200]}")
            if rec.code_diff:
                print(f"      Diff: {rec.code_diff[:150]}")
            print(f"      Confidence: {rec.confidence:.0%}  Score: {r.score:.3f}")
            print()

        storage.close()

    except ImportError:
        pass  # actian-vectorai not installed — skip silently
    except Exception:
        pass  # DB not running or collection not init — skip silently


if __name__ == "__main__":
    main()
