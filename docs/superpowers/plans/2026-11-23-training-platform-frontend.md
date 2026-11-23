# Training Platform Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved two-page certificate administration UI with safe actor switching, write retries, and CSV export.

**Architecture:** React + TypeScript + Vite, with route-based pages for certificates and courses. A single API client attaches the selected demo actor; one pending-write helper owns idempotency keys and retry state. Read data stays in page state and is refetched after writes or actor changes.

**Tech Stack:** React, TypeScript, Vite, React Router, browser `fetch`, Vitest, React Testing Library.

**Spec:** `/Users/inception/learning/ocean-training-platform/docs/superpowers/specs/2026-11-23-training-platform-frontend-design.md`; backend contract: `/Users/inception/learning/ocean-training-platform/docs/superpowers/specs/2026-11-22-training-platform-backend-design.md`.

## Global Constraints

- Project root: `/Users/inception/learning/ocean-training-platform`.
- No login UI; top-right demo actor choices: `alice@east.test` / `bob@west.test`; API header `X-Actor-Email`.
- Pages: `/certificates` and `/courses`; no tenant picker or tenant ID supplied by the UI.
- Write endpoints require `Idempotency-Key`; same operation retry reuses its key; new deliberate operation gets a new key.
- GET requests are side-effect free, use fresh backend reads, and do not use idempotency keys.
- Display backend-provided tenant-local dates/times; do not convert via browser timezone.
- CSV export preserves current `search`, `sort`, `direction` and excludes pagination.
- A backend-owned startup command will build and serve the frontend; this plan delivers a working Vite build and documents its build output.

## Review Focus

1. A late Alice response after switching to Bob must never appear in Bob's UI (Task 1 test).
2. A write timeout followed by retry must reuse the same key and original actor/path/body (Task 3 test).
3. A revoked certificate remains visible and a second revoke with a new key must not look like a fresh change (Task 3 test).
4. Export must use the visible search/sort and leave list interactions usable while download is pending (Task 5 test).
5. The Sydney/Perth date shown must be the API value even when the browser timezone differs (Task 2 test).

---

## File Map

| File | Responsibility |
| --- | --- |
| `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json` | Build, scripts, type checking and tests |
| `frontend/src/main.tsx`, `frontend/src/App.tsx` | Root mount, routes and shared shell |
| `frontend/src/api/types.ts`, `frontend/src/api/client.ts` | Fixed API DTOs, actor-scoped reads and writes |
| `frontend/src/actor/ActorProvider.tsx`, `frontend/src/actor/ActorMenu.tsx` | Demo actor state, verification and switch UI |
| `frontend/src/lib/pendingWrite.ts`, `frontend/src/lib/writeRequest.ts` | Key creation, session persistence and exact retry |
| `frontend/src/pages/CertificatesPage.tsx`, `frontend/src/pages/CertificateDrawer.tsx`, `frontend/src/pages/RevokeDialog.tsx` | Certificate list, detail and revoke |
| `frontend/src/pages/CoursesPage.tsx`, `frontend/src/pages/BulkIssueResults.tsx` | Course completion and bulk issue |
| `frontend/src/features/certificates/exportCsv.ts` | Actor-bound CSV download |
| `frontend/src/styles.css` | Shared layout and component styles |
| `frontend/src/**/*.test.tsx`, `frontend/src/**/*.test.ts` | Focused behavior tests |

## API JSON Contract to Lock With Backend

Use snake_case JSON fields as follows (TypeScript names may match them directly):

