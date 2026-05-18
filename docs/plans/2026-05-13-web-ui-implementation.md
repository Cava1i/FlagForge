# CTF Agent Web UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local Web application for challenge management, single-run execution, live logs, and result inspection on top of the existing CTF agent runtime.

**Architecture:** Keep the current CLI runtime intact and add a Web layer around it. Flask provides REST and SSE endpoints, a new application service layer manages run lifecycle and persistence, and a Vue SPA acts as the operator console.

**Tech Stack:** Flask, SQLite, pytest, Vue 3, Vite, TypeScript, SSE, existing `ChallengeSwarm` and Docker sandbox runtime

---

### Task 1: Scaffold Backend Web And Storage Packages

**Files:**
- Create: `backend/web/__init__.py`
- Create: `backend/web/app.py`
- Create: `backend/web/routes/__init__.py`
- Create: `backend/app/__init__.py`
- Create: `backend/storage/__init__.py`
- Create: `backend/storage/db.py`
- Modify: `pyproject.toml`
- Test: `tests/web/test_app_factory.py`

**Step 1: Write the failing test**

Create `tests/web/test_app_factory.py` asserting:

- the Flask app factory returns an app
- `/api/health` returns 200

**Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_app_factory.py -v`

Expected: FAIL because the app factory and route do not exist.

**Step 3: Write minimal implementation**

- Add Flask dependency in `pyproject.toml`
- Create app factory in `backend/web/app.py`
- Register a minimal `/api/health` route
- Create SQLite bootstrap helper in `backend/storage/db.py`

**Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_app_factory.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml backend/web backend/app backend/storage tests/web/test_app_factory.py
git commit -m "feat: scaffold flask web backend"
```

### Task 2: Add Challenge Persistence And Directory Service

**Files:**
- Create: `backend/storage/challenge_repo.py`
- Create: `backend/app/challenge_service.py`
- Create: `backend/web/routes/challenges.py`
- Modify: `backend/web/app.py`
- Test: `tests/app/test_challenge_service.py`
- Test: `tests/web/test_challenges_api.py`

**Step 1: Write the failing tests**

Add tests covering:

- create challenge from existing path
- list stored challenges
- read a challenge detail record

**Step 2: Run tests to verify they fail**

Run: `pytest tests/app/test_challenge_service.py tests/web/test_challenges_api.py -v`

Expected: FAIL because repository, service, and routes do not exist.

**Step 3: Write minimal implementation**

- Create SQLite table for challenges
- Implement repository CRUD needed for v1
- Implement service methods:
  - `import_from_path`
  - `list_challenges`
  - `get_challenge`
- Expose:
  - `GET /api/challenges`
  - `POST /api/challenges`
  - `GET /api/challenges/<id>`

**Step 4: Run tests to verify they pass**

Run: `pytest tests/app/test_challenge_service.py tests/web/test_challenges_api.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/storage/challenge_repo.py backend/app/challenge_service.py backend/web/routes/challenges.py backend/web/app.py tests/app/test_challenge_service.py tests/web/test_challenges_api.py
git commit -m "feat: add challenge import and listing"
```

### Task 3: Add Metadata Editing API

**Files:**
- Modify: `backend/app/challenge_service.py`
- Modify: `backend/web/routes/challenges.py`
- Test: `tests/app/test_challenge_service.py`
- Test: `tests/web/test_challenges_api.py`

**Step 1: Write the failing tests**

Add tests covering:

- update `metadata.yml` fields
- persist summary changes into SQLite
- reject invalid challenge update payload

**Step 2: Run tests to verify they fail**

Run: `pytest tests/app/test_challenge_service.py tests/web/test_challenges_api.py -v`

Expected: FAIL on missing update behavior.

**Step 3: Write minimal implementation**

- Add `update_challenge_metadata`
- Rewrite `metadata.yml` safely
- Update index fields in repository
- Expose `PUT /api/challenges/<id>`

**Step 4: Run tests to verify they pass**

