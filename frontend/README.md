# Apparatus Frontend

**TypeScript, Next.js 15 (App Router), React 19, Redux Toolkit, Readium Web**

This is the e-reader web client. It is a fork of [Thorium Web](https://github.com/edrlab/thorium-web) that adds Auth0 authentication, a backend-for-frontend (BFF) proxy layer, and AI-powered features on top of the base Readium/Thorium e-reading experience.

Node version is managed by nvm (see `.nvmrc`). Package manager is pnpm.

## Local development

```bash
nvm use          # use Node v22
pnpm install
pnpm dev         # starts Next.js on http://localhost:3000
```

Or start everything at once from the repo root with `tmuxp load tmuxp.yaml`.

The frontend needs `reader_api` running (for BFF proxy targets) and a Readium CLI server (for publication content). See `../docs/README.md` for the full local setup.

### Environment variables

Copy or create `.env.local` in this directory. Key variables:

| Variable | Purpose |
|----------|---------|
| `READER_API_ORIGIN` | URL of reader_api (default `http://localhost:8000`) |
| `NEXT_PUBLIC_MANIFEST_BASE_URL` | Where the Readium navigator fetches manifests from (default `http://localhost:3000/api/pub`) |
| `AUTH0_SECRET` | Encryption key for Auth0 session cookies |
| `AUTH0_DOMAIN` | Auth0 tenant domain |
| `AUTH0_CLIENT_ID` / `AUTH0_CLIENT_SECRET` | Auth0 application credentials |
| `AUTH0_AUDIENCE` | Auth0 API audience identifier |
| `AUTH0_SCOPE` | OAuth scopes (`openid profile email read:reading_state write:reading_state`) |
| `APP_BASE_URL` | Public URL of this frontend (also aliased as `AUTH0_BASE_URL`) |

### Common operations

```bash
pnpm dev              # Development server with hot reload
pnpm build            # Production build
pnpm start            # Start production server
pnpm lint             # ESLint
pnpm typecheck        # TypeScript type checking
pnpm format           # Prettier formatting
pnpm add <package>    # Add a dependency
```

## Architecture

### BFF proxy

The frontend does not expose backend credentials to the browser. Instead, Next.js API routes act as a proxy:

1. Browser makes request with Auth0 session cookie
2. API route extracts the access token from the session
3. Adds `Authorization: Bearer` header and forwards to `reader_api`

This is implemented in `src/app/api/`. The main proxy route is `pub/[...path]/route.ts`, which forwards all publication resource requests (`/api/pub/*` -> `reader_api /read/*`).

### Auth0

Uses `@auth0/nextjs-auth0` v4. The session is stored as an HTTP-only cookie. `src/middleware.ts` checks authentication on all routes except `/login` and `/auth`.

### Readium Web integration

The reader uses `@readium/navigator` to render EPUB content inside an iframe. The `StatefulReader` component (in `src/components/Epub/`) wraps the navigator and connects it to the Redux store.

Publication manifests are fetched through the BFF proxy, which means Readium's navigator requests flow through `/api/pub/` and get authenticated automatically.

### Redux store

Configured in `src/lib/store.ts`. Key reducers:

| Reducer | Purpose |
|---------|---------|
| `readerReducer` | Loading state, immersive mode, fullscreen |
| `settingsReducer` | Font size, line height, spacing |
| `themeReducer` | Theme and color scheme |
| `publicationReducer` | Publication metadata, position lists |
| `selectionReducer` | Text selection state |
| `readerApi` | RTK Query endpoints for API calls |

State is persisted to localStorage with debouncing.

### Plugin system

Reader functionality is extended via plugins (`src/components/Plugins/`):

- `createDefaultPlugin()` - base reader behavior
- `createAnswersPlugin()` - AI-powered Q&A for selected text

### Preferences

The preferences system (`src/preferences/`) controls typography, theming, actions, docking, and display configuration. `ThPreferencesProvider` makes settings available via React context. `ThReduxPreferencesAdapter` bridges preferences with the Redux store.

## Directory structure

```
src/
├── app/                        # Next.js App Router
│   ├── page.tsx                # Home page (publication grid)
│   ├── layout.tsx              # Root layout (Redux, Preferences, i18n providers)
│   ├── login/                  # Auth0 login page
│   ├── read/[identifier]/      # Reader page
│   │   ├── page.tsx            # Server component: fetches reading location
│   │   └── ReaderClientPage.tsx # Client component: renders the reader
│   └── api/                    # BFF proxy routes
│       ├── pub/[...path]/      # Publication content proxy -> reader_api /read/
│       ├── reading-state/      # Save reading position -> reader_api /api/reading-state
│       ├── ask-automatic/      # AI Q&A proxy -> reader_api /api/ask-automatic
│       ├── protected/          # Auth test endpoint
│       └── verify-manifest/    # Manifest domain verification
├── components/
│   ├── Epub/                   # Core reader components (StatefulReader + subcomponents)
│   ├── Plugins/                # Reader plugin system
│   ├── SelectionToolbar/       # Text selection toolbar (triggers AI answers)
│   ├── Settings/               # Reader display settings UI
│   ├── Sheets/                 # Modal/bottom sheet UI
│   ├── Docking/                # Resizable panel layout
│   ├── Actions/                # Action bar components
│   ├── PublicationGrid.tsx     # Library grid of book covers
│   ├── UserMenu.tsx            # User avatar/menu
│   └── Stateful*.tsx           # State-connected reader UI pieces
├── lib/
│   ├── store.ts                # Redux store configuration
│   ├── api.ts                  # RTK Query API definitions
│   ├── auth0.ts                # Auth0 client setup
│   └── *Reducer.ts             # Redux slice reducers
├── preferences/                # Preference system (types, defaults, provider)
├── core/                       # Generic components, helpers, hooks (bundled for package export)
├── hooks/                      # App-specific hooks (usePublication, etc.)
├── helpers/                    # Utility functions
├── i18n/                       # i18next configuration and provider
├── config/                     # Publication manifest configuration
├── types/                      # TypeScript type definitions
└── middleware.ts               # Auth0 session checks for all routes
```

## Upstream

This frontend is a fork of [Thorium Web](https://github.com/edrlab/thorium-web). The package is published as `@edrlab/thorium-web` and can be used independently (see Thorium Web's docs). Apparatus-specific additions are primarily in `src/app/api/`, `src/components/Plugins/`, `src/components/SelectionToolbar/`, and the Auth0 integration.
