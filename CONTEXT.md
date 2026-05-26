# CONTEXT.md — InvestmentTracker

> Documento de contexto para nuevas sesiones de Claude Code / Claude.ai.
> Refleja el estado REAL del código al 25 May 2026 (actualizado: Export CSV en Histórico de Posiciones).

---

## 1. Stack Tecnológico

**Backend:**
- Python 3.12
- FastAPI >= 0.111.0
- SQLAlchemy >= 2.0.0
- Uvicorn >= 0.30.0
- pandas >= 2.0.0
- openpyxl >= 3.1.0
- yfinance >= 0.2.0
- pdfplumber >= 0.11.0
- Pydantic >= 2.0.0
- python-dateutil >= 2.8.0
- requests >= 2.28.0

**Frontend:**
- React 18.3.1
- TypeScript ~5.6.2
- Vite 5.4.10
- React Router DOM 6.30.3
- Axios 1.13.6
- Recharts 3.8.0
- Tailwind CSS 3.4.19
- Lucide React 0.577.0
- date-fns 4.1.0

**Base de datos:** SQLite (`backend/investment_tracker.db`)

---

## 2. Cómo Levantar el Sistema

```bash
./start.sh
```

O manualmente:

```bash
# Backend
cd backend
pip3 install -r requirements.txt
python3 -m uvicorn app.main:app --reload --port 8000

# Frontend (otra terminal)
cd frontend
npm install
npm run dev
```

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://localhost:5173`
- La DB se crea automáticamente en `backend/investment_tracker.db` al iniciar.

---

## 3. Estructura de Carpetas

```
InvestmentTracker/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app, routers, startup migrations
│   │   ├── database.py                 # Engines, sessions, _migrate_provento_items(), _migrate_return_source()
│   │   ├── models/
│   │   │   ├── instrument.py
│   │   │   ├── monthly_position.py
│   │   │   ├── portfolio_snapshot.py
│   │   │   ├── annual_summary.py
│   │   │   ├── provento.py
│   │   │   ├── provento_item.py
│   │   │   ├── provento_forecast.py
│   │   │   ├── quote.py
│   │   │   ├── transaction.py
│   │   │   ├── import_log.py
│   │   │   ├── instrument_code_mapping.py
│   │   │   └── market_rate.py
│   │   ├── routers/
│   │   │   ├── dashboard.py
│   │   │   ├── positions.py
│   │   │   ├── history.py
│   │   │   ├── annual.py
│   │   │   ├── proventos.py
│   │   │   ├── provento_forecast.py
│   │   │   ├── transactions.py
│   │   │   ├── instruments.py
│   │   │   ├── quotes.py
│   │   │   ├── import_excel.py
│   │   │   ├── import_fixed_income.py
│   │   │   ├── import_proventos.py
│   │   │   ├── import_international.py
│   │   │   ├── equity_trades.py
│   │   │   └── ticker.py
│   │   ├── services/
│   │   │   ├── importer.py
│   │   │   ├── fixed_income_importer.py
│   │   │   ├── proventos_importer.py
│   │   │   ├── international_importer.py
│   │   │   ├── equity_recalculate.py
│   │   │   ├── return_calculator.py
│   │   │   └── performance.py
│   │   └── schemas/
│   │       ├── common.py
│   │       ├── instrument.py
│   │       ├── transaction.py
│   │       └── fixed_income_import.py
│   ├── create_demo_db.py               # Genera investment_tracker_demo.db con datos falsos
│   ├── import_initial_data.py          # Importa Inversiones.xlsx al inicio
│   ├── migrate_fixed_income.py         # Script de migración de schema
│   ├── investment_tracker.db
│   ├── investment_tracker_demo.db
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx                     # Router principal
│   │   ├── main.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Positions.tsx
│   │   │   ├── History.tsx
│   │   │   ├── Annual.tsx
│   │   │   ├── Proventos.tsx
│   │   │   ├── Transactions.tsx
│   │   │   ├── Settings.tsx
│   │   │   ├── ImportFixedIncome.tsx
│   │   │   ├── ImportProventos.tsx
│   │   │   ├── ImportInternational.tsx
│   │   │   └── EquityTrades.tsx
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   └── Sidebar.tsx         # Incluye toggle Demo/Real
│   │   │   ├── charts/
│   │   │   │   └── BarChartComp.tsx
│   │   │   └── ui/
│   │   │       ├── KpiCard.tsx
│   │   │       ├── Modal.tsx
│   │   │       ├── SkeletonLoader.tsx
│   │   │       └── InstrumentCombobox.tsx  # Combobox reutilizable con búsqueda (nombre + custodian)
│   │   ├── context/
│   │   │   ├── ThemeContext.tsx
│   │   │   └── EnvContext.tsx          # Demo/Real env, persiste en localStorage
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   └── ...
│   │   │   └── TickerBand.tsx          # Banda animada de tickers (marquee)
│   │   ├── api/
│   │   │   ├── client.ts               # Axios instance + X-Env header interceptor
│   │   │   ├── dashboard.ts
│   │   │   ├── positions.ts
│   │   │   ├── history.ts
│   │   │   ├── annual.ts
│   │   │   ├── proventos.ts
│   │   │   ├── transactions.ts
│   │   │   ├── instruments.ts
│   │   │   ├── import.ts
│   │   │   ├── importFixedIncome.ts
│   │   │   ├── importProventos.ts
│   │   │   ├── importInternational.ts
│   │   │   ├── equityTrades.ts
│   │   │   └── ticker.ts
│   │   └── utils/
│   │       └── formatters.ts
│   └── package.json
├── specs/
│   └── pending/
│       ├── prompt_importacion_renta_fija.txt
│       └── prompt_importacion_proventos.txt
├── start.sh
├── README.md
├── TASKS.md
├── PLAN.md
└── CONTEXT.md
```

