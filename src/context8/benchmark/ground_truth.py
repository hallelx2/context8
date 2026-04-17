from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GroundTruthQuery:
    query: str
    expected_slug: str
    language: str | None = None
    framework: str | None = None
    code_context: str = ""


GROUND_TRUTH: list[GroundTruthQuery] = [
    GroundTruthQuery(
        query="opencv import broken after pip install in venv",
        expected_slug="py-cv2-venv",
        language="python",
    ),
    GroundTruthQuery(
        query="pip refusing to install on ubuntu, externally managed",
        expected_slug="py-pep668",
        language="python",
    ),
    GroundTruthQuery(
        query="typing.Annotated missing on older Python",
        expected_slug="py-annotated-38",
        language="python",
    ),
    GroundTruthQuery(
        query="await/asyncio inside a notebook cell complains about running loop",
        expected_slug="py-asyncio-jupyter",
        language="python",
    ),
    GroundTruthQuery(
        query="GPU runs out of memory while training even at batch size 1",
        expected_slug="py-torch-cuda-oom",
        language="python",
    ),
    GroundTruthQuery(
        query="npm install errors on peer dep mismatch after upgrading",
        expected_slug="npm-eresolve-peer",
        language="javascript",
    ),
    GroundTruthQuery(
        query="cannot require an esm-only package from commonjs file",
        expected_slug="node-esm-cjs",
        language="javascript",
    ),
    GroundTruthQuery(
        query="webpack build crashes with allocation failed on large project",
        expected_slug="node-heap-oom",
        language="javascript",
    ),
    GroundTruthQuery(
        query="server-rendered markup doesn't match client on first render",
        expected_slug="next-hydration",
        language="typescript",
        framework="nextjs",
    ),
    GroundTruthQuery(
        query="warning about updating parent state inside a child render",
        expected_slug="react-setstate-render",
        language="typescript",
        framework="react",
    ),
    GroundTruthQuery(
        query="next.js api handler logs unresolved warning when streaming responses",
        expected_slug="next-api-streaming",
        language="typescript",
        framework="nextjs",
    ),
    GroundTruthQuery(
        query="mounted folder shows up empty inside the container on Windows",
        expected_slug="docker-volume-empty",
        framework="docker",
    ),
    GroundTruthQuery(
        query="postgres docker container can't bind because port is taken",
        expected_slug="docker-port-conflict",
        framework="docker",
    ),
    GroundTruthQuery(
        query="typescript inferring an empty array as never[] and rejecting pushes",
        expected_slug="ts-never-array",
        language="typescript",
    ),
    GroundTruthQuery(
        query="vite can't find module imported via @ alias even though tsc is happy",
        expected_slug="ts-path-aliases",
        language="typescript",
    ),
    GroundTruthQuery(
        query="prisma timing out with too many connections on vercel functions",
        expected_slug="db-pool-serverless",
        framework="prisma",
    ),
    GroundTruthQuery(
        query="huge merge conflict in package-lock.json, can't resolve by hand",
        expected_slug="git-lockfile-conflict",
    ),
    GroundTruthQuery(
        query="ENOENT on windows when path inside node_modules gets too long",
        expected_slug="win-long-path",
        language="javascript",
    ),
    GroundTruthQuery(
        query="vite dev server breaks with 'is not a function' after adding a dep",
        expected_slug="vite-prebundle",
        framework="vite",
    ),
    GroundTruthQuery(
        query="rust compile error E0463 building for wasm32 target",
        expected_slug="rust-wasm-no-std",
        language="rust",
    ),
    GroundTruthQuery(
        query="borrow checker rejects mutating a vec while iterating over it",
        expected_slug="rust-borrow-loop",
        language="rust",
    ),
    GroundTruthQuery(
        query="hitting 429 from OpenAI when sending many requests in parallel",
        expected_slug="openai-rate-limit",
        language="python",
    ),
    GroundTruthQuery(
        query="huggingface model outputs the same token over and over after training",
        expected_slug="hf-generate-gibberish",
        language="python",
        framework="transformers",
    ),
    GroundTruthQuery(
        query="ERESOLVE unable to resolve dependency tree",
        expected_slug="npm-eresolve-peer",
    ),
    GroundTruthQuery(
        query="ModuleNotFoundError: No module named 'cv2'",
        expected_slug="py-cv2-venv",
    ),
    GroundTruthQuery(
        query="ERR_REQUIRE_ESM",
        expected_slug="node-esm-cjs",
    ),
    GroundTruthQuery(
        query="error[E0463]",
        expected_slug="rust-wasm-no-std",
    ),
]
