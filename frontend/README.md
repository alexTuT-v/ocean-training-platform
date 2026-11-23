# Frontend

React + TypeScript + Vite implementation of the approved certificate admin UI.

## Local development

```bash
npm install
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. Start the backend separately for local development. The actor menu sends `X-Actor-Email` with either `alice@east.test` or `bob@west.test`; this is an assessment demo identity, not production authentication.

## Verification and build

```bash
npm test
npm run typecheck
npm run build
```

The production build is emitted to `frontend/dist`. The root one-command startup should install declared dependencies, initialize demo data, run `npm --prefix frontend run build`, and serve `frontend/dist` plus `/api` from FastAPI, with an SPA fallback for `/certificates` and `/courses`.

The UI expects the JSON response shapes listed in `docs/superpowers/plans/2026-11-23-training-platform-frontend.md` at the project root. The backend is not part of this frontend implementation; end-to-end behavior requires that backend contract and the root startup script.