---

## 4. Modelos de Base de Datos

### Instrument — `instruments`
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK | NO |
| name | String | NO |
| ticker | String | SI, indexed |
| custodian | String | NO |
| type | String | NO, default="outro" |
| location | String | NO, default="brasil" |
| currency | String | NO, default="BRL" |
| maturity_date | Date | SI |
| issue_date | Date | SI |
| index_type | String | SI — PREFIXADO \| IPCA \| DI \| SELIC |
| in_liquidation | Boolean | NO, default=False |
| pays_dividends | Boolean | NO, default=False |
| asset_class | String | SI — CDB \| CRI \| CRA \| DEB \| LCA \| LCI \| LIG \| TD \| FUNDO_CREDITO |
| liquidity | String | SI |
| status | String | NO, default="activo" — activo \| cerrado \| sin_datos |
| rank_1m … rank_12m | Integer | SI |
| return_1m … return_12m | Float | SI |
| current_balance_brl | Float | SI — cache del balance actual |
| portfolio_pct | Float | SI |
| return_source | String | SI — "price" \| "balance" \| "none" (método usado en último recalculate-stats) |
| created_at | DateTime | NO |

**Tipos válidos:** `accion`, `fii`, `renta_fija`, `fundo`, `previdencia`, `prestamos`, `saving`, `fgts`, `outro`

---

### MonthlyPosition — `monthly_positions`
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK | NO |
| instrument_id | FK → instruments, indexed | NO |
| date | Date, indexed | NO — siempre día 1 del mes |
| balance_brl | Float | SI |
| balance_usd | Float | SI |
| usd_rate | Float | SI |
| applications | Float | SI |
| redemptions | Float | SI |
| calculated_balance | Float | SI |
| previous_balance | Float | SI |
| gain | Float | SI |
| gain_pct | Float | SI |
| proventos | Float | SI |
| avg_price | Float | SI |
| quantity | Float | SI |
| unit_price | Float | SI |
| custodian_override | String | SI — "XP" \| "SANTANDER" \| "INTER" para cross-custodio |
| capital_invested | Float | SI — Valor Aplicado (solo Tesouro Direto) |

**UNIQUE:** `(instrument_id, date, custodian_override)`

---

### PortfolioSnapshot — `portfolio_snapshots`
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK | NO |
| date | Date, indexed, UNIQUE | NO |
| total_brl | Float | SI |
| total_with_prev | Float | SI — suma todas las posiciones activas |
| total_usd | Float | SI |
| total_usd_with_prev | Float | SI |
| usd_rate | Float | SI |
| monthly_change_pct | Float | SI |
| total_without_b3 | Float | SI |
| hsbc_total … usa_total | Float | SI — desglose por custodio |

---

### AnnualSummary — `annual_summaries`
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK | NO |
| year | Integer, UNIQUE | NO |
| year_date | Date | SI |
| total | Float | SI — valor inicio del año |
| diff | Float | SI — total final - total inicio |
| gain | Float | SI |
| net_flow | Float | SI — aplicaciones - rescates |

---

### Provento — `proventos` (agregado anual histórico)
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK | NO |
| instrument_id | FK → instruments, indexed | NO |
| year | Integer | NO |
| month | Integer | SI — NULL = total anual |
| amount | Float | SI |

**UNIQUE:** `(instrument_id, year, month)`

> **IMPORTANTE:** Solo se usa para años anteriores al año actual. El año actual siempre
> se lee desde `provento_items`. Nunca escribir nuevos registros para el año en curso en esta tabla.

---

### ProvéntoItem — `provento_items` (transaccional)
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK | NO |
| instrument_id | FK → instruments, indexed | NO |
| date | Date | NO |
| amount_brl | Float | NO |
| type | String(50) | NO — 'dividendo' \| 'jcp' \| 'amortizacion' |
| notes | Text | SI |
| quantity | Float | SI |
| unit_price | Float | SI |
| custodian | String(50) | SI — 'XP' \| 'SANTANDER' \| 'INTER' |
| source | String(50) | SI — 'MANUAL' \| 'EXCEL_XP_SANTANDER' |
| import_batch_id | String(36), indexed | SI |
| raw_event_type | Text | SI — "Tipo de Evento" original del Excel |

**UNIQUE:** `(instrument_id, date, type, amount_brl)`

> La constraint incluye `amount_brl` para permitir 2 pagos del mismo tipo en el mismo día
> con montos diferentes (ej: 2 pagos JCP). Solo bloquea registros 100% idénticos.

---

### ProventoForecast — `provento_forecast`
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK | NO |
| instrument_id | FK → instruments, indexed | NO |
| year | Integer | NO |
| month | Integer | NO — 1-12 |
| amount | Float | NO |

**UNIQUE:** `(instrument_id, year, month)`

---

### Transaction — `transactions`
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK | NO |
| instrument_id | FK → instruments, indexed | NO |
| date | Date, indexed | NO |
| type | String | NO — aplicacion \| rescate \| provento \| outro |
| amount_brl | Float | SI |
| amount_usd | Float | SI |
| notes | Text | SI |
| created_at | DateTime | NO |

