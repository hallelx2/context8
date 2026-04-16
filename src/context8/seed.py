"""Curated seed data for Context8 — solves the cold start problem.

These are real-world problem-solution pairs covering the long tail of
uncommon errors that don't appear in official documentation.
"""

from __future__ import annotations

import logging

from .embeddings import EmbeddingService
from .models import ResolutionRecord
from .storage import StorageService

logger = logging.getLogger("context8.seed")


SEED_DATA: list[dict] = [
    # ── Python Environment ────────────────────────────────────────────────
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
    {
        "problem_text": "torch.cuda.OutOfMemoryError when fine-tuning LLM even with small batch size",
        "solution_text": "GPU memory fragmentation or model too large. Fixes in order: 1) torch.cuda.empty_cache() before training, 2) Use gradient_checkpointing_enable(), 3) Use bitsandbytes 4-bit quantization (load_in_4bit=True), 4) Use DeepSpeed ZeRO Stage 3.",
        "error_type": "OutOfMemoryError",
        "language": "python",
        "framework": "pytorch",
        "tags": ["cuda", "oom", "fine-tuning", "gpu"],
        "confidence": 0.93,
    },
    # ── Node.js / npm ─────────────────────────────────────────────────────
    {
        "problem_text": "ERESOLVE unable to resolve dependency tree - npm peer dependency conflict",
        "solution_text": "npm 7+ enforces strict peer deps. Fix options: 1) npm install --legacy-peer-deps (quick fix), 2) Add overrides in package.json to force version, 3) Upgrade conflicting packages. Option 2 is most robust.",
        "error_type": "ERESOLVE",
        "language": "javascript",
        "tags": ["npm", "peer-deps", "dependency-conflict"],
        "confidence": 0.94,
    },
    {
        "problem_text": "ERR_REQUIRE_ESM: require() of ES Module not supported - importing ESM-only package in CommonJS",
        "solution_text": "Package uses ESM only (type: module). Options: 1) Use dynamic import: const pkg = await import('package'), 2) Add 'type': 'module' to your package.json and use .mjs, 3) Use an older CJS-compatible version.",
        "error_type": "ERR_REQUIRE_ESM",
        "language": "javascript",
        "tags": ["esm", "commonjs", "import", "require"],
        "confidence": 0.93,
    },
    {
        "problem_text": "Node.js heap out of memory during build (FATAL ERROR: CALL_AND_RETRY_LAST Allocation failed)",
        "solution_text": "Default Node heap is ~1.7GB. Fix: set NODE_OPTIONS='--max-old-space-size=8192' (8GB). For CI: add to environment variables. For package.json scripts: cross-env NODE_OPTIONS=--max-old-space-size=4096.",
        "error_type": "HeapOutOfMemory",
        "language": "javascript",
        "tags": ["heap", "memory", "build", "node-options"],
        "confidence": 0.96,
    },
    # ── React / Next.js ───────────────────────────────────────────────────
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
        "problem_text": "Cannot update a component while rendering a different component - React setState during render",
        "solution_text": "Calling setState during another component's render violates React rules. Move the state update to useEffect, an event handler, or useMemo. Common culprit: updating parent state in child's render body.",
        "error_type": "ReactRenderError",
        "language": "typescript",
        "framework": "react",
        "tags": ["setState", "render", "useEffect"],
        "confidence": 0.95,
    },
    {
        "problem_text": "Next.js API route returns 'API resolved without sending a response' warning with streaming",
        "solution_text": "Next.js expects API routes to complete synchronously or return a Response. For streaming: use the App Router route handlers (app/api/route.ts) with 'return new Response(stream)'. Pages Router API routes don't support streaming natively.",
        "error_type": "APIRouteWarning",
        "language": "typescript",
        "framework": "nextjs",
        "tags": ["api-route", "streaming", "app-router"],
        "confidence": 0.91,
    },
    # ── Docker ────────────────────────────────────────────────────────────
    {
        "problem_text": "Docker bind mount volume shows empty directory - files from host not visible in container",
        "solution_text": "On Windows with WSL2: ensure the path uses Linux format (/mnt/c/...) not Windows (C:\\\\...). On Mac: the directory must be in Docker Desktop's file sharing settings. Also: container might overwrite the mount with a build step.",
        "error_type": "VolumeError",
        "language": "",
        "framework": "docker",
        "tags": ["volume", "bind-mount", "wsl2", "file-sharing"],
        "confidence": 0.91,
    },
    {
        "problem_text": "docker compose up fails with 'port is already allocated' on port 5432",
        "solution_text": "Another process is using the port. Fix: 1) Stop the local service: sudo systemctl stop postgresql, 2) Or remap: '5433:5432' in docker-compose.yml. Find what's using it: lsof -i :5432 (Linux) or netstat -ano | findstr 5432 (Windows).",
        "error_type": "PortConflict",
        "framework": "docker",
        "tags": ["port-conflict", "postgresql", "docker-compose"],
        "confidence": 0.97,
    },
    # ── TypeScript ────────────────────────────────────────────────────────
    {
        "problem_text": "Type 'X' is not assignable to type 'never' - TypeScript array with conditional types",
        "solution_text": "TypeScript narrows an array to never[] because it can't infer the element type. Fix: explicitly type the array: const items: (TypeA | TypeB)[] = []. Or use 'as const' for literal arrays.",
        "error_type": "TS2322",
        "language": "typescript",
        "tags": ["type-narrowing", "never", "array-type"],
        "confidence": 0.93,
    },
    {
        "problem_text": "Cannot find module './Component' or its corresponding type declarations - TypeScript path aliases",
        "solution_text": "tsconfig paths are only for the TypeScript compiler, not the bundler. Fix: configure paths in BOTH tsconfig.json AND your bundler (vite: resolve.alias, webpack: resolve.alias). Or use tsconfig-paths package for Node.js runtime.",
        "error_type": "TS2307",
        "language": "typescript",
        "tags": ["path-aliases", "tsconfig", "module-resolution"],
        "confidence": 0.96,
    },
    # ── Database ──────────────────────────────────────────────────────────
    {
        "problem_text": "Connection pool exhausted - too many clients already in PostgreSQL with Prisma in serverless",
        "solution_text": "Serverless functions create new connections per invocation. Fix: 1) Use PgBouncer or Supabase Pooler, 2) Set connection_limit=1 in Prisma datasource, 3) Use Prisma Accelerate for managed pooling.",
        "error_type": "ConnectionPoolExhausted",
        "language": "typescript",
        "framework": "prisma",
        "tags": ["connection-pool", "serverless", "postgresql", "pgbouncer"],
        "confidence": 0.94,
    },
    # ── Git ────────────────────────────────────────────────────────────────
    {
        "problem_text": "Git merge conflict in package-lock.json / yarn.lock - massive unresolvable diff",
        "solution_text": "Never manually resolve lockfile conflicts. Fix: 1) Accept either version: git checkout --theirs package-lock.json, 2) Delete lockfile: rm package-lock.json, 3) Regenerate: npm install, 4) Commit the fresh lockfile.",
        "error_type": "MergeConflict",
        "tags": ["git", "merge-conflict", "lockfile", "npm"],
        "confidence": 0.98,
    },
    # ── Cross-Platform ────────────────────────────────────────────────────
    {
        "problem_text": "ENOENT: no such file or directory - Windows path too long (>260 characters) in node_modules",
        "solution_text": "Windows has 260-char path limit by default. Fix: 1) Enable long paths: reg add HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1, 2) Move project closer to root (C:\\dev\\project).",
        "error_type": "ENOENT",
        "language": "javascript",
        "tags": ["windows", "long-path", "node_modules", "enoent"],
        "confidence": 0.92,
    },
    # ── Build Tools ───────────────────────────────────────────────────────
    {
        "problem_text": "Vite prebundling failed - 'X is not a function' after adding new dependency",
        "solution_text": "Vite's pre-bundling cache is stale. Fix: 1) Delete node_modules/.vite, 2) Run: npx vite --force, 3) Or add the package to optimizeDeps.include in vite.config.ts.",
        "error_type": "PrebundleError",
        "language": "typescript",
        "framework": "vite",
        "tags": ["vite", "prebundling", "cache", "dependency"],
        "confidence": 0.94,
    },
    # ── Rust ──────────────────────────────────────────────────────────────
    {
        "problem_text": "error[E0463]: can't find crate for 'std' when targeting wasm32-unknown-unknown",
        "solution_text": "wasm32-unknown-unknown doesn't support std. Use #![no_std] or switch to wasm32-wasi which has partial std support. For web: use wasm-bindgen + web-sys crates instead of std.",
        "error_type": "E0463",
        "language": "rust",
        "tags": ["wasm", "no-std", "wasm-bindgen", "target"],
        "confidence": 0.91,
    },
    {
        "problem_text": "borrow checker error: cannot borrow as mutable because it is also borrowed as immutable in loop",
        "solution_text": "Classic borrow checker conflict. Solutions: 1) Collect into Vec first then mutate, 2) Use indices instead of references: for i in 0..vec.len(), 3) Use interior mutability: RefCell or Cell, 4) Restructure to separate borrows.",
        "error_type": "E0502",
        "language": "rust",
        "tags": ["borrow-checker", "mutable", "lifetime"],
        "confidence": 0.90,
    },
    # ── AI / ML ───────────────────────────────────────────────────────────
    {
        "problem_text": "OpenAI API error 429 Too Many Requests - rate limit exceeded with batch processing",
        "solution_text": "Add exponential backoff with jitter. Use tenacity library: @retry(wait=wait_exponential(min=1, max=60), stop=stop_after_attempt(6)). Or use asyncio.Semaphore to limit concurrent requests to 5-10.",
        "error_type": "RateLimitError",
        "language": "python",
        "tags": ["openai", "rate-limit", "backoff", "async"],
        "confidence": 0.95,
    },
    {
        "problem_text": "HuggingFace model.generate() returns repeated tokens or gibberish after fine-tuning",
        "solution_text": "Common causes: 1) Learning rate too high (try 2e-5), 2) Training data not formatted correctly for the tokenizer, 3) Missing pad_token (set tokenizer.pad_token = tokenizer.eos_token), 4) Use do_sample=True, temperature=0.7, top_p=0.9.",
        "error_type": "GenerationError",
        "language": "python",
        "framework": "transformers",
        "tags": ["huggingface", "fine-tuning", "generation", "repetition"],
        "confidence": 0.88,
    },
]


def seed_database(
    storage: StorageService | None = None,
    host: str = "localhost",
    port: int = 50051,
) -> int:
    """Seed Context8 with curated problem-solution pairs.

    Returns number of records seeded.
    """
    own_storage = storage is None
    if own_storage:
        storage = StorageService(url=f"{host}:{port}")
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

        try:
            vectors = embeddings.embed_record(
                problem_text=record.problem_text,
                solution_text=record.solution_text,
                code_snippet=data.get("code_snippet", ""),
            )
            storage.store_record(record, vectors)
            count += 1
            logger.info(
                f"[{count}/{len(SEED_DATA)}] {record.error_type}: {record.problem_text[:60]}..."
            )
        except Exception as e:
            logger.warning(f"Failed to seed record: {e}")
            continue

    if own_storage:
        storage.close()

    return count