- `GET /api/me`: `{ admin: { id, email }, tenant: { id, name, timezone } }`.
- `GET /api/courses`: `{ items: [{ id, title }] }`.
- `GET /api/courses/{id}/enrollments`: `{ course: { id, title }, items: [{ learner_id, learner_name, status, active_certificate_id }] }`, where `status` is `COMPLETED` or `INCOMPLETE` and `active_certificate_id` is nullable.
- `GET /api/certificates`: `{ items: [{ id, serial_number, learner_name, course_title, issued_local_date, status }], page, page_size, total }`.
- `GET /api/certificates/{id}`: `{ id, serial_number, learner_name, course_title, issued_local_date, issued_local_datetime, status }`.
- `POST /api/courses/{id}/bulk-issue`: `{ operation_id, status: 'COMPLETED', summary: { issued, skipped, failed }, outcomes: [{ learner_id, learner_name, result, reason, certificate_id, serial_number }] }`; optional outcome fields are nullable.
- `POST /api/certificates/{id}/revoke`: `{ operation_id, certificate_id, status: 'REVOKED', changed }`.

These exact shapes need to be mirrored in the backend implementation plan and verified at integration; changing one requires updating both sides before implementation.

### Task 1: Application Shell and Actor Boundary

**Files:** Create `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/actor/ActorProvider.tsx`, `frontend/src/actor/ActorMenu.tsx`, `frontend/src/styles.css`; test `frontend/src/actor/ActorProvider.test.tsx`.

**Interfaces:** `ApiClient` exposes `getJson<T>(path: string, actorEmail: string, signal?: AbortSignal): Promise<T>` and `postJson<T>(path: string, actorEmail: string, key: string, body?: object): Promise<T>`; both use `cache: 'no-store'` for GET and attach `X-Actor-Email`. `useActor()` returns `{ actorEmail, tenant, generation, switchActor }`. DTOs in `api/types.ts` define the fields in frontend spec §6.

- [ ] Write a failing actor test: render Alice tenant in the shell, switch to Bob, resolve an older Alice `/api/me` request afterward, assert the shell still displays only Bob/West; assert Bob requests use `X-Actor-Email: bob@west.test`.
- [ ] Run `npm --prefix frontend test -- ActorProvider.test.tsx`; expect this test to fail before implementation.
- [ ] Implement Vite app, two routes, shared top bar/sidebar, actor provider, actor menu, `/api/me` verification, request generation guard and abort of stale reads. Initial actor is Alice; unknown actor shows error and retry.
- [ ] Run the actor test, `npm --prefix frontend run typecheck`, and `npm --prefix frontend run build`; expect all to pass and `frontend/dist` to exist.
- [ ] Commit shell and actor boundary as one independently reviewable change.

### Task 2: Certificate List and Detail

**Files:** Create `frontend/src/pages/CertificatesPage.tsx`, `frontend/src/pages/CertificateDrawer.tsx`; test `frontend/src/pages/CertificatesPage.test.tsx`.

**Interfaces:** Page reads `GET /api/certificates?search&sort&direction&page&page_size` and `GET /api/certificates/{id}` through Task 1 client. URL query parameters are the source of truth for search, sort, direction and page. `CertificatesPage` owns a selected certificate ID and renders `CertificateDrawer`.

- [ ] Write a failing page test: search updates URL and resets page to 1; sort and pagination reach the API; empty/search-empty/error/loading states appear; date text `2026-01-11` is shown exactly as returned regardless of test browser timezone.
- [ ] Run `npm --prefix frontend test -- CertificatesPage.test.tsx`; expect failures for missing UI behavior.
- [ ] Implement server-side list loading, pagination, search, sort whitelist, four status states, row selection and detail drawer with backend-local date/time and status. Include both `ACTIVE` and `REVOKED` rows.
- [ ] Run the page test and typecheck; expect both to pass.
- [ ] Commit certificate browsing and detail.

### Task 3: Shared Write Retry and Revocation

**Files:** Create `frontend/src/lib/pendingWrite.ts`, `frontend/src/lib/writeRequest.ts`, `frontend/src/pages/RevokeDialog.tsx`; modify `frontend/src/pages/CertificateDrawer.tsx`; test `frontend/src/lib/writeRequest.test.ts` and `frontend/src/pages/RevokeDialog.test.tsx`.