> Al crear/editar/eliminar una transacción, se recalcula automáticamente `balance_brl`
> y `balance_usd` en `monthly_positions` desde el mes de la transacción en adelante.
> Lógica: balance_mes = balance_mes_anterior + aplicaciones - rescates.

---

### Quote — `quotes`
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK | NO |
| date | Date, UNIQUE | NO — día 1 del mes |
| usd_brl | Float | SI |
| bvmf3_price | Float | SI |

---

### ImportLog — `import_logs`
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK | NO |
| filename | String | NO |
| imported_at | DateTime | NO |
| status | String | NO — success \| partial \| failed |
| records_* | Integer | SI — conteos por entidad |
| warnings | JSON | NO, default=[] |
| errors | JSON | NO, default=[] |

---

### InstrumentCodeMapping — `instrument_code_mappings`
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK | NO |
| codigo_excel | String, UNIQUE, indexed | NO |
| instrument_id | FK → instruments | NO |
| created_at | DateTime | NO |

---

### MarketRate — `market_rates`
| Campo | Tipo | Nullable |
|---|---|---|
| date | String(7), PK | NO — "YYYY-MM" |
| series | String(10), PK | NO — "cdi" \| "ipca" |
| rate | Float | NO |

---

### EquityTrade — `equity_trades`
| Campo | Tipo | Nullable |
|---|---|---|
| id | INTEGER PK, autoincrement | NO |
| instrument_id | FK → instruments, indexed | NO |
| date | Date, indexed | NO — fecha exacta de la operación |
| trade_type | String(10) | NO — "compra" \| "venta" |
| quantity | Float | NO — siempre positivo |
| price | Float | NO — precio unitario en BRL (o USD si currency=USD) |
| amount_brl | Float | SI — calculado como quantity × price al guardar |
| notes | Text | SI |
| created_at | DateTime | NO |

> Sin UNIQUE constraint: se permiten múltiples operaciones del mismo instrumento el mismo día.
> Al crear/editar/eliminar un EquityTrade se recalcutan las MonthlyPosition desde el mes de la
> operación en adelante via `equity_recalculate.recalculate_equity_positions()`.

---

## 5. Endpoints Implementados

### `/api/dashboard`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/kpis` | total_brl, ytd_pct, monthly_change, proventos_ytd, proventos_projection |
| GET | `/evolution?range=1y\|3y\|5y\|all&currency=BRL\|USD` | Serie histórica del portfolio |
| GET | `/distribution` | Distribución por tipo, custodio y localización. Response: `{ by_type, by_custodian, by_location }`. `by_location` agrupa por `Instrument.location` (null → "brasil"). |
| GET | `/evolution-by-type?range=...` | Evolución apilada por tipo |
| GET | `/benchmarks?range=...` | CDI/IPCA desde BCB (cacheado en market_rates) |
| GET | `/maturities` | Posiciones agrupadas por mes de vencimiento |
| GET | `/top-bottom` | Top 5 y Bottom 5 instrumentos |

### `/api/positions`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/?sort=default&order=asc&...` | Lista paginada; sort=default → brasil→exterior→tipo→nombre |
| GET | `/export` | CSV stream con posiciones |
| PATCH | `/{mp_id}/unit-price` | Actualiza unit_price y recalcula balances en cascada (accion/fii). BRL: balance_brl = qty × price, balance_usd = balance_brl / usd_rate. USD: balance_usd = qty × price, balance_brl = balance_usd × usd_rate. Usa mp.usd_rate con fallback al PortfolioSnapshot del mes. Llama sync_snapshot_for_date. |
| PATCH | `/{mp_id}/balance` | Actualiza balance_brl, balance_usd o quantity |
| GET | `/last-fixed-income-date` | Último mes importado (renta_fija) |
| GET | `/count-without-price` | Count de renta_fija activos sin balance |
| POST | `/update-equities-prices?month=YYYY-MM` | Actualiza precios B3 via yfinance |
| POST | `/update-usd-rate?month=YYYY-MM` | Actualiza cotización USD/BRL. Clasifica posiciones por `Instrument.currency` (no `location`). Persiste `usd_rate` en cada `MonthlyPosition`. Recalcula snapshot via `sync_snapshot_for_date`. Response incluye `usd_recalculated`, `brl_recalculated`, `skipped_no_balance`. |
| POST | `/copy-previous-month` | Copia balances/quantities de los instrumentos activos al mes actual |
| POST | `/recalculate-stats` | Recalcula current_balance_brl, portfolio_pct, return_1m/3m/6m/12m (vía compute_period_return), return_source, rankings |
| POST | `/ensure-month` | Crea MonthlyPosition vacía para instrument_id+month si no existe; retorna mp_id |

### `/api/history`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/{instrument_id}?date_from&date_to` | Historial de posiciones + métricas |
| GET | `/compare?ids=1,2,3` | Comparación multi-instrumento |
| GET | `/monthly?year&currency&custodian&type&market` | Matriz mensual: instrumentos × 12 meses con totals |
| GET | `/annual?currency&custodian&type&market` | Matriz anual: instrumentos × últimos 10 años con totals |

