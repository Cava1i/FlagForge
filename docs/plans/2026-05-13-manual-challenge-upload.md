# Manual Challenge Upload Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a browser workflow for creating challenges by editing metadata, listing distfiles, and uploading files.

**Architecture:** Keep path import intact. Add a multipart API that writes a new challenge directory under `challenges/<slug>/`, stores metadata in `metadata.yml`, saves uploaded files in `distfiles/`, indexes the challenge in SQLite, and returns the same challenge detail shape used by the existing UI.

**Tech Stack:** Flask multipart forms, PyYAML, SQLite repository, Vue 3 + TypeScript, Vite.

---

### Task 1: Backend Manual Create API

**Files:**
- Modify: `backend/app/challenge_service.py`
- Modify: `backend/web/app.py`
- Modify: `backend/web/routes/challenges.py`
- Modify: `tests/app/test_challenge_service.py`
- Modify: `tests/web/test_challenges_api.py`

**Steps:**
1. Add failing service tests for creating a challenge from metadata and uploaded files.
2. Add failing route tests for `POST /api/challenges/manual`.
3. Implement slug validation, directory creation, metadata writing, `distfiles/` storage, and duplicate slug rejection.
4. Run targeted app/web tests.

### Task 2: Frontend Manual Create Flow

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/ChallengesPage.vue`
- Modify: `frontend/src/styles.css`

**Steps:**
1. Add typed API support for multipart challenge creation.
2. Add a manual creation panel with metadata fields, distfile names, file picker, and submit action.
3. Keep the existing path import workflow.
4. Run `npm --prefix frontend run build`.

### Task 3: Example Challenge And Smoke

**Files:**
- Create: `examples/manual-challenge/metadata.yml`
- Create: `examples/manual-challenge/distfiles/README.txt`
- Modify: `README.md`

**Steps:**
1. Add an example challenge directory matching the manual upload shape.
2. Document the manual-create flow.
3. Run backend tests, frontend build, and a curl smoke against the multipart API.
