# Plan 03 — Storage Schema & Collection Design

## Objective

Design and implement the Actian VectorAI DB collection schema for Context8. This defines how resolution records are stored, indexed, and organized for efficient retrieval.

## Collection Design

### Collection: `context8_store`

This is the single primary collection. All resolution records live here, differentiated by metadata filters.

```python
from actian_vectorai import (
    VectorParams,
    Distance,
    SparseVectorParams,
    HnswConfigDiff,
)

COLLECTION_NAME = "context8_store"

# Named dense vectors — three semantic spaces
VECTORS_CONFIG = {
    "problem": VectorParams(
        size=384,
        distance=Distance.Cosine,
    ),
    "solution": VectorParams(
        size=384,
        distance=Distance.Cosine,
    ),
    "code_context": VectorParams(
        size=768,
        distance=Distance.Cosine,
    ),
}

# Sparse vectors for BM25-style keyword matching
SPARSE_VECTORS_CONFIG = {
    "keywords": SparseVectorParams(),
}

# HNSW tuning for our expected scale (1K-100K records)
HNSW_CONFIG = HnswConfigDiff(
    m=16,              # Default — good balance for <100K points
    ef_construct=200,  # Default — sufficient accuracy for our scale
)
```

### Point Structure

Each point represents one **resolution record** — a problem that was encountered and solved:

```python
from actian_vectorai import PointStruct, SparseVector
import uuid
from datetime import datetime

point = PointStruct(
    id=str(uuid.uuid4()),  # UUID string ID
    
    vector={
        # Named dense vectors
        "problem":      problem_embedding,       # list[float], 384d
        "solution":     solution_embedding,       # list[float], 384d
        "code_context": code_context_embedding,   # list[float], 768d
        
        # Sparse vector
        "keywords": SparseVector(
            indices=keyword_indices,    # list[int]
            values=keyword_values,      # list[float]
        ),
    },
    
    payload={
        # === Filterable Fields (indexed) ===
        "language":         "python",
        "framework":        "django",
        "error_type":       "ImportError",
        "agent":            "claude-code",
        "os":               "windows",
        "resolved":         True,
        "timestamp":        datetime.utcnow().isoformat(),
        
        # === Searchable Tags ===
        "tags":             ["import", "virtual-env", "pip"],
        "libraries":        ["django@4.2", "celery@5.3"],
        
        # === Content Fields (returned, not indexed) ===
        "problem_text":     "ModuleNotFoundError: No module named 'celery'",
        "solution_text":    "Celery was installed in system Python, not in the project venv. Fix: activate venv first, then pip install celery",
        "code_snippet":     "from celery import Celery\napp = Celery('myproject')",
        "code_diff":        "# No code change — environment fix",
        "stack_trace":      "Traceback (most recent call last):\n  File \"manage.py\", line 22...",
        "file_path":        "myproject/celery.py",
        
        # === Analytics Fields ===
        "confidence":       0.95,
        "occurrence_count": 1,
        "resolution_time_secs": 12,
        "last_seen":        datetime.utcnow().isoformat(),
        "source":           "local",  # "local" | "cloud" | "community"
    },
)
```

### Field Index Strategy

Actian VectorAI DB supports payload field indexing for faster filtered search. We declare indexes at collection creation time (since `create_field_index()` is not yet implemented server-side):

**Priority indexes (filter frequently):**

| Field | Type | Why |
|-------|------|-----|
| `language` | Keyword | Every search filters by language |
| `framework` | Keyword | Second most common filter |
| `error_type` | Keyword | Narrow to specific error class |
| `resolved` | Bool | Only show confirmed solutions |
| `timestamp` | Datetime | Recency sorting/filtering |
| `agent` | Keyword | Filter by agent type |

**Secondary indexes (filter occasionally):**

| Field | Type | Why |
|-------|------|-----|
| `os` | Keyword | Environment-specific issues |
| `tags` | Keyword | User-defined categorization |
| `confidence` | Float | Filter out low-confidence solutions |

**Note:** Since `create_field_index()` is `UNIMPLEMENTED` on the server, we rely on the collection's natural indexing. For hackathon scale (<10K records), this has minimal performance impact. For production, we would declare indexes at collection creation time.

## Data Model (Python)

