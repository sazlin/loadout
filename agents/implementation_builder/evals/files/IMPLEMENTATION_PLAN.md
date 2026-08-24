# Implementation Plan

**Source PRD:** PRD.md
**Goal:** Retry failed GETs with exponential backoff.
**Architecture:** A `retry_get` helper in `backoff.py`.
**Tech stack:** Python, pytest

## Tasks

### Task 1: Exponential backoff helper

- Files: `evals/files/backoff.py`
- Steps: Retry HTTP 429 and 503 with exponential backoff (base 0.1s, factor 2, max 3 attempts). Do not edit `helpers.py`.
- Tests: `uv run pytest -q evals/files/test_backoff.py` (create if missing)
- Done when: a 503 then a 200 succeeds, and delays double.