### `/api/annual`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Lógica híbrida: Transaction si hay datos ese año → `data_source=calculated`; AnnualSummary legacy → `data_source=legacy`. Items con patrimonio_inicio/fin, net_flow, gain, diff, pct_growth, pct_valorization. Metrics: total_invested, total_gained, gain_ratio, cagr. |
| GET | `/monthly?year=` | Serie mensual de 12 meses para el año: patrimonio exacto de cada PortfolioSnapshot del mes, net_flow acumulado, valorización acumulada (vs base dic año anterior). Lista de transacciones del año con instrument_name. Summary: patrimonio_inicio/fin, net_flow_total, gain_total, pct_net_flow, pct_gain. |

### `/api/proventos`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/?page&limit&status` | Tabla anual por instrumento (año actual = provento_items + forecast) |
| GET | `/monthly?year` | Serie mensual: {month, amount(pagado), forecast(no pagado)} |
| GET | `/grid?year&type` | Grilla editable mensual; incluye `forecast_months` (previstos donde no hay pago) y `paid_month_totals` para coloración diferenciada de totales |
| PATCH | `/grid/{instrument_id}/{year}/{month}` | Reemplaza TODOS los registros de la celda con uno MANUAL |

### `/api/proventos/forecast`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/?year&type` | Grilla de previsión; orden: brasil→exterior→tipo→nombre |
| PATCH | `/{instrument_id}/{year}/{month}` | Upsert forecast para una celda |
| POST | `/import/preview` | Preview importación Excel de forecast |
| POST | `/import/confirm` | Confirma importación de forecast |

### `/api/transactions`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/?instrument_id&type&date_from&date_to&custodian&month_year&page&limit` | Lista paginada. `custodian` filtra por join a Instrument. `month_year` ("YYYY-MM") filtra por mes. |
| POST | `/` | Crea transacción + recalcula monthly_positions. Acepta `amount_brl` y `amount_usd` opcionales; el frontend calcula el secundario con cotización del mes. |
| PUT | `/{txn_id}` | Actualiza + recalcula |
| DELETE | `/{txn_id}` | Elimina + recalcula |

### `/api/instruments`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/?status&type&location&currency&custodian&search&sort&order&page&limit` | Lista paginada |
| POST | `/` | Crea instrumento manualmente; opcionalmente crea MonthlyPosition con balance_usd calculado |
| GET | `/{id}` | Detalle |
| PUT | `/{id}` | Actualiza campos |
| POST | `/{id}/rescate-total` | Crea transacción rescate y cierra instrumento (solo renta_fija activo) |

### `/api/import`
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/` | Import Excel genérico (6 hojas) |
| GET | `/history` | Log de importaciones |
| GET | `/history/{log_id}` | Detalle de una importación |

### `/api/import/fixed-income`
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/preview` | Parsea Excel, calcula diff, devuelve token (30 min TTL) |
| POST | `/confirm` | Aplica import usando token |
| GET | `/suggestions?file_token&codigo` | Sugerencias de matching para un código |
| POST | `/map-instrument` | Persiste mapeo codigo_excel → instrument_id |

### `/api/import/proventos`
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/preview` | Parsea Excel de proventos, calcula diff |
| POST | `/confirm` | Aplica import |
| POST | `/map-instrument` | Mapeo manual de instrumento |

### `/api/import/international`
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/preview` | Parsea PDF XP International, clasifica, matchea, devuelve diff posiciones + dividendos (token 30 min TTL) |
| POST | `/confirm` | Aplica import usando token: upsert MonthlyPosition + crea ProvéntoItem |
| POST | `/map-instrument` | Persiste mapeo clave (CUSIP/ticker) → instrument_id |

### `/api/equity-trades`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/?instrument_id&date_from&date_to&trade_type&page&limit` | Lista paginada con EquityTradeOut (incluye instrument_name, ticker) |
| POST | `/` | Crea operación, calcula amount_brl, dispara recálculo; retorna + recalculated_months, affected_from |
| GET | `/{id}` | Detalle de una operación |
| PUT | `/{id}` | Edita operación, recalcula desde min(date_anterior, date_nueva) |
| DELETE | `/{id}` | Elimina + recalcula; status 204 |
| GET | `/summary/{instrument_id}` | Resumen: qty_actual, avg_price_compra, ultimo_precio, pl_no_realizado, pl_no_realizado_pct |

---

### `/api/quotes`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/lookup?month=YYYY-MM` | Retorna `{ month, rate, found }` con la cotización USD/BRL almacenada para ese mes. `rate=null` y `found=false` si no existe. |
| GET | `/?date_from&date_to` | Lista de cotizaciones |
| POST | `/` | Upsert cotización (usd_brl, bvmf3_price) |

### `/api/ticker`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/quotes` | Precios y variación del día de instrumentos accion/fii activos vía yfinance. Cache en memoria TTL 5 min. Tickers B3 con sufijo ".SA". Responde siempre HTTP 200. |

### Otros
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | `{status: "ok", version: "1.0.0"}` |
| GET | `/api/env` | Retorna env activo según header X-Env |
| POST | `/api/demo/regenerate` | Regenera investment_tracker_demo.db |

---

## 6. Páginas del Frontend

### Dashboard (`/`)
Banda ticker animada (TickerBand) al tope con precio y variación del día de instrumentos accion/fii.
KPIs (total cartera, variación del mes, YTD, proventos pagados + proyección), gráfico de evolución,
distribución por tipo/custodio/localización (tres donuts con porcentaje en tooltip y leyenda), top/bottom 5, vencimientos.
**API:** `/api/dashboard/kpis`, `/evolution`, `/distribution`, `/top-bottom`, `/benchmarks`, `/maturities`, `/api/ticker/quotes`