Run: `pytest tests/app/test_challenge_service.py tests/web/test_challenges_api.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/challenge_service.py backend/web/routes/challenges.py tests/app/test_challenge_service.py tests/web/test_challenges_api.py
git commit -m "feat: add challenge metadata editing"
```

### Task 4: Build Run Persistence And RunManager Skeleton

**Files:**
- Create: `backend/storage/run_repo.py`
- Create: `backend/app/run_manager.py`
- Create: `backend/web/routes/runs.py`
- Modify: `backend/web/app.py`
- Test: `tests/app/test_run_manager.py`
- Test: `tests/web/test_runs_api.py`

**Step 1: Write the failing tests**

Add tests covering:

- create run record
- list runs
- get run detail
- create run request returns queued run

**Step 2: Run tests to verify they fail**

Run: `pytest tests/app/test_run_manager.py tests/web/test_runs_api.py -v`

Expected: FAIL because run storage and manager do not exist.

**Step 3: Write minimal implementation**

- Add SQLite table for runs
- Implement `RunManager.create_run`
- Implement in-memory registry for active tasks
- Expose:
  - `GET /api/runs`
  - `POST /api/runs`
  - `GET /api/runs/<id>`

Use a fake or placeholder executor first so route and persistence behavior can be verified without real solver execution.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/app/test_run_manager.py tests/web/test_runs_api.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/storage/run_repo.py backend/app/run_manager.py backend/web/routes/runs.py backend/web/app.py tests/app/test_run_manager.py tests/web/test_runs_api.py
git commit -m "feat: add run persistence and api skeleton"
```

### Task 5: Integrate Real ChallengeSwarm Execution

**Files:**
- Modify: `backend/app/run_manager.py`
- Modify: `backend/agents/swarm.py`
- Modify: `backend/cli.py`
- Test: `tests/app/test_run_manager.py`

**Step 1: Write the failing tests**

Add tests using a fake swarm adapter to prove:

- run transitions `queued -> running -> succeeded`
- run transitions `queued -> running -> failed`
- cancellation marks the run cancelled

**Step 2: Run tests to verify they fail**

Run: `pytest tests/app/test_run_manager.py -v`

Expected: FAIL because lifecycle transitions are incomplete.

**Step 3: Write minimal implementation**

- Add a swarm runner adapter inside `RunManager`
- Start each run in a background thread
- Create a dedicated event loop in that thread
- Instantiate and await `ChallengeSwarm.run()`
- Persist final status, cost, flag, and summary

Do not remove or rewrite CLI behavior. Reuse the same runtime path from the Web layer.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/app/test_run_manager.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/run_manager.py backend/agents/swarm.py backend/cli.py tests/app/test_run_manager.py
git commit -m "feat: integrate web run manager with swarm runtime"
```

### Task 6: Add File Logging And SSE Streaming

**Files:**
- Create: `backend/web/routes/stream.py`
- Modify: `backend/app/run_manager.py`
- Modify: `backend/web/app.py`
- Test: `tests/web/test_run_stream_api.py`

**Step 1: Write the failing test**

Add tests covering:

- log file created for a run
- SSE endpoint returns initial streamed data
- status events are emitted on completion

**Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_run_stream_api.py -v`

Expected: FAIL because streaming route and log writer do not exist.

**Step 3: Write minimal implementation**

- Create `logs/runs/<run_id>.log`
- Append run lifecycle messages from `RunManager`
- Add SSE endpoint `GET /api/runs/<id>/logs/stream`
- Emit `log`, `status`, and `heartbeat` events

**Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_run_stream_api.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/web/routes/stream.py backend/app/run_manager.py backend/web/app.py tests/web/test_run_stream_api.py
git commit -m "feat: add run log streaming over sse"
```

