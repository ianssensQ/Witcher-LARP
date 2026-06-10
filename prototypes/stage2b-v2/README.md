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

## Legacy / reference screens

Everything outside the confirmed list above is legacy/reference until the user
explicitly re-confirms it in a later screen pass.

- `/login` is legacy. This is the old Stage 2B showcase/landing page from the
  screenshot with "Ведьмачий ЛАРП: командный стол, Гвинт и мобильные досье";
  it is not the active lord login.
- `/` is legacy. It shows the generic showcase composition with `HeroHeader`,
  `LordCommandTable`, `GwentBoard`, `MobileRoleScreens`, `AdminOps` and
  `AssetHandoff`.
- `/lords`, `/lords/castle` and `/lords/dashboard` are compatibility/old alias
  routes, not canonical acceptance entry points.
- `/lords/endpoints` and `/endpoints` are debug/index screens, not player flow.
- Any plain/static login panel or local-only code validation that bypasses
  backend role-token auth is legacy.
- The FastAPI static panel in `backend/witcher_larp/web/lord/` is legacy.

For local e2e checks, run the backend API separately and run this Vite app on
the browser port. The canonical e2e route is:

`/lords/login` -> `/lords/home` -> `/lords/home?panel=orders`.
