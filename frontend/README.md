# Frontend

React + TypeScript + Vite certificate administration UI.

## Complete app

From the project root, run `./run.sh`. It installs declared dependencies, initializes demo data, builds `frontend/dist` and serves the UI and `/api` from FastAPI at `http://127.0.0.1:8000`.

## Frontend development

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`, so run the backend separately during Vite development. The actor menu sends `X-Actor-Email` for `alice@east.test` or `bob@west.test`. This is demo identity, not production authentication.

## Verification

```bash
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

The production build is in `frontend/dist`. The frontend's JSON response shapes are locked to `backend/app/contracts.py` and the backend design document.
