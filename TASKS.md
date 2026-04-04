# TASKS — Import Internacional XP

Feature: Importador de posiciones y dividendos desde extracto PDF de XP International.
Wizard de 3 pasos: upload PDF → preview diff → confirmar.

---

## Setup
- [ ] Agregar `pdfplumber` a `backend/requirements.txt`
- [ ] Actualizar lista de custodios normalizados en `CONTEXT.md` (agregar XP_INTERNATIONAL)

## Fix update-equities-prices (prerequisito crítico)
- [ ] Leer código actual de `update-equities-prices` en `backend/app/routers/positions.py`
- [ ] Separar instrumentos en lote BRL (ticker + ".SA") y lote USD (sin sufijo)
- [ ] Para instrumentos USD: actualizar `balance_usd` y calcular `balance_brl = balance_usd * mp.usd_rate`
- [ ] Descargar ambos lotes en llamadas separadas a `yf.download()`

## Backend — Parser
- [ ] Crear `backend/app/services/international_importer.py`
- [ ] Implementar `parse_xp_international_pdf()` con pdfplumber
- [ ] Implementar `_merge_symbol_cusip_rows()` para manejar CUSIP en fila separada
- [ ] Implementar `parse_atividade()` filtrando solo CASH_DIVIDEND
- [ ] Implementar `parse_period_dates()` extrayendo fechas del header
- [ ] Implementar `get_usd_brl_rate()` con yfinance (BRL=X)

## Backend — Clasificación y Matching
- [ ] Implementar `classify_international()` (UST / CORP_BOND / ETF)
- [ ] Implementar `match_instrument()` (CUSIP → ticker → instrument_code_mappings)

## Backend — Diff y Apply
- [ ] Implementar `compute_position_diffs()` comparando con MonthlyPosition existente
- [ ] Implementar `check_dividend_duplicates()` contra provento_items
- [ ] Implementar `apply_import_positions()` con upsert MonthlyPosition
- [ ] Implementar `apply_import_dividends()` creando ProvéntoItem

## Backend — Router
- [ ] Crear `backend/app/routers/import_international.py`
- [ ] Endpoint `POST /api/import/international/preview`
- [ ] Endpoint `POST /api/import/international/confirm`
- [ ] Endpoint `POST /api/import/international/map-instrument`
- [ ] Registrar router en `backend/app/main.py`

## Frontend
- [ ] Crear `frontend/src/api/importInternational.ts`
- [ ] Crear `frontend/src/pages/ImportInternational.tsx` (wizard 3 pasos)
  - [ ] Paso 1: upload PDF + tipo de cambio + opciones
  - [ ] Paso 2: tabs posiciones/dividendos con checkboxes y resumen
  - [ ] Paso 3: resultado con métricas de importación
- [ ] Agregar ruta `/import/international` en `frontend/src/App.tsx`
- [ ] Agregar botón "Importar Internacional" en `frontend/src/pages/Positions.tsx`
- [ ] Agregar entrada en sidebar bajo "Importar" en `frontend/src/components/layout/Sidebar.tsx`

## Verificación
- [ ] Test E2E: subir PDF de Marzo 2026, confirmar, verificar 8 posiciones en BD
- [ ] Test duplicados: segunda importación del mismo PDF → 0 nuevas posiciones, 0 nuevos dividendos
- [ ] Verificar balance_brl calculado correctamente con rate ingresado
- [ ] Verificar que update-equities-prices actualiza VOO/RDVY sin romper PETR4/VALE3

## Documentación final
- [ ] Actualizar `CONTEXT.md` (endpoints, custodio XP_INTERNATIONAL, página ImportInternational)
- [ ] Actualizar `PLAN.md` (marcar feature como completada)
- [ ] Mover spec de `specs/pending/` a `specs/done/`
- [ ] Commit código + documentación