```python
# src/context8/models.py

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4


@dataclass
class ResolutionRecord:
    """A problem-solution pair stored in Context8."""
    
    # Problem description
    problem_text: str
    error_type: str = ""
    stack_trace: str = ""
    
    # Solution description
    solution_text: str = ""
    code_snippet: str = ""
    code_diff: str = ""
    
    # Metadata
    language: str = ""
    framework: str = ""
    libraries: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    agent: str = "unknown"
    os: str = ""
    file_path: str = ""
    
    # Status
    resolved: bool = True
    confidence: float = 0.5
    
    # Auto-populated
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    occurrence_count: int = 1
    resolution_time_secs: int = 0
    last_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "local"

    def to_payload(self) -> dict:
        """Convert to Actian payload format."""
        return {
            "problem_text": self.problem_text,
            "error_type": self.error_type,
            "stack_trace": self.stack_trace,
            "solution_text": self.solution_text,
            "code_snippet": self.code_snippet,
            "code_diff": self.code_diff,
            "language": self.language,
            "framework": self.framework,
            "libraries": self.libraries,
            "tags": self.tags,
            "agent": self.agent,
            "os": self.os,
            "file_path": self.file_path,
            "resolved": self.resolved,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "occurrence_count": self.occurrence_count,
            "resolution_time_secs": self.resolution_time_secs,
            "last_seen": self.last_seen,
            "source": self.source,
        }

    @classmethod
    def from_payload(cls, id: str, payload: dict) -> ResolutionRecord:
        """Reconstruct from Actian payload."""
        return cls(
            id=id,
            problem_text=payload.get("problem_text", ""),
            error_type=payload.get("error_type", ""),
            stack_trace=payload.get("stack_trace", ""),
            solution_text=payload.get("solution_text", ""),
            code_snippet=payload.get("code_snippet", ""),
            code_diff=payload.get("code_diff", ""),
            language=payload.get("language", ""),
            framework=payload.get("framework", ""),
            libraries=payload.get("libraries", []),
            tags=payload.get("tags", []),
            agent=payload.get("agent", "unknown"),
            os=payload.get("os", ""),
            file_path=payload.get("file_path", ""),
            resolved=payload.get("resolved", True),
            confidence=payload.get("confidence", 0.5),
            timestamp=payload.get("timestamp", ""),
            occurrence_count=payload.get("occurrence_count", 1),
            resolution_time_secs=payload.get("resolution_time_secs", 0),
            last_seen=payload.get("last_seen", ""),
            source=payload.get("source", "local"),
        )


@dataclass
class SearchResult:
    """A search result from Context8."""
    record: ResolutionRecord
    score: float
    match_type: str = "hybrid"  # "dense", "sparse", "hybrid"
```

## Storage Service

```python
# src/context8/storage.py

from __future__ import annotations
from typing import Optional

from actian_vectorai import (
    VectorAIClient,
    AsyncVectorAIClient,
    VectorParams,
    Distance,
    SparseVectorParams,
    PointStruct,
    SparseVector,
    HnswConfigDiff,
)

from .models import ResolutionRecord

COLLECTION_NAME = "context8_store"


class StorageService:
    """Manages Actian VectorAI DB operations for Context8."""

    def __init__(self, host: str = "localhost", port: int = 50051):
        self.url = f"{host}:{port}"
        self._client: Optional[VectorAIClient] = None

    @property
    def client(self) -> VectorAIClient:
        if self._client is None:
            self._client = VectorAIClient(self.url)
        return self._client

    def initialize(self) -> None:
        """Create collection if it doesn't exist."""
        if self.client.collections.exists(COLLECTION_NAME):
            return

        self.client.collections.create(
            COLLECTION_NAME,
            vectors_config={
                "problem": VectorParams(size=384, distance=Distance.Cosine),
                "solution": VectorParams(size=384, distance=Distance.Cosine),
                "code_context": VectorParams(size=768, distance=Distance.Cosine),
            },
            sparse_vectors_config={
                "keywords": SparseVectorParams(),
            },
            hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
        )

    def store_record(
        self,
        record: ResolutionRecord,
        vectors: dict,
    ) -> str:
        """Store a resolution record with its vectors.
        
        Args:
            record: The resolution record to store
            vectors: Dict from EmbeddingService.embed_record()
            
        Returns:
            The record ID
        """
        point = PointStruct(
            id=record.id,
            vector={
                "problem": vectors["problem"],
                "solution": vectors["solution"],
                "code_context": vectors["code_context"],
                "keywords": SparseVector(
                    indices=vectors["keywords_indices"],
                    values=vectors["keywords_values"],
                ),
            },
            payload=record.to_payload(),
        )
        
        self.client.points.upsert(COLLECTION_NAME, [point])
        return record.id

    def get_record(self, record_id: str) -> Optional[ResolutionRecord]:
        """Retrieve a record by ID."""
        results = self.client.points.get(
            COLLECTION_NAME,
            ids=[record_id],
            with_payload=True,
        )
        if not results:
            return None
        return ResolutionRecord.from_payload(results[0].id, results[0].payload)

    def count(self) -> int:
        """Get total number of records."""
        return self.client.points.count(COLLECTION_NAME)

    def delete_record(self, record_id: str) -> None:
        """Delete a record by ID."""
        self.client.points.delete_by_ids(COLLECTION_NAME, [record_id])

    def close(self) -> None:
        """Close the client connection."""
        if self._client:
            self._client.close()
            self._client = None
```

## Testing Criteria

- [ ] Collection creates with correct named vectors (3 dense + 1 sparse)
- [ ] Collection creation is idempotent (no error if already exists)
- [ ] Points can be upserted with all named vectors + sparse + payload
- [ ] Points can be retrieved by ID with full payload
- [ ] Points can be deleted by ID
- [ ] Count returns correct number after inserts/deletes
- [ ] ResolutionRecord serializes/deserializes correctly (to_payload / from_payload)
- [ ] UUID generation produces unique IDs

## Files Created

```
src/context8/
├── __init__.py
├── models.py          # ResolutionRecord, SearchResult dataclasses
├── storage.py         # StorageService — Actian VectorAI DB operations
└── config.py          # Collection name, vector dimensions, constants
```

## Estimated Time: 45 minutes

## Dependencies: Plan 01 (running DB), Plan 02 (embedding dimensions must match)

## Next: Plan 04 (MCP Server)
