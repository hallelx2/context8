# Plan 07 — Cold Start Problem & Data Seeding

## The Cold Start Problem

Context8 is only valuable when it has enough data to return useful search results. A brand-new instance has zero records. When an agent searches and finds nothing, it loses trust in the tool and stops using it. This is the cold start death spiral:

```
Empty DB → No results → Agent stops searching → DB stays empty → No value
```

## Mitigation Strategies

### Strategy 1: Curated Seed Dataset (Day 1 Solution)

Pre-populate Context8 with 50-100 high-quality problem-solution pairs covering the most common "long tail" problems across popular ecosystems.

**Sources for seed data:**
1. **Personal experience** — Problems you've solved that aren't in docs
2. **Stack Overflow "uncommon" tag** — Answers with <10 votes but marked as accepted
3. **GitHub Issues** — Resolved issues on popular repos with "workaround" in comments
4. **AI agent logs** — Extract from past Claude Code / Cursor sessions

**Seed data categories:**

| Category | Examples | Count |
|----------|---------|-------|
| Python environment | venv conflicts, pip version hell, conda vs pip | 8 |
| Node/npm | peer dependency conflicts, ESM vs CJS, resolution errors | 8 |
| React/Next.js | Hydration mismatches, Suspense edge cases, SSR issues | 8 |
| TypeScript | Complex type errors, generic constraints, declaration files | 6 |
| Docker | Port conflicts, volume permissions, build cache issues | 6 |
| Database | Connection pool exhaustion, migration conflicts, ORM quirks | 6 |
| Git | Merge conflicts in lockfiles, submodule issues, LFS problems | 4 |
| Rust | Borrow checker patterns, WASM targets, lifetime issues | 4 |
| Cross-platform | Windows path issues, line endings, case sensitivity | 5 |
| Build tools | Webpack/Vite/esbuild config conflicts, polyfill issues | 5 |

**Total: ~60 seed records**

### Strategy 2: Auto-Learning Mode

During the first 2 weeks of use, Context8 can be more aggressive about logging:

```python
# config.py
COLD_START_MODE = True  # Auto-log more aggressively
COLD_START_THRESHOLD = 100  # Exit cold start after 100 records

# In server.py, when logging:
if storage_service.count() < COLD_START_THRESHOLD:
    # Lower the dedup threshold (log more variations)
    dedup_threshold = 0.98  # vs normal 0.95
    # Lower the "non-trivial" bar
    # Accept records even for moderately simple fixes
```

### Strategy 3: Community Seed Packs

Distribute pre-built seed datasets as downloadable packs:

```bash
# Install a community seed pack
python -m context8 --seed-pack react-ecosystem
python -m context8 --seed-pack python-ml
python -m context8 --seed-pack devops-docker
```

This is a v2 feature but the architecture supports it from day 1.

## Seed Data Implementation