### Positions (`/positions`)
Tabla de posiciones filtrable/paginable/sortable. Sort default: brasil→exterior→tipo→nombre.
Botones para importar Fixed Income, actualizar precios B3, actualizar USD/BRL, copiar mes ant.
Edición inline: celdas de Saldo BRL, Saldo USD y Cantidad son clickeables para todos los tipos. La celda "Precio actual" (P. Unit.) es clickeable y editable solo para instrumentos tipo accion/fii — muestra subrayado punteado al hover; instrumentos sin precio muestran "Sin precio" en gris itálico.
**API:** `/api/positions`, `/api/positions/export`, `/api/positions/copy-previous-month`, etc.

### History (`/history`)
Matriz Histórico: tabla instrumento × período (vista Mensual o Anual). Toggle BRL/USD, selector de año,
filtros por instrumento (texto, client-side), custodio, tipo y mercado con limpiar filtros, scroll horizontal.
Vista Mensual: 12 columnas (Ene–Dic) para el año seleccionado.
Vista Anual: hasta 10 columnas (últimos años con datos, valor de diciembre o último mes disponible).
Comportamiento: filas ordenadas por mercado (brasil→exterior) y tipo (TYPE_ORDER); celdas en verde si
el valor aumentó vs el período anterior; filas sin ningún valor ocultas; fila de totales fija arriba (en thead).
**Export CSV:** botón Download (ícono lucide-react) en la barra de controles, junto al toggle BRL/USD.
Genera CSV client-side desde el estado React (sin llamada al backend). Respeta todos los filtros activos,
incluido el filtro de texto. Valores numéricos crudos (sin formato). Nombre: `historico_mensual_<year>_<currency>.csv`
o `historico_anual_<currency>.csv`. Botón deshabilitado si no hay datos visibles.
Nota: también existe endpoint legacy para historial de un instrumento (`/api/history/{id}`) usado internamente.
**API:** `/api/history/monthly`, `/api/history/annual`, `/api/history/{id}`, `/api/history/compare`

### Annual (`/annual`) — Análisis de Patrimonio
Dos vistas con toggle Anual/Mensual.
**Vista Anual:** 4 cards de métricas (total aportado, ganado por mercado, CAGR, mejor año); gráfico de barras agrupadas (Recharts ComposedChart) con aportes netos + valorización por año y línea de patrimonio fin en eje Y derecho; tabla con columnas: Año | Inicio | Aportes netos | Valorización | Fin | Crecim. | % Valor. | Fuente (⚡ calculated / 📋 legacy). Lógica híbrida por año: usa Transaction si hay datos, AnnualSummary como fallback legacy.
**Vista Mensual:** selector de año (DESC); 3 cards (patrimonio fin, aportes netos %, valorización %); gráfico de líneas (patrimonio total + valorización acumulada), Dot personalizado en meses con movimientos (verde=aporte, rojo=rescate); tooltip muestra aportes netos acumulados del año (azul/rojo/gris según valor, calculado con reduce en frontend). Sin lista de movimientos.
**API:** `/api/annual`, `/api/annual/monthly?year=`

### Proventos (`/proventos`)
Tres tabs:
- **Histórico:** tabla anual por instrumento. Año actual = provento_items + forecast (misma lógica que gráfico).
- **Mensual:** gráfico de barras apiladas (Pagado + Previsto por mes). Cards: total pagado, proyección anual, variación vs año anterior.
- **Grilla pagado:** editable por celda, orden brasil→exterior→tipo→nombre. Celdas con forecast pero sin pago se muestran en ámbar (*) y se incluyen en los totales. Al editar, el valor previsto se pre-popula en el input. El backend devuelve `forecast_months` y `paid_month_totals` por instrumento.
- **Previsión:** grilla de forecast editable, mismo orden.
**API:** `/api/proventos`, `/api/proventos/monthly`, `/api/proventos/grid`, `/api/proventos/forecast`

### Transactions (`/transactions`)
CRUD de transacciones manuales (aplicacion, rescate, provento, outro).
Barra de filtros: custodio (XP/SANTANDER/INTER/XP_INTERNATIONAL), mes/año (input type=month), tipo, instrumento (combobox con búsqueda). Botón "Limpiar filtros" visible solo cuando hay filtro activo. Conteo "X transacciones" debajo de los filtros.
Edición: botón Editar abre modal pre-cargado. Instrumento se muestra como texto estático (no editable) en modo edición.
**Componente reutilizable:** `frontend/src/components/ui/InstrumentCombobox.tsx` — combobox con búsqueda en tiempo real por nombre y custodian, ícono X para limpiar, dropdown scrollable 200px.
**API:** `/api/transactions`

### Settings (`/settings`)
Catálogo de instrumentos editable. Import Excel genérico (drag & drop). Cotizaciones manuales.
**API:** `/api/instruments`, `/api/import`, `/api/quotes`

### ImportFixedIncome (`/import/fixed-income`)
Wizard 3 pasos: (1) subir archivo + config, (2) preview del diff con tabla paginada, (3) resultado.
Soporta cross-custodio, mapeo manual de instrumentos.
**API:** `/api/import/fixed-income/*`

### ImportProventos (`/import/proventos`)
Wizard similar para importar proventos pagados desde Excel de XP/Santander.
**API:** `/api/import/proventos/*`

