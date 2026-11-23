# Selected Bulk Issue Implementation Plan

**Goal:** Issue certificates only to explicitly selected course learners.

**Architecture:** The existing bulk endpoint accepts a required `learner_ids` array. Validation and tenant-scoped enrollment lookup occur inside the existing idempotent write transaction. The React course page holds a cross-page set of selected IDs, snapshots it for confirmation, and stores that exact body with the idempotency key for retries.

**Tech stack:** FastAPI, SQLite, React, TypeScript, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-23-selected-bulk-issue-spec.md`

## Tasks

1. Add failing backend tests for subset issue, invalid selections, tenant isolation, and replay body conflicts.
2. Validate the explicit ID array and query only those enrollments in stable order; keep existing per-learner savepoints and result shape.
3. Update existing backend tests and documentation to use an explicit selection.
4. Add failing frontend tests for individual and visible-page selection, cross-page persistence, disabled eligibility, and saved retry body.
5. Add course-page selection controls, count, confirmation snapshot, and post-write refresh.
6. Run backend and frontend suites, production build, diff checks, and review the 100,000-row behavior.

## Review focus

- A selected learner disappears or changes eligibility before the write.
- An ID from another tenant or course is submitted.
- A retry occurs after selection changes or page refresh.
- The active actor or course changes while selections exist.
- A visible page has no eligible learners.