```python
# src/context8/seed.py

"""Seed Context8 with curated problem-solution pairs."""

from __future__ import annotations

from .models import ResolutionRecord
from .embeddings import EmbeddingService
from .storage import StorageService


SEED_DATA: list[dict] = [
    # === Python Environment ===
    {
        "problem_text": "ModuleNotFoundError: No module named 'cv2' even though opencv-python is installed via pip",
        "solution_text": "opencv-python was installed in a different Python environment (system vs venv). Fix: deactivate and reactivate venv, then pip install opencv-python-headless. Use 'which python' to verify correct interpreter.",
        "error_type": "ModuleNotFoundError",
        "language": "python",
        "tags": ["virtual-env", "opencv", "import"],
        "confidence": 0.95,
    },
    {
        "problem_text": "pip install fails with 'externally-managed-environment' error on Ubuntu 23.04+",
        "solution_text": "PEP 668 marks system Python as externally-managed. Fix: use 'python -m venv .venv && source .venv/bin/activate' before pip install. Or use pipx for CLI tools. Never use --break-system-packages.",
        "error_type": "ExternallyManagedEnvironment",
        "language": "python",
        "framework": "",
        "tags": ["pip", "pep668", "ubuntu", "venv"],
        "confidence": 0.98,
    },
    {
        "problem_text": "ImportError: cannot import name 'Annotated' from 'typing' with Python 3.8",
        "solution_text": "typing.Annotated was added in Python 3.9. For 3.8 compat: 'from typing_extensions import Annotated'. Add typing-extensions to requirements.",
        "error_type": "ImportError",
        "language": "python",
        "tags": ["typing", "backport", "python-version"],
        "confidence": 0.97,
    },
    {
        "problem_text": "RuntimeError: asyncio.run() cannot be called from a running event loop (Jupyter notebook)",
        "solution_text": "Jupyter already runs an event loop. Use 'import nest_asyncio; nest_asyncio.apply()' at the top of the notebook. Or use 'await coroutine()' directly in cells.",
        "error_type": "RuntimeError",
        "language": "python",
        "framework": "jupyter",
        "tags": ["asyncio", "jupyter", "event-loop"],
        "confidence": 0.96,
    },
    # === Node.js / npm ===
    {
        "problem_text": "ERESOLVE unable to resolve dependency tree - npm peer dependency conflict",
        "solution_text": "npm 7+ enforces strict peer deps. Fix options: 1) npm install --legacy-peer-deps (quick fix), 2) Add overrides in package.json to force version, 3) Upgrade conflicting packages. Option 2 is most robust.",
        "error_type": "ERESOLVE",
        "language": "javascript",
        "tags": ["npm", "peer-deps", "dependency-conflict"],
        "confidence": 0.94,
    },
    {
        "problem_text": "ERR_REQUIRE_ESM: require() of ES Module not supported - when importing an ESM-only package in CommonJS",
        "solution_text": "Package uses ESM only (type: module). Options: 1) Use dynamic import: const pkg = await import('package'), 2) Add 'type': 'module' to your package.json and rename .js to .mjs, 3) Use an older version that still supports CJS.",
        "error_type": "ERR_REQUIRE_ESM",
        "language": "javascript",
        "tags": ["esm", "commonjs", "import", "require"],
        "confidence": 0.93,
    },
    # === React / Next.js ===
    {
        "problem_text": "Hydration failed because the initial UI does not match what was rendered on the server - Next.js",
        "solution_text": "Common causes: 1) Using Date.now() or Math.random() in render, 2) Browser extensions modifying DOM, 3) Invalid HTML nesting (p inside p, div inside p). Fix: Use suppressHydrationWarning for intentional mismatches, useEffect for client-only values, or fix HTML structure.",
        "error_type": "HydrationError",
        "language": "typescript",
        "framework": "nextjs",
        "tags": ["hydration", "ssr", "nextjs"],
        "confidence": 0.92,
    },
    {
        "problem_text": "Cannot update a component while rendering a different component - React setState in render",
        "solution_text": "Calling setState during another component's render violates React rules. Move the state update to useEffect, an event handler, or useMemo. Common culprit: updating parent state in child's render body.",
        "error_type": "ReactRenderError",
        "language": "typescript",
        "framework": "react",
        "tags": ["setState", "render", "useEffect"],
        "confidence": 0.95,
    },
    # === Docker ===
    {
        "problem_text": "Docker bind mount volume shows empty directory - files from host not visible in container",
        "solution_text": "On Windows with WSL2 Docker: ensure the path uses Linux format (/mnt/c/...) not Windows (C:\\\\...). On Mac: the host directory must be in Docker Desktop's file sharing settings. Also check: container might overwrite the mount with a build step (use named volumes for node_modules).",
        "error_type": "VolumeError",
        "language": "",
        "framework": "docker",
        "tags": ["volume", "bind-mount", "wsl2", "file-sharing"],
        "confidence": 0.91,
    },
    {
        "problem_text": "docker compose up fails with 'port is already allocated' on port 5432",
        "solution_text": "Another process (often a local PostgreSQL service) is using the port. Fix: 1) Stop the local service: sudo systemctl stop postgresql, 2) Or remap the port in docker-compose.yml: '5433:5432'. Find what's using it: lsof -i :5432 or netstat -tlnp | grep 5432.",
        "error_type": "PortConflict",
        "language": "",
        "framework": "docker",
        "tags": ["port-conflict", "postgresql", "docker-compose"],
        "confidence": 0.97,
    },
    # === TypeScript ===
    {
        "problem_text": "Type 'X' is not assignable to type 'never' - TypeScript array with conditional types",
        "solution_text": "This happens when TypeScript narrows an array to never[] because it can't infer the element type. Fix: explicitly type the array: const items: (TypeA | TypeB)[] = []. Or use 'as const' for literal arrays.",
        "error_type": "TS2322",
        "language": "typescript",
        "tags": ["type-narrowing", "never", "array-type"],
        "confidence": 0.93,
    },
    {
        "problem_text": "Cannot find module './Component' or its corresponding type declarations - TypeScript with path aliases",
        "solution_text": "tsconfig paths are only for TypeScript compiler, not the bundler. Fix: 1) Configure paths in BOTH tsconfig.json AND bundler (vite.config.ts resolve.alias, webpack resolve.alias, etc.), 2) Or use tsconfig-paths package for Node.js runtime.",
        "error_type": "TS2307",
        "language": "typescript",
        "tags": ["path-aliases", "tsconfig", "module-resolution"],
        "confidence": 0.96,
    },
    # === Database ===
    {
        "problem_text": "Connection pool exhausted - too many clients already in PostgreSQL with Prisma in serverless",
        "solution_text": "Serverless functions create new connections on each invocation, exhausting the pool. Fix: 1) Use connection pooler like PgBouncer or Supabase Pooler, 2) Set connection_limit=1 in Prisma datasource, 3) Use Prisma Accelerate or Data Proxy for managed pooling.",
        "error_type": "ConnectionPoolExhausted",
        "language": "typescript",
        "framework": "prisma",
        "tags": ["connection-pool", "serverless", "postgresql", "pgbouncer"],
        "confidence": 0.94,
    },
    # === Git ===
    {
        "problem_text": "Git merge conflict in package-lock.json / yarn.lock - massive unresolvable diff",
        "solution_text": "Never manually resolve lockfile conflicts. Fix: 1) Accept either version: git checkout --theirs package-lock.json, 2) Delete lockfile: rm package-lock.json, 3) Regenerate: npm install, 4) Commit the fresh lockfile. Same pattern for yarn.lock and pnpm-lock.yaml.",
        "error_type": "MergeConflict",
        "language": "",
        "tags": ["git", "merge-conflict", "lockfile", "npm"],
        "confidence": 0.98,
    },
    # === Cross-Platform ===
    {
        "problem_text": "ENOENT: no such file or directory - Windows path too long (>260 characters) in node_modules",
        "solution_text": "Windows has 260-char path limit by default. Fix: 1) Enable long paths: reg add HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1, 2) Use npm config set prefix to shorten base path, 3) Move project closer to root (C:\\dev\\project).",
        "error_type": "ENOENT",
        "language": "javascript",
        "tags": ["windows", "long-path", "node_modules", "enoent"],
        "confidence": 0.92,
    },
    # === Build Tools ===
    {
        "problem_text": "Vite prebundling failed - 'X is not a function' after adding new dependency",
        "solution_text": "Vite's pre-bundling cache is stale. Fix: 1) Delete node_modules/.vite directory, 2) Run: npx vite --force, 3) Or add the package to optimizeDeps.include in vite.config.ts to force pre-bundling.",
        "error_type": "PrebundleError",
        "language": "typescript",
        "framework": "vite",
        "tags": ["vite", "prebundling", "cache", "dependency"],
        "confidence": 0.94,
    },
]


def seed_database(host: str = "localhost", port: int = 50051) -> int:
    """Seed Context8 with curated problem-solution pairs.
    
    Returns number of records seeded.
    """
    storage = StorageService(host=host, port=port)
    storage.initialize()
    
    embeddings = EmbeddingService()
    count = 0

    for data in SEED_DATA:
        record = ResolutionRecord(
            problem_text=data["problem_text"],
            solution_text=data["solution_text"],
            error_type=data.get("error_type", ""),
            language=data.get("language", ""),
            framework=data.get("framework", ""),
            tags=data.get("tags", []),
            confidence=data.get("confidence", 0.9),
            source="seed",
        )

        vectors = embeddings.embed_record(
            problem_text=record.problem_text,
            solution_text=record.solution_text,
            code_snippet=data.get("code_snippet", ""),
        )

        storage.store_record(record, vectors)
        count += 1
        print(f"  [{count}/{len(SEED_DATA)}] {record.error_type}: {record.problem_text[:60]}...")

    storage.close()
    return count
```

