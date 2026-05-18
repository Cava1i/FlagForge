# CTF Agent Web UI Design

**Date:** 2026-05-13

**Goal**

Build a local, single-user Web application around the existing CTF agent so the user can manage challenge directories, edit challenge metadata, launch solver runs, stream logs, and inspect results without using the CLI directly.

**Context**

The current repository is a Python CLI application centered around:

- `backend/cli.py` for command entry
- `backend/agents/swarm.py` for challenge-level orchestration
- `backend/agents/codex_solver.py` and `backend/agents/claude_solver.py` for model execution
- `backend/sandbox.py` for Docker-backed execution
- `backend/prompts.py` for challenge prompt construction

There is no existing Web layer or frontend project in the repository.

## Product Scope

This v1 targets a local, single-user workflow.

Included:

- Challenge list and detail views
- Create/import challenge directories
- Edit `metadata.yml` fields
- Launch a single challenge run with configurable models and flags
- View run history
- Stream run logs in real time
- View final run result, flag, and cost summary

Not included:

- Multi-user authentication
- Remote deployment hardening
- Coordinator-mode control surface
- Automatic recovery of in-flight runs after backend restart

## Recommended Architecture

Use a three-layer structure:

1. Vue frontend for operator workflows
2. Flask Web/API layer for HTTP and SSE endpoints
3. A new application service layer that adapts the existing async swarm runtime to a Web task model

The important boundary is that Flask should not directly instantiate and control solver internals inside route handlers. A `RunManager` service should own task lifecycle and persistence.

## Approach Decision

Chosen approach: `Flask API + dedicated task service + Vue SPA`

Why:

- Reuses the existing Python core with the fewest behavior changes
- Keeps HTTP concerns separate from swarm runtime concerns
- Gives a clean place to add persistence, cancellation, and log streaming
- Avoids turning Flask routes into long-running orchestration code

## Stack Decisions

Backend:

- Flask for HTTP API and serving built frontend assets
- Server-Sent Events for live log streaming
- SQLite for persisted challenge/run metadata
- Plain local log files for run log bodies

Frontend:

- Vue 3 with Vite
- TypeScript
- Typed fetch wrapper instead of a heavier client layer

Task/runtime:

- Existing `ChallengeSwarm` remains the execution engine
- Each run executes in a background thread with its own asyncio event loop

## Data Model

### ChallengeRecord

Represents a local challenge entry managed by the Web UI.

Fields:

- `id`
- `name`
- `slug`
- `path`
- `category`
- `value`
- `connection_info`
- `created_at`
- `updated_at`

This record is a UI index. The source of truth for challenge content remains the challenge directory and `metadata.yml`.

### RunRecord

Represents one solver execution.

Fields:

- `id`
- `challenge_id`
- `mode` (`single`)
- `model_specs` (JSON array)
- `status` (`queued`, `running`, `succeeded`, `failed`, `cancelled`, `interrupted`)
- `no_submit`
- `result_flag`
- `cost_usd`
- `log_path`
- `error_summary`
- `started_at`
- `finished_at`

### RunProcess

In-memory only. Tracks a live run bound to the Flask process.

Fields:

- background thread handle
- asyncio event loop handle
- cancellation signal
- current status cache
- SSE subscriber fanout handle

## Persistence Model

Use SQLite plus filesystem storage.

SQLite:

- challenge index
- run metadata
- timestamps and result summaries

Filesystem:

- challenge directories remain under `challenges/<slug>/`
- run logs stored at `logs/runs/<run_id>.log`

Why this split:

- Existing project is already directory-centric for challenge assets
- SQLite is better suited to queryable metadata than large log blobs
- Log tailing is simpler and more reliable when logs stay append-only files

## Backend Module Layout

Recommended new packages:

- `backend/web/`
- `backend/app/`
- `backend/storage/`

Suggested responsibilities:

- `backend/web/app.py`
  Flask app factory and extension bootstrap
- `backend/web/routes/challenges.py`
  Challenge CRUD endpoints
- `backend/web/routes/runs.py`
  Run creation, listing, detail, cancellation
- `backend/web/routes/stream.py`
  SSE log streaming
- `backend/app/run_manager.py`
  Owns lifecycle of in-memory running tasks
- `backend/app/challenge_service.py`
  Import, create, edit, and inspect challenge directories
- `backend/storage/db.py`
  SQLite connection and schema bootstrap
