# Selected bulk certificate issue — Spec

This spec supersedes the course-wide bulk issue behavior described in the original backend and frontend design documents.

## Background and goal

The course completion page is paginated, but its bulk action currently issues to every eligible learner in the course. Administrators need to choose the learners affected by each operation.

## Requirements

- F1: Each eligible learner can be selected individually. Incomplete learners and learners with an active certificate cannot be selected.
- F2: “Select all” selects eligible learners on the visible page. Selection persists across pages and is cleared when the actor or course changes.
- F3: The page displays the total selected count and requires at least one selection before a new issue request. Confirmation displays the exact selected count.
- F4: The write request explicitly names selected learner IDs. An omitted or empty selection never means the entire course. The backend verifies every ID belongs to the authenticated tenant and course.
- F5: Learners whose eligibility changes before execution are skipped with a per-learner outcome. An invalid or cross-tenant ID rejects the whole new request without writes.
- F6: Retries after an uncertain response reuse the same key and exact selected IDs, including after page refresh. A successful operation clears the selection and refreshes enrollment data.

## Quality constraints

- Q1: Selection and issue must remain usable with a 100,000-learner course; the page continues to fetch only one page and the write queries only requested IDs.
- Q2: Existing tenant isolation, per-learner rollback, idempotency replay, and certificate audit behavior remain intact.

## Acceptance

- A1: Selecting one learner issues only that learner's certificate.
- A2: Selecting all on one page does not include another page; manually selected IDs remain selected when returning to a prior page.
- A3: Empty, duplicate, malformed, unknown, or cross-tenant selections cause no certificate, audit, or idempotency record.
- A4: The same key and body return the original result; a changed selection with the same key conflicts.
- A5: A failed or lost response can be retried with the saved request body and key.
