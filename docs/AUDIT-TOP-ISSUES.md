# R2R — Top Issues Audit

**Date:** 2026-07-20  
**Scope:** Static scan of this clone (v3.6.6, last activity ~Nov 2025). No runtime exploit verification.  
**Intent:** Ranked showstoppers / high-priority bugs before any fix work.  
**Status:** Findings only — not fixed yet.

---

## Context

R2R is an unmaintained production-style agentic RAG platform (FastAPI, Postgres/pgvector, optional Hatchet, Python/JS SDKs). Default config is oriented toward local demos but is unsafe if exposed and brittle as a first-run experience.

Related project orientation: root `AGENTS.md`.

---

## Ranking criteria

Issues ordered by combined **severity × likelihood on default config**. Security that turns “open port” into full compromise ranks above functional bit-rot.

---

## Top 10

### 1. Unauthenticated callers become superuser (critical)

**Where**

- `py/core/base/providers/auth.py` — `auth_wrapper`
- Default: `require_authentication = false` in `py/r2r/r2r.toml`

**What**

With auth not required, any request **without** Bearer token or API key is resolved to the **default admin user** (`_get_default_admin_user()`).

**Impact**

- Full admin capabilities without credentials
- Superuser path skips collection/owner filter enforcement used for normal users
- Superuser **skips rate limits** (`base_router.py` rate_limit_dependency)
- Combined with other findings → open data plane + RCE surface

**Fix direction (later)**

- Never map anonymous → superuser; use a least-privilege guest or require auth
- Prefer `require_authentication = true` as default for non-local profiles
- Keep a explicit “dev open mode” that is hard to enable and loud in logs

---

### 2. Hardcoded JWT signing secret (critical)

**Where**

- `py/core/providers/crypto/bcrypt.py` — `DEFAULT_BCRYPT_SECRET_KEY`
- `py/core/providers/crypto/nacl.py` — `DEFAULT_NACL_SECRET_KEY`
- Same value: `wNFbczH3QhUVcPALwtWZCPi0lrDlGV3P1DPRVEQCPbM`
- Fallback order: config → `R2R_SECRET_KEY` env → **hardcoded default**
- `docker/env/r2r.env` ships `R2R_SECRET_KEY=` empty → default wins

**What**

JWT access/refresh tokens are HS256-signed with a secret published in the repository.

**Impact**

Anyone with the source can **forge valid tokens** for any user (including admin), even after enabling authentication, if the secret is not rotated.

**Fix direction (later)**

- Fail fast if `R2R_SECRET_KEY` unset in non-dev
- Generate a one-time random secret for pure local dev and print it once
- Never ship a static fallback secret in production images

---

### 3. Default admin password + very long-lived tokens (critical / high)

**Where**

- `py/r2r/r2r.toml`: `default_admin_password = "change_me_immediately"`, `default_admin_email = "admin@example.com"`
- `access_token_lifetime_in_minutes = 60000` (~41 days)
- Also in dashboard env, docs cookbooks, JS/Python tests

**What**

Well-known default credentials; access tokens live for weeks.

**Impact**

Trivial account takeover if auth is enabled but password not changed; stolen/forged tokens remain valid for a long time.

**Fix direction (later)**

- Force password change on first login or refuse start if default password still set when auth required
- Shorter access token TTL; rely on refresh with rotation
- Keep demo password only in tests / explicit dev profile

---

### 4. Research agent `python_executor` = host RCE (critical)

**Where**

- Default `research_tools` in `py/r2r/r2r.toml` includes `"python_executor"`
- `py/core/agent/research.py` — `_execute_python_with_process_timeout`
- Implementation: write user code to temp `.py`, `subprocess.run([sys.executable, script_path], …)` with timeout only

**What**

Arbitrary Python runs in the server’s Python environment with **no sandbox** (full FS, network, env as the service user).

**Impact**

Any caller who can invoke the research agent can execute code on the host. With finding **#1**, that is **unauthenticated RCE** on default config if the agent endpoint is reachable.

**Fix direction (later)**

- Disable `python_executor` by default
- If enabled: isolate (container, gVisor, restricted interpreter), deny network, resource limits, allowlist APIs
- Gate research agent behind auth and role checks always

