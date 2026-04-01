# TASKS — Operaciones de Renta Variable

Feature: Registro de compras/ventas de acciones/FIIs con recálculo automático de posiciones.

---

## Backend

### Modelo y Schema
- [ ] Crear `backend/app/models/equity_trade.py` (tabla equity_trades)
- [ ] Crear `backend/app/schemas/equity_trade.py` (EquityTradeCreate, EquityTradeUpdate, EquityTradeOut)
- [ ] Registrar EquityTrade en `backend/app/database.py` → `create_tables()`
- [ ] Crear `backend/migrations/add_equity_trades.py` (script idempotente)

### Servicio de Recálculo
- [ ] Crear `backend/app/services/equity_recalculate.py` con `recalculate_equity_positions()`
  - [ ] Normalizar from_date al primer día del mes
  - [ ] Obtener MonthlyPositions >= from_month ordenadas ASC
  - [ ] Para cada mes: calcular quantity acumulada (compras - ventas hasta fin de mes)
  - [ ] Actualizar quantity en MonthlyPosition
  - [ ] Si unit_price != null → actualizar balance_brl = quantity × unit_price
  - [ ] Calcular avg_price ponderado (solo compras) y actualizar mp.avg_price
  - [ ] Loguear warning si quantity resulta negativa (no lanzar excepción)

### Router y Endpoints
- [ ] Crear `backend/app/routers/equity_trades.py`
  - [ ] GET `/api/equity-trades/` — lista paginada con filtros
  - [ ] POST `/api/equity-trades/` — crear + recalcular
  - [ ] GET `/api/equity-trades/{id}` — detalle
  - [ ] PUT `/api/equity-trades/{id}` — editar + recalcular desde min(fecha_ant, fecha_nueva)
  - [ ] DELETE `/api/equity-trades/{id}` — eliminar + recalcular (204)
  - [ ] GET `/api/equity-trades/summary/{instrument_id}` — resumen P&L
- [ ] Registrar router en `backend/app/main.py` bajo `/api/equity-trades`

---

## Frontend

### API client
- [ ] Crear `frontend/src/api/equityTrades.ts`
  - [ ] `getEquityTrades(params)`
  - [ ] `createEquityTrade(data)`
  - [ ] `updateEquityTrade(id, data)`
  - [ ] `deleteEquityTrade(id)`
  - [ ] `getEquityTradeSummary(instrumentId)`

### Componentes
- [ ] Crear `frontend/src/components/EquityTradeForm.tsx` (formulario reutilizable: crear + editar)
  - [ ] Autocomplete de instrumento (ticker + nombre)
  - [ ] Toggle Compra/Venta
  - [ ] Date picker (default hoy)
  - [ ] Inputs numéricos (cantidad, precio)
  - [ ] Campo calculado Monto Total (read-only, cantidad × precio, en tiempo real)
  - [ ] Textarea notas (opcional)
- [ ] Crear `frontend/src/components/EquityTradeSummaryCard.tsx`
  - [ ] Mostrar qty actual, avg_price, último precio, P&L en BRL y %
  - [ ] Color verde/rojo según P&L
  - [ ] Badge rojo si qty_actual negativa

### Página principal
- [ ] Crear `frontend/src/pages/EquityTrades.tsx`
  - [ ] Sección superior: formulario nueva operación con toast de éxito
  - [ ] Sección inferior: tabla historial con filtros (instrumento, fechas, tipo)
  - [ ] Modal de edición (Dialog) con EquityTradeForm pre-cargado
  - [ ] AlertDialog de confirmación de eliminación con fecha afectada
  - [ ] Card de resumen al seleccionar instrumento en filtro
  - [ ] Paginación (50 por página)

### Integración
- [ ] Agregar ruta `/equity-trades` en `frontend/src/App.tsx`
- [ ] Agregar item "Operaciones" con icono `TrendingUp` en `frontend/src/components/layout/Sidebar.tsx`
- [ ] Agregar link "Ver operaciones" en `frontend/src/pages/Positions.tsx` (menú de fila para accion/fii)

---

## Documentación final
- [ ] Actualizar `CONTEXT.md` (tabla equity_trades, endpoints, página)
- [ ] Actualizar `PLAN.md` (marcar feature como completada)
- [ ] Commit del código
- [ ] Commit de documentación
