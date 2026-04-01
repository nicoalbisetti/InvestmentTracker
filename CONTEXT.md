# CONTEXT.md — InvestmentTracker

> Documento de contexto para nuevas sesiones de Claude Code / Claude.ai.
> Refleja el estado REAL del código al 1 Abr 2026.

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
│   │   ├── database.py                 # Engines, sessions, _migrate_provento_items()
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
│   │   │   └── import_proventos.py
│   │   ├── services/
│   │   │   ├── importer.py
│   │   │   ├── fixed_income_importer.py
│   │   │   ├── proventos_importer.py
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
│   │   │   └── ImportProventos.tsx
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   └── Sidebar.tsx         # Incluye toggle Demo/Real
│   │   │   ├── charts/
│   │   │   │   └── BarChartComp.tsx
│   │   │   └── ui/
│   │   │       └── KpiCard.tsx
│   │   ├── context/
│   │   │   ├── ThemeContext.tsx
│   │   │   └── EnvContext.tsx          # Demo/Real env, persiste en localStorage
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
│   │   │   └── importProventos.ts
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

## 5. Endpoints Implementados

### `/api/dashboard`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/kpis` | total_brl, ytd_pct, monthly_change, proventos_ytd, proventos_projection |
| GET | `/evolution?range=1y\|3y\|5y\|all&currency=BRL\|USD` | Serie histórica del portfolio |
| GET | `/distribution` | Distribución por tipo y custodio |
| GET | `/evolution-by-type?range=...` | Evolución apilada por tipo |
| GET | `/benchmarks?range=...` | CDI/IPCA desde BCB (cacheado en market_rates) |
| GET | `/maturities` | Posiciones agrupadas por mes de vencimiento |
| GET | `/top-bottom` | Top 5 y Bottom 5 instrumentos |

### `/api/positions`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/?sort=default&order=asc&...` | Lista paginada; sort=default → brasil→exterior→tipo→nombre |
| GET | `/export` | CSV stream con posiciones |
| PATCH | `/{mp_id}/balance` | Actualiza balance_brl, balance_usd o quantity |
| GET | `/last-fixed-income-date` | Último mes importado (renta_fija) |
| GET | `/count-without-price` | Count de renta_fija activos sin balance |
| POST | `/update-equities-prices?month=YYYY-MM` | Actualiza precios B3 via yfinance |
| POST | `/update-usd-rate?month=YYYY-MM` | Actualiza cotización USD/BRL |
| POST | `/recalculate-stats` | Recalcula current_balance_brl, portfolio_pct, rankings |

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
| GET | `/` | Tabla anual con métricas globales |

### `/api/proventos`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/?page&limit&status` | Tabla anual por instrumento (año actual = provento_items + forecast) |
| GET | `/monthly?year` | Serie mensual: {month, amount(pagado), forecast(no pagado)} |
| GET | `/grid?year&type` | Grilla editable mensual; orden: brasil→exterior→tipo→nombre |
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
| GET | `/?instrument_id&type&date_from&date_to&page&limit` | Lista paginada |
| POST | `/` | Crea transacción + recalcula monthly_positions |
| PUT | `/{txn_id}` | Actualiza + recalcula |
| DELETE | `/{txn_id}` | Elimina + recalcula |

### `/api/instruments`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/?status&type&location&currency&custodian&search&sort&order&page&limit` | Lista paginada |
| GET | `/{id}` | Detalle |
| PUT | `/{id}` | Actualiza campos |

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

### `/api/quotes`
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/?date_from&date_to` | Lista de cotizaciones |
| POST | `/` | Upsert cotización (usd_brl, bvmf3_price) |

### Otros
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | `{status: "ok", version: "1.0.0"}` |
| GET | `/api/env` | Retorna env activo según header X-Env |
| POST | `/api/demo/regenerate` | Regenera investment_tracker_demo.db |

---

## 6. Páginas del Frontend

### Dashboard (`/`)
KPIs (total cartera, variación del mes, YTD, proventos pagados + proyección), gráfico de evolución,
distribución por tipo/custodio, top/bottom 5, vencimientos.
**API:** `/api/dashboard/kpis`, `/evolution`, `/distribution`, `/top-bottom`, `/benchmarks`, `/maturities`

### Positions (`/positions`)
Tabla de posiciones filtrable/paginable/sortable. Sort default: brasil→exterior→tipo→nombre.
Botones para importar Fixed Income, actualizar precios B3, actualizar USD/BRL.
**API:** `/api/positions`, `/api/positions/export`, `/api/positions/update-equities-prices`, etc.

### History (`/history`)
Matriz Histórico: tabla instrumento × período (vista Mensual o Anual). Toggle BRL/USD, selector de año,
filtros por custodio/tipo/mercado con limpiar filtros, fila de totales, scroll horizontal.
Vista Mensual: 12 columnas (Ene–Dic) para el año seleccionado.
Vista Anual: hasta 10 columnas (últimos años con datos, valor de diciembre o último mes disponible).
Nota: también existe endpoint legacy para historial de un instrumento (`/api/history/{id}`) usado internamente.
**API:** `/api/history/monthly`, `/api/history/annual`, `/api/history/{id}`, `/api/history/compare`

### Annual (`/annual`)
Tabla anual con diff, gain, net_flow. Gráfico de barras apiladas.
**API:** `/api/annual`

### Proventos (`/proventos`)
Tres tabs:
- **Histórico:** tabla anual por instrumento. Año actual = provento_items + forecast (misma lógica que gráfico).
- **Mensual:** gráfico de barras apiladas (Pagado + Previsto por mes). Cards: total pagado, proyección anual, variación vs año anterior.
- **Grilla pagado:** editable por celda, orden brasil→exterior→tipo→nombre.
- **Previsión:** grilla de forecast editable, mismo orden.
**API:** `/api/proventos`, `/api/proventos/monthly`, `/api/proventos/grid`, `/api/proventos/forecast`

### Transactions (`/transactions`)
CRUD de transacciones manuales (aplicacion, rescate, provento, outro).
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

---

## 7. Servicios y Lógica de Negocio

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

### `services/proventos_importer.py`
- `parse_excel(file_bytes)` — parsea "Proventos Recebidos" de Excel XP/Santander
- `compute_diff(parsed_data, db)` → DiffReport con status NEW/DUPLICATE/CONFLICT/NO_MATCH/AMBIGUOUS_MATCH
- `apply_import(diff_report, force_duplicates, skip_indices, manual_mappings, period_label, db)` → ImportResult
- Detección de duplicados: en-archivo (mismo instrumento+fecha+tipo+monto) y en-DB

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
`"XP"` | `"SANTANDER"` | `"INTER"` | `"BRADESCO"` | `"ITAU"` | `"DESCONHECIDO"`

### Demo mode
El cliente Axios inyecta `X-Env: demo` si `localStorage.app_env === "demo"`.
`get_db()` en FastAPI rutea al `demo_engine` según ese header.

---

## 9. Features Implementados

- [x] Dashboard con KPIs, evolución, distribución, benchmarks (CDI/IPCA), top/bottom, vencimientos
- [x] Posiciones: filtros, paginación, sort (default: brasil→exterior→tipo→nombre), export CSV
- [x] Historial por instrumento: gráficos, CAGR, drawdown, volatility, comparación multi
- [x] Histórico matriz mensual/anual: instrumento × período, filtros custodio/tipo/mercado, BRL/USD toggle
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
- [x] Modo Demo (X-Env header → demo_engine)
- [x] Toggle Demo/Real en UI (sidebar)
- [x] Dark/Light theme
- [x] Migración automática de schema en startup (`_migrate_provento_items`)

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
