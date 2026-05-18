# README Logo Update Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dark, rectangular, text-free logo to the top of the README.

**Architecture:** Keep the asset as a standalone SVG in `docs/assets/` and render it in README with a centered banner above the title. No application code changes are needed.

**Tech Stack:** Markdown, SVG.

---

### Task 1: Create the logo asset

**Files:**
- Create: `docs/assets/logo.svg`

**Step 1: Write the asset**

Build a wide SVG with a dark panel, a terminal/capture motif, a small orchestration graph, and a flag icon. Do not include any visible text.

**Step 2: Verify the asset exists**

Run: `sed -n '1,220p' docs/assets/logo.svg`
Expected: the SVG markup is present and readable.

### Task 2: Update the README header

**Files:**
- Modify: `README.md`

**Step 1: Write the banner**

Add a centered logo image, centered project title, and a short subtitle above the existing README content.

**Step 2: Verify the markdown structure**

Run: `sed -n '1,40p' README.md`
Expected: the top of the file renders the logo block before the body text.

### Task 3: Check the final layout

**Files:**
- Modify: `README.md`
- Create: `docs/assets/logo.svg`

**Step 1: Inspect the result**

Open the README in the renderer and confirm the logo is rectangular, dark, and text-free.

**Step 2: Keep the scope tight**

Do not touch any application code, tests, or runtime behavior.
