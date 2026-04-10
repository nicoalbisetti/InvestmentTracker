# TASKS — Ticker de Renta Variable en Dashboard

## Backend

- [ ] Backend: nuevo archivo `backend/app/routers/ticker.py` con helper `get_equity_tickers()` y cache en memoria
- [ ] Backend: endpoint `GET /api/ticker/quotes` con cache TTL 5 min y lógica yfinance
- [ ] Backend: registrar router en `main.py`

## Frontend

- [ ] Frontend: nuevo archivo `frontend/src/api/ticker.ts` con tipos e interfaz
- [ ] Frontend: componente `TickerBand.tsx` con animación marquee, hover pause, shimmer loading
- [ ] Frontend: integrar `TickerBand` en `Dashboard.tsx` con ancho completo (negative margins)

## Documentación

- [ ] Docs: actualizar `CONTEXT.md` con endpoint `/api/ticker/quotes` y feature TickerBand
- [ ] Docs: actualizar `PLAN.md` marcando la tarea como completada
- [ ] Docs: mover spec de `specs/pending/` a `specs/done/`
- [ ] Docs: commit y push
