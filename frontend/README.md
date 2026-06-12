# Repo Research — Frontend

React + TypeScript SPA (Vite) using [CopilotKit](https://copilotkit.ai) for
generative UI, connected to the FastAPI backend over the
[AG-UI protocol](https://github.com/ag-ui-protocol).

## Prerequisites

- Node 18+ and **pnpm ≥ 10.16** (required for `minimumReleaseAge`).
- The backend running: from the repo root, `uv run repo-research serve`
  (defaults to `http://localhost:8000`). Make sure an LLM provider is configured
  (see the root README / `llm-provider-setup`).

## Develop

```bash
pnpm install
pnpm dev          # Vite dev server on http://localhost:5173
```

The dev server proxies `/api` and `/agent` to the backend on `:8000`
(see `vite.config.ts`), so the browser stays same-origin.

## Type generation

API types are generated from the backend's OpenAPI schema (the Pydantic models
are the single source of truth):

```bash
# From the repo root, refresh the committed schema:
uv run repo-research export-openapi -o frontend/openapi.json
# Then regenerate TypeScript types:
pnpm gen:api      # openapi.json -> src/types/api.ts
```

## Build

```bash
pnpm build        # tsc --noEmit && vite build  -> dist/
pnpm preview      # serve the production build
```

## Backend connection

`src/App.tsx` connects CopilotKit directly to the AG-UI `/agent` endpoint via
`@ag-ui/client`'s `HttpAgent` (runtime-less `agents__unsafe_dev_only` mode). This
keeps the stack Python-only for local development; a hosted CopilotRuntime can be
added later for production hardening.
