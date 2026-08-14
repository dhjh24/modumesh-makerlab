# ModuMesh MakerLab

**Self-hosted 3D generator platform.**

Schema-driven plugins → queued CAD generation → model validation → browser preview → download.

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Web     │────▶│  API     │────▶│  Worker  │
│ (Next.js)│     │ (FastAPI)│     │ (Python) │
└──────────┘     └──────────┘     └──────────┘
                      │                │
                      ▼                ▼
                 ┌──────────┐     ┌──────────┐
                 │PostgreSQL│     │  Redis   │
                 └──────────┘     └──────────┘
                      │                │
                      ▼                ▼
                 ┌─────────────────────────┐
                 │   MinIO (Object Store)   │
                 └─────────────────────────┘
```

## Quick Start

```bash
# Prerequisites: Docker, Docker Compose, Node 22+, Python 3.11+

# 1. Clone
git clone https://github.com/dhjh24/modumesh-makerlab.git
cd modumesh-makerlab

# 2. Install frontend dependencies
npm install

# 3. Copy environment config
cp .env.example .env
# Set real values for ADMIN_API_KEY and ADMIN_PLUGIN_SIGNING_SECRET
# (the API REFUSES to start without them — fail-closed admin auth).

# 4. Start everything (--env-file is required: Compose does not auto-read
#    a repo-root .env when the compose file lives in infra/compose/)
docker compose --env-file .env -f infra/compose/docker-compose.yml up -d

# 5. Open the web UI
open http://localhost:3000
```

## Services

| Service  | Port | Description                        |
| -------- | ---- | ---------------------------------- |
| Web      | 3000 | Next.js frontend                   |
| API      | 8000 | FastAPI backend                    |
| Worker   | —    | Queued CAD generation (background) |
| Postgres | 5432 (internal) | Primary database — no host port |
| Redis    | 6379 (internal) | Job queue and caching — no host port |
| MinIO    | 9000 (internal) | Object storage for model files — no host port |

## Project Structure

```
modumesh-makerlab/
├── apps/
│   ├── web/          # Next.js frontend
│   ├── api/          # FastAPI backend
│   └── worker/       # Python background worker
├── packages/
│   ├── plugin-sdk/      # TS types + JSON schemas
│   ├── plugin-sdk-py/  # Python SDK, runner, contract CLI
│   ├── shared-types/   # TypeScript types shared across apps
│   ├── viewer/         # 3D model viewer (Three.js / R3F)
│   └── ui/             # Shared UI components
├── plugins/
│   ├── fixture-echo/   # Non-CAD example plugin (Phase 3)
│   ├── fixture-mesh/   # STL/GLB fixture plugin (Phase 4)
│   └── nameplate/      # Reference CadQuery plugin (Phase 5)
├── infra/
│   └── compose/        # Docker Compose files
├── docs/
│   ├── adr/              # Architecture Decision Records
│   ├── plugins.md        # Plugin author guide
│   ├── architecture.md   # Current architecture
│   ├── ROADMAP.md        # Plugin-first delivery plan
│   └── AGENT_PROMPTS.md  # One implementation prompt per phase
└── tests/
    ├── e2e/            # End-to-end tests
    └── integration/    # Integration tests
```

## Planning

- [Plugin-first delivery plan](docs/ROADMAP.md)
- [Copy-ready implementation prompts](docs/AGENT_PROMPTS.md)

Start with Phase 0. It fixes deployed API reachability before real generator work begins. Run one phase per pull request and pass its exit gate before moving to the next prompt.

## Development

```bash
# Install dependencies
npm install
pip install -e packages/plugin-sdk-py

# Run all TypeScript type checks
npm run typecheck

# Plugin contract check
modumesh-plugin-check check plugins/fixture-echo \
  --input plugins/fixture-echo/fixtures/valid-input.json

# Run API tests
cd apps/api && pip install -e ".[dev]" && pytest

# Build containers
docker compose -f infra/compose/docker-compose.yml build
```

## License

MIT — see [LICENSE](LICENSE).