**Interfaces:** `PendingWrite` contains `{ actorEmail, method, path, body, key, createdAt }`. `createPendingWrite(actorEmail: string, path: string, body: object): PendingWrite` uses `crypto.randomUUID()`. `submitWrite<T>(write: PendingWrite): Promise<T>` sends the exact captured request. `loadPendingWrite()`/`savePendingWrite()`/`clearPendingWrite()` use `sessionStorage`. Revocation calls `POST /api/certificates/{id}/revoke` with `{}`.

- [ ] Write failing tests: timeout then retry sends the same key/actor/path/body; a different deliberate action gets a new key; confirmation is required; a returned `changed: false` displays “已撤销” rather than “撤销成功”; `409` never silently generates another key.
- [ ] Run the two focused test files; expect failures for missing retry and revoke UI.
- [ ] Implement pending-write persistence, retry action, conflict/error messages, revoke confirmation, in-flight button disabling and list/detail refetch on definite result. Block actor switching only while a write is in flight; retain pending write under its original actor after timeout.
- [ ] Run focused tests and typecheck; expect all to pass.
- [ ] Commit shared write behavior and revocation.

### Task 4: Course Completion and Bulk Issue

**Files:** Create `frontend/src/pages/CoursesPage.tsx`, `frontend/src/pages/BulkIssueResults.tsx`; test `frontend/src/pages/CoursesPage.test.tsx`.

**Interfaces:** Reads `GET /api/courses` and `GET /api/courses/{id}/enrollments`; posts `POST /api/courses/{id}/bulk-issue` with `{}` via Task 3 helper. Results consume `{ operation_id, status, summary: { issued, skipped, failed }, outcomes: [...] }`, with reasons and optional certificate identifiers.

- [ ] Write failing tests: changing course clears old enrollments; loading/empty/error states render; confirm then issue sends one in-flight request; `issued`, `skipped` with reason, and `failed` appear separately; retry retains the original key.
- [ ] Run `npm --prefix frontend test -- CoursesPage.test.tsx`; expect failures.
- [ ] Implement course selector, enrollment counts/table, eligibility explanation, confirmation, pending state and inline per-learner result panel. After a definite result, refresh enrollment status.
- [ ] Run focused tests and typecheck; expect all to pass.
- [ ] Commit course page and bulk issue.

### Task 5: Export, Integration and Page Verification

**Files:** Create `frontend/src/features/certificates/exportCsv.ts`; modify `frontend/src/pages/CertificatesPage.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`, `frontend/README.md`; test `frontend/src/features/certificates/exportCsv.test.ts`.

**Interfaces:** `exportCertificates(actorEmail: string, filters: { search: string; sort: string; direction: 'asc' | 'desc' }): Promise<void>` calls `GET /api/certificates/export`, uses captured actor and filters, and downloads the raw CSV without parsing it into rows. It is independent of list fetch state.

- [ ] Write a failing export test: URL has current search/sort/direction and no page; captured Alice header stays Alice after UI switch; a pending export does not disable a separate list request.
- [ ] Run `npm --prefix frontend test -- exportCsv.test.ts`; expect failures.
- [ ] Implement export loading/error UI, filename with originating tenant, complete page states and keyboard/label basics. Document `npm --prefix frontend run build` and `frontend/dist` handoff to backend startup.
- [ ] Run all frontend tests, typecheck and production build; expect passing commands and generated dist. Manually check Alice/Bob isolation, revoke, bulk outcomes, and download in a browser connected to the backend when available.
- [ ] Commit the frontend deliverable. Record any backend contract mismatch and adjust both specs or implementation before claiming end-to-end completion.

## Self-Review Result

Each frontend spec section maps to Tasks 1–5. Shared actor and API interfaces precede pages; write retry precedes bulk issue. The five Review Focus cases each have a named owning test. This plan intentionally leaves the back-end database, API implementation and one-command root startup to the backend/integration plan.