---

### 5. Filter metadata paths look SQL-injectable (high)

**Where**

- `py/core/providers/database/filters.py` — `_build_metadata_operator_condition`
  - Single key: `quoted_key = f"'{path_parts[0]}'"` then `metadata ->> {quoted_key}`
  - Multi path: string-built JSON path literal with `"`-joined segments
- Also: `py/core/providers/database/chunks.py` — `CREATE INDEX … {index_name}` / table name string assembly without identifier quoting helpers

**What**

User-controlled filter field paths are interpolated into SQL with quote wrapping that does not safely escape `'` / `"` inside path segments. Search/retrieval accept filters from clients.

**Impact**

Likely SQL injection against Postgres (read/write depending on statement context and privileges). Index name injection is a secondary vector for privileged callers.

**Fix direction (later)**

- Parameterize or strictly validate path segments (allowlist `[A-Za-z0-9_]` only)
- Use Postgres JSON path APIs with bound parameters
- Quote identifiers via a single safe helper; never f-string raw names from the client

**Note:** Values for many operators appear parameterized via `ParamHelper`; the risk called out here is **path/key** interpolation, not only value binding.

---

### 6. Startup `pip install` from `user_requirements.txt` (high)

**Where**

- `py/core/main/assembly/utils.py` — `install_user_tool_dependencies`
- Called from `py/core/main/assembly/builder.py` when `R2R_USER_TOOLS_PATH` or `../docker/user_tools` exists

**What**

On application build/start, runs:

`python -m pip install -r <user_tools>/user_requirements.txt`

Failures raise and can abort startup. Success mutates the runtime environment.

**Impact**

- Supply-chain / RCE if the requirements path is writable or untrusted
- Non-reproducible environments
- Surprise start failures in locked-down containers without pip/network

**Fix direction (later)**

- Never auto-pip at runtime; document image rebuild or optional explicit CLI
- If kept for dev: require explicit env flag and log a large warning

---

### 7. CORS `allow_origins=["*"]` with `allow_credentials=True` (high)

**Where**

- `py/core/main/app_entry.py`
- `py/core/main/app.py` — origins include `"*"` plus localhost entries

**What**

Wildcard origin plus credentials is an insecure / invalid browser pattern and signals “open API” defaults.

**Impact**

Cross-origin browser abuse risk depending on deployment and cookie/header usage; at minimum a production misconfiguration default.

**Fix direction (later)**

- Explicit origin allowlist from config/env
- Never combine `*` with credentials

---

### 8. Postgres is mandatory; README quickstart is misleading (onboarding showstopper)

**Where**

- `py/core/providers/database/postgres.py` — raises if `R2R_POSTGRES_USER/PASSWORD/HOST/PORT/DBNAME` missing
- Marketing path in `py/README.md`: `pip install r2r` → `python -m r2r.serve`

**What**

There is no embedded database. Serve always needs Postgres with extensions (`vector`, `pg_trgm`, etc. created at init).

**Impact**

First-run “quick install” fails without Docker/Compose or external Postgres. Wastes time and masks other config issues.

**Fix direction (later)**

- Document minimum env + pgvector as hard requirements
- Optional: compose-only quickstart as the default documented path
- Clearer error message listing all required env vars at once

---

### 9. Default models + `automatic_extraction = true` (high functional risk)

**Where**

- `py/r2r/r2r.toml`:
  - `fast_llm` / `quality_llm` / `vlm` → `openai/gpt-5-*` dated IDs
  - `automatic_extraction = true`
  - embeddings: `openai/text-embedding-3-small` via LiteLLM

**What**

Ingest (graph extraction) and user-facing RAG both depend on live LLM APIs, correct model IDs, and API keys. Unmaintained configs drift as providers rename models.

**Impact**

- Broken or expensive ingest out of the box
- Failed graph enrichment / agent paths
- Hard to distinguish “code bug” vs “model/key/config”

**Fix direction (later)**

- Safer defaults: extraction off until configured; stable model aliases or env-only model selection
- Startup validation of model reachability (optional, non-blocking warning)
- Profile TOMLs for OpenAI / Ollama / Azure kept accurate

---