## Ground Truth Evaluation Set

Per the hackathon guidance, create 30 representative question-answer pairs where we know which source record should match:

```python
# tests/ground_truth.py

GROUND_TRUTH = [
    {
        "query": "module not found cv2 python",
        "expected_error_type": "ModuleNotFoundError",
        "expected_tags": ["opencv"],
    },
    {
        "query": "pip install breaks on new ubuntu",
        "expected_error_type": "ExternallyManagedEnvironment",
        "expected_tags": ["pip", "pep668"],
    },
    {
        "query": "npm dependency tree won't resolve",
        "expected_error_type": "ERESOLVE",
        "expected_tags": ["npm", "peer-deps"],
    },
    {
        "query": "React SSR content mismatch between server and client",
        "expected_error_type": "HydrationError",
        "expected_tags": ["hydration", "ssr"],
    },
    {
        "query": "docker volume empty on windows",
        "expected_error_type": "VolumeError",
        "expected_tags": ["volume", "wsl2"],
    },
    # ... 25 more entries
]
```

## Testing Criteria

- [ ] Seed data loads without errors (all 60+ records)
- [ ] Each seeded record is retrievable by ID
- [ ] Ground truth queries find their expected records in top-3 results
- [ ] Recall@3 >= 0.8 (at least 80% of ground truth queries find the right answer in top 3)
- [ ] Precision@3 >= 0.6 (at least 60% of top-3 results are actually relevant)
- [ ] Seed operation is idempotent (running twice doesn't create duplicates)

## Estimated Time: 1 hour (mostly writing seed data)

## Dependencies: Plans 01-05

## Next: Plan 08 (Testing Strategy)
