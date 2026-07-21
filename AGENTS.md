# R2R — Project Rules for Grok

## What this is

R2R (SciPhi) is an **unmaintained production RAG platform**: multimodal ingestion, hybrid search, GraphRAG, agentic/research agents, multi-user auth, REST API + Python/JS SDKs.

- Package: `r2r` **3.6.6** (`py/pyproject.toml`)
- Python: `>=3.10,<3.13`
- Default API: `http://localhost:7272` · optional dashboard `:7273` · graph clustering `:7276`
- Last known upstream-style activity on this clone: ~Nov 2025 — expect bit-rot (deps, model names, docs URLs)

Treat this as a **fork / revival / learning codebase**, not a polished maintained product.

## Layout (where to look)

| Path | Role |
|------|------|
| `py/core/main/` | FastAPI app, assembly (`R2RBuilder`), services, v3 API routers |
| `py/core/main/api/v3/` | REST: documents, chunks, collections, conversations, retrieval, graph, indices, prompts, users, system |
| `py/core/main/services/` | auth, ingestion, retrieval, graph, management, maintenance |
| `py/core/agent/` | RAG + research agents |
| `py/core/providers/` | Pluggable LLM, embeddings, DB (Postgres/pgvector), file, auth, orchestration (Hatchet/simple), email, OCR |
| `py/core/parsers/` | Media / structured / text parsers |
| `py/core/providers/database/prompts/` | YAML prompt library |
| `py/r2r/` | Package entry (`serve.py`, default `r2r.toml`) |
| `py/sdk/` | Python client (sync + async) |
| `py/migrations/` | Alembic |
| `py/tests/` | unit + integration |
| `js/sdk/` | TypeScript client `r2r-js` |
| `docker/` | Compose light/full/swarm + env files |
| `deployment/k8s/` | Kustomize manifests |
| `services/` | Sidecars: Unstructured, graph clustering |
| `docs/` | Architecture + cookbooks (may drift from code) |

Root `README.md` → symlink to `py/README.md`.

## Architecture (short)

```
HTTP/SDK → FastAPI v3 routers → Services → Providers → Postgres/pgvector (+ S3/MinIO, Hatchet, sidecars)
```

Config is **TOML-first**: `py/r2r/r2r.toml` and `py/core/configs/*`, overridden by env (`R2R_CONFIG_NAME`, `R2R_CONFIG_PATH`, `R2R_HOST`, `R2R_PORT`, provider keys).

Two common run modes:

1. **Light**: `pip install 'r2r[core]'` then `python -m r2r.serve` (simple orchestration)
2. **Full**: Docker Compose (`docker/compose.full.yaml`) with Postgres, Hatchet/RabbitMQ, optional MinIO, Unstructured, dashboard, clustering

## Working conventions for this repo

- Prefer **read → plan → small change** over drive-by refactors. Codebase is large (~270+ Python modules).
- When changing API behavior, check **both** `py/core/main/api/v3/` and SDKs (`py/sdk/`, `js/sdk/src/`).
- DB/schema changes go through **Alembic** (`py/migrations/`), not ad-hoc SQL only.
- Do not commit secrets. Default config has demo admin creds (`admin@example.com` / `change_me_immediately`) and auth often off — never treat as production-safe without hardening.
- Dependency pins are aggressive (e.g. Hatchet, tokenizers). Prefer minimal version bumps unless the task is modernization.
- Docs under `docs/` are helpful orientation, not ground truth — verify against code.

## Commands (when relevant)

```bash
# Python package root
cd py

# Install (uv or pip); server needs core extra
# pip install -e '.[core]'   or use uv with py/uv.lock

# Serve (light)
python -m r2r.serve

# Docker (from repo root or docker/)
# docker compose -f docker/compose.yaml --profile postgres up -d

# Tests (from py/)
# pytest tests/unit
# pytest tests/integration   # needs running stack
```

Exact install/test workflows may need discovery — do not invent CI flags that are not in the repo.

## Goals for agent sessions (default)

Unless the user says otherwise:

1. Map the smallest relevant subsystem before editing.
2. Prefer local, reversible changes; confirm before force-push, destructive git, or shared-remote actions.
3. Call out bit-rot / unmaintained risks when they block a task.
4. Keep AGENTS.md updated only when durable project facts change (entry points, run modes, constraints) — not session chatter.

## Known audit

Ranked showstoppers / high-prio issues (security + onboarding): **`docs/AUDIT-TOP-ISSUES.md`** (2026-07-20, findings only).

## Chunk prefix (custom)

Document create metadata key **`chunk_prefix`**: prepended to every chunk **before embed + store** (Plan B). Helper: `py/core/utils/chunk_prefix.py`. Applied in `IngestionService.embed_document` and re-applied after chunk enrichment.
