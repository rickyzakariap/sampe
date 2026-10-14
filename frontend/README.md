# frontend (fastapi-vite-shadcn)

React 19 + JavaScript on **Vite**, Tailwind CSS **v4** via `@tailwindcss/vite` (theme tokens live in
`src/index.css` under `@theme`; there is no `tailwind.config.js`/`postcss.config.js`), shadcn/ui (Radix),
react-router-dom, axios, TanStack Query (`QueryClientProvider` mounted in `src/index.js`, client in
`src/lib/queryClient.js`).

Same conventions as the classic `shadcn` (fastapi_react_mongo_shadcn) template: JSX lives in `.js` files (`src/index.js`,
`src/App.js`), the `@/*` alias maps to `src/*`, and the frontend reads
`process.env.REACT_APP_BACKEND_URL` from `frontend/.env` (Vite inlines every `REACT_APP_*` key
at build time via `vite.config.mjs`).

## Scripts

- `npm ci` — install exactly from `package-lock.json`
- `npm run start` / `npm run dev` — Vite dev server on port 3000
- `npm run build` — production bundle into `build/`
- `npm run preview` — serve the production bundle locally

Hot reload is Vite HMR; restart the dev server after changing `.env` or
`vite.config.mjs`, or after installing dependencies.

Visual edits: the packaged `@emergentbase/visual-edits` plugin tags `.jsx`/`.tsx`; because this
template keeps JSX in `.js`, `vite.config.mjs` stamps the same `x-*` metadata on `src/**/*.js`
before compiling the JSX (dev server only; `DISABLE_VISUAL_EDITS=true` turns it off).
