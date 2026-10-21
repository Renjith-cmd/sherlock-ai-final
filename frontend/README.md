# Sherlock AI

Sherlock AI is a graph-first investigation workbench built with React, TypeScript, and Vite.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.

## Vercel Deployment

Import this repository into Vercel and set **Root Directory** to `frontend`.
Set the `VITE_API_BASE_URL` environment variable to the public origin of the
FastAPI backend (for example, `https://your-api.example.com`, without `/api`),
then deploy. Vercel builds with `npm run build` and serves `dist`.

Vercel hosts only the static frontend. The FastAPI backend must run separately
on a service with persistent storage, and it must allow requests from the
Vercel site origin. The current backend stores data in a local SQLite file, so
do not run it as a stateless serverless function; use durable backend/database
storage or migrate to a managed database first. Configure `SHERLOCK_AI_JWT_SECRET`
on the backend host.

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