### ImportInternational (`/import/international`)
Wizard 3 pasos para importar posiciones y dividendos desde extracto PDF de XP International.
Paso 1: upload PDF + tipo de cambio USD/BRL (sugerido por yfinance) + opciones.
Paso 2: preview con tabs Posiciones/Dividendos, checkboxes para excluir items, badges de match/status/duplicado.
Paso 3: resultado con métricas de importación.
Clasifica instrumentos como UST / CORP_BOND / ETF (type=renta_fija o accion). Match por CUSIP o ticker.
Dividendos: solo CASH_DIVIDEND, valor neto (post-withholding), crea ProvéntoItem con source="XP_INTERNATIONAL_PDF".
**API:** `/api/import/international/*`
**Link desde Positions:** botón "Importar Internacional".

### EquityTrades (`/equity-trades`)
Registro de compras y ventas de acciones/FIIs/ETFs. Sección superior: formulario nueva operación
(autocomplete instrumento, toggle compra/venta, date picker, cantidad, precio, monto calculado, notas).
Sección inferior: historial con filtros (instrumento, rango fechas, tipo), tabla con badge verde/rojo
por tipo, paginación. Modal de edición, AlertDialog de eliminación con fecha afectada.
Al seleccionar instrumento en filtro: muestra EquityTradeSummaryCard (qty actual, avg_price, último
precio, P&L no realizado en BRL y %). Toast de confirmación con meses recalculados.
**API:** `/api/equity-trades/*`
**Link desde Positions:** botón "Ver operaciones" en filas de tipo accion/fii.

---

## 7. Servicios y Lógica de Negocio

### `services/snapshot_sync.py`
- `sync_snapshot_for_date(db, target_date)` — Sincroniza `PortfolioSnapshot` (total_brl, total_usd) de un mes en particular desde los saldos de `MonthlyPosition`.
- `sync_all_snapshots(db)` — Sincroniza la tabla entera iterando por cada fecha existente.
- Se debe llamar cada vez que se alteran balances históricos o se copian meses (ej. transacciones, precios, equities).

### `services/performance.py`
- `calculate_cagr(initial, final, years)` — retorno anualizado
- `calculate_drawdown(values)` — máxima caída desde peak
- `calculate_volatility(returns)` — desviación anualizada (monthly_std × √12)

### `services/fixed_income_importer.py`
- `parse_excel(file_bytes, config)` — parsea "Posição - Renda Fixa" (38 cols) y "Posição - Tesouro Direto" (3 cols); detecta cross-custodio
- `compute_diff(parsed, target_date, config, db)` → `[DiffItem]` con status NEW/UPDATED/UNCHANGED/DISAPPEARED
- `apply_import(diff, parsed, target_date, config, skip_codes, db)` → upsert Instrument + MonthlyPosition + InstrumentCodeMapping
- `store_preview(token, data)` / `load_preview(token)` — caché en memoria, TTL 30 min
- `_safe_float(val)` — convierte "1.234,56" → 1234.56 (formato brasileño)
- `_normalize_custodian(raw)` → "XP" | "SANTANDER" | "INTER" | custom
- `_extract_asset_class(produto)` → CDB | CRI | CRA | DEB | LCA | LCI | LIG | TD | FUNDO_CREDITO
- `_clean_nome(produto)` → (nombre_limpio, in_liquidation: bool)
- `auto_match_score(parsed, inst)` → 0-100 basado en keywords + vencimiento

### `services/international_importer.py`
- `parse_xp_international_pdf(pdf_bytes)` — parsea extracto PDF de XP International; retorna `ParsedReport`
- `_parse_carteira_table()` — extrae posiciones de la tabla CARTEIRA (pdfplumber)
- `_merge_symbol_cusip_rows()` — maneja CUSIP en fila separada o misma celda con `\n`
- `parse_atividade()` — extrae dividendos CASH_DIVIDEND de la tabla ATIVIDADE
- `classify_international(pos)` — detecta UST / CORP_BOND / ETF por regex
- `match_instrument(pos, classification, db)` — CUSIP → ticker → instrument_code_mappings
- `get_usd_brl_rate(reference_date)` — consulta yfinance "BRL=X" para el tipo de cambio
- `compute_position_diffs()` / `check_dividend_duplicates()` — genera diff vs BD
- `apply_import_positions()` / `apply_import_dividends()` — aplica import a la BD
- `store_preview()` / `load_preview()` — caché en memoria, TTL 30 min

### `services/proventos_importer.py`
- `parse_excel(file_bytes)` — parsea "Proventos Recebidos" de Excel XP/Santander
- `compute_diff(parsed_data, db)` → DiffReport con status NEW/DUPLICATE/CONFLICT/NO_MATCH/AMBIGUOUS_MATCH
- `apply_import(diff_report, force_duplicates, skip_indices, manual_mappings, period_label, db)` → ImportResult
- Detección de duplicados: en-archivo (mismo instrumento+fecha+tipo+monto) y en-DB

### `services/return_calculator.py`
- `compute_period_return(instrument_id, instrument_type, latest_date, n_months, db)` — calcula retorno del instrumento en los últimos N meses.
  - **Rama price** (`accion`, `fii`): `(unit_price_actual - unit_price_N_meses_atrás) / unit_price_N_meses_atrás`. Mide retorno del activo sin interferencia de compras/ventas.
  - **Rama balance** (resto): Modified Dietz simplificado con flujos netos de `transactions` (tipo `aplicacion`/`rescate`). Fórmula: `(balance_actual - balance_anterior - net_flow) / (balance_anterior + net_flow × 0.5)`.
  - Gap máximo de 45 días entre la fecha de referencia histórica y `target_date`; si se excede retorna `None`.
