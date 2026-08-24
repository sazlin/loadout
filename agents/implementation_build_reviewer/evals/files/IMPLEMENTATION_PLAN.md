# Implementation Plan

**Goal:** Retry failed GETs with **exponential backoff**.

## Tasks

### Task 1: Exponential backoff helper

- Files: `evals/files/backoff.py`
- Steps: Retry 429/503 with exponential backoff (base 0.1s, factor 2).
- Tests: unit test that delays double.
- Done when: delays are exponential, not linear.
