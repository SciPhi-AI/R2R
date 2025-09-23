# Ellen V2 – Proposed Repository Layout

> Last updated: 2025-09-19

This document captures the **recommended directory structure** for the first runnable prototype.  
It follows the three-engine architecture (Ingestion / Query / Synthesis) and keeps front- and back-end services decoupled yet co-located in a single monorepo.

```text
ellen-v2/
│
├── apps/                       # Everything that _runs_
│   ├── web/                    # Next.js 14 + Supabase auth (React + TS)
│   ├── r2r-api/                # Full R2R FastAPI instance (Python 3.11)
│   └── crewai-api/             # CrewAI service & flows (Python 3.11)
│
├── packages/                   # Shared runtime-agnostic code
│   ├── db/                     # Pydantic models, SQL helpers, generated types
│   └── ui/                     # Shared React components (shadcn/ui wrappers)
│
├── infra/                      # Dev & deploy infrastructure
│   ├── docker-compose.yml      # Local stack: Postgres, Supabase, R2R, CrewAI
│   ├── render/                 # Render YAML (or Terraform) for live deploys
│   └── supabase/               # Supabase CLI config (edge functions, SQL)
│
├── .windsurf/workflows/        # Automation workflows (already exists)
│   ├── git_auto_push.yaml
│   └── checkpoint_workflow.yaml
│
├── docs/                       # Architecture, API, tutorials, **this file**
│   └── …
└── project-logs/YYYY/MM/DD.md  # Daily log system  (see `project_log_index.md`)
```

## Rationale
| Area                     | Reasoning |
|--------------------------|-----------|
| **apps/**                | Isolates runtime artifacts; easy to docker-compose or deploy independently. |
| **packages/**            | Promotes code-sharing across web and Python back-ends without circular deps. |
| **infra/**               | Keeps infra-as-code separate from apps and docs; can grow into Terraform or remain Render YAML as the project evolves. |
| **.windsurf/workflows/** | Windsurf auto-discovers workflows here; Git automation & checkpoints already configured. |

## Next Steps Checklist
- [ ] Scaffold `apps/web` with `create-next-app -e supabase`, then install Shadcn/ui.
- [ ] Scaffold `apps/r2r-api` with `poetry new`, then add Dockerfile.
- [ ] Scaffold `apps/crewai-api` with `poetry new`, then add Dockerfile.
- [ ] Write `infra/docker-compose.yml` for local development.
- [ ] Draft Render YAML files in `infra/render/` once services are ready.
- [ ] Wire shared ENV vars (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, …).

---
_See the `three_engine_architecture.mmd` diagram for a visual overview._