- Usado por `POST /api/positions/recalculate-stats`.
- `PRICE_TYPES = {"accion", "fii"}` — constante exportada para determinar `return_source`.

### `services/equity_recalculate.py`
- Calcula y persiste `gain` y `gain_pct` en `MonthlyPosition` para acciones/FIIs con Modified Dietz usando trades del mes y balance del mes anterior.

### `services/importer.py`
- Importa el Excel genérico (Inversiones.xlsx) con 6 hojas
- Upsert de Instrument, MonthlyPosition, PortfolioSnapshot, AnnualSummary, Provento, Quote

---

## 8. Convenciones del Código

### Fechas
Siempre normalizar al primer día del mes para datos mensuales:
```python
target_date = date(year, month, 1)
target_date = some_date.replace(day=1)
```

### Tipos de instrumento
```python
TYPE_ORDER = ["accion", "fii", "renta_fija", "fundo", "previdencia", "prestamos", "saving", "fgts", "outro"]
LOCATION_ORDER = ["brasil", "exterior"]
```
Ordenamiento estándar en grillas y tablas: location → type → nombre.

### Números brasileños (backend)
```python
_safe_float("1.234,56")  # → 1234.56
_safe_float("1.234.567,89")  # → 1234567.89
```

### Números brasileños (frontend)
```typescript
fmtBRL(value)    // "R$ 1.234,56"
fmtPct(value)    // "12,34%"
fmtNumber(value) // "1.234.567"
```

### Upsert de posiciones mensuales
```python
# UNIQUE(instrument_id, date, custodian_override)
existing = db.query(MonthlyPosition).filter_by(
    instrument_id=inst_id, date=target_date, custodian_override=override
).first()
if existing:
    existing.balance_brl = new_value
else:
    db.add(MonthlyPosition(instrument_id=inst_id, date=target_date, ...))
db.commit()
```

### Custodios normalizados
`"XP"` | `"SANTANDER"` | `"INTER"` | `"BRADESCO"` | `"ITAU"` | `"XP_INTERNATIONAL"` | `"DESCONHECIDO"`

### Demo mode
El cliente Axios inyecta `X-Env: demo` si `localStorage.app_env === "demo"`.
`get_db()` en FastAPI rutea al `demo_engine` según ese header.

---

## 9. Features Implementados

- [x] Dashboard con KPIs, evolución, distribución, benchmarks (CDI/IPCA), top/bottom, vencimientos
- [x] Posiciones: filtros, paginación, sort (default: brasil→exterior→tipo→nombre), export CSV
- [x] Historial por instrumento: gráficos, CAGR, drawdown, volatility, comparación multi
- [x] Histórico matriz mensual/anual: instrumento × período, filtros instrumento/custodio/tipo/mercado, BRL/USD toggle, export CSV client-side
- [x] Resumen anual: tabla + gráfico apilado
- [x] Proventos: tabla histórica (año actual desde provento_items + forecast), gráfico barras apiladas (Pagado + Previsto), grilla editable, previsión
- [x] Importador Fixed Income (renta fija): wizard 3 pasos, diff preview, cross-custodio, mapeo manual
- [x] Importador Proventos: wizard 3 pasos, deduplicación, mapeo manual
- [x] CRUD transacciones con recálculo automático de posiciones mensuales
- [x] Catálogo de instrumentos editable
- [x] Import Excel genérico (6 hojas)
- [x] Actualización automática de precios B3 via yfinance
- [x] Actualización USD/BRL via yfinance
- [x] Cotizaciones manuales
- [x] Benchmarks CDI/IPCA con caché local (BCB API)
- [x] Operaciones de Renta Variable: registro compras/ventas, recálculo automático de MonthlyPosition (quantity, balance_brl, avg_price), historial, card resumen P&L
- [x] Importador XP International: wizard PDF 3 pasos, posiciones + dividendos, clasificación UST/CORP_BOND/ETF, matching por CUSIP/ticker, fix update-equities-prices para USD vs BRL
- [x] Modo Demo (X-Env header → demo_engine)
- [x] Toggle Demo/Real en UI (sidebar)
- [x] Dark/Light theme
- [x] Migración automática de schema en startup (`_migrate_provento_items`)
- [x] Copiar posiciones del mes anterior al actual de forma segura para instrumentos activos
- [x] Sincronización automática de pre-cálculos del PortfolioSnapshot al editar históricos (snapshot_sync)
- [x] Ticker de renta variable en dashboard (yfinance, cache 5 min, animación marquee, hover pause)
- [x] Rescate total de instrumento (ícono en tabla de posiciones para renta fija)
- [x] Creación manual de instrumento con saldo inicial opcional (modal en Settings → Catálogo)
- [x] Grilla pagado: celdas previstas en ámbar (*), totales de columna/fila incluyen previstos no pagados, edición pre-popula valor previsto
- [x] Análisis de Patrimonio (/annual): vista anual + mensual con lógica híbrida Transaction/AnnualSummary, gráficos Recharts (barras agrupadas + líneas), indicador de fuente de dato (⚡/📋), tooltip mensual con aportes netos acumulados (net_flow_acum calculado con reduce)
- [x] Mejoras CRUD Transacciones: filtros por custodio/mes-año/tipo/instrumento, edición de transacciones (modal pre-cargado, instrumento estático), combobox de instrumento reutilizable (InstrumentCombobox), label sidebar /annual → "Análisis de Patrimonio"
- [x] Monto por moneda en transacciones: formulario solicita monto en moneda nativa del instrumento (BRL/USD), calcula segundo monto con cotización del mes (GET /api/quotes/lookup), input manual si no hay cotización, checkbox para override, modo edición arranca con override=true
- [x] Distribución con porcentajes y gráfico por localización: DonutChart muestra % en tooltip y leyenda; backend agrega by_location; Dashboard agrega tercer donut "Por Localización" (esmeralda=brasil, índigo=exterior)
- [x] Edición inline de unit_price en Posiciones: celda P. Unit. clickeable para accion/fii; PATCH /api/positions/{mp_id}/unit-price recalcula balances en cascada con fallback usd_rate; sincroniza PortfolioSnapshot del mes afectado