### 10. Core RAG tool `search_file_knowledge` fragile / empty on error (high product bug)

**Where**

- `py/core/base/agent/tools/built_in/search_file_knowledge.py`
- Listed in default `rag_tools` in `r2r.toml`

**What**

Code comments/FIXMEs document past silent failures (wrong kwargs / embedding vs query). Exceptions are caught and turned into an **empty** `AggregateSearchResult` rather than surfacing failure.

**Impact**

Agentic RAG can appear successful while returning no knowledge; hard to debug; undermines the main product path.

**Fix direction (later)**

- Align call signature with `knowledge_search_method` once and for all
- Propagate errors or tool-error payloads to the agent
- Integration test: ingest → agent tool → non-empty chunks

---

## Issue map (how they compound)

```text
Default deploy
  ├─ #1 open superuser ──► #4 python RCE
  │                    └─► #5 SQLi as privileged DB role
  ├─ #2 forge JWTs (even after enabling auth, if secret not set)
  ├─ #3 default password + long-lived tokens
  ├─ #6 pip on boot
  ├─ #7 wild CORS
  └─ #8 need Postgres ──► #9 LLM models/keys ──► #10 empty agent search
```

---

## Honorable mentions (outside top 10)

| Issue | Location / notes |
|--------|------------------|
| Superuser skips rate limits | `py/core/main/api/v3/base_router.py` — already implied by #1 |
| Indices API incomplete TODOs | `py/core/main/api/v3/indices_router.py` |
| Document deleted when last chunk removed — partial BUGFIX | `management_service.py` (still review multi-chunk races) |
| Package directory typo `asnyc_methods` | Works via consistent import; tech debt |
| Pinned/old orchestration deps | e.g. `hatchet-sdk==0.47.0` — ops bit-rot |
| CORS + open admin | Product of #1 + #7 |
| `access_token_lifetime` 60000 | Covered under #3 |
| Filter owner/collection parsing brittle for non-admin | `retrieval_service.py` TODO around filter parse |
| Metadata on chunk create “doesn’t seem to get passed” FIXME | `documents_router.py` |

---

## Suggested fix sprints (when ready)

### Sprint A — Security defaults (priority if anything is network-reachable)

1. Anonymous must not be superuser; tighten `require_authentication` defaults  
2. Remove hardcoded JWT secret; require `R2R_SECRET_KEY`  
3. Default password / token lifetime hygiene  
4. Disable `python_executor` by default; sandbox or remove  
5. Fix filter path / identifier SQL construction  
6. Remove runtime pip install; fix CORS allowlist  

### Sprint B — Make local run honest and usable

1. Document + compose path for Postgres/pgvector  
2. Safer model defaults; extraction off until configured  
3. Harden `search_file_knowledge` + agent smoke tests  

---

## Key file index

| Area | Paths |
|------|--------|
| Auth wrapper | `py/core/base/providers/auth.py` |
| Default config | `py/r2r/r2r.toml` |
| JWT crypto | `py/core/providers/crypto/bcrypt.py`, `nacl.py` |
| Python executor | `py/core/agent/research.py` |
| Filters / SQL | `py/core/providers/database/filters.py` |
| Index DDL | `py/core/providers/database/chunks.py` |
| User tools pip | `py/core/main/assembly/utils.py`, `builder.py` |
| CORS | `py/core/main/app_entry.py`, `app.py` |
| Postgres env | `py/core/providers/database/postgres.py` |
| RAG tool | `py/core/base/agent/tools/built_in/search_file_knowledge.py` |
| Rate limits | `py/core/main/api/v3/base_router.py` |
| Docker env | `docker/env/r2r.env` |

---

## Method notes

- Static review: config, auth, crypto, agent tools, filters, assembly, API routers, compose env  
- Grep for secrets, TODOs/FIXMEs, `require_authentication`, subprocess/exec, SQL f-strings  
- No proof-of-concept exploits run against a live instance  
- Model ID availability not re-validated against current OpenAI catalog (treat #9 as config risk)

---

## Changelog of this document

| Date | Change |
|------|--------|
| 2026-07-20 | Initial audit from project scan; top 10 + honorable mentions + fix sprint sketch |
