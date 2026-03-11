# Apparatus Frontend

**TypeScript, Next.js 15 (App Router), React 19, Redux Toolkit, Readium Web**

This is the e-reader web client. It is a fork of [Thorium Web](https://github.com/edrlab/thorium-web) that adds Auth0 authentication, a backend-for-frontend (BFF) proxy layer, and AI-powered features on top of the base Readium/Thorium e-reading experience.

Node version is managed by nvm (see `.nvmrc`). Package manager is pnpm.

## Local development

```bash
nvm use
pnpm install
pnpm dev
```

Or start everything at once from the repo root with `tmuxp load tmuxp.yaml`.

The frontend needs `reader_api` running (for BFF proxy targets) and a Readium CLI server (for publication content). See `../docs/README.md` for the full local setup.

### Environment variables

Copy `ENV_EXAMPLE` to `.env.local` and fill in values. See `ENV_EXAMPLE` for the full list with descriptions.

### Common operations

```bash
pnpm dev                # Development server with hot reload
pnpm build              # Production build
pnpm start              # Start production server
pnpm lint               # ESLint
pnpm typecheck          # TypeScript type checking
pnpm format             # Prettier formatting
pnpm generate-api-types # Regenerate API types from OpenAPI schema
pnpm add <package>      # Add a dependency
```

## Architecture

**BFF proxy**: the frontend does not expose backend credentials to the browser. Next.js API routes in `src/app/api/` act as a proxy: the browser makes a request with an Auth0 session cookie, the API route extracts the access token, and forwards the request to `reader_api` with an `Authorization: Bearer` header. All proxy logic is centralized in `src/lib/proxy.ts`, which provides `proxyJson` (for JSON API routes), `proxyStream` (for streaming publication assets), and `serverFetchJson` (for server-component data loading). The main streaming route is `api/pub/[...path]`, which forwards all publication resource requests to `reader_api`'s `/read/` routes.

**API types**: request and response types are generated from reader_api's Pydantic models via OpenAPI. The generated file is `src/lib/api-types.generated.ts`, and convenience re-exports live in `src/lib/api.ts`. To regenerate after a backend model change, run `./scripts/generate-api-types.sh` from the repo root (or `pnpm generate-api-types` for just the TS generation step).

**Auth**: uses `@auth0/nextjs-auth0` v4. The session is stored as an HTTP-only cookie. Middleware checks authentication on all routes except `/login` and `/auth`.

**Readium Web**: the reader uses `@readium/navigator` to render EPUB content inside an iframe. Publication manifests are fetched through the BFF proxy, so Readium's requests get authenticated automatically.

**Redux**: the store is configured in `src/lib/store.ts` with reducers for reader state, display settings, theming, publication metadata, text selection, and RTK Query API endpoints. State is persisted to localStorage with debouncing.

**Plugins**: reader functionality is extended via plugins in `src/components/Plugins/`. The default plugin provides base reader behavior; the answers plugin adds AI-powered Q&A for selected text.

**Preferences**: the preferences system in `src/preferences/` controls typography, theming, actions, docking, and display configuration. `ThPreferencesProvider` exposes settings via React context; `ThReduxPreferencesAdapter` bridges them with the Redux store.

## Upstream

This frontend is a fork of [Thorium Web](https://github.com/edrlab/thorium-web). The package is published as `@edrlab/thorium-web` and can be used independently (see Thorium Web's docs). Apparatus-specific additions are primarily in `src/app/api/`, `src/components/Plugins/`, `src/components/SelectionToolbar/`, and the Auth0 integration.
