# TASKS — Crecimiento de Patrimonio

Feature: Reemplazar /annual con vista de Crecimiento de Patrimonio (anual + mensual)
Spec: specs/pending/prompt_crecimiento_patrimonio.txt

---

## PASO 0

- [x] Crear TASKS.md con todas las tareas
- [x] Crear lista en ClickUp (folder_id: 90177874339)
- [ ] Crear tareas en ClickUp por cada ítem

---

## BACKEND

- [ ] Reemplazar contenido de `backend/app/routers/annual.py`:
  - Endpoint `GET /api/annual` con lógica híbrida Transaction + AnnualSummary + PortfolioSnapshot
  - Calcular net_flow, gain, patrimonio_inicio, patrimonio_fin, data_source por año
  - Métricas globales: total_invested, total_gained, gain_ratio, cagr
- [ ] Agregar endpoint `GET /api/annual/monthly?year=`:
  - Serie mensual de patrimonio (PortfolioSnapshot más cercano a cada mes)
  - Transacciones del año agrupadas y en lista
  - Valorización acumulada por mes
  - Summary del año

---

## FRONTEND

- [ ] Crear `frontend/src/api/growth.ts`:
  - Tipos: AnnualItem, AnnualGrowthResponse, MonthlyPoint, MonthlyTransaction, MonthlyGrowthResponse
  - Funciones: `getAnnualGrowth()`, `getMonthlyGrowth(year)`

- [ ] Reemplazar `frontend/src/pages/Annual.tsx` — Vista Anual:
  - Header: título + total actual + tabs Anual/Mensual
  - Cards de métricas (4): total aportado, ganado por mercado, CAGR, mejor año
  - Gráfico barras agrupadas (Recharts): net_flow + gain por año, línea patrimonio_fin
  - Tabla anual: Año | Inicio | Aportes netos | Valorización | Fin | Crecim. | % valor. | Fuente
  - Indicador de fuente: ⚡ calculated vs 📋 legacy con tooltip

- [ ] Agregar Vista Mensual en `Annual.tsx`:
  - Selector de año (select con años DESC)
  - Cards de métricas (3): patrimonio fin, aportes netos, valorización
  - Gráfico de líneas (Recharts): patrimonio + valorización acum., dots personalizados en movimientos
  - Lista de movimientos del año

- [ ] Verificar consumidores de `annual.ts` y eliminar si solo lo usa Annual.tsx
- [ ] BarChartComp.tsx se mantiene (lo usa Proventos.tsx)

---

## QA

- [ ] GET /api/annual responde con items y metrics
- [ ] GET /api/annual/monthly?year=2024 responde con 12 meses, transactions y summary
- [ ] data_source = "calculated" para año con transacciones
- [ ] data_source = "legacy" para año sin transacciones
- [ ] metrics.cagr calculado correctamente
- [ ] Frontend: tab Anual funciona con tabla Fuente + íconos/tooltips
- [ ] Frontend: tab Mensual con selector de año y puntos de color en movimientos
- [ ] Frontend: cards de métricas correctas

---

## PASO FINAL

- [ ] Actualizar CONTEXT.md (sección Annual)
- [ ] Actualizar PLAN.md
- [ ] Mover spec a specs/done/
- [ ] Commit y push
- [ ] Mensaje Slack #claudio-coding
