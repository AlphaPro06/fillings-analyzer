# Filings Analyzer — Frontend

A React + TypeScript single-page app for the Financial Filings Analyzer backend.
Register or sign in, upload a PDF filing, and ask natural-language questions about
it — answers are grounded in the filing text, and repeated questions are served
instantly from the backend's cache.

Built with React, TypeScript, and Vite. No UI framework — the design system is
hand-written CSS.

## Prerequisites

The backend must be running first (default: `http://localhost:8000`). See the
backend's own README to start it. The frontend just talks to that API.

## Setup

```bash
npm install
cp .env.example .env    # optional — only if your backend isn't on localhost:8000
npm run dev
```

Then open the URL Vite prints (usually `http://localhost:5173`).

## Configuration

The only setting is the backend URL, read from `VITE_API_BASE`:

```
VITE_API_BASE=http://localhost:8000
```

Leave the `.env` out and it defaults to `http://localhost:8000`, which matches the
backend's local dev server — so for local development you usually don't need to
configure anything.

## How it's organized

- **`src/api.ts`** — a small typed client for the backend. All network calls, token
  handling, and error normalization live here, so components never touch `fetch`
  directly. Request/response types mirror the backend's schemas.
- **`src/App.tsx`** — two screens: an auth screen (register / login) and the main
  workspace (document sidebar + upload + question/answer panel).
- **`src/index.css`** — design tokens (color, type scale, shared primitives).
- **`src/App.css`** — layout and component styles.

## Notes on the design

The interface is themed as an analytical instrument for reading filings: an
ink-navy and warm-paper palette, a serif display face (Fraunces) paired with a
clean interface sans (Inter), and answers rendered like margin annotations against
a gold rule.

## Building for production

```bash
npm run build      # type-checks and outputs to dist/
npm run preview    # serves the built output locally to check it
```

The `dist/` folder is a static bundle you can deploy to any static host. Point
`VITE_API_BASE` at your deployed backend when you build for production.