---

## 10. Features Pendientes

*(de `specs/pending/`)*

- [ ] **prompt_importacion_renta_fija.txt** — Verificación completa del importador Fixed Income:
  archivo Feb 2026 → 38 RF + 3 TD; CDBs EM LIQUIDACAO → badge rojo; CRIs sin precio → indicador;
  config desmarcar valores; token expirado → 410; reimport mismo período → upsert no duplica;
  custodian_override cross-custodio funciona

- [ ] **prompt_importacion_proventos.txt** — Verificación completa del importador Proventos:
  deduplicación por (instrument_id, date, type, amount_brl); 2 JCP mismo día montos distintos → 2 registros;
  repeated confirm → idempotente; mapeo manual persiste

---

## 11. Notas Importantes para Futuros Features

### Sin Alembic — migraciones manuales
No hay Alembic. Para cambiar schema:
1. Crear script `backend/migrate_*.py` con SQLite DDL directo (DROP+CREATE pattern)
2. Llamarlo en `startup()` de `main.py` o ejecutarlo manualmente
3. Ver `database.py::_migrate_provento_items()` como referencia

### Provento vs ProvéntoItem — distinción crítica
- `proventos` = agregados anuales **solo para años pasados** (importados con Excel genérico)
- `provento_items` = registros transaccionales (importados con ImportProventos o editados en grilla)
- **Año actual:** siempre leer de `provento_items`. NUNCA escribir en `proventos` para el año en curso.
- **Años anteriores:** si existe data en `provento_items`, tiene precedencia sobre `proventos`

### Lógica Pagado + Previsto (año actual)
Para cualquier mes del año actual, la visualización muestra:
- **Pagado** = sum(`provento_items`) para ese mes
- **Previsto** = sum(`provento_forecast`) para instrumentos que **no tienen** `provento_items` ese mes

Esta lógica aplica en: `/api/proventos/monthly`, `/api/proventos` (columna año actual), `/api/dashboard/kpis` (proventos_projection).

### Grilla de proventos — semántica de edición
`PATCH /api/proventos/grid/{instrument_id}/{year}/{month}` **elimina TODOS** los registros de `provento_items`
para esa celda (importados + manuales) y crea uno nuevo con `source="MANUAL"`. Esto es intencional.

### Token Cache (Fixed Income y Proventos)
- En memoria (`_TOKEN_CACHE` dict), TTL 30 min
- No persiste entre reinicios del servidor
- Si token expiró: respuesta 410 Gone
- El frontend debe manejar el 410 y pedir re-upload

### Recálculo de posiciones desde transacciones
`transactions.py::_recompute_positions(db, instrument_id, from_date)`:
- Toma el balance del mes inmediatamente anterior (sin filtrar por balance > 0)
- Para cada mes desde `from_date`: balance = prev_balance + aplicaciones - rescates
- Crea la fila de `monthly_positions` si no existe
- Solo aplica a instrumentos tipo saving/fundo/renta_fija (sin unit_price)
- No recalcula instrumentos con precio (accion, fii) — esos se actualizan via yfinance

### Cross-custodio en Fixed Income
Mismo instrumento en 2 custodios → 2 `MonthlyPosition` con `custodian_override` diferente.
Queries de balance deben sumar ambas filas. El campo `custodian_override` es `NULL` para instrumentos
sin duplicado cross-custodio.

### Sort "default" en posiciones
`GET /api/positions?sort=default` → ORDER BY: location CASE (brasil=0, exterior=1), type CASE (TYPE_ORDER), name.
Es el default del frontend. Si el usuario hace click en columna, cambia a ese sort.

### Demo DB
`create_demo_db.py` genera datos falsos escalados proporcionalmente. Copia `instruments`, `market_rates`,
`quotes`, `instrument_code_mappings` sin cambios. Escala `monthly_positions`, `proventos`,
`provento_items`, `annual_summaries` por un factor = demo_total / real_total. Copia `provento_forecast` y
`provento_import_batches` sin cambios.

### CORS
`allow_origins=["*"]` + `allow_credentials=False`. No usar `allow_credentials=True` con wildcard origins
(incompatible en CORS spec). El global exception handler agrega `Access-Control-Allow-Origin: *` en
respuestas 500 para evitar que el browser bloquee errores del servidor.

### Sincronización de PortfolioSnapshot
El Dashboard lee directamente de `PortfolioSnapshot` por rendimiento. Si editas balances históricos (`update_position_balance`), creas operaciones (`equity_trades` o `transactions`), o copias posiciones (`copy-previous-month`), **siempre** invocar `sync_snapshot_for_date(db, affected_date)` para garantizar que el total fotográfico (KPIs) coincida con la sumatoria estricta de `MonthlyPosition`.