### Task 7: Scaffold Vue Frontend

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/sse.ts`
- Test: `frontend` build

**Step 1: Create the frontend scaffold**

Set up a Vue 3 + TypeScript + Vite app with:

- Vue Router
- typed fetch wrapper
- basic layout shell

**Step 2: Run build to verify scaffold**

Run: `cd frontend && npm run build`

Expected: PASS

**Step 3: Commit**

```bash
git add frontend
git commit -m "feat: scaffold vue frontend"
```

### Task 8: Build Challenge Management UI

**Files:**
- Create: `frontend/src/pages/ChallengesPage.vue`
- Create: `frontend/src/pages/ChallengeDetailPage.vue`
- Create: `frontend/src/components/ChallengeForm.vue`
- Modify: `frontend/src/router.ts`
- Test: `frontend` build

**Step 1: Implement challenge list page**

Include:

- local challenge list
- import challenge from path
- open challenge detail

**Step 2: Implement challenge detail page**

Include:

- metadata form
- save action
- distfiles summary
- start-run action entry point

**Step 3: Run build to verify pages compile**

Run: `cd frontend && npm run build`

Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/pages frontend/src/components frontend/src/router.ts
git commit -m "feat: add challenge management ui"
```

### Task 9: Build Run List And Run Detail UI

**Files:**
- Create: `frontend/src/pages/RunsPage.vue`
- Create: `frontend/src/pages/RunDetailPage.vue`
- Create: `frontend/src/components/RunLauncherForm.vue`
- Create: `frontend/src/components/RunLogViewer.vue`
- Modify: `frontend/src/router.ts`
- Test: `frontend` build

**Step 1: Implement run list page**

Include:

- run history table
- status badges
- result summary

**Step 2: Implement run detail page**

Include:

- run metadata header
- live log viewer using SSE
- cancel button
- final result card

**Step 3: Implement run launcher form**

Include:

- model specs input
- `no_submit` toggle
- challenge launch action

**Step 4: Run build to verify pages compile**

Run: `cd frontend && npm run build`

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/pages frontend/src/components frontend/src/router.ts
git commit -m "feat: add run management ui"
```

### Task 10: Serve Frontend From Flask And Add Smoke Test

**Files:**
- Modify: `backend/web/app.py`
- Modify: `README.md`
- Create: `tests/web/test_frontend_serving.py`

**Step 1: Write the failing test**

Add a test proving:

- Flask serves the built frontend shell
- API routes still work

**Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_frontend_serving.py -v`

Expected: FAIL because static frontend serving is not wired in yet.

**Step 3: Write minimal implementation**

- Configure Flask static serving for built frontend assets
- Add a catch-all route for SPA navigation
- Document exact dev and build commands in `README.md`

**Step 4: Run verification**

Run:

```bash
pytest tests/web/test_frontend_serving.py -v
cd frontend && npm run build
uv --cache-dir /home/ctf-agent/.uv-cache run python -m backend.web.app
```

Expected:

- test passes
- frontend build passes
- backend starts successfully

**Step 5: Commit**

```bash
git add backend/web/app.py README.md tests/web/test_frontend_serving.py
git commit -m "feat: serve built frontend from flask"
```

### Task 11: Manual End-To-End Smoke Test

**Files:**
- No code changes required unless bugs are found

**Step 1: Start backend**

Run:

```bash
uv --cache-dir /home/ctf-agent/.uv-cache run python -m backend.web.app
```

**Step 2: Start frontend dev server**

Run:

```bash
cd frontend && npm run dev
```

**Step 3: Verify workflows**

Verify:

- import a challenge from existing path
- edit metadata and save
- launch a dry-run with `codex/gpt-5.4-mini`
- observe live logs
- cancel a running task
- refresh and confirm run history remains visible

**Step 4: Fix any defects found**

Run targeted tests and rebuild after each fix.

**Step 5: Commit**

```bash
git add .
git commit -m "feat: complete web ui v1 smoke-tested flow"
```

## Notes For Execution

- Keep CLI behavior working throughout implementation.
- Do not remove existing solver backends.
- Keep coordinator mode out of scope for the initial Web UI.
- Prefer fake runner tests for lifecycle behavior before wiring real swarms.
- Treat challenge directories and `metadata.yml` as the source of truth for challenge content.

Plan complete and saved to `docs/plans/2026-05-13-web-ui-implementation.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
