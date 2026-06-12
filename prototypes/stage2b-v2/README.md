# Current lord visual frontend

`prototypes/stage2b-v2` is the current React/Vite visual frontend only for the
confirmed lord player flow.

## Confirmed current screens

- `/lords/login` - active generated login: cold castle background,
  `Witcher LARP I` logo image, and the dynamic chained plaque with `Вход` /
  `Обучение`.
- `/lords/home`
- `/lords/home?panel=orders`
- all `/lords/home` panels and follow-up lord screens opened from that home UI,
  including map, battle, buildings, recruit, raids, orders and territory flows

Successful login must authenticate through `/api/auth/role-token`, store the
lord token/id for `/lords/home`, and then open `/lords/home`.

## Removed old browser entrypoints

The old Stage 2B showcase/landing page and debug/index routes were removed from
runtime. The routes `/`, `/login`, `/lords`, `/lords/castle`,
`/lords/dashboard`, `/lords/endpoints` and `/endpoints` no longer render old
screens: they redirect to the canonical lord flow instead.

The FastAPI-served static lord panel under `backend/witcher_larp/web/lord/` was
deleted. The backend now acts as API/Admin Studio for the Vite lord frontend.

For local e2e checks, run the backend API separately and run this Vite app on
the browser port. The canonical e2e route is:

`/lords/login` -> `/lords/home` -> `/lords/home?panel=orders`.
