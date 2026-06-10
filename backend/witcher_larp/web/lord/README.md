# Legacy static lord panel

This FastAPI-served static lord panel is legacy. Do not use its login screen as
the current lord browser UI for visual/e2e checks.

Current lord visual/e2e work lives in:

- `prototypes/stage2b-v2/src/App.tsx`
- `prototypes/stage2b-v2/src/index.css`
- `prototypes/stage2b-v2/package.json`

Run the backend as the API server and the React/Vite frontend on the browser
port. `/lords/home`, `/lords/home?panel=orders`, and the lord panels/screens
opened from `/lords/home` are the current main flow. The active login is the
generated Warcraft-3-style chained plaque in the Vite app, connected to
`/api/auth/role-token`.