- `backend/storage/challenge_repo.py`
  Challenge persistence adapter
- `backend/storage/run_repo.py`
  Run persistence adapter

## Runtime Model

`POST /api/runs` should not block on solver completion.

Flow:

1. API validates request and creates a `RunRecord` with `queued`
2. `RunManager` allocates a log file and in-memory task entry
3. `RunManager` starts a background thread
4. That thread creates a dedicated asyncio event loop
5. The event loop instantiates `ChallengeSwarm` and awaits `swarm.run()`
6. Status transitions are persisted as the run advances
7. On completion or failure, the final state is written back to SQLite

This preserves the async swarm model without requiring a migration to an async-first Web framework.

## Log Streaming

Use SSE rather than WebSocket.

Why:

- Log output is server-to-client only
- Browser and Flask support are straightforward
- Simpler reconnection behavior
- Lower implementation complexity for a local single-user app

SSE endpoint behavior:

- Stream historical tail first from the log file
- Continue streaming appended lines while the run is active
- Emit structured `status` events when run state changes

Event types:

- `log`
- `status`
- `heartbeat`

## API Shape

### Challenge endpoints

- `GET /api/challenges`
- `POST /api/challenges`
- `GET /api/challenges/<id>`
- `PUT /api/challenges/<id>`

`POST /api/challenges` supports:

- create from existing path
- create from uploaded metadata plus attachments

### Run endpoints

- `GET /api/runs`
- `POST /api/runs`
- `GET /api/runs/<id>`
- `POST /api/runs/<id>/cancel`
- `GET /api/runs/<id>/logs/stream`

## Frontend Structure

Recommended pages:

- `Challenges`
- `Challenge Detail`
- `Runs`
- `Run Detail`

Recommended UI flow:

1. User creates or imports a challenge
2. User edits or reviews metadata in challenge detail
3. User starts a run from challenge detail
4. User is redirected to run detail
5. Run detail streams logs and updates terminal result state

Recommended frontend structure:

- `frontend/src/pages/ChallengesPage.vue`
- `frontend/src/pages/ChallengeDetailPage.vue`
- `frontend/src/pages/RunsPage.vue`
- `frontend/src/pages/RunDetailPage.vue`
- `frontend/src/components/ChallengeForm.vue`
- `frontend/src/components/RunLauncherForm.vue`
- `frontend/src/components/RunLogViewer.vue`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/sse.ts`

## Error Handling

Three error classes should be separated clearly.

### API errors

Examples:

- missing challenge
- invalid payload
- invalid model list

Response shape:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "challenge_id is required"
  }
}
```

### Runtime errors

Examples:

- Docker unavailable
- Codex upstream 502
- malformed challenge directory

These should fail the run, not the Flask process.

### Infrastructure errors

Examples:

- SQLite open failure
- log file creation failure

These are true backend failures and should return 500.

## Restart Behavior

On backend startup:

- SQLite history remains available
- any run previously marked `running` is converted to `interrupted`
- no attempt is made to resume in-flight swarms

This is the correct v1 tradeoff for a local, single-user tool.

## Testing Strategy

Backend:

- pytest unit tests for repositories and services
- integration tests for Flask routes
- fake runner tests for `RunManager`

Frontend:

- component tests for forms, lists, and log viewer
- no heavy end-to-end browser suite required for v1

Manual smoke tests:

- import challenge from path
- edit metadata
- start dry-run task
- observe live log stream
- cancel task
- refresh page and confirm history remains visible

## Rollout Strategy

Implement in two internal phases while keeping the current CLI untouched.

Phase 1:

- Flask API
- SQLite persistence
- run lifecycle
- SSE logs

Phase 2:

- Vue SPA
- challenge editor
- run list and run detail UI

The CLI should remain operational throughout. The Web layer should reuse core services, not replace them.

## Key Risks

- Mixing Flask request lifecycle with long-lived async tasks
- Over-coupling Web routes to solver internals
- Letting challenge metadata in SQLite diverge from `metadata.yml`
- Making the first version coordinator-aware before single-run behavior is stable

## Recommendation Summary

Build a local single-user `Vue + Flask` application around the existing runtime by introducing a dedicated `RunManager`, persisting metadata in SQLite, keeping logs on disk, and exposing a small `REST + SSE` API. Keep the CLI intact and treat the Web app as a control surface over the existing swarm engine.
